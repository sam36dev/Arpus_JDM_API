from sqlalchemy.orm import Session

from .models import Card, Rarity

RARITIES = [
    {"id": "comum", "label": "Comum", "color": "#8a8a9a", "chance": 0.60},
    {"id": "incomum", "label": "Incomum", "color": "#4a9eff", "chance": 0.25},
    {"id": "rara", "label": "Rara", "color": "#c8a44a", "chance": 0.10},
    {"id": "holo", "label": "Holo Rara", "color": "#c060ff", "chance": 0.04},
    {"id": "ultra", "label": "Ultra Rara", "color": "#ff4040", "chance": 0.01},
]

CARDS = [
    ("Honda EK9 Civic Type R", "comum"),
    ("Toyota AE86 Trueno", "comum"),
    ("Mazda RX-7 FD3S", "comum"),
    ("Nissan Skyline R34", "incomum"),
    ("Toyota Supra MK4", "incomum"),
    ("Mitsubishi Lancer Evo VI", "rara"),
    ("Subaru Impreza WRX STI 22B", "rara"),
    ("Nissan Skyline GT-R R34 Nismo", "holo"),
    ("Toyota Supra MK4 Top Secret", "ultra"),
]


def seed_initial_data(db: Session) -> None:
    """Popula raridades e cartas iniciais, se ainda não existirem. Idempotente —
    seguro de chamar a cada boot (ex: primeiro deploy em banco vazio)."""
    if db.query(Rarity).count() == 0:
        for r in RARITIES:
            db.add(Rarity(**r))
        db.commit()

    if db.query(Card).count() == 0:
        for name, rarity_id in CARDS:
            db.add(Card(name=name, rarity_id=rarity_id))
        db.commit()
