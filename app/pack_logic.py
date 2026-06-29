import random

from sqlalchemy.orm import Session

from . import models


def draw_rarity(db: Session, allow_lendaria: bool = True, force_min_rarity: str | None = None) -> models.Rarity:
    """Sorteia uma raridade com base no peso (chance) de cada uma."""
    rarities = db.query(models.Rarity).all()
    if not allow_lendaria:
        rarities = [r for r in rarities if r.id != "lendaria"]
    if force_min_rarity:
        order = ["normal", "rara", "lendaria"]
        min_idx = order.index(force_min_rarity)
        rarities = [r for r in rarities if order.index(r.id) >= min_idx]

    weights = [r.chance for r in rarities]
    return random.choices(rarities, weights=weights, k=1)[0]


def draw_card(db: Session, rarity: models.Rarity) -> models.Card | None:
    cards = db.query(models.Card).filter(models.Card.rarity_id == rarity.id).all()
    if not cards:
        return None
    return random.choice(cards)


def open_bonus_card(db: Session, product: models.Product) -> list[models.Card]:
    """Sorteia a carta bônus de um produto (não-pacote) que inclui 1 carta."""
    if not product.bonus_card_enabled:
        return []
    rarity_id = product.bonus_card_rarity or "random"
    if rarity_id == "random":
        rarity = draw_rarity(db)
    else:
        rarity = db.get(models.Rarity, rarity_id)
        if not rarity:
            rarity = draw_rarity(db)
    card = draw_card(db, rarity)
    return [card] if card else []


def open_pack(db: Session, product: models.Product) -> list[models.Card]:
    """Sorteia as cartas de um pacote, respeitando pack_config (server-side, anti-fraude)."""
    config = product.pack_config
    min_cards = config.min_cards if config else 1
    max_cards = config.max_cards if config else 1
    n = random.randint(min_cards, max_cards)

    # ultra_possible/holo_guaranteed: nomes herdados do esquema antigo de 5 raridades,
    # agora representam "pode sair lendária" e "garante pelo menos 1 rara"
    allow_lendaria = config.ultra_possible if config else True
    rara_guaranteed = config.holo_guaranteed if config else False

    drawn: list[models.Card] = []
    for i in range(n):
        force_min = "rara" if (rara_guaranteed and i == n - 1 and not any(
            c.rarity_id in ("rara", "lendaria") for c in drawn
        )) else None
        rarity = draw_rarity(db, allow_lendaria=allow_lendaria, force_min_rarity=force_min)
        card = draw_card(db, rarity)
        if card:
            drawn.append(card)
    return drawn
