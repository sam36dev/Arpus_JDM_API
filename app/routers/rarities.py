from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/rarities", tags=["rarities"])


@router.get("", response_model=list[schemas.RarityOut])
def list_rarities(db: Session = Depends(get_db)):
    return db.query(models.Rarity).all()
