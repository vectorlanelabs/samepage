"""Model round-trip + integrity constraints for every table in PLAN-v2-samepage.md §5."""

import sqlite3

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models import (
    Account,
    Category,
    Collection,
    Group,
    GroupAdmin,
    Item,
    ItemTag,
    MealDetail,
    Tag,
)


def test_account_round_trip(db_session):
    account = Account(
        email="test@example.com",
        password_hash="pbkdf2-hash",
        display_name="Test User",
    )
    db_session.add(account)
    db_session.commit()

    # Prove persistence by expiring and re-reading from the database.
    db_session.expire_all()

    account_q = db_session.get(Account, account.id)
    assert account_q.email == "test@example.com"
    assert account_q.password_hash == "pbkdf2-hash"
    assert account_q.display_name == "Test User"


def test_group_and_admin_round_trip(db_session):
    owner = Account(email="owner@example.com", password_hash="hash1", display_name="Owner")
    admin = Account(email="admin@example.com", password_hash="hash2", display_name="Admin")
    db_session.add_all([owner, admin])
    db_session.flush()

    group = Group(name="Test Group", owner_account_id=owner.id)
    db_session.add(group)
    db_session.flush()

    group_admin = GroupAdmin(group_id=group.id, account_id=admin.id)
    db_session.add(group_admin)
    db_session.commit()

    # Prove persistence by expiring and re-reading from the database.
    db_session.expire_all()

    group_q = db_session.get(Group, group.id)
    assert group_q.name == "Test Group"
    assert group_q.owner_account_id == owner.id

    group_admin_q = db_session.get(GroupAdmin, (group.id, admin.id))
    assert group_admin_q is not None
    assert group_admin_q.group_id == group.id
    assert group_admin_q.account_id == admin.id


def test_duplicate_account_email_raises_integrity_error(db_session):
    """Duplicate email constraint."""
    account1 = Account(email="test@example.com", password_hash="hash1", display_name="User 1")
    db_session.add(account1)
    db_session.commit()

    with pytest.raises(IntegrityError):
        account2 = Account(email="test@example.com", password_hash="hash2", display_name="User 2")
        db_session.add(account2)
        db_session.commit()
    db_session.rollback()


def test_delete_referenced_account_raises_integrity_error(db_session):
    """No cascade deletes: an account referenced by a group cannot be deleted."""
    account = Account(email="owner@example.com", password_hash="hash", display_name="Owner")
    db_session.add(account)
    db_session.flush()
    db_session.add(Group(name="Test Group", owner_account_id=account.id))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.delete(account)
        db_session.commit()
    db_session.rollback()


def test_collection_round_trip(db_session):
    account = Account(email="owner@example.com", password_hash="hash", display_name="Owner")
    db_session.add(account)
    db_session.flush()

    group = Group(name="Test Group", owner_account_id=account.id)
    db_session.add(group)
    db_session.flush()

    collection = Collection(group_id=group.id, kind="meal", name="Meal Planner")
    db_session.add(collection)
    db_session.commit()

    db_session.expire_all()

    collection_q = db_session.get(Collection, collection.id)
    assert collection_q.group_id == group.id
    assert collection_q.kind == "meal"
    assert collection_q.name == "Meal Planner"


def test_category_unique_constraint_per_collection(db_session):
    """Categories with the same name can exist in different collections."""
    account = Account(email="owner@example.com", password_hash="hash", display_name="Owner")
    db_session.add(account)
    db_session.flush()

    group = Group(name="Test Group", owner_account_id=account.id)
    db_session.add(group)
    db_session.flush()

    collection1 = Collection(group_id=group.id, kind="meal", name="Collection 1")
    collection2 = Collection(group_id=group.id, kind="meal", name="Collection 2")
    db_session.add_all([collection1, collection2])
    db_session.flush()

    # Same category name in different collections should succeed.
    cat1 = Category(collection_id=collection1.id, name="Pasta")
    cat2 = Category(collection_id=collection2.id, name="Pasta")
    db_session.add_all([cat1, cat2])
    db_session.commit()

    # But duplicate within the same collection should fail.
    with pytest.raises(IntegrityError):
        cat3 = Category(collection_id=collection1.id, name="Pasta")
        db_session.add(cat3)
        db_session.commit()
    db_session.rollback()


def test_tag_unique_constraint_per_group(db_session):
    """Tags with the same name can exist in different groups."""
    account1 = Account(email="owner1@example.com", password_hash="hash1", display_name="Owner 1")
    account2 = Account(email="owner2@example.com", password_hash="hash2", display_name="Owner 2")
    db_session.add_all([account1, account2])
    db_session.flush()

    group1 = Group(name="Group 1", owner_account_id=account1.id)
    group2 = Group(name="Group 2", owner_account_id=account2.id)
    db_session.add_all([group1, group2])
    db_session.flush()

    # Same tag name in different groups should succeed.
    tag1 = Tag(group_id=group1.id, name="takeout")
    tag2 = Tag(group_id=group2.id, name="takeout")
    db_session.add_all([tag1, tag2])
    db_session.commit()

    # But duplicate within the same group should fail.
    with pytest.raises(IntegrityError):
        tag3 = Tag(group_id=group1.id, name="takeout")
        db_session.add(tag3)
        db_session.commit()
    db_session.rollback()


def test_item_and_meal_detail_round_trip(db_session):
    """Item and MealDetail are 1:1; both persist and reload correctly."""
    account = Account(email="owner@example.com", password_hash="hash", display_name="Owner")
    db_session.add(account)
    db_session.flush()

    group = Group(name="Test Group", owner_account_id=account.id)
    db_session.add(group)
    db_session.flush()

    collection = Collection(group_id=group.id, kind="meal", name="Meal Planner")
    db_session.add(collection)
    db_session.flush()

    item = Item(
        collection_id=collection.id,
        name="Pasta Carbonara",
        normalized_name="pasta carbonara",
        description="Classic Italian pasta",
        is_active=True,
    )
    db_session.add(item)
    db_session.flush()

    detail = MealDetail(
        item_id=item.id,
        type="dinner",
        ingredients="Pasta\nEggs\nBacon",
        recipe_text="Cook pasta. Mix eggs and bacon.",
        source_url="https://example.com/carbonara",
    )
    db_session.add(detail)
    db_session.commit()

    db_session.expire_all()

    item_q = db_session.get(Item, item.id)
    assert item_q.name == "Pasta Carbonara"
    assert item_q.times_kept == 0

    detail_q = db_session.get(MealDetail, item.id)
    assert detail_q.type == "dinner"
    assert detail_q.ingredients == "Pasta\nEggs\nBacon"
    assert detail_q.source_url == "https://example.com/carbonara"


def test_item_tag_linkage(db_session):
    """ItemTag links items to group-scoped tags."""
    account = Account(email="owner@example.com", password_hash="hash", display_name="Owner")
    db_session.add(account)
    db_session.flush()

    group = Group(name="Test Group", owner_account_id=account.id)
    db_session.add(group)
    db_session.flush()

    collection = Collection(group_id=group.id, kind="meal", name="Meal Planner")
    db_session.add(collection)
    db_session.flush()

    tag1 = Tag(group_id=group.id, name="takeout")
    tag2 = Tag(group_id=group.id, name="spicy")
    db_session.add_all([tag1, tag2])
    db_session.flush()

    item = Item(
        collection_id=collection.id,
        name="Thai food",
        normalized_name="thai food",
        is_active=True,
    )
    db_session.add(item)
    db_session.flush()

    db_session.add_all([
        ItemTag(item_id=item.id, tag_id=tag1.id),
        ItemTag(item_id=item.id, tag_id=tag2.id),
    ])
    db_session.commit()

    db_session.expire_all()

    # Verify the tags are linked.
    tags = db_session.scalars(
        select(Tag).join(ItemTag).where(ItemTag.item_id == item.id)
    ).all()
    assert {t.name for t in tags} == {"takeout", "spicy"}


def test_invalid_meal_detail_type_rejected_by_check_constraint(tmp_path):
    """DB-level guard: an out-of-domain MealDetail.type violates the CHECK constraint.

    Raw sqlite3 on purpose — there is no SQLAlchemy app-layer validation yet,
    so the CHECK constraint is the guard.
    """
    db_path = str(tmp_path / "check.db")
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    conn = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO meal_detail (item_id, type)"
                " VALUES (1, 'breakfast')"
            )
    finally:
        conn.close()
