"""Pure voting-rule logic for SamePage sessions (M3a) — no DB, no models.

This module implements the consensus rules from PLAN-v2-samepage.md §5.5/§5.6
as pure functions over plain values (ints, lists, sets, dataclasses, enums).
It deliberately imports nothing from ``app.db`` or ``app.models``: the
caller (future M3 routes) owns all persistence and passes plain data in.

Design notes:
- ``BATCH_SIZE`` caps how many options a batch assembles.
- ``classify()`` returns plain strings. The stored outcomes are the three
  ``Outcome`` enum values; ``'majority'`` is a TRANSIENT classification
  meaning "non-unanimous, yes > no — offer to the host", which the host
  turns into ``Outcome.KEPT_HOST`` (or lets it fall to ``NOT_KEPT``) at
  batch results. ``'majority'`` is never written to ``batch_item.outcome``.
- Transitions follow CLAUDE.md #7 (idempotency): re-applying the state
  you are already in is a no-op, never an error.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

BATCH_SIZE = 15


def assemble_batch(eligible_ids: list[int], already_offered: set[int], size: int = BATCH_SIZE) -> list[int]:
    """Return the first ``size`` ids from ``eligible_ids`` not yet offered.

    The caller pre-orders the pool (e.g. least-recently-kept first), and
    that order is preserved. Returns fewer than ``size`` ids when the pool
    is exhausted, and ``[]`` when nothing eligible remains. Never mutates
    its inputs. ``size`` must be positive.
    """
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    return [item_id for item_id in eligible_ids if item_id not in already_offered][:size]


@dataclass(frozen=True)
class Tally:
    """Aggregate yes/no counts for one batch item."""

    yes: int
    no: int


def tally_responses(choices: list[str]) -> Tally:
    """Count 'yes'/'no' choices. Anything else is ignored defensively."""
    yes = sum(1 for choice in choices if choice == "yes")
    no = sum(1 for choice in choices if choice == "no")
    return Tally(yes=yes, no=no)


def is_unanimous(tally: Tally, roster_size: int) -> bool:
    """True iff every roster member voted yes.

    Unanimity is measured against the frozen roster at batch start: a
    missing vote is not a yes, so ``tally.yes`` must equal ``roster_size``
    exactly. A roster of 0 is never unanimous.
    """
    return roster_size > 0 and tally.yes == roster_size


def is_majority(tally: Tally) -> bool:
    """True iff yes > no (strict; ties excluded)."""
    return tally.yes > tally.no


class Outcome(str, Enum):
    """Durable ``batch_item.outcome`` values (plan §5)."""

    KEPT_UNANIMOUS = "kept_unanimous"
    KEPT_HOST = "kept_host"
    NOT_KEPT = "not_kept"


def classify(tally: Tally, roster_size: int) -> str:
    """Classify a closed batch item's tally.

    Returns plain strings:
    - ``'kept_unanimous'`` — full frozen roster voted yes (auto-kept);
    - ``'majority'`` — non-unanimous but yes > no: a TRANSIENT result
      meaning "offer to host". Never stored; the host's accept/reject
      writes ``Outcome.KEPT_HOST`` or ``Outcome.NOT_KEPT``;
    - ``'not_kept'`` — tie or majority-no.
    """
    if is_unanimous(tally, roster_size):
        return Outcome.KEPT_UNANIMOUS.value
    if is_majority(tally):
        return "majority"
    return Outcome.NOT_KEPT.value


def resolve_missing_as_no(roster_size: int, yes_responses: int) -> Tally:
    """Manual close (D5): missing votes count as no.

    Given how many roster members voted yes, synthesize the no count as
    ``roster_size - yes_responses``. (Auto-close uses the real recorded
    no's via ``tally_responses``; manual close invents no's for
    non-voters.)

    Raises ValueError if ``yes_responses`` exceeds ``roster_size`` or is
    negative — a yes count outside ``[0, roster_size]`` is corrupted input
    (stale roster, double-count), and a negative synthesized no would
    silently corrupt the durable outcome record (§5.4).
    """
    if not 0 <= yes_responses <= roster_size:
        raise ValueError(
            f"yes_responses {yes_responses} out of range for roster_size {roster_size}"
        )
    return Tally(yes=yes_responses, no=roster_size - yes_responses)


def over_target_selection(candidate_ids: list[int], remaining_target: int) -> tuple[list[int], list[int]]:
    """D13 over-target: pick which keeps stay when a batch agrees on more
    keeps than slots remain.

    - ``remaining_target <= 0``: nothing auto-kept, everything deferred;
    - all candidates fit: all kept, nothing deferred;
    - otherwise the first ``remaining_target`` are kept and the excess is
      deferred — the caller (host) has pre-ordered candidates by
      preference. Pure slicing; deterministic; no input mutation.
    """
    if remaining_target <= 0:
        return [], list(candidate_ids)
    if len(candidate_ids) <= remaining_target:
        return list(candidate_ids), []
    return candidate_ids[:remaining_target], candidate_ids[remaining_target:]


def next_seq(existing_seqs: list[int]) -> int:
    """Next batch sequence number: max(existing, default=0) + 1.

    Monotonic, not gapless — the ``UNIQUE(session_id, seq)`` constraint is
    what matters.
    """
    return max(existing_seqs, default=0) + 1


# --- Session/batch state transitions (idempotency helpers) -----------------

SESSION_TRANSITIONS = {
    "lobby": {"voting", "expired"},
    "voting": {"complete", "expired"},
    "complete": set(),
    "expired": set(),
}


def can_transition(current: str, target: str) -> bool:
    """True iff ``current -> target`` is a legal session transition."""
    if current not in SESSION_TRANSITIONS:
        raise ValueError(f"unknown session status: {current!r}")
    return target in SESSION_TRANSITIONS[current]


def apply_transition(current: str, target: str) -> str:
    """Apply a session status transition, idempotently.

    Returns ``target`` on a legal transition; returns ``current`` unchanged
    when ``current == target`` (double-submitted start/end is a no-op, not
    an error); raises ValueError for any other illegal transition.
    """
    if can_transition(current, target):
        return target
    if current == target:
        return current
    raise ValueError(f"illegal transition {current}->{target}")


BATCH_TRANSITIONS = {
    "open": {"closed"},
    "closed": set(),
}


def can_close_batch(status: str) -> bool:
    """True iff the batch is open and can be closed."""
    return status == "open"


def apply_batch_close(status: str) -> str:
    """Close a batch, idempotently.

    Returns ``'closed'`` from ``'open'``; returns ``'closed'`` unchanged
    when already ``'closed'`` (double-submit close applies once); raises
    ValueError for any other status.
    """
    if status == "open" or status == "closed":
        return "closed"
    raise ValueError(f"illegal batch close from status {status!r}")


# --- Session code generation (M3b) ------------------------------------------

WORDLIST: tuple[str, ...] = (
    "amber",
    "basil",
    "cedar",
    "cobalt",
    "coral",
    "daisy",
    "ember",
    "fern",
    "ginger",
    "harbor",
    "indigo",
    "ivory",
    "jade",
    "lemon",
    "lilac",
    "maple",
    "mango",
    "meadow",
    "olive",
    "onyx",
    "opal",
    "pepper",
    "plum",
    "poppy",
    "quartz",
    "raven",
    "rowan",
    "sable",
    "sage",
    "teal",
    "umber",
    "willow",
)


def make_code(existing: set[str], rand: random.Random) -> str:
    """Generate a unique ``word-nnnn`` session code, with collision retry.

    ``rand`` is a ``random.Random`` instance passed IN — this function never
    touches the global random module, so callers/tests control the seed. Codes
    are permanent and unique forever (never recycled): the caller persists the
    code against the UNIQUE ``session.code`` column, and ``existing`` is the
    set of codes already in use. Retries up to 100 times; raises RuntimeError
    when the code space is exhausted.
    """
    for _ in range(100):
        code = f"{rand.choice(WORDLIST)}-{rand.randint(0, 9999):04d}"
        if code not in existing:
            return code
    raise RuntimeError("could not generate a unique session code")
