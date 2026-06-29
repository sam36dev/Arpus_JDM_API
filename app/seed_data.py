from sqlalchemy.orm import Session

from .models import Card, Rarity

RARITIES = [
    {"id": "normal", "label": "Normal", "color": "#8a8a9a", "chance": 0.70},
    {"id": "rara", "label": "Rara", "color": "#c060ff", "chance": 0.20},
    {"id": "lendaria", "label": "Lendária", "color": "#c8a44a", "chance": 0.10},
]

CARDS = [
    ("Honda EK9 Civic Type R", "normal"),
    ("Toyota AE86 Trueno", "normal"),
    ("Mazda RX-7 FD3S", "normal"),
    ("Nissan Skyline R34", "normal"),
    ("Toyota Supra MK4", "normal"),
    ("Mitsubishi Lancer Evo VI", "rara"),
    ("Subaru Impreza WRX STI 22B", "rara"),
    ("Nissan Skyline GT-R R34 Nismo", "lendaria"),
    ("Toyota Supra MK4 Top Secret", "lendaria"),
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
