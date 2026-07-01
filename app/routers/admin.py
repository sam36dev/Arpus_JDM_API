import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
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


@router.post("/migrate-images-column")
def migrate_images_column(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """Adiciona coluna images à tabela products se não existir."""
    try:
        db.execute(text("ALTER TABLE products ADD COLUMN images JSON"))
        db.commit()
        return {"ok": True, "msg": "Coluna images adicionada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


@router.post("/seed-packs")
def seed_packs(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """Cria os 3 pacotes padrão se ainda não existirem."""
    packs_data = [
        dict(name="Pack Solo", brand="ARPUS Collectibles", category="pacotes",
             price=11.99, description="1 carta por pack. Cada abertura pode surpreender.",
             is_pack=True, rating=5.0, reviews=0, specs=[],
             cfg=dict(min_cards=1, max_cards=1, holo_guaranteed=False, ultra_possible=True)),
        dict(name="Pack Trio", brand="ARPUS Collectibles", category="pacotes",
             price=29.97, description="3 cartas por pack. Mais chances, mais surpresas.",
             is_pack=True, rating=5.0, reviews=0, specs=[],
             cfg=dict(min_cards=3, max_cards=3, holo_guaranteed=False, ultra_possible=True)),
        dict(name="Pack Sexteto", brand="ARPUS Collectibles", category="pacotes",
             price=53.94, description="6 cartas por pack. Garante pelo menos 1 Rara.",
             is_pack=True, rating=5.0, reviews=0, specs=[],
             cfg=dict(min_cards=6, max_cards=6, holo_guaranteed=True, ultra_possible=True)),
    ]
    created = []
    for data in packs_data:
        cfg = data.pop("cfg")
        existing = db.query(models.Product).filter(models.Product.name == data["name"]).first()
        if not existing:
            product = models.Product(**data, bonus_card_enabled=False)
            db.add(product)
            db.flush()
            db.add(models.PackConfig(product_id=product.id, **cfg))
            created.append(data["name"])
    db.commit()
    return {"created": created}


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


