"""Build a plain-text deadline reminder to paste into the league's group chat.

Plain text on purpose: it has to survive KakaoTalk, WhatsApp and Viber, none
of which render markdown.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import analysis as an
from . import api
from . import prizes as pz

ZONES = [("KST", "Asia/Seoul"), ("NPT", "Asia/Kathmandu")]


def _countdown(deadline):
    ms = deadline - datetime.now(timezone.utc)
    if ms.total_seconds() <= 0:
        return "deadline passed"
    days = ms.days
    hours = ms.seconds // 3600
    if days:
        return f"{days} days {hours} hours left"
    return f"{hours} hours {(ms.seconds // 60) % 60} minutes left"


def flagged_players(boot, squads):
    """Players owned by someone in the league who are injured or doubtful."""
    players = an.player_index(boot)
    teams = an.team_index(boot)
    out = []
    for pid, owners in squads.items():
        p = players.get(pid)
        if not p or an.is_available(p):
            continue
        chance = p["chance_of_playing_next_round"]
        out.append(
            {
                "name": p["web_name"],
                "team": teams[p["team"]]["short_name"],
                "owners": owners,
                "chance": chance,
                "news": (p["news"] or "").strip(),
            }
        )
    out.sort(key=lambda r: (-r["owners"], r["name"]))
    return out


def build(league_id, top_fixtures=4):
    boot = api.bootstrap()
    gw = api.next_gw()
    event = next(e for e in boot["events"] if e["id"] == gw)
    deadline = datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))

    league_data = api.league(league_id)
    managers = an.managers(league_data)
    standings = league_data["standings"]["results"]

    last = api.latest_played_gw()
    picks = api.parallel(lambda m: api.picks(m[0], last), managers)
    squads = {}
    for pick in picks:
        for entry in pick["picks"]:
            squads[entry["element"]] = squads.get(entry["element"], 0) + 1

    teams = an.team_index(boot)
    games = sorted(
        (f for f in api.fixtures() if f["event"] == gw),
        key=lambda f: f["kickoff_time"] or "",
    )

    lines = []
    add = lines.append
    add(f"GME FANTASY LEAGUE - GAMEWEEK {gw}")
    add("")
    for label, zone in ZONES:
        local = deadline.astimezone(ZoneInfo(zone))
        add(f"Deadline {label}: {local.strftime('%a %d %b, %I:%M %p').lstrip('0')}")
    add(f"({_countdown(deadline)})")
    add("")
    add(f"{pz.weekly_prize(gw):,} KRW to the highest score this week.")
    add("")

    add("TABLE")
    for row in standings:
        add(f"{row['rank']:>2}. {row['entry_name'][:20]:<20} {row['total']:>4}")
    add("")

    flags = flagged_players(boot, squads)
    if flags:
        add("FLAGGED IN OUR SQUADS - CHECK BEFORE THE DEADLINE")
        for f in flags[:8]:
            chance = "out" if f["chance"] in (0, None) else f"{f['chance']}%"
            add(f"  {f['name']} ({f['team']}) - {chance} - owned by {f['owners']}")
        add("")

    add(f"GW{gw} FIXTURES")
    for f in games[:top_fixtures] if top_fixtures else games:
        ko = datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00"))
        local = ko.astimezone(ZoneInfo(ZONES[0][1]))
        add(f"  {local.strftime('%a %d %b %H:%M')}  "
            f"{teams[f['team_h']]['short_name']} v {teams[f['team_a']]['short_name']}")
    if top_fixtures and len(games) > top_fixtures:
        add(f"  ...and {len(games) - top_fixtures} more")
    add("")
    add("Set your team and captain before the deadline.")
    return "\n".join(lines)
