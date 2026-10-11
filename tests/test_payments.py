import json

import pytest

from fpl import payments as pay

LINE = {"id": "gw6-1844688", "gw": 6, "team": "Carrickonthewheel", "amount": 7000}


class TestHistory:
    def test_the_latest_event_decides(self):
        events = []
        pay.record(events, LINE, "paid", on="2026-10-14")
        pay.record(events, LINE, "unpaid", on="2026-10-15", note="wrong person")
        assert pay.paid_ids(events) == []
        pay.record(events, LINE, "paid", on="2026-10-16")
        assert pay.paid_ids(events) == ["gw6-1844688"]
        assert len(events) == 3          # nothing overwritten

    def test_round_trips_through_the_file(self, tmp_path):
        path = tmp_path / "payments.json"
        events = []
        pay.record(events, LINE, "paid", on="2026-10-14")
        pay.save(path, events)
        assert pay.load(path) == events

    def test_a_hand_written_minimal_line_is_enough(self, tmp_path):
        path = tmp_path / "payments.json"
        path.write_text(json.dumps({"history": [
            {"id": "gw6-1844688", "status": "paid", "on": "2026-10-14"}]}))
        assert pay.paid_ids(pay.load(path)) == ["gw6-1844688"]

    def test_a_bad_status_is_refused_with_its_line_number(self, tmp_path):
        path = tmp_path / "payments.json"
        path.write_text(json.dumps({"history": [
            {"id": "gw6-1844688", "status": "payed"}]}))
        with pytest.raises(ValueError, match="line 1"):
            pay.load(path)

    def test_the_old_format_still_reads(self, tmp_path):
        path = tmp_path / "payments.json"
        path.write_text(json.dumps({"paid": ["gw1-1", "gw2-2"]}))
        assert pay.paid_ids(pay.load(path)) == ["gw1-1", "gw2-2"]

    def test_a_missing_file_is_an_empty_history(self, tmp_path):
        assert pay.load(tmp_path / "nope.json") == []
