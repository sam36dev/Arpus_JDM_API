import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .routers import admin, cards, collections, contas, customers, orders, products, rarities
from .seed_data import seed_initial_data

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    seed_initial_data(db)
finally:
    db.close()

app = FastAPI(title="ARPUS JDM API")

default_origins = "http://localhost:5173,http://127.0.0.1:5173"
cors_origins = os.getenv("CORS_ORIGINS", default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(admin.router)
app.include_router(customers.router)
app.include_router(orders.router)
app.include_router(rarities.router)
app.include_router(cards.router)
app.include_router(collections.router)
app.include_router(contas.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "arpus-jdm-api"}
