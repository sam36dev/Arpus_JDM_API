import os
import json
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_customer
from ..database import get_db
from .orders import _finalize_order

BR_OFFSET = timedelta(hours=-3)

def _next_schedule_utc() -> datetime:
    now_br = datetime.utcnow() + BR_OFFSET
    hour = now_br.hour
    if hour < 8:
        sched_br = now_br.replace(hour=8, minute=0, second=0, microsecond=0)
    elif hour < 15:
        sched_br = now_br.replace(hour=15, minute=0, second=0, microsecond=0)
    else:
        sched_br = (now_br + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return sched_br - BR_OFFSET

def _create_shipping_chamado(db: Session, order: models.Order) -> None:
    arthur = (
        db.query(models.Conta)
        .filter(models.Conta.buyer_name.ilike("%arthur%"))
        .first()
    )
    customer = order.customer
    name = customer.name if customer else (order.customer_email or "Cliente")
    lines = [f"Cliente: {name}"]
    if customer:
        parts = [
            customer.address_street, customer.address_number,
            customer.address_complement, customer.address_neighborhood,
            customer.address_city, customer.address_state, customer.address_cep,
        ]
        addr = ", ".join(p for p in parts if p)
        if addr:
            lines.append(f"Endereço: {addr}")
        if customer.phone:
            lines.append(f"Tel: {customer.phone}")
    lines.append("Itens:")
    for item in order.items:
        product = db.get(models.Product, item.product_id)
        pname = product.name if product else f"#{item.product_id}"
        lines.append(f"  - {pname} x{item.quantity}")
    lines.append(f"Total: R$ {order.total:.2f}")
    db.add(models.Chamado(
        title=f"Despachar pedido #{order.id} — {name}",
        description="\n".join(lines),
        hours=72,
        conta_id=arthur.id if arthur else None,
        scheduled_at=_next_schedule_utc(),
    ))
    db.commit()

router = APIRouter(prefix="/payments", tags=["payments"])

ASAAS_KEY = os.getenv("ASAAS_API_KEY", "")
ASAAS_BASE = (
    "https://sandbox.asaas.com/api/v3"
    if os.getenv("ASAAS_ENV") == "sandbox"
    else "https://api.asaas.com/v3"
)

VALID_COUPONS = {"JDM10": 10, "TURBO20": 20, "NISMO15": 15}


def _headers():
    return {"access_token": ASAAS_KEY, "Content-Type": "application/json"}


def _get_or_create_asaas_customer(customer: models.Customer) -> str:
    name = f"{customer.name} {customer.last_name or ''}".strip()
    cpf = customer.cpf or ""
    with httpx.Client(timeout=20) as http:
        r = http.get(
            f"{ASAAS_BASE}/customers",
            params={"cpfCnpj": cpf},
            headers=_headers(),
        )
        if r.is_success:
            data = r.json().get("data", [])
            if data:
                return data[0]["id"]
        r = http.post(
            f"{ASAAS_BASE}/customers",
            json={"name": name, "email": customer.email, "cpfCnpj": cpf},
            headers=_headers(),
        )
        if not r.is_success:
            raise HTTPException(502, f"Erro ao cadastrar no gateway: {r.text}")
        return r.json()["id"]


class CheckoutItem(BaseModel):
    product_id: int
    quantity: int = 1


class CheckoutCreate(BaseModel):
    items: list[CheckoutItem]
    billing_type: str  # PIX | BOLETO | CREDIT_CARD
    coupon: str | None = None


@router.post("/checkout")
def payment_checkout(
    payload: CheckoutCreate,
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    if not customer.cpf:
        raise HTTPException(400, "Complete seu cadastro (com CPF) antes de finalizar a compra")
    if not ASAAS_KEY:
        raise HTTPException(503, "Gateway de pagamento não configurado")
    if not payload.items:
        raise HTTPException(400, "Carrinho vazio")

    billing_type = payload.billing_type.upper()
    if billing_type not in ("PIX", "BOLETO", "CREDIT_CARD"):
        raise HTTPException(400, "Tipo de pagamento inválido")

    asaas_billing_type = "UNDEFINED" if billing_type == "CREDIT_CARD" else billing_type

    # Separate packs (one order per unit) from physical items (one combined order)
    pack_orders: list[models.Order] = []
    other_items: list[tuple[models.Product, int]] = []
    subtotal = 0.0

    for ci in payload.items:
        product = db.get(models.Product, ci.product_id)
        if not product:
            raise HTTPException(404, f"Produto {ci.product_id} não encontrado")
        if product.stock is not None and product.stock < ci.quantity:
            raise HTTPException(400, f"Estoque insuficiente para '{product.name}' (disponível: {product.stock})")
        if product.stock is not None:
            product.stock -= ci.quantity
        if product.is_pack:
            for _ in range(ci.quantity):
                o = models.Order(
                    status="aguardando_pagamento",
                    total=product.price,
                    customer_id=customer.id,
                    customer_email=customer.email,
                )
                o.items = [models.OrderItem(product_id=product.id, quantity=1, unit_price=product.price)]
                db.add(o)
                db.flush()
                pack_orders.append(o)
            subtotal += product.price * ci.quantity
        else:
            other_items.append((product, ci.quantity))
            subtotal += product.price * ci.quantity

    other_order: models.Order | None = None
    if other_items:
        other_subtotal = sum(p.price * q for p, q in other_items)
        other_order = models.Order(
            status="aguardando_pagamento",
            total=other_subtotal,
            customer_id=customer.id,
            customer_email=customer.email,
        )
        other_order.items = [
            models.OrderItem(product_id=p.id, quantity=q, unit_price=p.price)
            for p, q in other_items
        ]
        db.add(other_order)
        db.flush()

    db.commit()

    all_orders = pack_orders + ([other_order] if other_order else [])
    order_ids = [o.id for o in all_orders]
    external_ref = ",".join(str(i) for i in order_ids)

    # Coupon discount (on subtotal)
    discount_pct = VALID_COUPONS.get((payload.coupon or "").upper(), 0)
    discount_amt = subtotal * discount_pct / 100

    # Shipping applies only to non-pack items
    non_pack_subtotal = sum(p.price * q for p, q in other_items)
    shipping = 0.0 if (not other_items or non_pack_subtotal >= 500) else 49.90

    total = round(max(subtotal - discount_amt + shipping, 0.01), 2)

    try:
        asaas_customer_id = _get_or_create_asaas_customer(customer)
    except HTTPException:
        for o in all_orders:
            db.delete(o)
        db.commit()
        raise

    due_date = (date.today() + timedelta(days=3)).isoformat()
    try:
        with httpx.Client(timeout=20) as http:
            r = http.post(
                f"{ASAAS_BASE}/payments",
                json={
                    "customer": asaas_customer_id,
                    "billingType": asaas_billing_type,
                    "value": total,
                    "dueDate": due_date,
                    "externalReference": external_ref,
                    "description": "Pedido ARPUS JDM",
                },
                headers=_headers(),
            )
            if not r.is_success:
                raise HTTPException(502, f"Erro no gateway de pagamento: {r.text}")

            payment = r.json()
            payment_id = payment["id"]

            result: dict = {
                "order_ids": order_ids,
                "payment_id": payment_id,
                "billing_type": billing_type,
                "total": total,
                "invoice_url": payment.get("invoiceUrl"),
            }

            if billing_type == "PIX":
                pix_r = http.get(
                    f"{ASAAS_BASE}/payments/{payment_id}/pixQrCode",
                    headers=_headers(),
                )
                if pix_r.is_success:
                    pix = pix_r.json()
                    result["pix_qr_code"] = pix.get("encodedImage")
                    result["pix_copy_paste"] = pix.get("payload")
                    result["pix_expiration"] = pix.get("expirationDate")

            elif billing_type == "BOLETO":
                result["boleto_url"] = payment.get("bankSlipUrl")
                result["boleto_barcode"] = payment.get("identificationField")

            return result

    except HTTPException:
        raise
    except Exception as e:
        for o in all_orders:
            db.delete(o)
        db.commit()
        raise HTTPException(502, f"Erro ao processar pagamento: {str(e)}")


@router.get("/order/{order_id}/status")
def order_payment_status(
    order_id: int,
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order.customer_id != customer.id:
        raise HTTPException(403, "Acesso negado")
    return {"order_id": order_id, "status": order.status}


@router.post("/webhook")
def asaas_webhook(body: Any = Body(default=None), db: Session = Depends(get_db)):
    """Webhook da Asaas — sem autenticação (chamado pelo servidor da Asaas)."""
    if not body:
        return {"ok": True}

    event = body.get("event", "") if isinstance(body, dict) else ""
    if event not in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
        return {"ok": True}

    payment = body.get("payment", {})
    external_ref = payment.get("externalReference", "")
    if not external_ref:
        return {"ok": True}

    try:
        order_ids = [int(x.strip()) for x in external_ref.split(",") if x.strip()]
    except ValueError:
        return {"ok": True}

    for oid in order_ids:
        order = db.get(models.Order, oid)
        if not order or order.status != "aguardando_pagamento":
            continue

        has_pack = any(
            bool((db.get(models.Product, item.product_id) or models.Product()).is_pack)
            for item in order.items
        )
        if has_pack:
            order.status = "pendente"
            db.commit()
        else:
            try:
                _finalize_order(db, order)
                _create_shipping_chamado(db, order)
            except Exception:
                order.status = "pago"
                db.commit()

    return {"ok": True}
