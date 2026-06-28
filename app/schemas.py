from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SpecItem(BaseModel):
    label: str
    value: str


class BonusCard(BaseModel):
    enabled: bool = False
    rarity: str = "random"


class PackConfigSchema(BaseModel):
    min_cards: int = 1
    max_cards: int = 1
    holo_guaranteed: bool = False
    ultra_possible: bool = True


class ProductBase(BaseModel):
    name: str
    brand: Optional[str] = None
    category: str
    price: float
    original_price: Optional[float] = None
    badge: Optional[str] = None
    badge_color: Optional[str] = None
    rating: float = 5.0
    reviews: int = 0
    description: Optional[str] = None
    specs: list[SpecItem] = []
    image: Optional[str] = None
    is_pack: bool = False
    bonus_card: BonusCard = BonusCard()
    pack_config: Optional[PackConfigSchema] = None


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class RarityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    color: str
    chance: float


class AdminLogin(BaseModel):
    email: str
    password: str


class AdminBootstrap(BaseModel):
    email: str
    password: str
    bootstrap_key: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CustomerRegister(BaseModel):
    name: str
    email: str
    password: str


class CustomerLogin(BaseModel):
    email: str
    password: str


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = 1


class OrderCreate(BaseModel):
    items: list[OrderItemCreate]
    customer_email: Optional[str] = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    quantity: int
    unit_price: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    total: float
    created_at: datetime
    items: list[OrderItemOut]


class CardPullOut(BaseModel):
    order_item_id: int
    card_id: int
    card_name: str
    card_image: Optional[str] = None
    rarity_id: str
    rarity_label: str
    rarity_color: str


class CustomerCardOut(BaseModel):
    card_id: int
    card_name: str
    card_image: Optional[str] = None
    rarity_id: str
    rarity_label: str
    rarity_color: str
    quantity: int
