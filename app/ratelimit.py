"""In-memory sliding-window rate limiting for the join-by-code surface (M5b).

Session codes (WORD-####) are guessable, and ``GET /s/{code}`` /
``POST /s/{code}/join`` take an arbitrary attacker-supplied code — the one
cross-tenant guessing surface left on the shared deployment now that SSO
removed the password surface (plan §5.6, §8 M5). This module throttles those
two routes per client IP.

Why in-memory and dependency-free: the app runs single-process, single-worker
on SQLite (CLAUDE.md), so a ``dict`` of recent-hit timestamps is shared by
every request and there is no cross-worker consistency to coordinate. The
counters reset on restart — acceptable for a throttle (a guesser who can
restart the server to clear the counters is not a realistic attacker). No
Redis, no DB table.

The numbers: ``JOIN_LIMITER`` allows 20 code lookups per IP per 60s window —
generous for a real family passing a link around (each phone does one lookup
+ one join), punishing for a script cycling WORD-#### codes.

Trust boundary: ``client_ip`` prefers the LEFTMOST ``X-Forwarded-For`` entry
(the original client as the reverse proxy sees it). That header is only
trustworthy behind our own proxy — the deployment is VPS-hosted behind HTTPS
via Caddy (plan §7) — so the deployment MUST sit behind the proxy for this
limiter to be correct. It does; a client that can reach the app directly
could spoof the header, which is why this is documented rather than assumed.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

Clock = Callable[[], float]


class SlidingWindowLimiter:
    """Sliding-window hit counter per key, held in memory.

    ``hit`` records the timestamp, drops entries older than ``window_seconds``,
    and reports whether the key is now OVER ``max_hits`` — record-then-check,
    so the blocking hit itself is counted. Timestamps come from the injected
    ``clock`` (a zero-arg callable returning seconds; default
    ``time.monotonic``) so tests can drive time without sleeping.
    """

    def __init__(self, max_hits: int, window_seconds: float, clock: Clock = time.monotonic):
        self.max_hits = max_hits
        self.window_seconds = window_seconds
        self._clock = clock
        # key → timestamps of recent hits, oldest at the left. Appends are
        # monotonic in the clock, so pruning from the left keeps each deque
        # sorted.
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        """Record a hit for ``key``; True when the key is now OVER the limit."""
        now = self._clock()
        window = self._hits.setdefault(key, deque())
        window.append(now)
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(self._hits) > 256:
            # Amortized full sweep: a one-hit-wonder key must not live forever
            # (bounded memory). The just-appended timestamp is never stale, so
            # the current key survives its own sweep.
            self._prune_all(now)
        return len(window) > self.max_hits

    def _prune_all(self, now: float) -> None:
        """Drop stale timestamps for every key and delete keys whose window
        emptied. ``hit`` only prunes its own key, so this is the opportunistic
        housekeeping that keeps the dict from growing unbounded."""
        cutoff = now - self.window_seconds
        for key in list(self._hits):
            window = self._hits[key]
            while window and window[0] < cutoff:
                window.popleft()
            if not window:
                del self._hits[key]


# The join-by-code throttle: 20 code lookups per IP per 60s. See the module
# docstring for the threat model, the trust boundary, and why in-memory is
# sufficient on this single-process deployment.
JOIN_LIMITER = SlidingWindowLimiter(max_hits=20, window_seconds=60)


def client_ip(request: Request) -> str:
    """Best-effort client IP for rate-limit keys.

    Leftmost ``X-Forwarded-For`` entry when present (the original client as
    our reverse proxy sees it), else the direct peer. Only correct behind the
    proxy — see the module docstring's trust boundary.
    """
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"
