"""Payment history for the weekly prizes.

The record is a list of events, oldest first. Nothing is ever overwritten:
paying a prize appends a "paid" event, taking it back appends an "unpaid"
one. A prize's current state is its latest event.

The file is meant to be edited by hand too. The smallest valid event is

    {"id": "gw6-2586046", "status": "paid", "on": "2026-10-14"}

where the id is "gw<gameweek>-<FPL entry id>", as `fpl books` lists them.
It holds entry ids, team names and amounts only, never managers' real names,
because it is committed to a public repo.
"""
import json
import os
from datetime import date

STATUSES = ("paid", "unpaid")

HOW = [
    "Payment history for the weekly prizes, oldest first. Never edit or delete",
    "a past line: append a new one. A prize's latest line is its current state.",
    "Smallest valid line: {\"id\": \"gw6-2586046\", \"status\": \"paid\", \"on\": \"2026-10-14\"}",
    "Or use: python3 -m fpl pay 6   /   python3 -m fpl pay 6 --undo",
]


def load(path):
    """Events from the file, oldest first. A missing file is an empty history.

    Also reads the old format, {"paid": [ids]}, as one "paid" event per id.
    """
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        raw = json.load(fh)
    if "history" not in raw:
        return [{"id": i, "status": "paid", "on": None} for i in raw.get("paid", [])]
    events = raw["history"]
    for n, event in enumerate(events, 1):
        if not event.get("id") or event.get("status") not in STATUSES:
            raise ValueError(
                f"{path}: line {n} of history needs an id and a status of "
                f"'paid' or 'unpaid', got {event!r}"
            )
    return events


def save(path, events):
    with open(path, "w") as fh:
        json.dump({"_how": HOW, "history": events}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def state(events):
    """Latest event per prize id."""
    latest = {}
    for event in events:
        latest[event["id"]] = event
    return latest


def paid_ids(events):
    return sorted(i for i, e in state(events).items() if e["status"] == "paid")


def record(events, line, status, on=None, note=""):
    """Append one event for a payable line from `treasury.items`."""
    event = {
        "id": line["id"],
        "gw": line["gw"],
        "team": line["team"],
        "amount": line["amount"],
        "status": status,
        "on": on or date.today().isoformat(),
    }
    if note:
        event["note"] = note
    events.append(event)
    return event
