from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/products", tags=["products"])


def _to_out(p: models.Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "brand": p.brand,
        "category": p.category,
        "price": p.price,
        "original_price": p.original_price,
        "badge": p.badge,
        "badge_color": p.badge_color,
        "rating": p.rating,
        "reviews": p.reviews,
        "description": p.description,
        "specs": p.specs or [],
        "image": p.image,
        "images": p.images or [],
        "miniature_type": p.miniature_type,
        "is_pack": p.is_pack,
        "stock": p.stock,
        "created_at": p.created_at,
        "bonus_card": {
            "enabled": p.bonus_card_enabled,
            "rarity": p.bonus_card_rarity or "random",
        },
        "pack_config": (
            {
                "min_cards": p.pack_config.min_cards,
                "max_cards": p.pack_config.max_cards,
                "holo_guaranteed": p.pack_config.holo_guaranteed,
                "ultra_possible": p.pack_config.ultra_possible,
            }
            if p.pack_config
            else None
        ),
    }


@router.get("", response_model=list[schemas.ProductOut])
def list_products(category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Product)
    if category:
        query = query.filter(models.Product.category == category)
    return [_to_out(p) for p in query.all()]


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Product, product_id)
    if not p:
        raise HTTPException(404, "Produto não encontrado")
    return _to_out(p)


@router.post("", response_model=schemas.ProductOut)
def create_product(
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    data = payload.model_dump(exclude={"bonus_card", "pack_config", "specs"})
    data["image"] = data["images"][0] if data.get("images") else data.get("image")
    product = models.Product(
        **data,
        specs=[s.model_dump() for s in payload.specs],
        bonus_card_enabled=payload.bonus_card.enabled,
        bonus_card_rarity=payload.bonus_card.rarity,
    )
    db.add(product)
    db.flush()

    if payload.is_pack and payload.pack_config:
        db.add(models.PackConfig(product_id=product.id, **payload.pack_config.model_dump()))

    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(404, "Produto não encontrado")

    data = payload.model_dump(exclude={"bonus_card", "pack_config", "specs"})
    data["image"] = data["images"][0] if data.get("images") else data.get("image")
    for key, value in data.items():
        setattr(product, key, value)
    product.specs = [s.model_dump() for s in payload.specs]
    product.bonus_card_enabled = payload.bonus_card.enabled
    product.bonus_card_rarity = payload.bonus_card.rarity

    if payload.is_pack and payload.pack_config:
        if product.pack_config:
            for key, value in payload.pack_config.model_dump().items():
                setattr(product.pack_config, key, value)
        else:
            db.add(models.PackConfig(product_id=product.id, **payload.pack_config.model_dump()))
    elif product.pack_config:
        db.delete(product.pack_config)

    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(404, "Produto não encontrado")
    db.delete(product)
    db.commit()
    return {"ok": True}
