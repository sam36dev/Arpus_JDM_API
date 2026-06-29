from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[schemas.CardOut])
def list_cards(db: Session = Depends(get_db)):
    return db.query(models.Card).all()


@router.post("", response_model=schemas.CardOut)
def create_card(
    payload: schemas.CardCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    if not db.get(models.Rarity, payload.rarity_id):
        raise HTTPException(404, "Raridade não encontrada")
    card = models.Card(**payload.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/{card_id}", response_model=schemas.CardOut)
def update_card(
    card_id: int,
    payload: schemas.CardCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    card = db.get(models.Card, card_id)
    if not card:
        raise HTTPException(404, "Carta não encontrada")
    if not db.get(models.Rarity, payload.rarity_id):
        raise HTTPException(404, "Raridade não encontrada")
    for key, value in payload.model_dump().items():
        setattr(card, key, value)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=204)
def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    card = db.get(models.Card, card_id)
    if not card:
        raise HTTPException(404, "Carta não encontrada")
    try:
        db.delete(card)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Esta carta já foi sorteada em algum pedido e não pode ser excluída")
