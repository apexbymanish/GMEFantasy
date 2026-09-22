# FPL Mini-League Analyzer — Design

*2026-09-22*

## Problem

A 10-manager FPL mini-league has no good way to see itself. The official site
shows a standings table and nothing else: no gameweek winners, no history of the
title race, no way to see what a rival owns that you don't.

## Data source

The public FPL API, `https://fantasy.premierleague.com/api/`. No key required.

| Data | Endpoint | Notes |
|---|---|---|
| Players, teams, gameweek states | `bootstrap-static/` | ~1.7MB, 667 players × 109 fields incl. xG, xA, ICT, ownership |
| Fixtures and difficulty | `fixtures/` | FDR 1–5 per side |
| League standings | `leagues-classic/{id}/standings/` | paginated at 50; our league has 10 |
| A manager's season | `entry/{id}/history/` | gameweek-by-gameweek + chips |
| A manager's squad in one gameweek | `entry/{id}/event/{gw}/picks/` | **one call per manager per gameweek** |
| Player points in one gameweek | `event/{gw}/live/` | one call covers everyone |

Three constraints drove the design:

1. **Standings do not include squads.** To compare teams you must call `picks`
   once per manager. 10 managers × 38 gameweeks = 380 calls for a full season.
2. **The API sends no CORS headers.** A browser-only app cannot call it. Not a
   problem for a CLI; it is the deciding constraint if this becomes a web app.
3. **Future gameweeks return 404.** Valid range must be read from
   `bootstrap-static → events` (`is_current`, `is_next`, `finished`).

## Architecture

Three layers, each testable on its own.

```
fpl/api.py       fetch + cache      (the only code that touches the network)
fpl/analysis.py  pure functions     (no I/O at all)
fpl/cli.py       formatting         (argparse + terminal output)
```

### Caching

This is the load-bearing decision. **A finished gameweek is immutable**, so its
`picks` and `live` data are cached permanently on disk. Only the gameweek in
progress is re-fetched, and at most once a minute.

| Data | TTL |
|---|---|
| `bootstrap-static` | 1 hour |
| `fixtures` | 1 day |
| `picks`, `live` — finished gameweek | forever |
| `picks`, `live` — current gameweek | 60s |
| standings, history | 5 min |

Result: a cold run makes ~13 calls; a warm run makes none and completes in 0.4s.
Rivals are fetched concurrently with a 10-worker thread pool.

### Analysis

Pure functions taking already-fetched dicts. Key decisions:

- **Weekly rank is net of transfer hits.** Gross points decide nothing; a -4 has
  swung a gameweek in this league already.
- **Ownership counts starters only** (picks 1–11). A benched player contributes
  nothing, so counting the full 15 would misreport how "template" a squad is —
  except under Bench Boost, which is accepted as a known simplification.
- **Player scoring is normalised within position.** Defenders would otherwise
  lose to strikers on attacking numbers. Weighting: form 30%, points-per-game
  20%, xGI/90 20%, fixture ease 20%, value 10%.
- **Availability filter:** `status == "a"` and `chance_of_playing_next_round`
  either null or ≥ 75, plus a minimum-minutes floor, plus exclusion of teams
  with no fixture in the window (blank gameweeks).

## Testing

The analysis layer is pure, so it is tested against hand-built fixture data with
no network. 29 tests covering: hit-adjusted ranking, captain doubling, starter
vs. squad ownership, differential detection, cumulative league position, fixture
difficulty windows, normalisation of flat inputs, and every availability filter.

## Known limitations

- Bench Boost weeks are not special-cased in ownership counts.
- Player scoring ignores set-piece duty, rotation risk and double gameweeks.
- No authentication, so it cannot read your team before a deadline — only
  squads that are already locked in.

## If this becomes a web app

`api.py` and `analysis.py` move behind HTTP routes unchanged. The server-side
fetch also solves the CORS block. The cache becomes shared rather than per-user,
which makes it strictly cheaper.
