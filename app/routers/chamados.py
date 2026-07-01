from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/chamados", tags=["chamados"])


@router.get("", response_model=list[schemas.ChamadoOut])
def list_chamados(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    return db.query(models.Chamado).order_by(models.Chamado.created_at.desc()).all()


@router.get("/count")
def count_abertos(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    count = db.query(models.Chamado).filter(models.Chamado.status == "aberto").count()
    return {"count": count}


@router.post("", response_model=schemas.ChamadoOut)
def create_chamado(payload: schemas.ChamadoCreate, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    chamado = models.Chamado(**payload.model_dump())
    db.add(chamado)
    db.commit()
    db.refresh(chamado)
    return chamado


@router.patch("/{chamado_id}", response_model=schemas.ChamadoOut)
def update_chamado(chamado_id: int, payload: schemas.ChamadoUpdate, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    chamado = db.get(models.Chamado, chamado_id)
    if not chamado:
        raise HTTPException(404, "Chamado não encontrado")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(chamado, key, value)
    db.commit()
    db.refresh(chamado)
    return chamado


@router.delete("/{chamado_id}", status_code=204)
def delete_chamado(chamado_id: int, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    chamado = db.get(models.Chamado, chamado_id)
    if not chamado:
        raise HTTPException(404, "Chamado não encontrado")
    db.delete(chamado)
    db.commit()
