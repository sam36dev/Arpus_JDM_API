import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, text, desc
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
@limiter.limit("30/hour")
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


@router.post("/contas/merge-duplicates")
def merge_duplicate_contas(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """Junta contas com o mesmo nome: mantém a mais antiga, reatribui chamados e soma valores."""
    from collections import defaultdict
    all_contas = db.query(models.Conta).order_by(models.Conta.id).all()
    by_name = defaultdict(list)
    for c in all_contas:
        by_name[c.buyer_name.strip().lower()].append(c)

    merged = 0
    for name, group in by_name.items():
        if len(group) <= 1:
            continue
        keep = group[0]  # mais antiga (menor id)
        duplicates = group[1:]
        for dup in duplicates:
            # Reatribui chamados
            db.query(models.Chamado).filter(models.Chamado.conta_id == dup.id).update({"conta_id": keep.id})
            # Soma valores
            keep.transferred += dup.transferred
            keep.spent += dup.spent
            db.delete(dup)
            merged += 1
    db.commit()
    return {"ok": True, "merged": merged}


@router.post("/migrate-chamado-scheduled")
def migrate_chamado_scheduled(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    try:
        db.execute(text("ALTER TABLE chamados ADD COLUMN scheduled_at TIMESTAMP"))
        db.commit()
        return {"ok": True, "msg": "Coluna scheduled_at adicionada"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "msg": str(e)}


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


@router.post("/migrate-customer-profile")
def migrate_customer_profile(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """Adiciona as colunas de perfil completo à tabela customers."""
    columns = [
        ("last_name", "ALTER TABLE customers ADD COLUMN last_name VARCHAR"),
        ("phone", "ALTER TABLE customers ADD COLUMN phone VARCHAR"),
        ("cpf", "ALTER TABLE customers ADD COLUMN cpf VARCHAR UNIQUE"),
        ("birth_date", "ALTER TABLE customers ADD COLUMN birth_date VARCHAR"),
        ("address_cep", "ALTER TABLE customers ADD COLUMN address_cep VARCHAR"),
        ("address_street", "ALTER TABLE customers ADD COLUMN address_street VARCHAR"),
        ("address_number", "ALTER TABLE customers ADD COLUMN address_number VARCHAR"),
        ("address_complement", "ALTER TABLE customers ADD COLUMN address_complement VARCHAR"),
        ("address_neighborhood", "ALTER TABLE customers ADD COLUMN address_neighborhood VARCHAR"),
        ("address_city", "ALTER TABLE customers ADD COLUMN address_city VARCHAR"),
        ("address_state", "ALTER TABLE customers ADD COLUMN address_state VARCHAR"),
    ]
    results = []
    for col, ddl in columns:
        try:
            db.execute(text(ddl))
            db.commit()
            results.append(f"{col}: ok")
        except Exception as e:
            db.rollback()
            results.append(f"{col}: {e}")
    return {"results": results}


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    payload: ChangePasswordPayload,
    db: Session = Depends(get_db),
    admin: models.AdminUser = Depends(get_current_admin),
):
    if not verify_password(payload.current_password, admin.hashed_password):
        raise HTTPException(400, "Senha atual incorreta")
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Nova senha precisa ter no mínimo 8 caracteres")
    admin.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


@router.get("/customers/ranking")
def customers_ranking(
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    rows = (
        db.query(
            models.Customer.id,
            models.Customer.name,
            models.Customer.email,
            models.Customer.plate,
            func.coalesce(func.sum(models.Order.total), 0).label("points"),
            func.count(models.Order.id).label("orders"),
        )
        .outerjoin(
            models.Order,
            (models.Order.customer_id == models.Customer.id) &
            (models.Order.total > 0) &
            (models.Order.status.in_(["pago", "pendente"]))
        )
        .group_by(models.Customer.id)
        .order_by(desc("points"))
        .all()
    )
    return [
        {
            "position": i + 1,
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "plate": r.plate,
            "points": round(float(r.points), 2),
            "orders": r.orders,
        }
        for i, r in enumerate(rows)
    ]


@router.get("/customers/by-plate/{plate}")
def customer_by_plate(
    plate: str,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    customer = db.query(models.Customer).filter(
        func.lower(models.Customer.plate) == plate.strip().lower()
    ).first()
    if not customer:
        raise HTTPException(404, "Nenhum cliente com essa placa")

    my_card_ids = {
        pull.card_id
        for pull in db.query(models.CardPull)
        .join(models.OrderItem, models.CardPull.order_item_id == models.OrderItem.id)
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .filter(models.Order.customer_id == customer.id)
        .all()
    }
    total_cards = len(my_card_ids)

    collections = db.query(models.Collection).all()
    collection_progress = []
    for col in collections:
        col_card_ids = {c.id for c in col.cards}
        if not col_card_ids:
            continue
        owned = len(col_card_ids & my_card_ids)
        collection_progress.append({
            "name": col.name,
            "owned": owned,
            "total": len(col_card_ids),
        })

    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "plate": customer.plate,
        "total_cards": total_cards,
        "collections": collection_progress,
    }


class GiftPacksPayload(BaseModel):
    customer_id: int
    pack_product_id: int
    quantity: int


@router.post("/gift-packs")
def gift_packs(
    payload: GiftPacksPayload,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    customer = db.get(models.Customer, payload.customer_id)
    if not customer:
        raise HTTPException(404, "Cliente não encontrado")
    product = db.get(models.Product, payload.pack_product_id)
    if not product or not product.is_pack:
        raise HTTPException(400, "Produto não é um pacote")
    if payload.quantity < 1 or payload.quantity > 50:
        raise HTTPException(400, "Quantidade inválida (1–50)")

    for _ in range(payload.quantity):
        order = models.Order(
            customer_id=customer.id,
            customer_email=customer.email,
            status="pendente",
            total=0.0,
        )
        db.add(order)
        db.flush()
        db.add(models.OrderItem(order_id=order.id, product_id=product.id, quantity=1, unit_price=0.0))

    db.commit()
    return {"ok": True, "sent": payload.quantity}


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


