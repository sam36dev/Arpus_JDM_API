import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .database import Base, SessionLocal, engine
from .limiter import limiter
from .routers import admin, cards, chamados, collections, contas, customers, orders, products, rarities
from .seed_data import seed_initial_data

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    seed_initial_data(db)
finally:
    db.close()

app = FastAPI(title="ARPUS JDM API")
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Muitas tentativas. Aguarde um momento e tente novamente."},
    )

default_origins = "http://localhost:5173,http://127.0.0.1:5173"
cors_origins = os.getenv("CORS_ORIGINS", default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://(.*\.vercel\.app|.*\.arpusjdm\.com|arpusjdm\.com)",
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
app.include_router(chamados.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "arpus-jdm-api"}
