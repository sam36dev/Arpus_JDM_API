"""Popula raridades e cartas iniciais. Rodar uma vez: python seed.py
(em produção isso já roda automaticamente no startup do main.py)"""
from app.database import Base, SessionLocal, engine
from app.seed_data import seed_initial_data

Base.metadata.create_all(bind=engine)
db = SessionLocal()
seed_initial_data(db)
db.close()
print("Seed concluído.")
