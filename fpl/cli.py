"""Command line interface."""
import argparse
import json
import os
import sys
import time

from . import analysis as an
from . import api
from . import export as export_mod
from . import remind as remind_mod
from . import treasury as tr
from .config import LEAGUE_ID, MY_ENTRY

USE_COLOUR = sys.stdout.isatty()


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else str(text)


bold = lambda t: c(t, "1")
dim = lambda t: c(t, "2")
green = lambda t: c(t, "32")
red = lambda t: c(t, "31")
yellow = lambda t: c(t, "33")
cyan = lambda t: c(t, "36")


def rule(width=72):
    print(dim("-" * width))


def load_league(league_id):
    """League metadata plus the manager list, in standings order."""
    data = api.league(league_id)
    return data["league"]["name"], an.managers(data)


def gw_rows(league_id, gw):
    """Build the weekly table for one gameweek."""
    _, managers = load_league(league_id)
    picks = api.parallel(lambda m: api.picks(m[0], gw), managers)
    points = an.live_points(api.live(gw))
    return managers, an.weekly_table(managers, picks, points), points


def resolve_gw(requested):
    latest = api.latest_played_gw()
    if requested is None:
        return latest
    if requested > latest:
        sys.exit(f"Gameweek {requested} hasn't been played yet (latest is {latest}).")
    return requested


# --- commands -------------------------------------------------------------

def cmd_week(args):
    gw = resolve_gw(args.gameweek)
    name, _ = load_league(args.league)
    _, rows, points = gw_rows(args.league, gw)
    players = an.player_index(api.bootstrap())
    live_now = not api.is_finished(gw)

    status = red(" LIVE") if live_now else ""
    print(f"\n{bold(name)}  ·  Gameweek {bold(gw)}{status}\n")
    print(f"{'#':>2}  {'TEAM':<22} {'PTS':>4} {'HIT':>4} {'BEN':>4}  {'CAPTAIN':<14} {'C.PTS':>5}  CHIP")
    rule()
    for row in rows:
        mine = row["entry"] == args.me
        team = bold(row["team"][:22]) if mine else row["team"][:22]
        pad = " " * (22 - len(row["team"][:22]))
        hit = red(f"-{row['hit']}") if row["hit"] else ""
        chip = yellow(row["chip"].upper()) if row["chip"] else ""
        cap = players[row["captain"]]["web_name"][:14]
        cap_pts = row["captain_points"]
        cap_str = green(f"{cap_pts:>5}") if cap_pts >= 12 else f"{cap_pts:>5}"
        bench = dim(f"{row['bench']:>4}")
        print(
            f"{row['place']:>2}  {team}{pad} {row['points']:>4} {hit:>4} "
            f"{bench}  {cap:<14} {cap_str}  {chip}"
        )

    winner = rows[0]
    print(f"\n{green('Winner')}: {bold(winner['team'])} ({winner['manager']}) — {winner['points']} pts")
    if len(rows) > 1:
        print(f"{dim('Margin')}: {winner['points'] - rows[1]['points']} over {rows[1]['team']}")

    counts = an.ownership(rows)
    print(f"\n{bold('Most-owned starters')}")
    for pid, n in sorted(counts.items(), key=lambda kv: (-kv[1], -points.get(kv[0], 0)))[:6]:
        print(f"  {n}/{len(rows)}  {players[pid]['web_name']:<16} {points.get(pid, 0):>3} pts")

    singles = sorted(
        ((points.get(p, 0), players[p]["web_name"]) for p, n in counts.items() if n == 1),
        reverse=True,
    )[:6]
    if singles:
        print(f"\n{bold('Differentials')} {dim('(one owner only)')}")
        for pts, nm in singles:
            print(f"  {nm:<16} {green(f'{pts:>3}') if pts >= 8 else f'{pts:>3}'} pts")
    print()


def cmd_season(args):
    name, managers = load_league(args.league)
    histories = api.parallel(lambda m: api.history(m[0]), managers)
    season = an.season_table(managers, histories)
    wins = an.weekly_wins(season)

    print(f"\n{bold(name)}  ·  Season so far\n")
    print(f"{'GW':>3}  {'WINNER':<22} {'PTS':>4}   {'LOWEST':<22} {'PTS':>4}   {'AVG':>5}")
    rule()
    for gw in sorted(season):
        rows = season[gw]
        avg = sum(r["points"] for r in rows) / len(rows)
        best, worst = rows[0], rows[-1]
        low = red(f"{worst['points']:>4}")
        top = green(f"{best['team'][:22]:<22}")
        print(
            f"{gw:>3}  {top} {best['points']:>4}   "
            f"{worst['team'][:22]:<22} {low}   {avg:>5.1f}"
        )

    print(f"\n{bold('Gameweek wins')}")
    for team, n in sorted(wins.items(), key=lambda kv: -kv[1]):
        print(f"  {n}  {'*' * n:<6} {team}")

    print(f"\n{bold('League position by gameweek')}")
    positions = an.league_position_by_gw(season)
    gws = sorted(season)
    header = "  ".join(f"{g:>2}" for g in gws)
    print(f"  {'TEAM':<22} {header}")
    rule()
    final = sorted(positions.items(), key=lambda kv: kv[1][gws[-1]])
    for team, by_gw in final:
        line = "  ".join(f"{by_gw[g]:>2}" for g in gws)
        label = bold(team[:22]) if team == args.team_name else team[:22]
        pad = " " * (22 - len(team[:22]))
        print(f"  {label}{pad} {line}")
    print()


def cmd_diff(args):
    gw = resolve_gw(args.gameweek)
    _, rows, points = gw_rows(args.league, gw)
    players = an.player_index(api.bootstrap())
    mine, theirs = an.differentials(rows, args.me, args.max_owners)

    me = next(r for r in rows if r["entry"] == args.me)
    print(f"\n{bold(me['team'])}  ·  Gameweek {gw}  ·  {me['points']} pts, place {me['place']}\n")

    print(bold(f"Your differentials (owned by <= {args.max_owners})"))
    if not mine:
        print(dim("  none — your XI is the league template"))
    for pid in sorted(mine, key=lambda p: -points.get(p, 0)):
        print(f"  {players[pid]['web_name']:<16} {points.get(pid, 0):>3} pts")

    print(f"\n{bold('Differentials you missed')}")
    ranked = sorted(theirs, key=lambda p: -points.get(p, 0))[:10]
    for pid in ranked:
        pts = points.get(pid, 0)
        mark = red(f"{pts:>3}") if pts >= 8 else f"{pts:>3}"
        print(f"  {players[pid]['web_name']:<16} {mark} pts")

    gained = sum(points.get(p, 0) for p in mine)
    lost = sum(points.get(p, 0) for p in ranked[:len(mine) or 1])
    print(f"\n{dim('Your differentials returned')} {gained} pts; "
          f"{dim('the best you missed returned')} {lost} pts\n")


def cmd_players(args):
    boot = api.bootstrap()
    from_gw = api.next_gw()
    results = an.rank_players(
        boot, api.fixtures(), from_gw, horizon=args.horizon, top=args.top
    )

    print(f"\n{bold('Best picks')}  ·  next {args.horizon} gameweeks from GW{from_gw}\n")
    for pos in ("GKP", "DEF", "MID", "FWD"):
        if pos not in results:
            continue
        print(bold(pos))
        print(f"  {'PLAYER':<16} {'TEAM':<5} {'£':>5} {'FORM':>5} {'PPG':>5} {'xGI90':>6} {'FDR':>5} {'OWN%':>6}")
        for p in results[pos]:
            fdr = green(f"{p['fdr']:>5}") if p["fdr"] <= 2.5 else (
                red(f"{p['fdr']:>5}") if p["fdr"] >= 3.6 else f"{p['fdr']:>5}")
            print(
                f"  {p['name']:<16} {p['team']:<5} {p['price']:>5} {p['form']:>5} "
                f"{p['ppg']:>5} {p['xgi90']:>6} {fdr} {p['owned']:>6}"
            )
        print()


def cmd_live(args):
    gw = api.current_gw()
    if api.is_finished(gw) and not args.force:
        print(dim(f"GW{gw} is finished — showing final table."))
    try:
        while True:
            _, rows, _ = gw_rows(args.league, gw)
            print("\033[2J\033[H" if USE_COLOUR else "")
            print(f"{bold('LIVE')}  ·  Gameweek {gw}  ·  {time.strftime('%H:%M:%S')}\n")
            for row in rows:
                mine = row["entry"] == args.me
                team = bold(row["team"][:22]) if mine else row["team"][:22]
                pad = " " * (22 - len(row["team"][:22]))
                print(f"{row['place']:>2}  {team}{pad} {row['points']:>4}")
            if not args.watch or api.is_finished(gw):
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()


def cmd_table(args):
    name, managers = load_league(args.league)
    data = api.league(args.league)
    print(f"\n{bold(name)}\n")
    print(f"{'#':>2}  {'TEAM':<22} {'MANAGER':<20} {'GW':>4} {'TOTAL':>6}")
    rule()
    for row in data["standings"]["results"]:
        mine = row["entry"] == args.me
        team = bold(row["entry_name"][:22]) if mine else row["entry_name"][:22]
        pad = " " * (22 - len(row["entry_name"][:22]))
        print(f"{row['rank']:>2}  {team}{pad} {row['player_name'][:20]:<20} "
              f"{row['event_total']:>4} {row['total']:>6}")
    print()


def cmd_export(args):
    data = export_mod.write(
        args.out, args.league, args.me, horizon=args.horizon, top=args.top,
        paid=_load_paid(_payments_path(args)),
    )
    size = os.path.getsize(args.out) / 1024
    print(f"Wrote {args.out} ({size:.0f} KB)")
    print(f"  {len(data['managers'])} managers, "
          f"gameweeks {data['playedGws'][0]}-{data['playedGws'][-1]}, "
          f"{len(data['players'])} players referenced")


def cmd_remind(args):
    print(remind_mod.build(args.league, top_fixtures=args.fixtures))


def _payments_path(args):
    return args.paid_file


def _load_paid(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return json.load(fh).get("paid", [])


def _save_paid(path, paid):
    with open(path, "w") as fh:
        json.dump({"paid": sorted(set(paid))}, fh, indent=2)


def _snapshot(args):
    with open(args.data) as fh:
        return json.load(fh)


def cmd_books(args):
    snap = _snapshot(args)
    books = tr.summary(snap["prizes"], _load_paid(_payments_path(args)))
    print(f"\n{bold(snap['league']['name'])}  {dim('prize pool')}\n")
    rows = [
        ("Collected", books["collected"]),
        ("Paid out", -books["paidOut"]),
        ("Balance on hand", books["balance"]),
        ("", None),
        ("Due now", books["dueNow"]),
        ("Reserved, future weeks", books["reservedWeekly"]),
        ("Reserved, specials", books["reservedSpecials"]),
        ("Reserved, podium", books["reservedPodium"]),
        ("Total still owed", books["committed"]),
        ("", None),
        ("Unallocated", books["unallocated"]),
    ]
    for label, value in rows:
        if value is None:
            rule(44)
            continue
        colour = red if value < 0 else (green if label == "Balance on hand" else str)
        print(f"  {label:<26} {colour(f'{value:>12,}')} KRW")

    print(f"\n{bold('Weekly prizes')}")
    for line in books["lines"]:
        state = green("PAID") if line["paid"] else red("DUE ")
        tie = dim(" (tie, split)") if line["tied"] else ""
        print(f"  GW{line['gw']:<3} {line['team'][:24]:<24} {line['amount']:>7,} KRW  {state}{tie}")
    print(f"\n  {books['paidCount']} of {books['totalCount']} paid\n")


def cmd_pay(args):
    snap = _snapshot(args)
    path = _payments_path(args)
    paid = set(_load_paid(path))
    lines = {l["id"]: l for l in tr.items(snap["prizes"])}

    targets = [l for l in lines.values() if l["gw"] in args.gameweeks] if args.gameweeks \
        else list(lines.values())
    if not targets:
        sys.exit("No weekly prizes match those gameweeks.")

    changed = []
    for line in targets:
        if args.undo and line["id"] in paid:
            paid.discard(line["id"]); changed.append(("unpaid", line))
        elif not args.undo and line["id"] not in paid:
            paid.add(line["id"]); changed.append(("paid", line))

    _save_paid(path, paid)
    if not changed:
        print("Nothing to change.")
    for action, line in changed:
        word = green("marked paid") if action == "paid" else yellow("marked unpaid")
        print(f"  GW{line['gw']} {line['team']:<24} {line['amount']:>7,} KRW  {word}")
    books = tr.summary(snap["prizes"], paid)
    print(f"\n  Balance on hand {bold(format(books['balance'], ','))} KRW"
          f"  |  due now {books['dueNow']:,} KRW")


def cmd_excel(args):
    from . import excel as xl
    snap = _snapshot(args)
    books = xl.build(snap, _load_paid(_payments_path(args)), args.out)
    size = os.path.getsize(args.out) / 1024
    print(f"Wrote {args.out} ({size:.0f} KB)")
    print(f"  5 sheets · {books['totalCount']} weekly prizes · "
          f"{books['paidCount']} paid · {books['balance']:,} KRW on hand")


def cmd_serve(args):
    """Serve the built dashboard so a browser can open it."""
    import functools
    import http.server
    import socketserver
    import webbrowser

    root = os.path.dirname(os.path.abspath(args.data)) or "."
    if not os.path.exists(os.path.join(root, "index.html")):
        sys.exit(f"No index.html in {root}. Run: python3 -m fpl export && python3 dashboard/build.py")

    http.server.SimpleHTTPRequestHandler.extensions_map[".js"] = "text/javascript"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    socketserver.TCPServer.allow_reuse_address = True
    url = f"http://127.0.0.1:{args.port}/index.html"
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"\n  {bold(url)}\n  serving {root}  ({dim('ctrl-c to stop')})\n")
        if args.open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fpl", description="FPL mini-league analyzer")
    parser.add_argument("--league", type=int, default=LEAGUE_ID, help="league id")
    parser.add_argument("--me", type=int, default=MY_ENTRY, help="your entry id")
    parser.add_argument("--data", default="dashboard/data.json", help="snapshot file")
    parser.add_argument("--paid-file", default="dashboard/payments.json",
                        help="record of prizes already paid")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("table", help="current league standings")
    p.set_defaults(func=cmd_table)

    p = sub.add_parser("week", help="one gameweek, everyone's squad and captain")
    p.add_argument("gameweek", nargs="?", type=int)
    p.set_defaults(func=cmd_week)

    p = sub.add_parser("season", help="every gameweek: winners, lowest, position trend")
    p.set_defaults(func=cmd_season, team_name=None)

    p = sub.add_parser("diff", help="your differentials vs the league")
    p.add_argument("gameweek", nargs="?", type=int)
    p.add_argument("--max-owners", type=int, default=1)
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("players", help="best players to buy, by fixtures and form")
    p.add_argument("--horizon", type=int, default=3, help="fixtures to look ahead")
    p.add_argument("--top", type=int, default=8)
    p.set_defaults(func=cmd_players)

    p = sub.add_parser("export", help="write a JSON snapshot for the dashboard")
    p.add_argument("--out", default="dashboard/data.json")
    p.add_argument("--horizon", type=int, default=3)
    p.add_argument("--top", type=int, default=8)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("remind", help="paste-ready deadline reminder for the group chat")
    p.add_argument("--fixtures", type=int, default=4, help="0 for all fixtures")
    p.set_defaults(func=cmd_remind)

    p = sub.add_parser("books", help="prize pool: paid, due and remaining")
    p.set_defaults(func=cmd_books)

    p = sub.add_parser("pay", help="mark weekly prizes as paid")
    p.add_argument("gameweeks", nargs="*", type=int, help="gameweeks to settle (default: all due)")
    p.add_argument("--undo", action="store_true", help="mark them unpaid again")
    p.set_defaults(func=cmd_pay)

    p = sub.add_parser("excel", help="write the books to a workbook")
    p.add_argument("--out", default="GME-fantasy-books.xlsx")
    p.set_defaults(func=cmd_excel)

    p = sub.add_parser("serve", help="run the dashboard on localhost")
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--open", action="store_true", help="open it in your browser")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("live", help="live gameweek scores")
    p.add_argument("--watch", action="store_true", help="refresh until the gameweek ends")
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_live)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except api.NotAvailable as exc:
        sys.exit(f"Not available yet: {exc}")


if __name__ == "__main__":
    main()
