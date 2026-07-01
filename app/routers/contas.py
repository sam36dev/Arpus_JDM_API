from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/contas", tags=["contas"])


@router.get("", response_model=list[schemas.ContaOut])
def list_contas(
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    return db.query(models.Conta).order_by(models.Conta.created_at.desc()).all()


@router.post("", response_model=schemas.ContaOut)
def create_conta(
    payload: schemas.ContaCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    conta = models.Conta(**payload.model_dump())
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.put("/{conta_id}", response_model=schemas.ContaOut)
def update_conta(
    conta_id: int,
    payload: schemas.ContaCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    conta = db.get(models.Conta, conta_id)
    if not conta:
        raise HTTPException(404, "Conta não encontrada")
    for key, value in payload.model_dump().items():
        setattr(conta, key, value)
    db.commit()
    db.refresh(conta)
    return conta


@router.delete("/{conta_id}", status_code=204)
def delete_conta(
    conta_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    conta = db.get(models.Conta, conta_id)
    if not conta:
        raise HTTPException(404, "Conta não encontrada")
    db.delete(conta)
    db.commit()
