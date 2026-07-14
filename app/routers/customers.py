import random
import string

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_customer, hash_password, verify_password
from ..database import get_db
from ..limiter import limiter


def _generate_plate(db: Session) -> str:
    while True:
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        digits = ''.join(random.choices(string.digits, k=4))
        plate = f"{letters}-{digits}"
        if not db.query(models.Customer).filter(models.Customer.plate == plate).first():
            return plate

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/register", response_model=schemas.CustomerLoginOut)
@limiter.limit("3/2hours")
def register(request: Request, payload: schemas.CustomerRegister, db: Session = Depends(get_db)):
    exists = db.query(models.Customer).filter(func.lower(models.Customer.email) == payload.email.lower()).first()
    if exists:
        raise HTTPException(400, "Já existe uma conta com este email")
    customer = models.Customer(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        plate=_generate_plate(db),
    )
    db.add(customer)
    db.commit()
    token = create_access_token({"sub": customer.email, "type": "customer"})
    return {"access_token": token, "name": customer.name, "email": customer.email, "plate": customer.plate}


@router.post("/login", response_model=schemas.CustomerLoginOut)
@limiter.limit("5/2hours")
def login(request: Request, payload: schemas.CustomerLogin, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(func.lower(models.Customer.email) == payload.email.lower()).first()
    if not customer or not verify_password(payload.password, customer.hashed_password):
        raise HTTPException(401, "Email ou senha inválidos")
    if not customer.plate:
        customer.plate = _generate_plate(db)
        db.commit()
    token = create_access_token({"sub": customer.email, "type": "customer"})
    return {"access_token": token, "name": customer.name, "email": customer.email, "plate": customer.plate}


@router.get("/me", response_model=schemas.CustomerOut)
def me(customer: models.Customer = Depends(get_current_customer)):
    return customer


@router.get("/me/cards", response_model=list[schemas.CustomerCardOut])
def my_cards(
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    pulls = (
        db.query(models.CardPull)
        .join(models.OrderItem, models.CardPull.order_item_id == models.OrderItem.id)
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .filter(models.Order.customer_id == customer.id)
        .all()
    )

    by_card: dict[int, dict] = {}
    for pull in pulls:
        card = pull.card
        if card.id not in by_card:
            by_card[card.id] = {
                "card_id": card.id,
                "card_name": card.name,
                "card_image": card.image,
                "rarity_id": card.rarity_id,
                "rarity_label": card.rarity.label,
                "rarity_color": card.rarity.color,
                "quantity": 0,
            }
        by_card[card.id]["quantity"] += 1

    return list(by_card.values())


@router.post("/me/trade-card", response_model=schemas.TradeCardOut)
def trade_card(
    payload: schemas.TradeCardIn,
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    pulls = (
        db.query(models.CardPull)
        .join(models.OrderItem, models.CardPull.order_item_id == models.OrderItem.id)
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .filter(models.Order.customer_id == customer.id)
        .filter(models.CardPull.card_id == payload.card_id)
        .all()
    )
    if len(pulls) < 5:
        raise HTTPException(400, "Você precisa de 5 cópias para trocar")

    for pull in pulls[:4]:
        db.delete(pull)

    pack = (
        db.query(models.Product)
        .filter(models.Product.is_pack == True, models.Product.name == "Pack Solo")
        .first()
    ) or (
        db.query(models.Product)
        .filter(models.Product.is_pack == True)
        .order_by(models.Product.price)
        .first()
    )
    if not pack:
        raise HTTPException(404, "Nenhum pacote disponível para troca")

    order = models.Order(status="pendente", total=0, customer_id=customer.id)
    db.add(order)
    db.flush()
    db.add(models.OrderItem(order_id=order.id, product_id=pack.id, quantity=1, unit_price=0))
    db.commit()

    return {"order_id": order.id, "pack_name": pack.name}


@router.get("/me/collections/claimed")
def my_claimed_collections(
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    claims = db.query(models.CollectionClaim).filter(
        models.CollectionClaim.customer_id == customer.id
    ).all()
    return [c.collection_id for c in claims]


@router.post("/me/collections/{collection_id}/claim")
def claim_collection(
    collection_id: int,
    payload: schemas.ClaimIn,
    db: Session = Depends(get_db),
    customer: models.Customer = Depends(get_current_customer),
):
    collection = db.get(models.Collection, collection_id)
    if not collection:
        raise HTTPException(404, "Coleção não encontrada")

    existing = db.query(models.CollectionClaim).filter(
        models.CollectionClaim.customer_id == customer.id,
        models.CollectionClaim.collection_id == collection_id,
    ).first()
    if existing:
        raise HTTPException(400, "Você já resgatou a recompensa desta coleção")

    my_card_ids = {
        pull.card_id
        for pull in db.query(models.CardPull)
        .join(models.OrderItem, models.CardPull.order_item_id == models.OrderItem.id)
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .filter(models.Order.customer_id == customer.id)
        .all()
    }
    collection_card_ids = {c.id for c in collection.cards}
    if not collection_card_ids.issubset(my_card_ids):
        raise HTTPException(400, "Você ainda não completou esta coleção")

    db.add(models.CollectionClaim(
        customer_id=customer.id,
        collection_id=collection_id,
        address=payload.address,
    ))

    plate = customer.plate or "sem placa"
    db.add(models.Chamado(
        title=f"{customer.name} da placa {plate} completou a coleção {collection.name}",
        description=f"Endereço de entrega:\n{payload.address}",
        hours=96,
        status="aberto",
    ))

    db.commit()
    return {"ok": True}
