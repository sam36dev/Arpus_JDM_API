from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_customer, hash_password, verify_password
from ..database import get_db

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/register", response_model=schemas.Token)
def register(payload: schemas.CustomerRegister, db: Session = Depends(get_db)):
    exists = db.query(models.Customer).filter(models.Customer.email == payload.email).first()
    if exists:
        raise HTTPException(400, "Já existe uma conta com este email")
    customer = models.Customer(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(customer)
    db.commit()
    token = create_access_token({"sub": customer.email, "type": "customer"})
    return {"access_token": token}


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.CustomerLogin, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.email == payload.email).first()
    if not customer or not verify_password(payload.password, customer.hashed_password):
        raise HTTPException(401, "Email ou senha inválidos")
    token = create_access_token({"sub": customer.email, "type": "customer"})
    return {"access_token": token}


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
