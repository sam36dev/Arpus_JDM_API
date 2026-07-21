from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin, get_current_customer
from ..database import get_db
from ..pack_logic import open_bonus_card, open_pack

router = APIRouter(prefix="/orders", tags=["orders"])


def _finalize_order(db: Session, order: models.Order) -> list[dict]:
    """Marca o pedido como pago e sorteia as cartas (pacotes + cartas bônus).
    Server-side, pra ninguém manipular o resultado pelo client."""
    if order.status == "pago":
        raise HTTPException(400, "Pedido já está pago")

    order.status = "pago"

    pulls_result = []
    for item in order.items:
        product = db.get(models.Product, item.product_id)
        if not product:
            continue
        for unit_index in range(item.quantity):
            cards = open_pack(db, product) if product.is_pack else open_bonus_card(db, product)
            for card in cards:
                pull = models.CardPull(order_item_id=item.id, unit_index=unit_index, card_id=card.id)
                db.add(pull)
                pulls_result.append(
                    {
                        "order_item_id": item.id,
                        "card_id": card.id,
                        "card_name": card.name,
                        "card_image": card.image,
                        "rarity_id": card.rarity_id,
                        "rarity_label": card.rarity.label,
                        "rarity_color": card.rarity.color,
                    }
                )

    db.commit()
    return pulls_result


@router.post("", response_model=schemas.OrderOut)
def create_order(
    payload: schemas.OrderCreate,
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    if not payload.items:
        raise HTTPException(400, "O pedido precisa ter ao menos um item")

    total = 0.0
    order_items = []
    for item in payload.items:
        product = db.get(models.Product, item.product_id)
        if not product:
            raise HTTPException(404, f"Produto {item.product_id} não encontrado")
        if product.stock is not None and product.stock < item.quantity:
            raise HTTPException(400, f"Estoque insuficiente para '{product.name}' (disponível: {product.stock})")
        total += product.price * item.quantity
        if product.stock is not None:
            product.stock -= item.quantity
        order_items.append(
            models.OrderItem(
                product_id=product.id,
                quantity=item.quantity,
                unit_price=product.price,
            )
        )

    order = models.Order(
        status="pendente",
        total=total,
        customer_id=customer.id,
        customer_email=customer.email,
    )
    order.items = order_items
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/me", response_model=list[schemas.OrderOut])
def my_orders(
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    return (
        db.query(models.Order)
        .filter(models.Order.customer_id == customer.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    return order


@router.post("/{order_id}/checkout")
def checkout(
    order_id: int,
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    """Confirmação de pagamento feita pelo próprio cliente. Enquanto não há um
    provedor real (Pix/cartão), o pagamento é confirmado instantaneamente aqui."""
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order.customer_id != customer.id:
        raise HTTPException(403, "Este pedido não pertence a você")

    pulls_result = _finalize_order(db, order)
    return {"ok": True, "pulls": pulls_result}


@router.post("/{order_id}/pay")
def mark_paid(
    order_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """Confirmação manual de pagamento pelo admin (ex: pedidos sem checkout
    automático, suporte). Usa a mesma lógica de sorteio do checkout do cliente."""
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "Pedido não encontrado")

    pulls_result = _finalize_order(db, order)
    return {"ok": True, "pulls": pulls_result}


@router.get("/{order_id}/pulls", response_model=list[schemas.CardPullOut])
def get_pulls(order_id: int, db: Session = Depends(get_db)):
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "Pedido não encontrado")

    result = []
    for item in order.items:
        for pull in item.pulls:
            card = pull.card
            result.append(
                {
                    "order_item_id": item.id,
                    "card_id": card.id,
                    "card_name": card.name,
                    "card_image": card.image,
                    "rarity_id": card.rarity_id,
                    "rarity_label": card.rarity.label,
                    "rarity_color": card.rarity.color,
                }
            )
    return result
