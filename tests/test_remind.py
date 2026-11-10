"""Tests for the deadline lines in the group reminder."""
from datetime import datetime, timezone

from fpl import remind


def test_deadline_lines_in_both_zones_without_leading_zero():
    deadline = datetime(2026, 11, 21, 11, 0, tzinfo=timezone.utc)
    lines = remind._deadline_lines(deadline)
    assert lines[0] == "Deadline KST: Sat 21 Nov, 8:00 PM"
    assert lines[1] == "Deadline NPT: Sat 21 Nov, 4:45 PM"
    assert lines[2].startswith("(")
