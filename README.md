# FPL Mini-League Analyzer

**Live: https://apexbymanish.github.io/GMEFantasy/**

Open it and pick your team from the menu in the top right; the board then shows
your position, your differentials and what you are owed. Until then it shows
the league.

A terminal tool for analysing a Fantasy Premier League mini-league: who won each
gameweek, how the table moved, which players are differentials, and who to buy next.

Built for **GME Fantasy League** (`478017`), but it works for any classic league.

## Install

Python 3.9+. No dependencies for the tool itself; `pytest` only for the tests.

```sh
git clone <this repo> && cd fpl-analyzer
python3 -m fpl table
```

## Commands

```sh
python3 -m fpl table            # current standings
python3 -m fpl week             # latest finished gameweek
python3 -m fpl week 4           # a specific gameweek
python3 -m fpl season           # every gameweek: winners, lowest, position trend
python3 -m fpl diff 5           # your differentials vs the league
python3 -m fpl players          # best players to buy, next 3 gameweeks
python3 -m fpl players --horizon 6 --top 12
python3 -m fpl live --watch     # refresh during matches
```

### Pointing it at a different league

```sh
python3 -m fpl --league 123456 --me 6144939 table
# or set them once:
export FPL_LEAGUE=123456 FPL_ENTRY=6144939
```

Find your entry id in the URL when you view your team on the FPL site.

## What each command tells you

**`week`** — the battle view. Every manager's net score, transfer hit, bench
points, captain and chip, sorted by who actually won. Then the most-owned
starters in your league, and the players only one manager fielded.

**`season`** — the weekly winner and the weakest score for every gameweek, a
tally of gameweek wins, and a grid showing each team's league position over time.

**`diff`** — the players in your XI that nobody else fielded, the best ones you
missed, and what each set returned.

**`players`** — every available player scored within their position on form,
points per game, expected goal involvement per 90, upcoming fixture difficulty
and value. Injured, doubtful, low-minutes and blank-gameweek players are excluded.

## Data source

The public FPL API at `https://fantasy.premierleague.com/api/`. No key, no
signup. It is undocumented and unofficial, so this tool caches aggressively:
a finished gameweek never changes, so its data is cached permanently. Only the
live gameweek is re-fetched, at most once a minute.

Cache lives in `~/.cache/fpl-analyzer` (override with `FPL_CACHE`). Delete it to
force a refresh.

## Design

The palette, type, mobile column priorities and keyboard shortcuts are
documented in [docs/DESIGN.md](docs/DESIGN.md). The architecture and data
sources are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```sh
python3 -m pytest tests/ -q
```

63 tests, no network — the analysis layer is pure functions over fixture data.

## Dashboard

The API sends no CORS headers, so a browser page cannot call it directly. The
dashboard therefore ships with a snapshot of the league baked in:

```sh
python3 -m fpl export          # writes dashboard/data.json
python3 dashboard/build.py     # inlines it into dashboard/index.html
```

Then run it:

```sh
python3 -m fpl serve --open      # http://127.0.0.1:8777
```

Re-run the export and build after each gameweek.

The page adapts to where it runs. Published as an artifact it records payments
in the artifact's own store, so everyone you share it with sees the same ledger.
On localhost there is no such store, so it falls back to this browser's storage
and an ordinary file download. The page says which one it is using.

## Prize pool

`fpl/prizes.py` encodes the league's own prize sheet (10 players, 50,000 KRW
entry, 500,000 KRW pool). The dashboard shows money banked from weekly wins and
what today's table would pay if the season froze.

Two readings the sheet leaves open, both surfaced rather than silently decided:

- **Ties.** The sheet does not say how a tied gameweek is settled, so the pot is
  shown split and flagged. GW1 was tied.
- **Which score counts.** The lowest-score award says hits are excluded, so it
  is judged on gross points. The highest-score award carries no such note, so it
  is judged on the net score the game itself reports.

## Reminders

```sh
python3 -m fpl remind        # plain text for the group chat
```

Deadline in KST and NPT, the table, every flagged player in the league's squads,
and the fixtures. Plain text so it survives KakaoTalk, WhatsApp and Viber.

## The books

The pool is collected up front, so every prize is already funded. What changes
over the season is how much has actually been handed over.

```sh
python3 -m fpl books            # collected, paid, due, reserved, balance
python3 -m fpl pay 6            # mark GW6 paid, dated today
python3 -m fpl pay 6 --on 2026-10-14 --note "bank transfer"
python3 -m fpl pay 6 --undo     # mark it unpaid again
python3 -m fpl excel            # five-sheet workbook
```

`unallocated` must always read zero: balance on hand minus everything still
owed. A non-zero figure means the prize sheet no longer adds up to the pool.

### Payment history

`payments.json` is the record, and it is committed. It is a history, not a
list: every change appends a line, nothing is overwritten, and a prize's latest
line is its current state. `fpl pay` writes it, or edit it by hand:

```json
{"id": "gw6-1844688", "status": "paid", "on": "2026-10-14", "note": "bank transfer"}
```

The id is `gw<gameweek>-<entry id>`, as `fpl books` lists them. To reverse a
payment, append a line with `"status": "unpaid"`; do not delete the old one.
It holds entry ids, team names and amounts only, never real names.

Push the change and the site updates within a few minutes (see below).
Payments toggled on the public page itself stay in that visitor's browser.


## Publishing

The site is GitHub Pages, served from `docs/`. It updates itself:
`.github/workflows/publish.yml` runs the export and build on GitHub and commits
`docs/index.html` when anything changed. It runs

- every 3 hours,
- whenever `payments.json` is pushed,
- and on demand: **Actions → Publish → Run workflow**.

A run that finds nothing new commits nothing. While a gameweek is live the site
can trail the real scores by up to 3 hours, and the header says "live, not final".

GitHub pauses scheduled workflows on a repo with no commits for 60 days; the
workflow's own commits keep it awake during the season.

To publish by hand instead:

```sh
python3 -m fpl export
python3 dashboard/build.py
git add docs && git commit -m "Through GW6" && git push
```

### What is public and what is not

The site is public, so `dashboard/build.py` writes two different pages:

| File | Data | Where it goes |
|---|---|---|
| `dashboard/index.html` | full, **including managers' real names** | local only, git-ignored |
| `docs/index.html` | same page, real names removed | GitHub Pages |

Team names are pseudonyms the managers chose and are already visible on the
FPL site; their real names are not. `dashboard/data.json` is git-ignored for
the same reason — regenerate it with `fpl export`.

Payments marked on the public site are stored in each visitor's own browser,
so they are not shared. `payments.json` is the real record.
