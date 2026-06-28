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
