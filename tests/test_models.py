"""Model round-trip + integrity constraints for every table in PLAN-v2-samepage.md §5."""

import sqlite3

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models import (
    Account,
    AuthIdentity,
    Batch,
    BatchItem,
    BatchResponse,
    Category,
    Collection,
    Group,
    GroupAdmin,
    Item,
    ItemTag,
    MealDetail,
    Session,
    SessionParticipant,
    SessionTarget,
    Tag,
)


def test_account_round_trip(db_session):
    account = Account(
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(account)
    db_session.commit()

    # Prove persistence by expiring and re-reading from the database.
    db_session.expire_all()

    account_q = db_session.get(Account, account.id)
    assert account_q.email == "test@example.com"
    assert account_q.display_name == "Test User"


def test_group_and_admin_round_trip(db_session):
    owner = Account(email="owner@example.com", display_name="Owner")
    admin = Account(email="admin@example.com", display_name="Admin")
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
    account1 = Account(email="test@example.com", display_name="User 1")
    db_session.add(account1)
    db_session.commit()

    with pytest.raises(IntegrityError):
        account2 = Account(email="test@example.com", display_name="User 2")
        db_session.add(account2)
        db_session.commit()
    db_session.rollback()


def test_delete_referenced_account_raises_integrity_error(db_session):
    """No cascade deletes: an account referenced by a group cannot be deleted."""
    account = Account(email="owner@example.com", display_name="Owner")
    db_session.add(account)
    db_session.flush()
    db_session.add(Group(name="Test Group", owner_account_id=account.id))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.delete(account)
        db_session.commit()
    db_session.rollback()


def test_collection_round_trip(db_session):
    account = Account(email="owner@example.com", display_name="Owner")
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
    account = Account(email="owner@example.com", display_name="Owner")
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
    account1 = Account(email="owner1@example.com", display_name="Owner 1")
    account2 = Account(email="owner2@example.com", display_name="Owner 2")
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
    account = Account(email="owner@example.com", display_name="Owner")
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
    account = Account(email="owner@example.com", display_name="Owner")
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


def test_auth_identity_round_trip(db_session):
    """AuthIdentity persists provider/subject/email against its account."""
    account = Account(email="sso@example.com", display_name="SSO User")
    db_session.add(account)
    db_session.commit()

    identity = AuthIdentity(
        account_id=account.id, provider="google", subject="sub-1", email="sso@example.com"
    )
    db_session.add(identity)
    db_session.commit()

    db_session.expire_all()
    identity_q = db_session.get(AuthIdentity, identity.id)
    assert identity_q.account_id == account.id
    assert identity_q.provider == "google"
    assert identity_q.subject == "sub-1"
    assert identity_q.email == "sso@example.com"


def test_auth_identity_unique_provider_subject(db_session):
    """Schema-level guard (test #9): the same (provider, subject) can only
    ever map to one account — a duplicate insert raises IntegrityError."""
    account = Account(email="sso@example.com", display_name="SSO User")
    db_session.add(account)
    db_session.commit()

    db_session.add(
        AuthIdentity(account_id=account.id, provider="google", subject="sub-dup", email="sso@example.com")
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(AuthIdentity(account_id=account.id, provider="google", subject="sub-dup"))
        db_session.commit()
    db_session.rollback()


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


# ---------------------------------------------------------------------------
# Voting-engine tables (M3a, plan §5): session/batch chain + constraints
# ---------------------------------------------------------------------------

def _seed_session_chain(db_session):
    """Account → group → collection → item → session → batch, committed."""
    account = Account(email="host@example.com", display_name="Host")
    db_session.add(account)
    db_session.flush()

    group = Group(name="Test Group", owner_account_id=account.id)
    db_session.add(group)
    db_session.flush()

    collection = Collection(group_id=group.id, kind="meal", name="Meal Planner")
    db_session.add(collection)
    db_session.flush()

    item = Item(collection_id=collection.id, name="Pasta", normalized_name="pasta")
    db_session.add(item)
    db_session.flush()

    session = Session(code="ABCDEF", status="lobby", group_id=group.id, host_account_id=account.id)
    db_session.add(session)
    db_session.flush()

    batch = Batch(session_id=session.id, seq=1, track_label="dinner")
    db_session.add(batch)
    db_session.commit()
    return {
        "account": account,
        "group": group,
        "collection": collection,
        "item": item,
        "session": session,
        "batch": batch,
    }


def test_session_batch_chain_round_trip(db_session):
    """The full M3a chain persists and reloads: Session → SessionTarget →
    SessionParticipant → Batch → BatchItem (item + ad hoc) → BatchResponse."""
    chain = _seed_session_chain(db_session)
    session = chain["session"]
    batch = chain["batch"]

    target = SessionTarget(session_id=session.id, track_label="dinner", target_count=3)
    participant = SessionParticipant(session_id=session.id, display_name="Sam")
    db_session.add_all([target, participant])
    db_session.flush()

    item_option = BatchItem(batch_id=batch.id, item_id=chain["item"].id, sort_order=0)
    adhoc_option = BatchItem(batch_id=batch.id, ad_hoc_label="Pizza place", sort_order=1)
    db_session.add_all([item_option, adhoc_option])
    db_session.flush()

    response = BatchResponse(
        batch_item_id=item_option.id,
        session_participant_id=participant.id,
        choice="yes",
    )
    db_session.add(response)
    db_session.commit()

    db_session.expire_all()

    session_q = db_session.get(Session, session.id)
    assert session_q.code == "ABCDEF"
    assert session_q.status == "lobby"
    assert session_q.group_id == chain["group"].id
    assert session_q.host_account_id == chain["account"].id
    assert session_q.finished_at is None

    target_q = db_session.get(SessionTarget, target.id)
    assert target_q.track_label == "dinner"
    assert target_q.target_count == 3

    participant_q = db_session.get(SessionParticipant, participant.id)
    assert participant_q.display_name == "Sam"

    batch_q = db_session.get(Batch, batch.id)
    assert batch_q.seq == 1
    assert batch_q.status == "open"  # default

    item_option_q = db_session.get(BatchItem, item_option.id)
    assert item_option_q.item_id == chain["item"].id
    assert item_option_q.ad_hoc_label is None
    assert item_option_q.yes_count == 0
    assert item_option_q.outcome is None

    adhoc_option_q = db_session.get(BatchItem, adhoc_option.id)
    assert adhoc_option_q.ad_hoc_label == "Pizza place"
    assert adhoc_option_q.item_id is None

    response_q = db_session.get(BatchResponse, response.id)
    assert response_q.choice == "yes"
    assert response_q.batch_item_id == item_option.id


def test_batch_item_check_rejects_both_null(db_session):
    """CHECK ck_batch_item_one_of: exactly one of item_id / ad_hoc_label."""
    chain = _seed_session_chain(db_session)
    with pytest.raises(IntegrityError):
        db_session.add(BatchItem(batch_id=chain["batch"].id, item_id=None, ad_hoc_label=None))
        db_session.commit()
    db_session.rollback()


def test_batch_item_check_rejects_both_set(db_session):
    """CHECK ck_batch_item_one_of: both item_id and ad_hoc_label is invalid."""
    chain = _seed_session_chain(db_session)
    with pytest.raises(IntegrityError):
        db_session.add(
            BatchItem(batch_id=chain["batch"].id, item_id=chain["item"].id, ad_hoc_label="Also a label")
        )
        db_session.commit()
    db_session.rollback()


def test_batch_item_partial_unique_index_rejects_duplicate_item(db_session):
    """uq_batch_item_item: the same item appears at most once per batch."""
    chain = _seed_session_chain(db_session)
    db_session.add(BatchItem(batch_id=chain["batch"].id, item_id=chain["item"].id, sort_order=0))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(BatchItem(batch_id=chain["batch"].id, item_id=chain["item"].id, sort_order=1))
        db_session.commit()
    db_session.rollback()


def test_batch_item_partial_unique_index_rejects_duplicate_adhoc_label(db_session):
    """uq_batch_item_adhoc: the same ad hoc label appears at most once per batch."""
    chain = _seed_session_chain(db_session)
    db_session.add(BatchItem(batch_id=chain["batch"].id, ad_hoc_label="Pizza place"))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(BatchItem(batch_id=chain["batch"].id, ad_hoc_label="Pizza place"))
        db_session.commit()
    db_session.rollback()
