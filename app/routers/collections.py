from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[schemas.CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    return db.query(models.Collection).order_by(models.Collection.created_at.desc()).all()


@router.get("/{collection_id}", response_model=schemas.CollectionOut)
def get_collection(collection_id: int, db: Session = Depends(get_db)):
    collection = db.get(models.Collection, collection_id)
    if not collection:
        raise HTTPException(404, "Coleção não encontrada")
    return collection


def _set_cards(db: Session, collection: models.Collection, card_ids: list[int]) -> None:
    if card_ids:
        cards = db.query(models.Card).filter(models.Card.id.in_(card_ids)).all()
        if len(cards) != len(set(card_ids)):
            raise HTTPException(404, "Uma ou mais cartas não foram encontradas")
        collection.cards = cards
    else:
        collection.cards = []


@router.post("", response_model=schemas.CollectionOut)
def create_collection(
    payload: schemas.CollectionCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    collection = models.Collection(
        name=payload.name, description=payload.description, image=payload.image
    )
    db.add(collection)
    db.flush()
    _set_cards(db, collection, payload.card_ids)
    db.commit()
    db.refresh(collection)
    return collection


@router.put("/{collection_id}", response_model=schemas.CollectionOut)
def update_collection(
    collection_id: int,
    payload: schemas.CollectionCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    collection = db.get(models.Collection, collection_id)
    if not collection:
        raise HTTPException(404, "Coleção não encontrada")
    collection.name = payload.name
    collection.description = payload.description
    collection.image = payload.image
    _set_cards(db, collection, payload.card_ids)
    db.commit()
    db.refresh(collection)
    return collection


@router.delete("/{collection_id}", status_code=204)
def delete_collection(
    collection_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    collection = db.get(models.Collection, collection_id)
    if not collection:
        raise HTTPException(404, "Coleção não encontrada")
    db.delete(collection)
    db.commit()
