"""Build a single JSON snapshot of the league for the dashboard.

The FPL API sends no CORS headers, so a browser page cannot call it. The
dashboard therefore ships with a snapshot produced here.
"""
import json
from datetime import datetime, timezone

from . import analysis as an
from . import api
from . import prizes as pz
from . import remind as rm


def snapshot(league_id, my_entry, horizon=3, top=8):
    boot = api.bootstrap()
    players = an.player_index(boot)
    teams = an.team_index(boot)
    positions = an.position_index(boot)

    league_data = api.league(league_id)
    managers = an.managers(league_data)
    histories = api.parallel(lambda m: api.history(m[0]), managers)
    season = an.season_table(managers, histories)
    played = sorted(season)

    def describe(pid):
        p = players[pid]
        return {
            "id": pid,
            "name": p["web_name"],
            "team": teams[p["team"]]["short_name"],
            "pos": positions[p["element_type"]],
            "price": p["now_cost"] / 10,
        }

    gameweeks = {}
    seen = set()
    for gw in played:
        picks = api.parallel(lambda m: api.picks(m[0], gw), managers)
        points = an.live_points(api.live(gw))
        rows = an.weekly_table(managers, picks, points)
        counts = an.ownership(rows)
        seen.update(counts)
        for row in rows:
            seen.add(row["captain"])

        gameweeks[str(gw)] = {
            "finished": api.is_finished(gw),
            "rows": [
                {
                    "place": r["place"],
                    "entry": r["entry"],
                    "team": r["team"],
                    "manager": r["manager"],
                    "points": r["points"],
                    "gross": r["gross"],
                    "hit": r["hit"],
                    "transfers": r["transfers"],
                    "bench": r["bench"],
                    "chip": r["chip"],
                    "captain": r["captain"],
                    "captainPoints": r["captain_points"],
                    "starters": r["starters"],
                }
                for r in rows
            ],
            "ownership": {str(k): v for k, v in counts.items()},
            "playerPoints": {str(p): points.get(p, 0) for p in counts},
        }

    suggestions = an.rank_players(
        boot, api.fixtures(), api.next_gw(), horizon=horizon, top=top
    )
    for bucket in suggestions.values():
        seen.update(p["id"] for p in bucket)

    # Upcoming fixtures, so managers can plan before the deadline.
    ahead = [
        e["id"] for e in boot["events"]
        if not e["finished"] and not e["is_current"] and e["id"] >= api.next_gw()
    ][:horizon]
    fixtures_data = api.fixtures()
    upcoming = {}
    for gw in ahead:
        games = [f for f in fixtures_data if f["event"] == gw]
        games.sort(key=lambda f: f["kickoff_time"] or "")
        deadline = next(
            (e["deadline_time"] for e in boot["events"] if e["id"] == gw), None
        )
        upcoming[str(gw)] = {
            "deadline": deadline,
            "games": [
                {
                    "kickoff": f["kickoff_time"],
                    "home": teams[f["team_h"]]["short_name"],
                    "away": teams[f["team_a"]]["short_name"],
                    "homeName": teams[f["team_h"]]["name"],
                    "awayName": teams[f["team_a"]]["name"],
                    "homeFdr": f["team_h_difficulty"],
                    "awayFdr": f["team_a_difficulty"],
                }
                for f in games
            ],
        }

    next_event = next((e for e in boot["events"] if e["is_next"]), None)

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "league": {"id": league_id, "name": league_data["league"]["name"]},
        "me": next((m[0] for m in managers if m[0] == my_entry), None),
        "currentGw": api.current_gw(),
        "nextGw": api.next_gw(),
        "nextDeadline": next_event["deadline_time"] if next_event else None,
        "playedGws": played,
        "managers": [
            {"entry": e, "team": t, "manager": n} for e, t, n in managers
        ],
        "standings": [
            {
                "rank": r["rank"],
                "entry": r["entry"],
                "team": r["entry_name"],
                "manager": r["player_name"],
                "gw": r["event_total"],
                "total": r["total"],
            }
            for r in league_data["standings"]["results"]
        ],
        "season": {
            str(gw): [
                {
                    "entry": r["entry"],
                    "team": r["team"],
                    "points": r["points"],
                    "total": r["total"],
                    "place": r["place"],
                }
                for r in rows
            ]
            for gw, rows in season.items()
        },
        "positions": {str(k): v for k, v in an.league_position_by_gw(season).items()},
        "gameweeks": gameweeks,
        "players": {str(p): describe(p) for p in sorted(seen)},
        "suggestions": suggestions,
        "horizon": horizon,
        "upcoming": upcoming,
        "reminder": rm.build(league_id, top_fixtures=0),
        "prizes": pz.ledger(season, gameweeks, [
            {
                "rank": r["rank"], "entry": r["entry"], "team": r["entry_name"],
            }
            for r in league_data["standings"]["results"]
        ]),
    }


def write(path, league_id, my_entry, **kw):
    data = snapshot(league_id, my_entry, **kw)
    with open(path, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
    return data
