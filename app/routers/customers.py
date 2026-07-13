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
    if len(pulls) < 4:
        raise HTTPException(400, "Você precisa de 4 cópias para trocar")

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
