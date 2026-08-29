"""Group management routes (M2a): create, list, detail, add admin, remove admin."""

from app.credentials import hash_password
from app.models import Account, Group, GroupAdmin


def _make_account(db_session, email="test@example.com", password="testpass123", display_name="Test User"):
    account = Account(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db_session.add(account)
    db_session.commit()
    return account


def _make_group(db_session, name="Test Group", owner=None):
    if owner is None:
        owner = _make_account(db_session)
    group = Group(name=name, owner_account_id=owner.id)
    db_session.add(group)
    db_session.commit()
    return group


def _login(post, email="test@example.com", password="testpass123"):
    post("/login", data={"email": email, "password": password})


def test_list_groups_requires_login(client, post):
    resp = client.get("/groups")
    assert resp.status_code == 401


def test_create_group_requires_login(client, post):
    resp = post("/groups", data={"name": "Test"})
    assert resp.status_code == 401


def test_create_group_sets_owner(client, post, db_session):
    account = _make_account(db_session, email="owner@example.com")
    _login(post, "owner@example.com")
    resp = post("/groups", data={"name": "My Group"}, follow_redirects=False)
    assert resp.status_code == 303
    group = db_session.query(Group).filter_by(name="My Group").first()
    assert group is not None
    assert group.owner_account_id == account.id


def test_list_groups_owned_and_admined(client, post, db_session):
    owner = _make_account(db_session, email="owner@example.com")
    admin = _make_account(db_session, email="admin@example.com")
    _make_group(db_session, "Owned Group", owner)
    group2 = _make_group(db_session, "Other Group")
    # Make admin an admin of group2.
    db_session.add(GroupAdmin(group_id=group2.id, account_id=admin.id))
    db_session.commit()

    # Login as owner.
    _login(post, "owner@example.com")
    resp = client.get("/groups")
    assert resp.status_code == 200
    assert "Owned Group" in resp.text
    assert "Owner" in resp.text  # role label

    # Login as admin.
    post("/logout", follow_redirects=False)
    _login(post, "admin@example.com")
    resp = client.get("/groups")
    assert resp.status_code == 200
    assert "Other Group" in resp.text
    assert "Admin" in resp.text


def test_group_detail_requires_owner_or_admin(client, post, db_session):
    owner = _make_account(db_session, email="owner@example.com")
    _make_account(db_session, email="other@example.com")
    group = _make_group(db_session, "Owned Group", owner)

    # Non-owner cannot view.
    _login(post, "other@example.com")
    resp = client.get(f"/groups/{group.id}")
    assert resp.status_code == 403

    # Owner can view.
    post("/logout", follow_redirects=False)
    _login(post, "owner@example.com")
    resp = client.get(f"/groups/{group.id}")
    assert resp.status_code == 200
    assert "Owned Group" in resp.text


def test_group_detail_404_missing(client, post, db_session):
    _make_account(db_session)
    _login(post)
    resp = client.get("/groups/999999")
    assert resp.status_code == 404


def test_add_admin_owner_only(client, post, db_session):
    owner = _make_account(db_session, email="owner@example.com")
    admin = _make_account(db_session, email="admin@example.com")
    other = _make_account(db_session, email="other@example.com")
    group = _make_group(db_session, "Owned Group", owner)
    # Make admin an admin of the group.
    db_session.add(GroupAdmin(group_id=group.id, account_id=admin.id))
    db_session.commit()

    # Admin cannot add another admin (403).
    _login(post, "admin@example.com")
    resp = post(f"/groups/{group.id}/admins", data={"email": "other@example.com"})
    assert resp.status_code == 403

    # Owner can add admin.
    post("/logout", follow_redirects=False)
    _login(post, "owner@example.com")
    resp = post(f"/groups/{group.id}/admins", data={"email": "other@example.com"}, follow_redirects=False)
    assert resp.status_code == 303
    # Verify the admin was added.
    admin_row = db_session.query(GroupAdmin).filter_by(group_id=group.id, account_id=other.id).first()
    assert admin_row is not None


def test_add_admin_nonexistent_email_400(client, post, db_session):
    account = _make_account(db_session, email="owner@example.com")
    group = _make_group(db_session, owner=account)
    _login(post, "owner@example.com")
    resp = post(f"/groups/{group.id}/admins", data={"email": "nonexistent@example.com"})
    assert resp.status_code == 400
    assert "No account with that email exists" in resp.text


def test_add_admin_already_owner_400(client, post, db_session):
    owner = _make_account(db_session, email="owner@example.com")
    group = _make_group(db_session, owner=owner)
    _login(post, "owner@example.com")
    resp = post(f"/groups/{group.id}/admins", data={"email": "owner@example.com"})
    assert resp.status_code == 400
    assert "already the owner" in resp.text


def test_add_admin_already_admin_400(client, post, db_session):
    owner = _make_account(db_session, email="owner@example.com")
    admin = _make_account(db_session, email="admin@example.com")
    group = _make_group(db_session, owner=owner)
    db_session.add(GroupAdmin(group_id=group.id, account_id=admin.id))
    db_session.commit()
    _login(post, "owner@example.com")
    resp = post(f"/groups/{group.id}/admins", data={"email": "admin@example.com"})
    assert resp.status_code == 400
    assert "already an admin" in resp.text


def test_remove_admin_owner_only(client, post, db_session):
    owner = _make_account(db_session, email="owner@example.com")
    admin = _make_account(db_session, email="admin@example.com")
    other_admin = _make_account(db_session, email="other_admin@example.com")
    group = _make_group(db_session, owner=owner)
    db_session.add(GroupAdmin(group_id=group.id, account_id=admin.id))
    db_session.add(GroupAdmin(group_id=group.id, account_id=other_admin.id))
    db_session.commit()

    # Admin cannot remove another admin (403).
    _login(post, "admin@example.com")
    resp = post(f"/groups/{group.id}/admins/{other_admin.id}/remove")
    assert resp.status_code == 403

    # Owner can remove admin.
    post("/logout", follow_redirects=False)
    _login(post, "owner@example.com")
    resp = post(f"/groups/{group.id}/admins/{admin.id}/remove", follow_redirects=False)
    assert resp.status_code == 303
    # Verify the admin was removed.
    admin_row = db_session.query(GroupAdmin).filter_by(group_id=group.id, account_id=admin.id).first()
    assert admin_row is None


def test_remove_admin_idempotent(client, post, db_session):
    owner = _make_account(db_session, email="owner@example.com")
    admin = _make_account(db_session, email="admin@example.com")
    group = _make_group(db_session, owner=owner)
    db_session.add(GroupAdmin(group_id=group.id, account_id=admin.id))
    db_session.commit()
    _login(post, "owner@example.com")
    # First remove.
    resp = post(f"/groups/{group.id}/admins/{admin.id}/remove", follow_redirects=False)
    assert resp.status_code == 303
    # Second remove (no error).
    resp = post(f"/groups/{group.id}/admins/{admin.id}/remove", follow_redirects=False)
    assert resp.status_code == 303
