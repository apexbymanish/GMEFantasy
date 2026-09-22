# Design system

The visual language of the GME Fantasy Board. Every value here is a token in
`dashboard/page.html`; nothing in the page hard-codes a colour.

## Where the colours come from

Sampled from gmeremit.com rather than guessed: `#ED1C24` is the dominant brand
colour there, appearing 73 times across text, backgrounds and gradients. The
site is white-first with generous space, so this page is light-first too.

This is a colleagues' fantasy league, not a GME product. It borrows the palette
and carries no GME logo or wordmark beyond the league's own name.

## The one rule that shapes everything

**Red means identity, not "negative".**

GME red marks the brand, the active tab, your own team, and figures that
genuinely demand action. It is deliberately *not* used for every negative
number: a `-4` transfer hit and a `-60` points gap are ordinary facts, and
painting them red would spend the accent until it stopped meaning anything.
Those sit in secondary ink, where the minus sign does the work.

| Meaning | Token | Used for |
|---|---|---|
| Identity | `--brand` | mark, active tab, your row, your line |
| Needs action | `--brand` | money owed, a captain who blanked |
| Ordinary negative | `--ink-2` | transfer hits, points gaps |
| Good | `--good` | an easy fixture, a settled payment |

## Tokens

Light is the default on bare `:root`. Dark redefines the same names under both
`@media (prefers-color-scheme: dark)` (guarded so an explicit light choice wins)
and `:root[data-theme="dark"]` (so the toggle wins the other way).

| Token | Light | Dark | Role |
|---|---|---|---|
| `--ground` | `#F5F6F8` | `#0E1013` | page behind everything |
| `--surface` | `#FFFFFF` | `#16181D` | cards, tables |
| `--surface-2` | `#EFF1F4` | `#1E2128` | inset fills, bar tracks |
| `--sunken` | `#F8F9FB` | `#121419` | code and message blocks |
| `--ink` | `#16181D` | `#EDEFF3` | primary text |
| `--ink-2` | `#545963` | `#A2A9B6` | secondary text |
| `--ink-3` | `#8A909C` | `#6C7381` | labels, axes, muted figures |
| `--line` | `#E4E7EC` | `#252932` | hairlines |
| `--line-2` | `#CFD4DC` | `#39404D` | control borders |
| `--brand` | `#ED1C24` | `#F0575D` | GME red |
| `--good` | `#0F7B4F` | `#2E9E6B` | positive state |
| `--s2` | `#1F6FD0` | `#5B90EE` | chart series |

Dark is stepped for its own surface, not inverted: the brand red lightens to
`#F0575D` so it still clears contrast on a dark ground.

## Chart palette, validated

Run through the data-viz validator before any chart code was written, not
eyeballed. Both modes pass every check:

| Mode | Steps | Surface | Worst adjacent pair |
|---|---|---|---|
| Light | `#ED1C24` `#1F6FD0` `#0F7B4F` | `#FFFFFF` | ΔE 20.9 deutan, 21.7 normal |
| Dark | `#F0575D` `#5B90EE` `#2E9E6B` | `#16181D` | ΔE 19.5 deutan, 22.0 normal |

An earlier candidate paired teal with green and failed twice: the teal read as
grey (chroma 0.094) and the pair sat at ΔE 10.1 for normal vision, below the
floor of 15. It was cut rather than shipped with a warning.

**Ten managers are never ten colours.** The title race draws your line in brand
red and every rival in `--ink-3`, with each team named at the end of its own
line. Identity comes from the label, so the chart stays readable and colour is
never the only channel.

## Typography

| Role | Face | Notes |
|---|---|---|
| Interface | Archivo 400-800 | headings at 700-800, tight tracking |
| Figures | IBM Plex Mono 400-600 | tabular, so columns line up |

Large single figures (`500,000`) use Archivo, not the mono: monospace gives the
comma a full character slot and the number reads as `500 , 000`.

## Shape and depth

`--r: 10px` for cards and panels, `--r-sm: 7px` for controls and badges.
Shadows are near-invisible in light (`0 1px 2px` at 5% plus `0 1px 3px` at 4%)
and absent in dark, where the surface step carries the separation instead.

Border, fill and shadow are spent by role. A table is one card; its rows are
not cards. Only the standing strip takes a coloured edge, because it is the one
thing about you.

## Mobile

Phone width is the design target, not an afterthought. Breakpoints at 860px
(two columns become one), 640px (phone) and 400px (small phone).

**Column priority.** The gameweek board has nine columns, which no phone fits.
Rather than scrolling sideways, columns marked `.col-opt` are hidden below
640px, leaving rank, team, score, captain and captain points — enough to answer
"who won and what did they captain". The same applies to each wide table:

| Table | Kept on a phone | Dropped |
|---|---|---|
| Gameweek board | rank, team, GW pts, captain, C pts | manager, season, hit, bench |
| Best picks | player, club, price, form, FDR | xGI/90, ownership |
| Prize ledger | GW, winner, amount, status | score |
| Projected winnings | position, team, projected, net | won so far, if frozen |

Every control is at least 38px tall and tabs are 44px, so they are comfortable
to tap. The page never scrolls horizontally; only the season chart does, inside
its own container.

## Keyboard

Shown on the page under `?`, and only offered on devices with a real pointer.

| Key | Action |
|---|---|
| `1` `2` `3` `4` | switch tab |
| `←` `→` | previous / next gameweek |
| `C` | copy the group reminder |
| `E` | download the workbook |
| `?` | this list |

## Installing it

The page builds a web app manifest at runtime and points a `<link rel=manifest>`
at it, so a phone can add it to the home screen and open it without browser
chrome. The icon is an inline SVG crest in brand red; there is no GME logo in it.
