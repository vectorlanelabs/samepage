"""SQLAlchemy models — every table from plan §6, exactly.

Notes:
- No cascade deletes anywhere: people and meals are deactivated, never
  deleted (D16), so foreign keys default to RESTRICT.
- No ``favorite`` table: favorites are derived from ``meal.times_kept`` /
  ``last_kept_at`` (D9).
- No ``legacy_rolls`` anywhere: the spreadsheet's Times Rolled column is
  deliberately ignored.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_pin_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_sheet_index: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class Meal(Base):
    __tablename__ = "meal"
    __table_args__ = (
        CheckConstraint("type IN ('dinner','lunch','both')", name="ck_meal_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False, default="dinner")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    times_kept: Mapped[int] = mapped_column(Integer, default=0)
    last_kept_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class MealTag(Base):
    __tablename__ = "meal_tag"

    meal_id: Mapped[int] = mapped_column(ForeignKey("meal.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id"), primary_key=True)


class Session(Base):
    __tablename__ = "session"
    __table_args__ = (
        CheckConstraint(
            "status IN ('lobby','voting','complete','expired')", name="ck_session_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="lobby")
    created_by_person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    lunch_target: Mapped[int] = mapped_column(Integer, nullable=False)
    dinner_target: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionParticipant(Base):
    __tablename__ = "session_participant"

    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Batch(Base):
    __tablename__ = "batch"
    __table_args__ = (
        UniqueConstraint("session_id", "seq"),
        CheckConstraint("status IN ('open','closed')", name="ck_batch_status"),
        CheckConstraint("track IN ('dinner','lunch')", name="ck_batch_track"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    track: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BatchMeal(Base):
    __tablename__ = "batch_meal"
    __table_args__ = (
        CheckConstraint(
            "kept_by IS NULL OR kept_by IN ('unanimous','host')",
            name="ck_batch_meal_kept_by",
        ),
    )

    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"), primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meal.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    kept: Mapped[bool] = mapped_column(Boolean, default=False)
    kept_by: Mapped[str | None] = mapped_column(String, nullable=True)


class Vote(Base):
    __tablename__ = "vote"
    __table_args__ = (
        UniqueConstraint("batch_id", "person_id", "meal_id"),
        CheckConstraint("choice IN ('yes','no')", name="ck_vote_choice"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meal.id"), nullable=False)
    choice: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
