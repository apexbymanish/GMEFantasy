"""Tests for the public build: real names never leave, code names do."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "build", Path(__file__).parent.parent / "dashboard" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_redact_leaves_no_full_name():
    raw = json.dumps({
        "managers": [{"entry": 1, "team": "Falano", "manager": "Jane Doe"}],
        "standings": [{"entry": 1, "team": "Falano", "manager": "Jane Doe"}],
        "gameweeks": {"1": {"rows": [{"entry": 1, "manager": "Jane Doe"}]}},
    })
    out = build.redact(raw)
    assert "Jane" not in out and "Doe" not in out
    data = json.loads(out)
    assert data["managers"][0]["manager"] == ""
    assert data["standings"][0]["manager"] == ""
    assert data["gameweeks"]["1"]["rows"][0]["manager"] == ""
    assert data["managers"][0]["team"] == "Falano"


def test_codename_pattern():
    assert build.codename("Jane Doe") == "Doe·Ja"
    assert build.codename("ana maria lopez") == "Lop·An"
    assert build.codename("Cher") == "Che"
    assert build.codename("") == ""


def test_public_page_keeps_codename_but_not_full_name():
    raw = json.dumps({"managers": [{"entry": 1, "team": "X", "manager": "Jane Doe"}]})
    data = json.loads(build.redact(build.with_codenames(raw)))
    assert data["managers"][0] == {"entry": 1, "team": "X", "manager": "", "alias": "Doe·Ja"}
