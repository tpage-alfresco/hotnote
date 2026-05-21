"""Unit tests for hotnotelib — pure helpers only, no I/O or GTK."""

import sys
import os
from unittest.mock import patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import hotnotelib as hn

# ── parse_recur ──────────────────────────────────────────────────────────────


class TestParseRecur:
    def test_days(self):
        assert hn.parse_recur("18d") == {"every": 18, "unit": "days"}

    def test_weeks(self):
        assert hn.parse_recur("2w") == {"every": 2, "unit": "weeks"}

    def test_months(self):
        assert hn.parse_recur("1m") == {"every": 1, "unit": "months"}

    def test_uppercase(self):
        assert hn.parse_recur("3W") == {"every": 3, "unit": "weeks"}

    def test_whitespace_stripped(self):
        assert hn.parse_recur("  5d  ") == {"every": 5, "unit": "days"}

    def test_none_string(self):
        assert hn.parse_recur("none") is None

    def test_none_string_uppercase(self):
        assert hn.parse_recur("None") is None

    def test_invalid_unit(self):
        assert hn.parse_recur("3x") is None

    def test_missing_number(self):
        assert hn.parse_recur("d") is None

    def test_empty(self):
        assert hn.parse_recur("") is None


# ── domain_from_url ──────────────────────────────────────────────────────────


class TestDomainFromUrl:
    def test_simple(self):
        assert hn.domain_from_url("https://example.com/page") == "example.com"

    def test_strips_www(self):
        assert hn.domain_from_url("https://www.github.com/repo") == "github.com"

    def test_with_port(self):
        assert hn.domain_from_url("http://localhost:8080/path") == "localhost"

    def test_non_url_fallback(self):
        result = hn.domain_from_url("not-a-url")
        assert isinstance(result, str)


# ── sort_key / pending / completed ───────────────────────────────────────────


def _note(id="aaa", importance="medium", urgency="soon", status="pending", **kw):
    n = {"id": id, "importance": importance, "urgency": urgency, "status": status}
    n.update(kw)
    return n


class TestSortKey:
    def test_critical_immediate_first(self):
        high = _note(importance="critical", urgency="immediate")
        low = _note(importance="low", urgency="whenever")
        assert hn.sort_key(high) < hn.sort_key(low)

    def test_same_importance_sorted_by_urgency(self):
        soon = _note(importance="high", urgency="soon")
        whenever = _note(importance="high", urgency="whenever")
        assert hn.sort_key(soon) < hn.sort_key(whenever)


class TestPendingAndCompleted:
    def test_pending_excludes_done(self):
        notes = [_note(id="1"), _note(id="2", status="done")]
        result = hn.pending(notes)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_pending_excludes_scheduled(self):
        notes = [
            _note(id="1"),
            _note(id="2", status="scheduled", appear_date="2099-01-01"),
        ]
        result = hn.pending(notes)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_completed_only_done(self):
        notes = [_note(id="1"), _note(id="2", status="done", completed="2025-01-01")]
        result = hn.completed(notes)
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_pending_sorted_by_priority(self):
        low = _note(id="low", importance="low", urgency="whenever")
        high = _note(id="high", importance="critical", urgency="immediate")
        result = hn.pending([low, high])
        assert result[0]["id"] == "high"
        assert result[1]["id"] == "low"


# ── find_note ────────────────────────────────────────────────────────────────


class TestFindNote:
    def test_found(self):
        notes = [_note(id="abc"), _note(id="def")]
        assert hn.find_note(notes, "def")["id"] == "def"

    def test_not_found(self):
        assert hn.find_note([_note(id="abc")], "zzz") is None


# ── fmt_recur_short ──────────────────────────────────────────────────────────


class TestFmtRecurShort:
    def test_days(self):
        note = _note(recur={"every": 18, "unit": "days"})
        assert hn.fmt_recur_short(note) == "↻18d"

    def test_weeks(self):
        note = _note(recur={"every": 2, "unit": "weeks"})
        assert hn.fmt_recur_short(note) == "↻2w"

    def test_months(self):
        note = _note(recur={"every": 1, "unit": "months"})
        assert hn.fmt_recur_short(note) == "↻1mo"

    def test_no_recurrence(self):
        assert hn.fmt_recur_short(_note()) == ""


# ── advance_next_due ─────────────────────────────────────────────────────────


class TestAdvanceNextDue:
    def test_advance_days(self):
        result = hn.advance_next_due(
            "2025-06-01T00:00:00Z", {"every": 5, "unit": "days"}
        )
        assert result == "2025-06-06T00:00:00Z"

    def test_advance_weeks(self):
        result = hn.advance_next_due(
            "2025-06-01T00:00:00Z", {"every": 2, "unit": "weeks"}
        )
        assert result == "2025-06-15T00:00:00Z"

    def test_advance_months(self):
        result = hn.advance_next_due(
            "2025-01-31T00:00:00Z", {"every": 1, "unit": "months"}
        )
        assert result == "2025-02-28T00:00:00Z"


class TestRecurringTaskCompletion:
    """Reproduce the Polish Tax Credit bug: completing a monthly recurring task
    should schedule the next occurrence relative to today, not blindly advance
    from a potentially-drifted next_due.

    Scenario: first_due = 2026-05-21, recur = 1m.  The user created the note
    on May 7 and immediately did 'done', which advanced next_due to June 21.
    Through repeated 'done' calls (e.g. from the scheduled tab in the GTK app)
    next_due drifted to Aug 21.  When the user completes the task for real on
    May 21, the next occurrence should be June 21 — not September 21.
    """

    MONTHLY = {"every": 1, "unit": "months"}

    def test_current_behaviour_advances_from_drifted_next_due(self):
        """Shows the bug: advance_next_due just adds an interval to the stored
        next_due regardless of today's date, so a drifted value keeps drifting."""
        result = hn.advance_next_due("2026-08-21T00:00:00Z", self.MONTHLY)
        assert result == "2026-09-21T00:00:00Z"

    def test_completing_on_due_date_should_give_next_month(self):
        """When the task is due today and completed today, next should be +1 interval."""
        next_due = hn.advance_next_due_from(
            next_due="2026-05-21T00:00:00Z",
            recur=self.MONTHLY,
            first_due="2026-05-21",
            now="2026-05-21T12:00:00Z",
        )
        assert next_due == "2026-06-21T00:00:00Z"

    def test_drifted_next_due_resets_to_cadence(self):
        """The Polish Tax Credit bug: next_due drifted to Aug but today is May,
        so completing should give June 21 (first cadence date after today)."""
        next_due = hn.advance_next_due_from(
            next_due="2026-08-21T00:00:00Z",
            recur=self.MONTHLY,
            first_due="2026-05-21",
            now="2026-05-21T12:00:00Z",
        )
        assert next_due == "2026-06-21T00:00:00Z"

    def test_overdue_task_skips_to_first_future_cadence_date(self):
        """If the task is overdue by several months, skip to the first future date."""
        next_due = hn.advance_next_due_from(
            next_due="2026-01-15T00:00:00Z",
            recur=self.MONTHLY,
            first_due="2026-01-15",
            now="2026-05-21T12:00:00Z",
        )
        assert next_due == "2026-06-15T00:00:00Z"

    def test_overdue_weekly_task(self):
        """Bi-weekly task overdue should jump to the next future cadence date.
        Apr 14 → Apr 28 → May 12 → May 26 (first date after May 21)."""
        next_due = hn.advance_next_due_from(
            next_due="2026-04-28T00:00:00Z",
            recur={"every": 2, "unit": "weeks"},
            first_due="2026-04-14",
            now="2026-05-21T12:00:00Z",
        )
        assert next_due == "2026-05-26T00:00:00Z"

    def test_early_completion_preserves_cadence(self):
        """Completing 3 days before the due date returns the current cadence
        date (June 21), preserving the monthly-on-the-21st rhythm."""
        next_due = hn.advance_next_due_from(
            next_due="2026-06-21T00:00:00Z",
            recur=self.MONTHLY,
            first_due="2026-05-21",
            now="2026-06-18T12:00:00Z",
        )
        assert next_due == "2026-06-21T00:00:00Z"


# ── mark_done / mark_reopened ─────────────────────────────────────────────────


class TestMarkDone:
    def test_non_recurring_becomes_done(self):
        note = _note(id="1", status="pending")
        hn.mark_done(note)
        assert note["status"] == "done"
        assert note["completed"] is not None

    def test_recurring_becomes_scheduled(self):
        note = _note(
            id="1",
            status="pending",
            recur={"every": 1, "unit": "months"},
            first_due="2020-01-15",
            next_due="2020-01-15T00:00:00Z",
        )
        hn.mark_done(note)
        assert note["status"] == "scheduled"
        assert note["appear_date"] == note["next_due"][:10]
        assert note["completed"] is not None

    def test_recurring_without_first_due_becomes_done(self):
        note = _note(
            id="1",
            status="pending",
            recur={"every": 5, "unit": "days"},
            next_due="2026-06-01T00:00:00Z",
        )
        hn.mark_done(note)
        assert note["status"] == "done"


class TestMarkReopened:
    def test_reopens_done_note(self):
        note = _note(id="1", status="done", completed="2026-05-01T00:00:00Z")
        hn.mark_reopened(note)
        assert note["status"] == "pending"
        assert note["completed"] is None

    def test_reopens_scheduled_note(self):
        note = _note(id="1", status="scheduled", completed="2026-05-01T00:00:00Z")
        hn.mark_reopened(note)
        assert note["status"] == "pending"
        assert note["completed"] is None


# ── scheduled ────────────────────────────────────────────────────────────────


class TestScheduled:
    def test_returns_only_scheduled(self):
        notes = [
            _note(id="1", status="pending"),
            _note(id="2", status="scheduled", appear_date="2026-06-01"),
            _note(id="3", status="done"),
        ]
        result = hn.scheduled(notes)
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_sorted_by_appear_date(self):
        notes = [
            _note(id="later", status="scheduled", appear_date="2026-09-01"),
            _note(id="sooner", status="scheduled", appear_date="2026-06-01"),
        ]
        result = hn.scheduled(notes)
        assert result[0]["id"] == "sooner"
        assert result[1]["id"] == "later"

    def test_empty_when_none_scheduled(self):
        notes = [_note(id="1", status="pending")]
        assert hn.scheduled(notes) == []


# ── scheduled_activate ───────────────────────────────────────────────────────


class TestScheduledActivate:
    def test_activates_past_date(self):
        notes = [_note(id="1", status="scheduled", appear_date="2020-01-01")]
        assert hn.scheduled_activate(notes) is True
        assert notes[0]["status"] == "pending"
        assert notes[0]["appear_date"] is None

    def test_leaves_future_date(self):
        notes = [_note(id="1", status="scheduled", appear_date="2099-12-31")]
        assert hn.scheduled_activate(notes) is False
        assert notes[0]["status"] == "scheduled"

    def test_activates_today(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        notes = [_note(id="1", status="scheduled", appear_date=today)]
        assert hn.scheduled_activate(notes) is True
        assert notes[0]["status"] == "pending"

    def test_ignores_non_scheduled(self):
        notes = [_note(id="1", status="pending")]
        assert hn.scheduled_activate(notes) is False

    def test_clears_completed_on_activate(self):
        notes = [
            _note(
                id="1",
                status="scheduled",
                appear_date="2020-01-01",
                completed="2020-01-01T00:00:00Z",
            )
        ]
        hn.scheduled_activate(notes)
        assert notes[0]["completed"] is None

    def test_recurring_note_activates(self):
        notes = [
            _note(
                id="1",
                status="scheduled",
                appear_date="2020-06-01",
                recur={"every": 1, "unit": "months"},
                next_due="2020-06-01T00:00:00Z",
            )
        ]
        hn.scheduled_activate(notes)
        assert notes[0]["status"] == "pending"


# ── parse_appear_date ────────────────────────────────────────────────────────


class TestParseAppearDate:
    def test_valid_future_date(self):
        assert hn.parse_appear_date("2099-06-01") == "2099-06-01"

    def test_today_is_valid(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert hn.parse_appear_date(today) == today

    def test_past_date_rejected(self):
        assert hn.parse_appear_date("2000-01-01") is None

    def test_invalid_format(self):
        assert hn.parse_appear_date("not-a-date") is None

    def test_whitespace_stripped(self):
        assert hn.parse_appear_date("  2099-06-01  ") == "2099-06-01"

    def test_empty_string(self):
        assert hn.parse_appear_date("") is None


# ── fmt_appear_short ─────────────────────────────────────────────────────────


class TestFmtAppearShort:
    def test_formats_date(self):
        note = _note(appear_date="2026-06-01")
        result = hn.fmt_appear_short(note)
        assert "Jun" in result
        assert "1" in result

    def test_no_appear_date(self):
        assert hn.fmt_appear_short(_note()) == ""

    def test_none_appear_date(self):
        assert hn.fmt_appear_short(_note(appear_date=None)) == ""
