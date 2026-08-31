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


def draw_card(db: Session, rarity: models.Rarity, exclude_ids: set[int] | None = None) -> models.Card | None:
    cards = (
        db.query(models.Card)
        .filter(models.Card.rarity_id == rarity.id)
        .filter(models.Card.collections.any())
        .all()
    )
    if exclude_ids:
        cards = [c for c in cards if c.id not in exclude_ids]
    if not cards:
        return None
    return random.choice(cards)


CARD_PER_REAIS = 39.0

def open_bonus_card(db: Session, product: models.Product) -> list[models.Card]:
    """1 carta aleatória a cada R$39 em miniaturas. Automático — sem toggle."""
    if product.is_pack or product.category != "miniaturas":
        return []
    n = int(product.price // CARD_PER_REAIS)
    if n <= 0:
        return []
    cards = []
    for _ in range(n):
        rarity = draw_rarity(db)
        card = draw_card(db, rarity)
        if card:
            cards.append(card)
    return cards


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
    drawn_ids: set[int] = set()
    for i in range(n):
        force_min = "rara" if (rara_guaranteed and i == n - 1 and not any(
            c.rarity_id in ("rara", "lendaria") for c in drawn
        )) else None
        rarity = draw_rarity(db, allow_lendaria=allow_lendaria, force_min_rarity=force_min)
        card = draw_card(db, rarity, exclude_ids=drawn_ids)
        if not card:
            # Se não sobrou carta única nessa raridade, sorteio sem restrição
            card = draw_card(db, rarity)
        if card:
            drawn.append(card)
            drawn_ids.add(card.id)
    return drawn
