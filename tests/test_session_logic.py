"""Pure voting-rule tests for app/session_logic (M3a).

Every function under test is pure (no I/O, no DB) per the slice spec —
these tests never touch a database.
"""

import pytest

from app.session_logic import (
    BATCH_SIZE,
    BATCH_TRANSITIONS,
    SESSION_TRANSITIONS,
    Outcome,
    Tally,
    apply_batch_close,
    apply_transition,
    assemble_batch,
    can_close_batch,
    can_transition,
    classify,
    is_majority,
    is_unanimous,
    next_seq,
    over_target_selection,
    resolve_missing_as_no,
    tally_responses,
)

# ---------------------------------------------------------------------------
# assemble_batch
# ---------------------------------------------------------------------------

def test_default_batch_size_is_15():
    assert BATCH_SIZE == 15


def test_assemble_batch_returns_first_size_ids():
    assert assemble_batch([1, 2, 3, 4, 5], set(), size=3) == [1, 2, 3]


def test_assemble_batch_dedups_against_already_offered():
    assert assemble_batch([1, 2, 3, 4, 5], {2, 4}) == [1, 3, 5]


def test_assemble_batch_fewer_than_size_when_pool_exhausted():
    assert assemble_batch([1, 2], set(), size=15) == [1, 2]


def test_assemble_batch_empty_pool_returns_empty():
    assert assemble_batch([], set()) == []


def test_assemble_batch_empty_already_offered_returns_first_size():
    ids = list(range(1, 21))
    result = assemble_batch(ids, set())
    assert result == list(range(1, 16))


def test_assemble_batch_preserves_caller_order():
    # Caller pre-orders the pool; the result must keep that order.
    assert assemble_batch([9, 2, 7, 1], {7}) == [9, 2, 1]


def test_assemble_batch_all_already_offered_returns_empty():
    assert assemble_batch([1, 2, 3], {1, 2, 3}) == []


def test_assemble_batch_size_zero_raises():
    # size=0 is a caller bug, not a valid empty request (Oscar M3a guard).
    with pytest.raises(ValueError):
        assemble_batch([1, 2, 3], set(), size=0)


def test_assemble_batch_does_not_mutate_inputs():
    eligible = [1, 2, 3, 4, 5]
    offered = {1, 3}
    eligible_before = list(eligible)
    offered_before = set(offered)
    assemble_batch(eligible, offered, size=2)
    assert eligible == eligible_before
    assert offered == offered_before


# ---------------------------------------------------------------------------
# tally_responses
# ---------------------------------------------------------------------------

def test_tally_responses_counts_yes_and_no():
    assert tally_responses(["yes", "no", "yes", "yes", "no"]) == Tally(yes=3, no=2)


def test_tally_responses_empty_list():
    assert tally_responses([]) == Tally(yes=0, no=0)


def test_tally_responses_ignores_unknown_values_defensively():
    assert tally_responses(["yes", "abstain", None, "no", "yes"]) == Tally(yes=2, no=1)


def test_tally_responses_all_yes():
    assert tally_responses(["yes", "yes"]) == Tally(yes=2, no=0)


def test_tally_responses_all_no():
    assert tally_responses(["no", "no"]) == Tally(yes=0, no=2)


# ---------------------------------------------------------------------------
# is_unanimous
# ---------------------------------------------------------------------------

def test_is_unanimous_full_roster_yes():
    assert is_unanimous(Tally(yes=3, no=0), roster_size=3) is True


def test_is_unanimous_one_missing_vote_is_false():
    # A missing vote is not a yes — unanimity needs every roster member.
    assert is_unanimous(Tally(yes=2, no=0), roster_size=3) is False


def test_is_unanimous_roster_zero_never_unanimous():
    assert is_unanimous(Tally(yes=0, no=0), roster_size=0) is False


def test_is_unanimous_more_yes_than_roster_is_false():
    # Impossible in practice; the roster_size guard must still hold.
    assert is_unanimous(Tally(yes=5, no=0), roster_size=3) is False


def test_is_unanimous_roster_one_single_yes():
    assert is_unanimous(Tally(yes=1, no=0), roster_size=1) is True


def test_is_unanimous_any_no_is_false():
    assert is_unanimous(Tally(yes=3, no=1), roster_size=4) is False


# ---------------------------------------------------------------------------
# is_majority
# ---------------------------------------------------------------------------

def test_is_majority_yes_greater_than_no():
    assert is_majority(Tally(yes=2, no=1)) is True


def test_is_majority_tie_is_false():
    assert is_majority(Tally(yes=1, no=1)) is False


def test_is_majority_all_no_is_false():
    assert is_majority(Tally(yes=0, no=3)) is False


def test_is_majority_zero_zero_is_false():
    assert is_majority(Tally(yes=0, no=0)) is False


def test_is_majority_large_yes():
    assert is_majority(Tally(yes=4, no=2)) is True


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------

def test_classify_unanimous_returns_kept_unanimous():
    assert classify(Tally(yes=3, no=0), roster_size=3) == "kept_unanimous"


def test_classify_non_unanimous_majority_returns_majority():
    # 2 of 3 voted yes: not unanimous, but yes > no → transient 'majority'
    # sentinel meaning "offer to host", NOT a stored outcome.
    assert classify(Tally(yes=2, no=0), roster_size=3) == "majority"


def test_classify_tie_returns_not_kept():
    assert classify(Tally(yes=1, no=1), roster_size=2) == "not_kept"


def test_classify_majority_no_returns_not_kept():
    assert classify(Tally(yes=1, no=2), roster_size=3) == "not_kept"


def test_classify_all_no_returns_not_kept():
    assert classify(Tally(yes=0, no=3), roster_size=3) == "not_kept"


def test_classify_roster_zero_returns_not_kept():
    assert classify(Tally(yes=0, no=0), roster_size=0) == "not_kept"


def test_classify_returns_plain_strings_not_enum_members():
    # Stored outcomes are the three Enum values; 'majority' is transient.
    # classify() must return plain str, never an Outcome member.
    assert type(classify(Tally(yes=1, no=0), roster_size=1)) is str
    assert type(classify(Tally(yes=1, no=0), roster_size=2)) is str
    assert type(classify(Tally(yes=0, no=1), roster_size=1)) is str


def test_outcome_enum_values_match_spec():
    assert Outcome.KEPT_UNANIMOUS.value == "kept_unanimous"
    assert Outcome.KEPT_HOST.value == "kept_host"
    assert Outcome.NOT_KEPT.value == "not_kept"


# ---------------------------------------------------------------------------
# resolve_missing_as_no (manual close, D5)
# ---------------------------------------------------------------------------

def test_resolve_missing_as_no_some_non_voters():
    assert resolve_missing_as_no(roster_size=5, yes_responses=3) == Tally(yes=3, no=2)


def test_resolve_missing_as_no_everyone_voted():
    assert resolve_missing_as_no(roster_size=4, yes_responses=4) == Tally(yes=4, no=0)


def test_resolve_missing_as_no_nobody_voted():
    assert resolve_missing_as_no(roster_size=4, yes_responses=0) == Tally(yes=0, no=4)


def test_resolve_missing_as_no_zero_roster():
    assert resolve_missing_as_no(roster_size=0, yes_responses=0) == Tally(yes=0, no=0)


# ---------------------------------------------------------------------------
# over_target_selection (D13)
# ---------------------------------------------------------------------------

def test_over_target_selection_all_fit():
    assert over_target_selection([1, 2, 3, 4, 5], remaining_target=7) == ([1, 2, 3, 4, 5], [])


def test_over_target_selection_over_by_some():
    # Caller pre-orders candidates by preference; excess is deferred.
    assert over_target_selection([1, 2, 3, 4, 5], remaining_target=3) == ([1, 2, 3], [4, 5])


def test_over_target_selection_exact_fit():
    assert over_target_selection([1, 2, 3, 4, 5], remaining_target=5) == ([1, 2, 3, 4, 5], [])


def test_over_target_selection_remaining_zero():
    assert over_target_selection([1, 2, 3], remaining_target=0) == ([], [1, 2, 3])


def test_over_target_selection_remaining_negative():
    assert over_target_selection([1, 2, 3], remaining_target=-2) == ([], [1, 2, 3])


def test_over_target_selection_empty_candidates():
    assert over_target_selection([], remaining_target=3) == ([], [])


def test_over_target_selection_does_not_mutate_inputs():
    candidates = [1, 2, 3, 4, 5]
    before = list(candidates)
    over_target_selection(candidates, remaining_target=2)
    assert candidates == before


# ---------------------------------------------------------------------------
# next_seq
# ---------------------------------------------------------------------------

def test_next_seq_empty_is_one():
    assert next_seq([]) == 1


def test_next_seq_max_plus_one():
    assert next_seq([3, 1, 2]) == 4


def test_next_seq_with_gaps():
    assert next_seq([1, 7, 3]) == 8


def test_next_seq_zero_seqs():
    assert next_seq([0]) == 1


# ---------------------------------------------------------------------------
# Session/batch state transitions (idempotency helpers)
# ---------------------------------------------------------------------------

def test_session_transitions_map_matches_spec():
    assert SESSION_TRANSITIONS == {
        "lobby": {"voting", "expired"},
        "voting": {"complete", "expired"},
        "complete": set(),
        "expired": set(),
    }


def test_can_transition_legal():
    assert can_transition("lobby", "voting") is True
    assert can_transition("lobby", "expired") is True
    assert can_transition("voting", "complete") is True
    assert can_transition("voting", "expired") is True


def test_can_transition_illegal():
    assert can_transition("lobby", "complete") is False
    assert can_transition("voting", "lobby") is False
    assert can_transition("complete", "voting") is False
    assert can_transition("expired", "lobby") is False


def test_can_transition_unknown_current_raises_value_error():
    with pytest.raises(ValueError):
        can_transition("banana", "voting")


def test_apply_transition_legal_returns_target():
    assert apply_transition("lobby", "voting") == "voting"
    assert apply_transition("voting", "complete") == "complete"


def test_apply_transition_idempotent_replay_is_noop():
    # Double-submitted "start voting" on an already-voting session is a
    # no-op, not an error.
    assert apply_transition("voting", "voting") == "voting"
    assert apply_transition("lobby", "lobby") == "lobby"
    assert apply_transition("complete", "complete") == "complete"


def test_apply_transition_illegal_raises_value_error():
    with pytest.raises(ValueError, match="illegal transition"):
        apply_transition("lobby", "complete")
    with pytest.raises(ValueError, match="illegal transition"):
        apply_transition("expired", "voting")


def test_apply_transition_unknown_current_raises_value_error():
    with pytest.raises(ValueError):
        apply_transition("banana", "voting")


def test_batch_transitions_map_matches_spec():
    assert BATCH_TRANSITIONS == {"open": {"closed"}, "closed": set()}


def test_can_close_batch():
    assert can_close_batch("open") is True
    assert can_close_batch("closed") is False


def test_apply_batch_close_open_to_closed():
    assert apply_batch_close("open") == "closed"


def test_apply_batch_close_idempotent():
    assert apply_batch_close("closed") == "closed"


def test_apply_batch_close_illegal_status_raises():
    with pytest.raises(ValueError):
        apply_batch_close("complete")


def test_resolve_missing_as_no_rejects_out_of_range():
    """Corrupted yes count (stale roster / double-count) must raise, not
    silently synthesize a negative no (Oscar M3a)."""
    import pytest as _pytest

    from app.session_logic import resolve_missing_as_no
    with _pytest.raises(ValueError):
        resolve_missing_as_no(roster_size=3, yes_responses=5)
    with _pytest.raises(ValueError):
        resolve_missing_as_no(roster_size=3, yes_responses=-1)
    # Boundary: everyone voted yes is valid.
    assert resolve_missing_as_no(roster_size=3, yes_responses=3).no == 0


def test_assemble_batch_rejects_nonpositive_size():
    import pytest as _pytest

    from app.session_logic import assemble_batch
    with _pytest.raises(ValueError):
        assemble_batch([1, 2, 3], set(), size=0)
    with _pytest.raises(ValueError):
        assemble_batch([1, 2, 3], set(), size=-1)
