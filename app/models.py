from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, JSON
)
from sqlalchemy.orm import relationship

from .database import Base


class Rarity(Base):
    __tablename__ = "rarities"

    id = Column(String, primary_key=True)  # comum, incomum, rara, holo, ultra
    label = Column(String, nullable=False)
    color = Column(String, nullable=False)
    chance = Column(Float, nullable=False)  # 0.60, 0.25, 0.10, 0.04, 0.01

    cards = relationship("Card", back_populates="rarity")


collection_cards = Table(
    "collection_cards",
    Base.metadata,
    Column("collection_id", Integer, ForeignKey("collections.id"), primary_key=True),
    Column("card_id", Integer, ForeignKey("cards.id"), primary_key=True),
)


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    image = Column(Text, nullable=True)
    rarity_id = Column(String, ForeignKey("rarities.id"), nullable=False)

    rarity = relationship("Rarity", back_populates="cards")
    collections = relationship("Collection", secondary=collection_cards, back_populates="cards")


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    cards = relationship("Card", secondary=collection_cards, back_populates="collections")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    category = Column(String, nullable=False)  # miniaturas, itens, pacotes
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    badge = Column(String, nullable=True)
    badge_color = Column(String, nullable=True)
    rating = Column(Float, default=5.0)
    reviews = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    specs = Column(JSON, default=list)  # [{label, value}]
    image = Column(Text, nullable=True)
    images = Column(JSON, default=list)
    miniature_type = Column(String, nullable=True)  # JDM, Outros
    is_pack = Column(Boolean, default=False)

    bonus_card_enabled = Column(Boolean, default=False)
    bonus_card_rarity = Column(String, nullable=True)  # rarity id or "random"

    created_at = Column(DateTime, default=datetime.utcnow)

    pack_config = relationship(
        "PackConfig", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )


class PackConfig(Base):
    __tablename__ = "pack_configs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), unique=True, nullable=False)
    min_cards = Column(Integer, default=1)
    max_cards = Column(Integer, default=1)
    holo_guaranteed = Column(Boolean, default=False)
    ultra_possible = Column(Boolean, default=True)

    product = relationship("Product", back_populates="pack_config")


class Chamado(Base):
    __tablename__ = "chamados"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    hours = Column(Integer, nullable=False)
    status = Column(String, default="em_andamento")  # em_andamento / concluido
    conta_id = Column(Integer, ForeignKey("contas.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conta = relationship("Conta")


class Conta(Base):
    __tablename__ = "contas"

    id = Column(Integer, primary_key=True, index=True)
    buyer_name = Column(String, nullable=False)
    transferred = Column(Float, nullable=False, default=0)
    spent = Column(Float, nullable=False, default=0)
    category = Column(String, nullable=False, default="miniatura")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="pendente")  # pendente, pago, cancelado
    total = Column(Float, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    pulls = relationship("CardPull", back_populates="order_item")


class CardPull(Base):
    __tablename__ = "card_pulls"

    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    unit_index = Column(Integer, default=0)  # qual unidade comprada (quando quantity > 1)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    order_item = relationship("OrderItem", back_populates="pulls")
    card = relationship("Card")
