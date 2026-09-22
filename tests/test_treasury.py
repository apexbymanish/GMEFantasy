"""Tests for the treasury view."""
import pytest

from fpl import prizes as pz
from fpl import treasury as tr

LEDGER = {
    "weeks": [
        {"gw": 1, "points": 60, "pot": 7000, "each": 3500, "tied": True,
         "winners": [{"entry": 1, "team": "Alpha"}, {"entry": 2, "team": "Beta"}]},
        {"gw": 2, "points": 117, "pot": 7000, "each": 7000, "tied": False,
         "winners": [{"entry": 1, "team": "Alpha"}]},
    ],
    "weeklyRemaining": 270_000 - 14_000,
}

STANDINGS = [
    {"rank": 1, "entry": 1, "team": "Alpha"},
    {"rank": 2, "entry": 2, "team": "Beta"},
    {"rank": 3, "entry": 3, "team": "Gamma"},
]


class TestItems:
    def test_a_tie_produces_one_payable_line_each(self):
        lines = tr.items(LEDGER)
        gw1 = [l for l in lines if l["gw"] == 1]
        assert len(gw1) == 2
        assert all(l["amount"] == 3500 for l in gw1)

    def test_ids_are_stable_and_document_safe(self):
        assert tr.payment_id(1, 6144939) == "gw1-6144939"
        assert all(c.isalnum() or c == "-" for c in tr.payment_id(38, 12))


class TestSummary:
    def test_nothing_paid_means_everything_is_due(self):
        s = tr.summary(LEDGER, [])
        assert s["paidOut"] == 0
        assert s["dueNow"] == 14_000
        assert s["balance"] == pz.POOL

    def test_paying_moves_money_from_due_to_paid(self):
        s = tr.summary(LEDGER, ["gw2-1"])
        assert s["paidOut"] == 7_000
        assert s["dueNow"] == 7_000
        assert s["balance"] == pz.POOL - 7_000

    def test_paying_one_side_of_a_tie_leaves_the_other_owed(self):
        s = tr.summary(LEDGER, ["gw1-1"])
        assert s["paidOut"] == 3_500
        assert s["dueNow"] == 10_500

    def test_books_reconcile_against_the_prize_sheet(self):
        # Balance on hand must exactly cover everything still owed.
        for paid in ([], ["gw1-1"], ["gw1-1", "gw1-2", "gw2-1"]):
            assert tr.summary(LEDGER, paid)["unallocated"] == 0

    def test_unknown_payment_ids_are_ignored(self):
        assert tr.summary(LEDGER, ["gw99-7"])["paidOut"] == 0

    def test_counts_track_progress(self):
        s = tr.summary(LEDGER, ["gw1-1"])
        assert (s["paidCount"], s["totalCount"]) == (1, 3)


class TestByManager:
    def test_splits_received_from_still_owed(self):
        s = tr.summary(LEDGER, ["gw2-1"])
        rows = tr.by_manager(s, STANDINGS)
        alpha = next(r for r in rows if r["team"] == "Alpha")
        assert alpha["received"] == 7_000   # GW2, paid
        assert alpha["owed"] == 3_500       # GW1 share, unpaid

    def test_managers_who_never_won_appear_with_zero(self):
        rows = tr.by_manager(tr.summary(LEDGER, []), STANDINGS)
        gamma = next(r for r in rows if r["team"] == "Gamma")
        assert gamma["received"] == 0 and gamma["owed"] == 0
