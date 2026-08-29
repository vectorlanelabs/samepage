"""SQLAlchemy models — every table from PLAN-v2-samepage.md §5, exactly.

Notes:
- No cascade deletes anywhere: accounts and meals are deactivated, never
  deleted, so foreign keys default to RESTRICT.
- No ``favorite`` table: favorites are derived from ``item.times_kept`` /
  ``last_kept_at``.
- No ``legacy_rolls`` anywhere: the spreadsheet's Times Rolled column is
  deliberately ignored.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Group(Base):
    __tablename__ = "group"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    owner_account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class GroupAdmin(Base):
    __tablename__ = "group_admin"

    group_id: Mapped[int] = mapped_column(ForeignKey("group.id"), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Collection(Base):
    __tablename__ = "collection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="meal")
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Category(Base):
    __tablename__ = "category"
    __table_args__ = (UniqueConstraint("collection_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collection.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_sheet_index: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("group_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collection.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    times_offered: Mapped[int] = mapped_column(Integer, default=0)
    times_kept: Mapped[int] = mapped_column(Integer, default=0)
    last_kept_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class ItemTag(Base):
    __tablename__ = "item_tag"

    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id"), primary_key=True)


class MealDetail(Base):
    __tablename__ = "meal_detail"
    __table_args__ = (
        CheckConstraint("type IN ('dinner','lunch','both')", name="ck_meal_detail_type"),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False, default="dinner")
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)


