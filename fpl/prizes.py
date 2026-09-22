"""GME Fantasy League 2026/27 prize pool.

Encodes the league's own prize sheet: 10 players, 50,000 KRW entry,
500,000 KRW pool. Amounts are KRW.
"""
from collections import defaultdict

ENTRY = 50_000
PLAYERS = 10
POOL = ENTRY * PLAYERS

WEEKLY = 7_000          # gameweeks 1-37
FINAL_GW = 38
FINAL_BONUS = 11_000    # gameweek 38 bonus round

SPECIALS = {
    "highest": 10_000,      # highest points in a single gameweek, all season
    "exact111": 10_000,     # exactly 111 in a single gameweek
    "lowest": 10_000,       # lowest single-gameweek score, hits excluded
    "fifth": 15_000,        # 5th in the final table
}
CHAMPION = 110_000
RUNNER_UP = 75_000

EXACT_TARGET = 111


def weekly_prize(gw):
    return FINAL_BONUS if gw == FINAL_GW else WEEKLY


def weekly_results(season):
    """Winner(s) and prize money for each completed gameweek.

    Ties are reported, not silently resolved — the prize sheet does not say
    how they are settled, so the money is shown split and flagged.
    """
    out = []
    for gw in sorted(season):
        rows = season[gw]
        best = max(r["points"] for r in rows)
        winners = [r for r in rows if r["points"] == best]
        pot = weekly_prize(gw)
        out.append(
            {
                "gw": gw,
                "points": best,
                "winners": [{"entry": w["entry"], "team": w["team"]} for w in winners],
                "pot": pot,
                "each": pot // len(winners),
                "tied": len(winners) > 1,
            }
        )
    return out


def standings_extremes(gameweeks):
    """Best and worst single-gameweek scores so far.

    The prize sheet excludes transfer-hit penalties from the lowest-score
    award, so that one is judged on gross points; the highest award has no
    such note and is judged on the score the game itself reports (net).
    """
    high = low = None
    exact = []
    for gw, data in gameweeks.items():
        for r in data["rows"]:
            net, gross = r["points"], r["gross"]
            cand_h = {"gw": int(gw), "entry": r["entry"], "team": r["team"], "points": net}
            cand_l = {"gw": int(gw), "entry": r["entry"], "team": r["team"], "points": gross}
            if high is None or net > high["points"]:
                high = cand_h
            if low is None or gross < low["points"]:
                low = cand_l
            if net == EXACT_TARGET:
                exact.append(cand_h)
    return {"highest": high, "lowest": low, "exact111": exact}


def ledger(season, gameweeks, standings):
    """Money banked so far plus what the table would pay if it froze today."""
    banked = defaultdict(int)
    weeks = weekly_results(season)
    for w in weeks:
        for win in w["winners"]:
            banked[win["entry"]] += w["each"]

    extremes = standings_extremes(gameweeks)
    provisional = defaultdict(int)
    if extremes["highest"]:
        provisional[extremes["highest"]["entry"]] += SPECIALS["highest"]
    if extremes["lowest"]:
        provisional[extremes["lowest"]["entry"]] += SPECIALS["lowest"]
    for hit in extremes["exact111"]:
        provisional[hit["entry"]] += SPECIALS["exact111"]

    by_rank = {r["rank"]: r["entry"] for r in standings}
    if 1 in by_rank:
        provisional[by_rank[1]] += CHAMPION
    if 2 in by_rank:
        provisional[by_rank[2]] += RUNNER_UP
    if 5 in by_rank:
        provisional[by_rank[5]] += SPECIALS["fifth"]

    rows = []
    for s in standings:
        e = s["entry"]
        rows.append(
            {
                "entry": e,
                "team": s["team"],
                "rank": s["rank"],
                "banked": banked[e],
                "provisional": provisional[e],
                "projected": banked[e] + provisional[e],
                "net": banked[e] + provisional[e] - ENTRY,
            }
        )
    rows.sort(key=lambda r: -r["projected"])

    remaining = sum(
        weekly_prize(g) for g in range(1, FINAL_GW + 1) if g not in season
    )
    return {
        "weeks": weeks,
        "extremes": extremes,
        "rows": rows,
        "entry": ENTRY,
        "pool": POOL,
        "paidOut": sum(w["pot"] for w in weeks),
        "weeklyRemaining": remaining,
        "specials": SPECIALS,
        "champion": CHAMPION,
        "runnerUp": RUNNER_UP,
        "weeklyPrize": WEEKLY,
        "finalBonus": FINAL_BONUS,
    }
