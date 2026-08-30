"""Sliding-window limiter unit tests (M5b): injected clock, no sleeping.

The limiter is pure in-memory state keyed by string, so every behavior is
testable with a fake clock. ``client_ip`` is security-relevant header
plumbing, so its trust-boundary behavior is pinned here too.

Two integration regression tests live at the end (Slice B fix + the final
audit's share-screen carve-out): a session member — and the share screen's
host — must never be join-rate-limited by their own session's traffic, while
a same-IP code guesser still 429s.
"""

from __future__ import annotations

import base64
import json
from collections import namedtuple

from conftest import stamp_session
from itsdangerous import TimestampSigner
from sqlalchemy import select

from app.models import (
    Account,
    Batch,
    BatchItem,
    Collection,
    Group,
    Item,
    MealDetail,
    MealType,
    SessionParticipant,
    SessionTarget,
)
from app.models import (
    Session as VotingSession,
)
from app.ratelimit import JOIN_LIMITER, SlidingWindowLimiter, client_ip
from app.routes.sessions import _SESSION_PARTICIPANT_COOKIE_KEY
from app.session_logic import BATCH_SIZE

Address = namedtuple("Address", ["host", "port"])


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_under_limit_returns_false():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_hits=3, window_seconds=60, clock=clock)
    assert limiter.hit("k") is False
    assert limiter.hit("k") is False
    assert limiter.hit("k") is False  # exactly max_hits → still allowed


def test_max_hits_plus_one_is_blocked():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_hits=3, window_seconds=60, clock=clock)
    for _ in range(3):
        assert limiter.hit("k") is False
    assert limiter.hit("k") is True  # the (max_hits+1)th hit in the window


def test_window_advance_allows_again():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_hits=3, window_seconds=60, clock=clock)
    for _ in range(4):
        limiter.hit("k")
    assert limiter.hit("k") is True  # over the limit
    clock.advance(61)  # past the window → the old hits fall out
    assert limiter.hit("k") is False


def test_different_keys_are_independent():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_hits=3, window_seconds=60, clock=clock)
    for _ in range(4):
        limiter.hit("a")
    assert limiter.hit("a") is True
    assert limiter.hit("b") is False  # untouched key, fresh window
    assert limiter.hit("b") is False
    assert limiter.hit("b") is False


def test_empty_window_pruned_from_dict():
    """A key whose window empties after pruning is deleted — no unbounded
    retention of one-hit-wonder keys."""
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_hits=3, window_seconds=60, clock=clock)
    limiter.hit("k")
    limiter.hit("other")
    assert "k" in limiter._hits
    limiter._prune_all(clock.now + 61)  # both hits are now stale
    assert "k" not in limiter._hits
    assert "other" not in limiter._hits


def test_prune_all_keeps_active_keys():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_hits=3, window_seconds=60, clock=clock)
    limiter.hit("stale")  # t=1000
    clock.advance(61)  # past the 60s window, so "stale" is now actually stale
    limiter.hit("active")  # t=1061, fresh
    limiter._prune_all(clock.now)
    assert "stale" not in limiter._hits
    assert "active" in limiter._hits
    assert list(limiter._hits["active"]) == [1061.0]


def test_join_limiter_numbers():
    """The documented join-surface throttle: 20 code lookups per IP per 60s."""
    assert JOIN_LIMITER.max_hits == 20
    assert JOIN_LIMITER.window_seconds == 60


class FakeRequest:
    def __init__(self, headers=None, client=None):
        self.headers = headers or {}
        self.client = client


def test_client_ip_uses_leftmost_xff():
    req = FakeRequest(
        headers={"x-forwarded-for": "203.0.113.9, 10.0.0.2"}, client=Address("10.0.0.2", 1234)
    )
    assert client_ip(req) == "203.0.113.9"


def test_client_ip_falls_back_to_direct_peer():
    req = FakeRequest(headers={}, client=Address("10.0.0.2", 1234))
    assert client_ip(req) == "10.0.0.2"


def test_client_ip_unknown_without_client():
    req = FakeRequest(headers={}, client=None)
    assert client_ip(req) == "unknown"


# ---------------------------------------------------------------------------
# Integration: membership exemption on the REAL limiter (Slice B fix)
# ---------------------------------------------------------------------------


def _stamp_participant(client, participant_id: int, code: str) -> None:
    """Point the client's signed session cookie at a participant row in the
    per-session map (HOTFIX4 shape: {code: participant_id}) — the flat
    participant_id shape no longer resolves (HOTFIX4b). Clears the jar first —
    a real browser holds ONE session cookie, but the test client accumulates a
    second 'session' entry (server-set + manually-set) that httpx then can't
    disambiguate, so the switch silently wouldn't reach the server."""
    client.cookies.clear()
    payload = base64.b64encode(
        json.dumps({_SESSION_PARTICIPANT_COOKIE_KEY: {code: participant_id}}).encode()
    )
    client.cookies.set(
        "session", TimestampSigner("test-secret-for-tests").sign(payload).decode()
    )


def _collection_session(db_session, item_count: int = BATCH_SIZE):
    """A lobby session backed by a collection with ``item_count`` dinner items
    (every one with recipe_text, so the voting card links each one), its host
    account, and one guest participant — all built directly (no HTTP) so the
    test controls who the client is at each step."""
    host = Account(email="host@example.com", display_name="Host")
    db_session.add(host)
    db_session.flush()
    group = Group(name="Test Group", owner_account_id=host.id)
    db_session.add(group)
    db_session.flush()
    collection = Collection(group_id=group.id, kind="meal", name="Meal Planner")
    db_session.add(collection)
    db_session.flush()
    for i in range(item_count):
        item = Item(
            collection_id=collection.id,
            name=f"Meal {i:02d}",
            normalized_name=f"meal {i:02d}",
        )
        db_session.add(item)
        db_session.flush()
        db_session.add(MealType(item_id=item.id, meal_type="dinner"))
        db_session.add(MealDetail(item_id=item.id, recipe_text=f"Method {i:02d}."))
    session = VotingSession(
        code="rate-limit-15",
        status="lobby",
        group_id=group.id,
        host_account_id=host.id,
        collection_id=collection.id,
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        SessionTarget(session_id=session.id, track_label="dinner", target_count=1)
    )
    guest = SessionParticipant(session_id=session.id, account_id=None, display_name="Guest")
    db_session.add(guest)
    db_session.commit()
    return session, host, guest


def test_session_member_exempt_while_guessing_still_limited(client, post, db_session):
    """Slice B fix, regression with the REAL limiter (no mid-test clear): a
    participant looping a 15-option batch — card → recipe → vote, 45 requests
    in one window — is never 429, while >20 GETs of unknown codes from the
    same IP still hits 429. Both halves run in ONE test so the member traffic
    and the guessing share the same window (the autouse clearing fixture can't
    reset the limiter between them)."""
    session, host, guest = _collection_session(db_session, item_count=BATCH_SIZE)
    stamp_session(client, host)
    resp = post(f"/s/{session.code}/start", follow_redirects=False)
    assert resp.status_code == 303

    # The guest participant loops all 15 options: card → recipe → vote.
    _stamp_participant(client, guest.id, session.code)
    batch = db_session.scalar(
        select(Batch).where((Batch.session_id == session.id) & (Batch.status == "open"))
    )
    assert batch is not None
    batch_items = list(
        db_session.scalars(
            select(BatchItem)
            .where(BatchItem.batch_id == batch.id)
            .order_by(BatchItem.sort_order, BatchItem.id)
        ).all()
    )
    assert len(batch_items) == BATCH_SIZE == 15
    for index, batch_item in enumerate(batch_items):
        card = client.get(f"/s/{session.code}")
        assert card.status_code == 200, card.status_code
        assert f"{index + 1} / {BATCH_SIZE}" in card.text
        # The card links this option's recipe (every item has recipe_text).
        assert f'href="/s/{session.code}/recipe/{batch_item.item_id}"' in card.text
        recipe = client.get(f"/s/{session.code}/recipe/{batch_item.item_id}")
        assert recipe.status_code == 200, recipe.status_code
        voted = post(
            f"/s/{session.code}/vote",
            data={"batch_item_id": str(batch_item.id), "choice": "yes"},
            follow_redirects=False,
        )
        assert voted.status_code == 303, voted.status_code

    # The member's 45 hits never touched the limiter — the bucket is empty,
    # so the same IP's code guessing is still throttled from scratch: 20
    # unknown-code GETs 404 (each burning a hit), the 21st 429.
    statuses = [client.get(f"/s/wrong-code-{i}").status_code for i in range(21)]
    assert statuses[:20] == [404] * 20
    assert statuses[20] == 429


def test_share_page_host_exempt_while_guessing_still_limited(client, db_session):
    """Final audit fix: /s/{code}/share draws from the SAME shared
    JOIN_LIMITER bucket and is host-only — every legitimate call IS the host,
    yet the route used to enforce the limiter unconditionally as its first
    line. A host reloading their own invite screen could burn the bucket and
    lock themselves out of it — the exact self-lockout the Slice B carve-out
    closes everywhere else. The share route now gets the same treatment: the
    host never pays, while a same-IP code guesser still 429s. Both halves run
    in ONE test so the host traffic and the guessing share the same window
    (the autouse clearing fixture can't reset the limiter between them)."""
    session, host, _guest = _collection_session(db_session)
    stamp_session(client, host)

    # 25 share-screen hits (> the 20/min limit) in one window — all 200: the
    # host's own /share traffic never touches the bucket.
    statuses = [client.get(f"/s/{session.code}/share").status_code for _ in range(25)]
    assert statuses == [200] * 25

    # The host's 25 hits left the bucket empty, so the same IP's code
    # guessing is still throttled from scratch: 20 unknown-code GETs 404
    # (each burning a hit), the 21st 429.
    statuses = [client.get(f"/s/wrong-code-{i}").status_code for i in range(21)]
    assert statuses[:20] == [404] * 20
    assert statuses[20] == 429
