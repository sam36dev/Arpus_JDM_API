from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/chamados", tags=["chamados"])

EM_ANDAMENTO = ("aberto", "em_andamento")


def _out(c: models.Chamado) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "hours": c.hours,
        "status": c.status,
        "conta_id": c.conta_id,
        "conta_name": c.conta.buyer_name if c.conta else None,
        "created_at": c.created_at,
    }


@router.get("", response_model=list[schemas.ChamadoOut])
def list_chamados(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    rows = (
        db.query(models.Chamado)
        .options(joinedload(models.Chamado.conta))
        .order_by(models.Chamado.created_at.desc())
        .all()
    )
    return [_out(c) for c in rows]


@router.get("/count")
def count_em_andamento(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    count = db.query(models.Chamado).filter(models.Chamado.status.in_(EM_ANDAMENTO)).count()
    return {"count": count}


@router.post("", response_model=schemas.ChamadoOut)
def create_chamado(payload: schemas.ChamadoCreate, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    chamado = models.Chamado(**payload.model_dump())
    db.add(chamado)
    db.commit()
    db.refresh(chamado)
    if chamado.conta_id:
        db.refresh(chamado.conta)
    return _out(chamado)


@router.patch("/{chamado_id}", response_model=schemas.ChamadoOut)
def update_chamado(chamado_id: int, payload: schemas.ChamadoUpdate, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    chamado = db.query(models.Chamado).options(joinedload(models.Chamado.conta)).filter(models.Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(404, "Chamado não encontrado")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(chamado, key, value)
    db.commit()
    db.refresh(chamado)
    return _out(chamado)


@router.delete("/{chamado_id}", status_code=204)
def delete_chamado(chamado_id: int, db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    chamado = db.get(models.Chamado, chamado_id)
    if not chamado:
        raise HTTPException(404, "Chamado não encontrado")
    db.delete(chamado)
    db.commit()
