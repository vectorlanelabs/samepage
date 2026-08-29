"""Sliding-window limiter unit tests (M5b): injected clock, no sleeping.

The limiter is pure in-memory state keyed by string, so every behavior is
testable with a fake clock. ``client_ip`` is security-relevant header
plumbing, so its trust-boundary behavior is pinned here too.
"""

from __future__ import annotations

from collections import namedtuple

from app.ratelimit import JOIN_LIMITER, SlidingWindowLimiter, client_ip

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
