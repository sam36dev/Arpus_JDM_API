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
    images: list[str] = []
    miniature_type: Optional[str] = None
    is_pack: bool = False
    stock: Optional[int] = None
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


class CardCreate(BaseModel):
    name: str
    image: Optional[str] = None
    rarity_id: str


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    image: Optional[str] = None
    rarity_id: str
    rarity: RarityOut


class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    reward_image: Optional[str] = None
    card_ids: list[int] = []


class CardOutLight(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    rarity_id: str
    rarity: RarityOut

class CollectionListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    reward_image: Optional[str] = None
    created_at: datetime
    cards: list[CardOutLight] = []

class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    reward_image: Optional[str] = None
    created_at: datetime
    cards: list[CardOut] = []


class ContaCreate(BaseModel):
    buyer_name: str
    transferred: float = 0
    spent: float = 0
    category: str = "miniatura"
    notes: Optional[str] = None


class ContaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    buyer_name: str
    transferred: float
    spent: float
    category: str
    notes: Optional[str]
    created_at: datetime


class ChamadoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    hours: int
    conta_id: Optional[int] = None


class ChamadoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    hours: Optional[int] = None
    status: Optional[str] = None
    conta_id: Optional[int] = None


class ChamadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str]
    hours: int
    status: str
    score: Optional[str] = None
    conta_id: Optional[int] = None
    conta_name: Optional[str] = None
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


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
    last_name: Optional[str] = None
    email: str
    password: str


class CustomerLogin(BaseModel):
    email: str
    password: str


class CompleteProfileIn(BaseModel):
    phone: str
    cpf: str
    birth_date: str
    address_cep: str
    address_street: str
    address_number: str
    address_complement: Optional[str] = None
    address_neighborhood: str
    address_city: str
    address_state: str


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    last_name: Optional[str] = None
    email: str
    plate: Optional[str] = None
    phone: Optional[str] = None
    cpf: Optional[str] = None
    birth_date: Optional[str] = None
    address_cep: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None

class CustomerLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    last_name: Optional[str] = None
    email: str
    plate: Optional[str] = None
    address_cep: Optional[str] = None


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

class TradeCardIn(BaseModel):
    card_id: int

class TradeCardOut(BaseModel):
    order_id: int
    pack_name: str

class ClaimIn(BaseModel):
    address: str
