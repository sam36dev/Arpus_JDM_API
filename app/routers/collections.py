from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[schemas.CollectionListOut])
def list_collections(db: Session = Depends(get_db)):
    cnt_sq = (
        db.query(
            models.collection_cards.c.collection_id,
            func.count().label("cnt"),
        )
        .group_by(models.collection_cards.c.collection_id)
        .subquery()
    )
    rows = (
        db.query(models.Collection, func.coalesce(cnt_sq.c.cnt, 0))
        .outerjoin(cnt_sq, models.Collection.id == cnt_sq.c.collection_id)
        .order_by(models.Collection.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id, "name": c.name, "description": c.description,
            "image": c.image, "reward_image": c.reward_image,
            "created_at": c.created_at, "card_count": int(cnt),
        }
        for c, cnt in rows
    ]


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
        name=payload.name, description=payload.description,
        image=payload.image, reward_image=payload.reward_image
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
    collection.reward_image = payload.reward_image
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
