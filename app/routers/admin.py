import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_admin, hash_password, verify_password
from ..database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(models.AdminUser).filter(models.AdminUser.email == payload.email).first()
    if not admin or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(401, "Email ou senha inválidos")
    token = create_access_token({"sub": admin.email, "type": "admin"})
    return {"access_token": token}


@router.get("/me")
def me(admin: models.AdminUser = Depends(get_current_admin)):
    return {"email": admin.email}


@router.post("/bootstrap")
def bootstrap(payload: schemas.AdminBootstrap, db: Session = Depends(get_db)):
    """Cria o primeiro admin. Exige ADMIN_BOOTSTRAP_KEY (env var) e só
    funciona se ainda não existir nenhum admin cadastrado."""
    bootstrap_key = os.getenv("ADMIN_BOOTSTRAP_KEY", "")
    if not bootstrap_key or payload.bootstrap_key != bootstrap_key:
        raise HTTPException(403, "Chave de bootstrap inválida")
    if db.query(models.AdminUser).count() > 0:
        raise HTTPException(403, "Já existe um admin cadastrado")
    admin = models.AdminUser(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(admin)
    db.commit()
    return {"ok": True}


RARITY_REMAP_V2 = {"comum": "normal", "incomum": "normal", "holo": "lendaria", "ultra": "lendaria"}
NEW_RARITIES_V2 = [
    {"id": "normal", "label": "Normal", "color": "#8a8a9a", "chance": 0.70},
    {"id": "rara", "label": "Rara", "color": "#c060ff", "chance": 0.20},
    {"id": "lendaria", "label": "Lendária", "color": "#c8a44a", "chance": 0.10},
]


@router.post("/migrate-rarities-v2")
def migrate_rarities_v2(
    db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """Migração única: 5 raridades (comum/incomum/rara/holo/ultra) -> 3
    (normal/rara/lendaria). Remove esta rota depois de rodar em todos os ambientes."""
    for r in NEW_RARITIES_V2:
        existing = db.get(models.Rarity, r["id"])
        if existing:
            existing.label, existing.color, existing.chance = r["label"], r["color"], r["chance"]
        else:
            db.add(models.Rarity(**r))
    db.flush()

    for card in db.query(models.Card).all():
        if card.rarity_id in RARITY_REMAP_V2:
            card.rarity_id = RARITY_REMAP_V2[card.rarity_id]

    for product in db.query(models.Product).all():
        if product.bonus_card_rarity in RARITY_REMAP_V2:
            product.bonus_card_rarity = RARITY_REMAP_V2[product.bonus_card_rarity]

    db.flush()
    for old_id in RARITY_REMAP_V2:
        old = db.get(models.Rarity, old_id)
        if old:
            db.delete(old)

    db.commit()
    return {"ok": True, "rarities": [r.id for r in db.query(models.Rarity).all()]}
