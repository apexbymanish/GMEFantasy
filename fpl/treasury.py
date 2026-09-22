"""Treasury view of the prize pool: what is owed, what is paid, what is left.

The pool is collected up front (10 entries of 50,000 KRW), so every prize is
already funded. What changes over the season is how much of it has actually
been handed over. This module answers that.
"""
from . import prizes as pz


def payment_id(gw, entry):
    """Stable id for one payment, safe as a document key."""
    return f"gw{gw}-{entry}"


def items(ledger):
    """One payable line per weekly winner. Ties produce one line each."""
    out = []
    for week in ledger["weeks"]:
        for winner in week["winners"]:
            out.append(
                {
                    "id": payment_id(week["gw"], winner["entry"]),
                    "gw": week["gw"],
                    "entry": winner["entry"],
                    "team": winner["team"],
                    "amount": week["each"],
                    "points": week["points"],
                    "tied": week["tied"],
                }
            )
    return out


def summary(ledger, paid_ids):
    """The books, as a treasurer would want them.

    `paid_ids` holds the ids of payments already handed over.
    """
    paid_ids = set(paid_ids or ())
    lines = items(ledger)
    for line in lines:
        line["paid"] = line["id"] in paid_ids

    collected = pz.POOL
    paid_out = sum(l["amount"] for l in lines if l["paid"])
    due_now = sum(l["amount"] for l in lines if not l["paid"])

    reserved_weekly = ledger["weeklyRemaining"]
    reserved_specials = sum(pz.SPECIALS.values())
    reserved_podium = pz.CHAMPION + pz.RUNNER_UP
    reserved = reserved_weekly + reserved_specials + reserved_podium

    balance = collected - paid_out
    # Everything still owed, whether decided yet or not.
    committed = due_now + reserved

    return {
        "lines": lines,
        "collected": collected,
        "entry": pz.ENTRY,
        "players": pz.PLAYERS,
        "paidOut": paid_out,
        "dueNow": due_now,
        "reservedWeekly": reserved_weekly,
        "reservedSpecials": reserved_specials,
        "reservedPodium": reserved_podium,
        "reserved": reserved,
        "balance": balance,
        "committed": committed,
        # Balance minus everything owed. Zero means the books reconcile;
        # anything else means the prize sheet does not add up to the pool.
        "unallocated": balance - committed,
        "paidCount": sum(1 for l in lines if l["paid"]),
        "totalCount": len(lines),
    }


def by_manager(summary_, standings):
    """Per-manager payout record: received so far, still owed from weeks won."""
    got, owed = {}, {}
    for line in summary_["lines"]:
        bucket = got if line["paid"] else owed
        bucket[line["entry"]] = bucket.get(line["entry"], 0) + line["amount"]
    rows = []
    for s in standings:
        e = s["entry"]
        rows.append(
            {
                "entry": e,
                "team": s["team"],
                "rank": s["rank"],
                "received": got.get(e, 0),
                "owed": owed.get(e, 0),
                "entryFee": pz.ENTRY,
            }
        )
    rows.sort(key=lambda r: (-(r["received"] + r["owed"]), r["rank"]))
    return rows
