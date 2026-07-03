from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/chamados", tags=["chamados"])

EM_ANDAMENTO = ("aberto", "em_andamento")


def _score(created_at: datetime, hours: int) -> str:
    total = hours * 3600
    elapsed = (datetime.utcnow() - created_at).total_seconds()
    pct = ((total - elapsed) / total) * 100
    if pct >= 90: return "JDM MASTER"
    if pct >= 85: return "EXCELENTE"
    if pct >= 70: return "BOM"
    if pct >= 50: return "MEDIANO"
    if pct >= 10: return "RUIM"
    return "PÉSSIMO"


def _out(c: models.Chamado) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "hours": c.hours,
        "status": c.status,
        "score": c.score,
        "conta_id": c.conta_id,
        "conta_name": c.conta.buyer_name if c.conta else None,
        "created_at": c.created_at,
        "completed_at": c.completed_at,
    }


def _auto_conclude(db: Session, rows: list) -> None:
    now = datetime.utcnow()
    changed = False
    for c in rows:
        if c.status in EM_ANDAMENTO:
            deadline = c.created_at.replace(tzinfo=None) + timedelta(hours=c.hours)
            if now >= deadline:
                c.status = "concluido"
                c.score = _score(c.created_at, c.hours)
                c.completed_at = now
                changed = True
    if changed:
        db.commit()

@router.get("", response_model=list[schemas.ChamadoOut])
def list_chamados(db: Session = Depends(get_db), _admin=Depends(get_current_admin)):
    rows = (
        db.query(models.Chamado)
        .options(joinedload(models.Chamado.conta))
        .order_by(models.Chamado.created_at.desc())
        .all()
    )
    _auto_conclude(db, rows)
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
    data = payload.model_dump(exclude_none=True)
    if data.get("status") == "concluido" and chamado.status != "concluido":
        chamado.score = _score(chamado.created_at, chamado.hours)
        chamado.completed_at = datetime.utcnow()
    elif data.get("status") in ("aberto", "em_andamento"):
        chamado.score = None
        chamado.completed_at = None
    for key, value in data.items():
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
