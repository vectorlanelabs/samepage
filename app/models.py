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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class AuthIdentity(Base):
    """External SSO identity (M5a): one row per (provider, subject) pair.

    The account is the durable login; this table records WHICH external
    identity is allowed to sign into it. ``UniqueConstraint(provider,
    subject)`` means one Google account maps to at most one Same Page
    account (the email match on callback links a first Google login to an
    existing account instead of creating a duplicate).
    """

    __tablename__ = "auth_identity"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
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


class Session(Base):
    """A voting session (plan §5): host-run, join-by-code, status per §5.6.

    ``status`` is app-enforced ('lobby'|'voting'|'complete'|'expired'),
    never a DB enum. ``last_activity_at`` feeds the §5.5 24-hour
    inactivity expiry rule.
    """

    __tablename__ = "session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id"), nullable=False)
    host_account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collection.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionTarget(Base):
    """One track's keep-target per session (generalizes lunch/dinner targets)."""

    __tablename__ = "session_target"
    __table_args__ = (
        CheckConstraint("target_count > 0", name="ck_session_target_positive"),
        UniqueConstraint("session_id", "track_label", name="uq_session_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), nullable=False)
    track_label: Mapped[str] = mapped_column(String, nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)


class SessionParticipant(Base):
    """Someone who joined a specific session — ephemeral, deleted at finish
    (§5.5). ``account_id`` is set only if logged in at join time (pre-fill
    only, confers no permission)."""

    __tablename__ = "session_participant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), nullable=False)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Batch(Base):
    """One round of options within a session. ``status``: 'open'|'closed'
    (§5.6)."""

    __tablename__ = "batch"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_batch_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    track_label: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BatchItem(Base):
    """One option in a batch — the durable outcome record (aggregate counts
    only, no person id; §5.4). Exactly one of ``item_id`` / ``ad_hoc_label``
    is set (DB CHECK). The partial unique indexes (mirrored in migration
    0009) stop the same item or label appearing twice in one batch."""

    __tablename__ = "batch_item"
    __table_args__ = (
        CheckConstraint("(item_id IS NULL) != (ad_hoc_label IS NULL)", name="ck_batch_item_one_of"),
        Index(
            "uq_batch_item_item",
            "batch_id",
            "item_id",
            unique=True,
            sqlite_where=text("item_id IS NOT NULL"),
        ),
        Index(
            "uq_batch_item_adhoc",
            "batch_id",
            "ad_hoc_label",
            unique=True,
            sqlite_where=text("ad_hoc_label IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"), nullable=False)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("item.id"), nullable=True)
    ad_hoc_label: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)


class BatchResponse(Base):
    """One participant's in-batch vote — EPHEMERAL: deleted in the same
    transaction that closes its batch (§5.5). The unique constraint means
    each participant answers each option exactly once."""

    __tablename__ = "batch_response"
    __table_args__ = (
        UniqueConstraint("batch_item_id", "session_participant_id", name="uq_batch_response"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_item_id: Mapped[int] = mapped_column(ForeignKey("batch_item.id"), nullable=False)
    session_participant_id: Mapped[int] = mapped_column(
        ForeignKey("session_participant.id"), nullable=False
    )
    choice: Mapped[str] = mapped_column(String, nullable=False)
    responded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


