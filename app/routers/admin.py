import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_admin, get_current_super_admin, hash_password, verify_password
from ..database import get_db
from ..limiter import limiter


class AdminCreate(BaseModel):
    email: str
    password: str
    role: str = "atendente"

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/2hours")
def login(request: Request, payload: schemas.AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(models.AdminUser).filter(func.lower(models.AdminUser.email) == payload.email.lower()).first()
    if not admin or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(401, "Email ou senha inválidos")
    token = create_access_token({"sub": admin.email, "type": "admin"})
    return {"access_token": token}


def _pct_to_score(pct: float) -> str:
    if pct >= 90: return "JDM MASTER"
    if pct >= 85: return "EXCELENTE"
    if pct >= 70: return "BOM"
    if pct >= 50: return "MEDIANO"
    if pct >= 10: return "RUIM"
    return "PÉSSIMO"

@router.get("/me")
def me(admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    # Auto-concluir vencidos antes de calcular score
    from .chamados import _auto_conclude as _ac
    active = db.query(models.Chamado).filter(
        models.Chamado.status.in_(["em_andamento", "aberto"])
    ).all()
    _ac(db, active)

    # Média dos índices de score de todos os chamados concluídos
    score_order = ["JDM MASTER", "EXCELENTE", "BOM", "MEDIANO", "RUIM", "PÉSSIMO"]
    concluded = (
        db.query(models.Chamado)
        .filter(models.Chamado.status == "concluido")
        .all()
    )
    if concluded:
        # Chamados sem score (histórico anterior à migração) contam como PÉSSIMO
        indices = [
            score_order.index(c.score) if c.score in score_order else 5
            for c in concluded
        ]
        score = score_order[round(sum(indices) / len(indices))]
    else:
        score = None
    return {"email": admin.email, "role": admin.role or "super", "score": score}


@router.delete("/customers/{email}/pulls")
def clear_customer_pulls(email: str, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    customer = db.query(models.Customer).filter(func.lower(models.Customer.email) == email.lower()).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado")
    orders = db.query(models.Order).filter(models.Order.customer_id == customer.id).all()
    deleted = 0
    for order in orders:
        for item in order.items:
            for pull in item.pulls:
                db.delete(pull)
                deleted += 1
    db.commit()
    return {"ok": True, "deleted": deleted}


@router.post("/create-admin")
def create_admin(payload: AdminCreate, db: Session = Depends(get_db), _super=Depends(get_current_super_admin)):
    if db.query(models.AdminUser).filter(models.AdminUser.email == payload.email).first():
        raise HTTPException(400, "Email já cadastrado")
    user = models.AdminUser(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    return {"ok": True, "email": payload.email, "role": payload.role}


@router.post("/migrate-customer-plate")
def migrate_customer_plate(db: Session = Depends(get_db)):
    try:
        db.execute(text("ALTER TABLE customers ADD COLUMN plate VARCHAR UNIQUE"))
        db.commit()
        return {"ok": True, "msg": "Coluna plate adicionada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


@router.post("/migrate-collection-reward")
def migrate_collection_reward(db: Session = Depends(get_db)):
    try:
        db.execute(text("ALTER TABLE collections ADD COLUMN reward_image TEXT"))
        db.commit()
        return {"ok": True, "msg": "Coluna reward_image adicionada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


@router.post("/migrate-product-stock")
def migrate_product_stock(db: Session = Depends(get_db)):
    try:
        db.execute(text("ALTER TABLE products ADD COLUMN stock INTEGER"))
        db.commit()
        return {"ok": True, "msg": "Coluna stock adicionada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


@router.post("/migrate-chamado-score")
def migrate_chamado_score(db: Session = Depends(get_db)):
    results = []
    for col, ddl in [
        ("score", "ALTER TABLE chamados ADD COLUMN score VARCHAR"),
        ("completed_at", "ALTER TABLE chamados ADD COLUMN completed_at TIMESTAMP"),
    ]:
        try:
            db.execute(text(ddl))
            db.commit()
            results.append(f"{col}: ok")
        except Exception as e:
            db.rollback()
            results.append(f"{col}: {e}")
    return {"results": results}


@router.post("/migrate-admin-role")
def migrate_admin_role(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    try:
        db.execute(text("ALTER TABLE admin_users ADD COLUMN role VARCHAR DEFAULT 'super'"))
        db.commit()
        return {"ok": True, "msg": "Coluna role adicionada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


@router.post("/migrate-chamado-conta")
def migrate_chamado_conta(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    try:
        db.execute(text("ALTER TABLE chamados ADD COLUMN conta_id INTEGER REFERENCES contas(id)"))
        db.commit()
        return {"ok": True, "msg": "Coluna conta_id adicionada a chamados"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


@router.post("/migrate-miniature-type")
def migrate_miniature_type(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    try:
        db.execute(text("ALTER TABLE products ADD COLUMN miniature_type VARCHAR"))
        db.commit()
        return {"ok": True, "msg": "Coluna miniature_type adicionada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


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


@router.post("/migrate-collection-claims")
def migrate_collection_claims(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS collection_claims (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                collection_id INTEGER REFERENCES collections(id),
                address TEXT NOT NULL,
                claimed_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db.commit()
        return {"ok": True, "msg": "Tabela collection_claims criada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


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


