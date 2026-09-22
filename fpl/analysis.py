"""Analysis layer: pure functions over already-fetched data.

Nothing here touches the network, so every function is testable offline
against a saved API response.
"""
from collections import defaultdict
from statistics import mean

# Squad positions 1-11 are the starting XI; 12-15 are the bench.
STARTERS = 11


def player_index(boot):
    return {p["id"]: p for p in boot["elements"]}


def team_index(boot):
    return {t["id"]: t for t in boot["teams"]}


def position_index(boot):
    return {t["id"]: t["singular_name_short"] for t in boot["element_types"]}


def managers(league_data):
    """(entry_id, team_name, manager_name) for everyone in the league."""
    return [
        (row["entry"], row["entry_name"], row["player_name"])
        for row in league_data["standings"]["results"]
    ]


def live_points(live_data):
    return {e["id"]: e["stats"]["total_points"] for e in live_data["elements"]}


def weekly_table(managers_, picks_by_manager, points_by_player):
    """One row per manager for a single gameweek, best score first.

    `points` is net of transfer hits, which is what actually decides the week.
    """
    rows = []
    for (entry_id, team_name, manager_name), pick_data in zip(managers_, picks_by_manager):
        summary = pick_data["entry_history"]
        hit = summary["event_transfers_cost"]
        captain = next(p["element"] for p in pick_data["picks"] if p["is_captain"])
        vice = next(p["element"] for p in pick_data["picks"] if p["is_vice_captain"])
        rows.append(
            {
                "entry": entry_id,
                "team": team_name,
                "manager": manager_name,
                "points": summary["points"] - hit,
                "gross": summary["points"],
                "hit": hit,
                "transfers": summary["event_transfers"],
                "bench": summary["points_on_bench"],
                "captain": captain,
                "captain_points": points_by_player.get(captain, 0) * 2,
                "vice": vice,
                "chip": pick_data.get("active_chip"),
                "squad": [p["element"] for p in pick_data["picks"]],
                "starters": [p["element"] for p in pick_data["picks"][:STARTERS]],
            }
        )
    rows.sort(key=lambda r: r["points"], reverse=True)
    for place, row in enumerate(rows, 1):
        row["place"] = place
    return rows


def ownership(rows, starters_only=True):
    """player_id -> how many managers in the league fielded them."""
    counts = defaultdict(int)
    for row in rows:
        for pid in (row["starters"] if starters_only else row["squad"]):
            counts[pid] += 1
    return dict(counts)


def differentials(rows, entry_id, max_owners=1):
    """Players in this manager's XI that at most `max_owners` managers field.

    Returns (mine, theirs): my differentials, and rivals' differentials I missed.
    """
    counts = ownership(rows)
    me = next(r for r in rows if r["entry"] == entry_id)
    mine = [pid for pid in me["starters"] if counts.get(pid, 0) <= max_owners]
    theirs = [
        pid
        for pid, n in counts.items()
        if n <= max_owners and pid not in me["squad"]
    ]
    return mine, theirs


def season_table(managers_, histories):
    """gw -> rows sorted by that week's net score. Drives the trend chart."""
    weeks = defaultdict(list)
    for (entry_id, team_name, _), hist in zip(managers_, histories):
        for gw in hist["current"]:
            weeks[gw["event"]].append(
                {
                    "entry": entry_id,
                    "team": team_name,
                    "points": gw["points"] - gw["event_transfers_cost"],
                    "total": gw["total_points"],
                    "overall_rank": gw["overall_rank"],
                }
            )
    for gw in weeks:
        weeks[gw].sort(key=lambda r: r["points"], reverse=True)
        for place, row in enumerate(weeks[gw], 1):
            row["place"] = place
    return dict(weeks)


def weekly_wins(season):
    """team name -> number of gameweeks won."""
    wins = defaultdict(int)
    for rows in season.values():
        wins[rows[0]["team"]] += 1
    return dict(wins)


def league_position_by_gw(season):
    """entry id -> {gw: cumulative league position}, i.e. the real title race.

    Keyed by entry rather than team name: two managers may pick the same
    team name, and a manager who joins mid-season simply has no entry for
    the gameweeks before they arrived.
    """
    positions = defaultdict(dict)
    for gw, rows in season.items():
        standings = sorted(rows, key=lambda r: r["total"], reverse=True)
        for place, row in enumerate(standings, 1):
            positions[row["entry"]][gw] = place
    return dict(positions)


# --- player suggestions ---------------------------------------------------

def fixture_difficulty(fixtures_data, from_gw, horizon=3):
    """team_id -> mean FDR over its next `horizon` fixtures (1 easy .. 5 hard)."""
    upcoming = defaultdict(list)
    for fix in fixtures_data:
        gw = fix["event"]
        if gw is None or gw < from_gw or gw >= from_gw + horizon:
            continue
        upcoming[fix["team_h"]].append(fix["team_h_difficulty"])
        upcoming[fix["team_a"]].append(fix["team_a_difficulty"])
    return {team: mean(vals) for team, vals in upcoming.items() if vals}


def _normalise(values):
    """Scale to 0..1. Flat input scores 0.5 so it cannot swing the ranking."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def is_available(player):
    """Fit, and not flagged as doubtful for the next round."""
    if player["status"] != "a":
        return False
    chance = player["chance_of_playing_next_round"]
    return chance is None or chance >= 75


def rank_players(boot, fixtures_data, from_gw, horizon=3, min_minutes=180, top=10):
    """Score every available player and return the best per position.

    Scored within position, so defenders compete with defenders rather than
    losing to strikers on attacking numbers.
    """
    fdr = fixture_difficulty(fixtures_data, from_gw, horizon)
    positions = position_index(boot)
    teams = team_index(boot)

    pool = defaultdict(list)
    for p in boot["elements"]:
        if not is_available(p) or p["minutes"] < min_minutes:
            continue
        if p["team"] not in fdr:
            continue  # blank gameweek: nothing to recommend
        pool[p["element_type"]].append(p)

    results = {}
    for element_type, players in pool.items():
        form = [float(p["form"]) for p in players]
        ppg = [float(p["points_per_game"]) for p in players]
        xgi = [float(p["expected_goal_involvements_per_90"]) for p in players]
        ease = [5.0 - fdr[p["team"]] for p in players]
        value = [p["total_points"] / (p["now_cost"] / 10) for p in players]

        scored = []
        for p, f, g, x, e, v in zip(
            players, _normalise(form), _normalise(ppg), _normalise(xgi),
            _normalise(ease), _normalise(value),
        ):
            score = 0.30 * f + 0.20 * g + 0.20 * x + 0.20 * e + 0.10 * v
            scored.append(
                {
                    "id": p["id"],
                    "name": p["web_name"],
                    "team": teams[p["team"]]["short_name"],
                    "position": positions[element_type],
                    "price": p["now_cost"] / 10,
                    "form": float(p["form"]),
                    "ppg": float(p["points_per_game"]),
                    "xgi90": float(p["expected_goal_involvements_per_90"]),
                    "fdr": round(fdr[p["team"]], 2),
                    "owned": float(p["selected_by_percent"]),
                    "score": round(score, 4),
                }
            )
        scored.sort(key=lambda r: r["score"], reverse=True)
        results[positions[element_type]] = scored[:top]
    return results
