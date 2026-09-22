"use strict";

const D = JSON.parse(document.getElementById("fpl-data").textContent);
const Z = D.prizes;
const P = D.players;
const GWS = D.playedGws;

/* Who is looking. The board belongs to the league, not to one manager, so
   nobody is assumed: personal panels stay dark until a team is picked, and
   the choice lives in this browser. */
const WHO_KEY = "gme-who-v1";
let ME = (() => {
  try {
    const saved = localStorage.getItem(WHO_KEY);
    if (saved && D.managers.some(m => String(m.entry) === saved)) return +saved;
  } catch (e) { /* private mode */ }
  return null;
})();
const picked = () => ME != null;
const myRow = () => D.standings.find(s => s.entry === ME);
const HAS_NAMES = D.managers.some(m => m.manager);

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
const krw = n => n.toLocaleString("en-US");
const ord = n => n + (["th", "st", "nd", "rd"][(n % 100 - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");
const fdrBand = v => (v <= 2 ? "easy" : v >= 4 ? "hard" : "mid");

/* Capabilities exist only inside the claude.ai viewer. On localhost the page
   falls back to browser storage and an ordinary download, so it works either way. */
const capability = async name =>
  (window.claude && window.claude.use) ? await window.claude.use(name) : null;

/* ---------------- tabs ---------------- */
const TABS = [
  { id: "overview", label: "Overview" },
  { id: "gameweeks", label: "Gameweeks" },
  { id: "planning", label: "Planning" },
  { id: "money", label: "Money" },
];
const tabBar = $("tabs");
tabBar.innerHTML = TABS.map((t, i) =>
  `<button role="tab" data-tab="${t.id}" aria-selected="${i === 0}"
     aria-controls="tab-${t.id}">${t.label}</button>`).join("");

function showTab(id) {
  TABS.forEach(t => { $("tab-" + t.id).hidden = t.id !== id; });
  tabBar.querySelectorAll("button").forEach(b =>
    b.setAttribute("aria-selected", b.dataset.tab === id));
  try { localStorage.setItem("gme-tab", id); } catch (e) { /* private mode */ }
  window.scrollTo({ top: 0, behavior: "instant" });
}
tabBar.addEventListener("click", e => {
  const b = e.target.closest("button[data-tab]");
  if (b) showTab(b.dataset.tab);
});
try {
  const saved = localStorage.getItem("gme-tab");
  if (saved && TABS.some(t => t.id === saved)) showTab(saved);
} catch (e) { /* private mode */ }

/* ---------------- who is looking ---------------- */
const who = $("who");
who.innerHTML = '<option value="">Everyone</option>' +
  D.standings.map(s => `<option value="${s.entry}">${esc(s.team)}</option>`).join("");
who.value = picked() ? String(ME) : "";
who.dataset.picked = picked() ? "1" : "0";
who.addEventListener("change", () => {
  ME = who.value ? +who.value : null;
  who.dataset.picked = picked() ? "1" : "0";
  try {
    picked() ? localStorage.setItem(WHO_KEY, String(ME)) : localStorage.removeItem(WHO_KEY);
  } catch (e) { /* private mode */ }
  renderAll();
});

/* ---------------- header ---------------- */
$("league-name").textContent = D.league.name;
$("league-sub").textContent = `${D.managers.length} managers, gameweek ${D.currentGw} of 38`;
$("gen-time").textContent = new Date(D.generated)
  .toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

const deadline = D.nextDeadline ? new Date(D.nextDeadline) : null;
$("deadline-label").textContent = `GW${D.nextGw} deadline`;
function tick() {
  if (!deadline) return;
  const ms = deadline - new Date();
  if (ms <= 0) { $("countdown").textContent = "closed"; return; }
  const d = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24, m = Math.floor(ms / 6e4) % 60;
  $("countdown").textContent = d > 0
    ? `${d}d ${String(h).padStart(2, "0")}h`
    : `${h}h ${String(m).padStart(2, "0")}m`;
}
tick(); setInterval(tick, 30000);

/* ---------------- headline card and stats ---------------- */
// Numbers that describe the league, true for everyone looking.
const leagueFacts = (() => {
  let high = null, low = null, total = 0, count = 0;
  GWS.forEach(gw => D.gameweeks[gw].rows.forEach(r => {
    total += r.points; count++;
    if (!high || r.points > high.points) high = { ...r, gw };
    if (!low || r.gross < low.gross) low = { ...r, gw };
  }));
  return { high, low, average: count ? total / count : 0 };
})();

function renderStanding() {
  const leader = D.standings[0];
  $("pick-prompt-block").hidden = picked();

  if (!picked()) {
    const chasing = D.standings[1];
    $("standing").innerHTML = `
      <div class="pos num">1<sup>st</sup></div>
      <div class="who">
        <h2>${esc(leader.team)}</h2>
        <p>leads on ${leader.total} points after ${GWS.length}
           gameweek${GWS.length === 1 ? "" : "s"}</p>
      </div>
      <div class="verdict">
        ${chasing ? `<b>${esc(chasing.team)}</b> is ${leader.total - chasing.total} behind. ` : ""}
        The highest single week so far is <b>${leagueFacts.high.points}</b>
        by ${esc(leagueFacts.high.team)} in GW${leagueFacts.high.gw}.
      </div>`;
    return;
  }

  const me = myRow();
  const weeks = GWS.map(gw => D.season[gw].find(r => r.entry === ME));
  const rows = GWS.map(gw => D.gameweeks[gw].rows.find(r => r.entry === ME));
  const best = weeks.reduce((x, y) => (y.points > x.points ? y : x));
  const worst = weeks.reduce((x, y) => (y.points < x.points ? y : x));
  const gap = leader.total - me.total;
  const benched = rows.reduce((t, r) => t + r.bench, 0);
  const hits = rows.reduce((t, r) => t + r.hit, 0);
  $("standing").innerHTML = `
    <div class="pos num">${me.rank}<sup>${ord(me.rank).slice(String(me.rank).length)}</sup></div>
    <div class="who">
      <h2>${esc(me.team)}</h2>
      <p>${HAS_NAMES && me.manager ? esc(me.manager) + " &middot; " : ""}${me.total} points &middot;
         ${gap === 0 ? "leading the league" : `${gap} behind ${esc(leader.team)}`}</p>
    </div>
    <div class="verdict">
      Best week <b>GW${GWS[weeks.indexOf(best)]} (${best.points})</b>,
      worst <b>GW${GWS[weeks.indexOf(worst)]} (${worst.points})</b>.
      Left <b>${benched} points on the bench</b> and paid <b>${hits} in hits</b>.
    </div>`;
}

function renderStats() {
  const f = leagueFacts;
  const cards = picked() ? (() => {
    const me = myRow();
    const weeks = GWS.map(gw => D.season[gw].find(r => r.entry === ME));
    const rows = GWS.map(gw => D.gameweeks[gw].rows.find(r => r.entry === ME));
    const best = weeks.reduce((x, y) => (y.points > x.points ? y : x));
    const gap = D.standings[0].total - me.total;
    const wins = GWS.filter(gw => D.gameweeks[gw].rows[0].entry === ME).length;
    return [
      { k: "Position", v: me.rank, n: `of ${D.managers.length}` },
      { k: "Total points", v: me.total, n: `${(me.total / GWS.length).toFixed(1)} per week` },
      { k: "Gap to top", v: gap === 0 ? "-" : "&minus;" + gap,
        n: gap === 0 ? "you lead" : esc(D.standings[0].team), cls: gap === 0 ? "good" : "bad" },
      { k: "Best gameweek", v: best.points, n: `gameweek ${GWS[weeks.indexOf(best)]}` },
      { k: "Left on bench", v: rows.reduce((t, r) => t + r.bench, 0), n: "never counted" },
      { k: "Gameweeks won", v: wins,
        n: `avg finish ${(rows.reduce((t, r) => t + r.place, 0) / rows.length).toFixed(1)}` },
    ];
  })() : [
    { k: "Leader", v: D.standings[0].total, n: esc(D.standings[0].team) },
    { k: "Gameweeks played", v: GWS.length, n: `of 38` },
    { k: "Highest week", v: f.high.points, n: `${esc(f.high.team)}, GW${f.high.gw}` },
    { k: "Lowest week", v: f.low.gross, n: `${esc(f.low.team)}, GW${f.low.gw}` },
    { k: "League average", v: f.average.toFixed(1), n: "points per manager per week" },
    { k: "Still to win", v: krw(Z.weeklyRemaining), n: "KRW in weekly prizes", cls: "money" },
  ];
  $("stats").innerHTML = cards.map(t => `<div class="stat"><div class="k">${t.k}</div>
    <div class="v ${t.cls === "money" ? "money" : "num"} ${t.cls && t.cls !== "money" ? t.cls : ""}">${t.v}</div>
    <div class="n">${t.n}</div></div>`).join("");
}

/* ---------------- title race ---------------- */
const N = D.managers.length;
// The plot widens with the season so gameweeks never crowd; the panel scrolls.
const PLOT_W = Math.max(320, 15 * Math.max(1, GWS.length - 1));
const VB = { w: 34 + PLOT_W + 268, h: 40 + N * 27, l: 34, r: 268, t: 26, b: 30 };
const STEP = Math.max(1, Math.ceil(30 / (PLOT_W / Math.max(1, GWS.length - 1))));
const px = i => VB.l + (GWS.length === 1 ? 0 : i * PLOT_W / (GWS.length - 1));
const py = pos => VB.t + (pos - 1) * ((VB.h - VB.t - VB.b) / Math.max(1, N - 1));

function renderBump() {
  const series = D.managers.map(m => {
    const mine = D.positions[m.entry] || {};
    // A manager who joined mid-season has no position for the earlier
    // gameweeks: start a new segment rather than drawing through the gap.
    let path = "", open = false, lastGw = null;
    GWS.forEach((gw, i) => {
      const pos = mine[gw];
      if (pos == null) { open = false; return; }
      path += `${open ? "L" : "M"}${px(i).toFixed(1)},${py(pos).toFixed(1)}`;
      open = true; lastGw = gw;
    });
    return {
      entry: m.entry, team: m.team, path,
      pts: GWS.map(gw => D.season[gw].find(r => r.entry === m.entry)),
      final: lastGw == null ? null : mine[lastGw],
      lastIndex: lastGw == null ? -1 : GWS.indexOf(lastGw),
      played: Object.keys(mine).length,
    };
  }).filter(t => t.played > 0);

  const legend = document.querySelector(".legend");
  if (legend) legend.style.display = picked() ? "" : "none";

  let s = `<svg viewBox="0 0 ${VB.w} ${VB.h}" role="img" aria-label="League position by gameweek">`;
  for (let p = 1; p <= N; p++) {
    s += `<line x1="${VB.l}" y1="${py(p)}" x2="${VB.w - VB.r + 6}" y2="${py(p)}" stroke="var(--line)" stroke-width="1"/>`;
    s += `<text x="${VB.l - 9}" y="${py(p) + 4}" text-anchor="end" font-size="11" fill="var(--ink-3)"
           font-family="IBM Plex Mono, monospace">${p}</text>`;
  }
  GWS.forEach((gw, i) => {
    // Always label the last gameweek, and drop any stepped label that would
    // land on top of it.
    const last = i === GWS.length - 1;
    if (!last && (i % STEP !== 0 || GWS.length - 1 - i < STEP)) return;
    s += `<text x="${px(i)}" y="${VB.h - 9}" text-anchor="middle" font-size="11" fill="var(--ink-3)"
           font-family="IBM Plex Mono, monospace">GW${gw}</text>`;
  });
  series.forEach(t => {
    const mine = picked() && t.entry === ME;
    s += `<path class="bump-line" data-e="${t.entry}" d="${t.path}"
           stroke="${mine ? "var(--s1)" : "var(--ink-3)"}" stroke-width="${mine ? 2.5 : 1.6}"/>`;
  });
  series.forEach(t => {
    const mine = picked() && t.entry === ME, cx = px(t.lastIndex), cy = py(t.final);
    s += `<circle cx="${cx}" cy="${cy}" r="${mine ? 4.5 : 3.5}"
           fill="${mine ? "var(--s1)" : "var(--ink-3)"}" stroke="var(--surface)" stroke-width="2"/>`;
    s += `<text x="${cx + 12}" y="${cy + 4}" font-size="12.5" font-family="Archivo, sans-serif"
           font-weight="${mine ? 700 : 500}" fill="${mine ? "var(--s1)" : "var(--ink-2)"}">${esc(t.team)}</text>`;
  });
  series.forEach(t => {
    s += `<path class="bump-hit" data-e="${t.entry}" d="${t.path}"><title>${esc(t.team)}</title></path>`;
  });
  $("bump-scroll").innerHTML = s + `</svg>`;

  const svg = $("bump-scroll").querySelector("svg"), tip = $("bump-tip");
  const wrap = svg.closest(".tipwrap");
  const highlight = entry => {
    svg.classList.toggle("dim", entry != null);
    svg.querySelectorAll(".bump-line").forEach(n => n.classList.toggle("on", n.dataset.e == entry));
  };
  svg.querySelectorAll(".bump-hit").forEach(hit => {
    const show = ev => {
      const t = series.find(x => x.entry == hit.dataset.e);
      highlight(t.entry);
      const r = wrap.getBoundingClientRect();
      const last = t.pts.filter(Boolean).pop();
      tip.innerHTML = `<b>${esc(t.team)}</b> &middot; ${ord(t.final)}<br>
        <span class="num">${last ? last.total : 0} pts</span>`;
      tip.style.left = (ev.clientX - r.left) + "px";
      tip.style.top = (ev.clientY - r.top) + "px";
      tip.classList.add("on");
    };
    hit.addEventListener("pointermove", show);
    hit.addEventListener("pointerenter", show);
    hit.addEventListener("pointerleave", () => { highlight(null); tip.classList.remove("on"); });
  });

  let rows = `<table><thead><tr><th>Team</th>` +
    GWS.map(g => `<th class="r">GW${g}</th>`).join("") + `</tr></thead><tbody>`;
  series.slice().sort((a, b) => a.final - b.final).forEach(t => {
    const mine = D.positions[t.entry] || {};
    rows += `<tr class="${t.entry === ME ? "me" : ""}"><td class="team">${esc(t.team)}</td>` +
      GWS.map(g => `<td class="r num">${mine[g] == null ? "-" : mine[g]}</td>`).join("") + `</tr>`;
  });
  $("bump-table").innerHTML = rows + `</tbody></table>`;
}

/* ---------------- gameweek board ---------------- */
let activeGw = GWS[GWS.length - 1];
const gwChips = $("gw-chips");
gwChips.innerHTML = GWS.map(g =>
  `<button class="chip" data-gw="${g}" aria-pressed="${g === activeGw}">GW${g}</button>`).join("");
gwChips.addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  activeGw = +b.dataset.gw;
  gwChips.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", c === b));
  renderGw();
});

function renderGw() {
  const g = D.gameweeks[activeGw], rows = g.rows, win = rows[0];
  const margin = rows.length > 1 ? win.points - rows[1].points : 0;
  const totals = Object.fromEntries(D.season[activeGw].map(x => [x.entry, x.total]));

  $("gw-caption").innerHTML = `<b>${esc(win.team)}</b> won with ${win.points}` +
    (margin ? `, ${margin} clear of ${esc(rows[1].team)}` : "") +
    `. <b>GW</b> is that week; <b>Season</b> is the running total.`;

  let t = `<table><thead><tr><th>#</th><th>Team</th>${HAS_NAMES ? '<th class="col-opt">Manager</th>' : ""}
    <th class="r">GW</th><th class="r col-opt">Season</th><th class="r col-opt">Hit</th>
    <th class="r col-opt">Bench</th><th>Captain</th><th class="r">C pts</th></tr></thead><tbody>`;
  rows.forEach(r => {
    const cap = P[r.captain];
    t += `<tr class="${r.entry === ME ? "me" : ""}">
      <td class="rank num">${r.place}</td>
      <td class="team">${esc(r.team)}${r.place === 1 ? ' <span class="badge win">win</span>' : ""}
        ${r.chip ? `<span class="badge alt">${esc(r.chip)}</span>` : ""}</td>
      ${HAS_NAMES ? `<td class="col-opt" style="color:var(--ink-3)">${esc(r.manager)}</td>` : ""}
      <td class="r num" style="font-weight:700">${r.points}</td>
      <td class="r num col-opt" style="color:var(--ink-2)">${totals[r.entry] ?? "-"}</td>
      <td class="r num col-opt ${r.hit ? "neg" : "zero"}">${r.hit ? "&minus;" + r.hit : "-"}</td>
      <td class="r num col-opt ${r.bench >= 10 ? "alert" : "zero"}">${r.bench}</td>
      <td>${cap ? esc(cap.name) : "-"}</td>
      <td class="r num ${r.captainPoints === 0 ? "alert" : ""}">${r.captainPoints}</td>
    </tr>`;
  });
  $("gw-table").innerHTML = t + `</tbody></table>`;

  const max = Math.max(...rows.map(r => r.points));
  $("gw-bars").innerHTML = rows.map(r => `
    <div class="bar-row ${r.entry === ME ? "me" : ""}">
      <span class="nm">${esc(r.team)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.max(2, r.points / max * 100)}%"></span></span>
      <span class="val num">${r.points}</span>
    </div>`).join("");

  renderPitch();
  renderDiff();
}

function renderDiff() {
  const g = D.gameweeks[activeGw], own = g.ownership, pts = g.playerPoints;
  const item = p => {
    const pl = P[p] || { name: "?", team: "", pos: "" };
    return `<li><span class="pos">${pl.pos}</span><span>${esc(pl.name)}</span>
      <span class="club">${esc(pl.team)}</span><span class="p">${pts[p] || 0}</span></li>`;
  };
  const byPoints = (a, b) => (pts[b] || 0) - (pts[a] || 0);

  if (!picked()) {
    // Nobody has claimed a team, so answer the league-wide question instead:
    // who gambled, and what did everyone own in common.
    const owners = {};
    g.rows.forEach(r => r.starters.forEach(id => {
      (owners[id] = owners[id] || []).push(r.team);
    }));
    const solo = Object.keys(own).filter(p => own[p] === 1).sort(byPoints).slice(0, 8);
    const template = Object.keys(own).sort((a, b) => own[b] - own[a] || byPoints(a, b)).slice(0, 8);

    $("diff-caption").innerHTML = `Gameweek ${activeGw}. ${solo.length} player${solo.length === 1 ? " was" : "s were"}
      started by exactly one manager.`;
    $("diff-mine-head").textContent = "Started by one manager only";
    $("diff-theirs-head").textContent = "What almost everyone owned";
    $("diff-mine").innerHTML = solo.length
      ? `<ul class="dlist">${solo.map(p => {
          const pl = P[p] || { name: "?", team: "", pos: "" };
          return `<li><span class="pos">${pl.pos}</span><span>${esc(pl.name)}</span>
            <span class="club">${esc((owners[p] || [])[0] || "")}</span>
            <span class="p">${pts[p] || 0}</span></li>`;
        }).join("")}</ul>`
      : `<p class="empty">Everyone owned the same players.</p>`;
    $("diff-theirs").innerHTML = `<ul class="dlist">${template.map(p => {
      const pl = P[p] || { name: "?", team: "", pos: "" };
      return `<li><span class="pos">${pl.pos}</span><span>${esc(pl.name)}</span>
        <span class="club">${own[p]}/${g.rows.length} owned</span>
        <span class="p">${pts[p] || 0}</span></li>`;
    }).join("")}</ul>`;
    return;
  }

  const mine = g.rows.find(r => r.entry === ME);
  const started = new Set(mine.starters);
  const myDiff = mine.starters.filter(p => own[p] === 1).sort(byPoints);
  const missed = Object.keys(own).filter(p => own[p] === 1 && !started.has(+p))
    .sort(byPoints).slice(0, 7);
  const gained = myDiff.reduce((s, p) => s + (pts[p] || 0), 0);
  const lost = missed.reduce((s, p) => s + (pts[p] || 0), 0);

  $("diff-caption").innerHTML = `Gameweek ${activeGw}. ${esc(mine.team)} gained
    <b>${gained}</b> from differentials; the best they missed returned <b>${lost}</b>.`;
  $("diff-mine-head").textContent = "Only they started";
  $("diff-theirs-head").textContent = "Best they missed";
  $("diff-mine").innerHTML = myDiff.length
    ? `<ul class="dlist">${myDiff.map(item).join("")}</ul>`
    : `<p class="empty">Nothing - that XI was the league template.</p>`;
  $("diff-theirs").innerHTML = missed.length
    ? `<ul class="dlist">${missed.map(item).join("")}</ul>`
    : `<p class="empty">Nobody else had a differential either.</p>`;
}

/* ---------------- line-up on a pitch ---------------- */
const ROWS = ["GKP", "DEF", "MID", "FWD"];
const pitchWho = $("pitch-who");
let pitchEntry = null;   // null means "follow the picked team, or the winner"

pitchWho.addEventListener("change", () => {
  pitchEntry = pitchWho.value ? +pitchWho.value : null;
  renderPitch();
});

function pitchSubject() {
  const rows = D.gameweeks[activeGw].rows;
  const wanted = pitchEntry ?? ME;
  return rows.find(r => r.entry === wanted) || rows[0];   // fall back to the week's winner
}

function kit(id, points, badge, benched) {
  const p = P[id] || { name: "?", team: "", pos: "" };
  return `<div class="kit">
    ${badge ? `<span class="arm ${badge === "V" ? "v" : ""}">${badge}</span>` : ""}
    <div class="shirt">${esc(p.team)}</div>
    <div class="nm">${esc(p.name)}</div>
    <div class="pt ${points ? "" : "zero"}">${points}</div>
  </div>`;
}

function renderPitch() {
  const gw = D.gameweeks[activeGw];
  const pts = gw.playerPoints;
  const subject = pitchSubject();

  pitchWho.innerHTML = `<option value="">${picked() ? "Your team" : "Gameweek winner"}</option>` +
    gw.rows.map(r => `<option value="${r.entry}">${esc(r.team)}</option>`).join("");
  pitchWho.value = pitchEntry ? String(pitchEntry) : "";

  const starters = subject.starters;
  const bench = subject.squad.slice(11);
  const badge = id => (id === subject.captain ? "C" : id === subject.vice ? "V" : "");

  const byRow = {};
  starters.forEach(id => {
    const pos = (P[id] || {}).pos || "MID";
    (byRow[pos] = byRow[pos] || []).push(id);
  });
  const formation = ROWS.slice(1).map(r => (byRow[r] || []).length).join("-");

  $("pitch").innerHTML = ROWS.map(pos => {
    const ids = byRow[pos] || [];
    return ids.length ? `<div class="row">${ids.map(id =>
      kit(id, pts[id] ?? 0, badge(id))).join("")}</div>` : "";
  }).join("");

  $("bench").innerHTML = `<div class="bench-label">Bench</div>` +
    bench.map(id => kit(id, pts[id] ?? 0, badge(id), true)).join("");

  const captainPts = (pts[subject.captain] ?? 0) * 2;
  $("pitch-caption").innerHTML =
    `<b>${esc(subject.team)}</b> in gameweek ${activeGw} &middot; ${formation} &middot;
     ${subject.points} points${subject.hit ? ` after a &minus;${subject.hit} hit` : ""}.
     Captain ${esc((P[subject.captain] || {}).name || "-")} returned ${captainPts}.
     ${subject.bench ? `${subject.bench} left on the bench.` : "Nothing wasted on the bench."}`;
}

/* ---------------- planning ---------------- */
const UP = Object.keys(D.upcoming).map(Number).sort((a, b) => a - b);
let activeUp = UP[0];
const upChips = $("up-chips");
upChips.innerHTML = UP.map(g =>
  `<button class="chip" data-gw="${g}" aria-pressed="${g === activeUp}">GW${g}</button>`).join("");
upChips.addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  activeUp = +b.dataset.gw;
  upChips.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", c === b));
  renderUpcoming();
});

function renderUpcoming() {
  const u = D.upcoming[activeUp], dl = new Date(u.deadline);
  const left = dl - new Date();
  const days = Math.floor(left / 864e5), hrs = Math.floor(left / 36e5) % 24;
  $("up-caption").innerHTML = `Deadline <b>${dl.toLocaleString(undefined,
    { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</b>` +
    (left > 0 ? ` &middot; ${days}d ${hrs}h to go &middot; your local time` : " &middot; closed") +
    `. Each club carries its own difficulty for the same match: ` +
    (u.games.length ? (() => {
      // Show the clearest mismatch in the round as the worked example.
      const g = u.games.reduce((a, b) =>
        Math.abs(b.homeFdr - b.awayFdr) > Math.abs(a.homeFdr - a.awayFdr) ? b : a);
      const easier = g.homeFdr <= g.awayFdr ? g : { homeName: g.awayName };
      const harder = g.homeFdr <= g.awayFdr ? { awayName: g.awayName } : { awayName: g.homeName };
      return `<b>${esc(g.home)} ${g.homeFdr} v ${esc(g.away)} ${g.awayFdr}</b> is an easy game
        for ${esc(easier.homeName)} and a hard one for ${esc(harder.awayName)}.`;
    })() : "");
  $("up-fixtures").innerHTML = u.games.map(g => {
    const ko = new Date(g.kickoff);
    return `<div class="fx">
      <span class="ko">${ko.toLocaleString(undefined, { weekday: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
      <span class="tm">${esc(g.home)}</span><span class="fdr ${fdrBand(g.homeFdr)}">${g.homeFdr}</span>
      <span class="v">v</span>
      <span class="tm">${esc(g.away)}</span><span class="fdr ${fdrBand(g.awayFdr)}">${g.awayFdr}</span>
    </div>`;
  }).join("");
}

const POSITIONS = ["GKP", "DEF", "MID", "FWD"];
let activePos = "MID";
const seg = $("pos-seg");
seg.innerHTML = POSITIONS.filter(p => D.suggestions[p]).map(p =>
  `<button data-pos="${p}" aria-pressed="${p === activePos}">${p}</button>`).join("");
seg.addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  activePos = b.dataset.pos;
  seg.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b));
  renderPicks();
});

function renderPicks() {
  const list = D.suggestions[activePos] || [];
  let t = `<table><thead><tr><th>Player</th><th>Club</th><th class="r">&pound;m</th>
    <th class="r">Form</th><th class="r col-opt">xGI/90</th><th class="r">FDR</th>
    <th class="r col-opt">Owned</th></tr></thead><tbody>`;
  list.forEach(p => {
    const band = p.fdr <= 2.6 ? "easy" : p.fdr >= 3.6 ? "hard" : "mid";
    t += `<tr><td class="team">${esc(p.name)}</td>
      <td style="color:var(--ink-3)">${esc(p.team)}</td>
      <td class="r num">${p.price.toFixed(1)}</td>
      <td class="r num" style="font-weight:600">${p.form.toFixed(1)}</td>
      <td class="r num col-opt">${p.xgi90.toFixed(2)}</td>
      <td class="r"><span class="fdr ${band}">${p.fdr.toFixed(1)}</span></td>
      <td class="r num col-opt" style="color:var(--ink-3)">${p.owned.toFixed(1)}%</td></tr>`;
  });
  $("pick-table").innerHTML = t + `</tbody></table>`;
  $("pick-caption").innerHTML =
    `Next ${D.horizon} gameweeks from GW${D.nextGw}, ranked within position on form,
     expected goal involvement, fixtures and value. Injured and doubtful players excluded.`;
}

$("remind-text").textContent = D.reminder;
$("copy-btn").addEventListener("click", async e => {
  const btn = e.currentTarget, original = btn.textContent;
  try {
    await navigator.clipboard.writeText(D.reminder);
    btn.textContent = "Copied";
  } catch (err) {
    const r = document.createRange();
    r.selectNodeContents($("remind-text"));
    const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
    btn.textContent = "Selected - press Cmd+C";
  }
  setTimeout(() => { btn.textContent = original; }, 2500);
});

/* ---------------- money ---------------- */
const PAY_LINES = [];
Z.weeks.forEach(w => w.winners.forEach(win => PAY_LINES.push({
  id: `gw${w.gw}-${win.entry}`, gw: w.gw, entry: win.entry, team: win.team,
  amount: w.each, points: w.points, tied: w.tied,
})));
const RESERVED_SPECIALS = Object.values(Z.specials).reduce((a, b) => a + b, 0);
const RESERVED_PODIUM = Z.champion + Z.runnerUp;
const LOCAL_KEY = "gme-payments-v2";

/* Three layers, in order of authority:
   1. the artifact's shared store, when the page is published there;
   2. otherwise, the record baked in at build time by the treasurer;
   3. plus anything this browser has toggled since, kept as a delta so a
      later build that settles a prize is not fought by stale local state. */
const BASE_PAID = new Set(D.paid || []);
let overrides = {};
let paidIds = new Set(BASE_PAID);
let store = null;          // the artifact's shared store, when there is one
let mode = "loading";      // loading | shared | local | readonly

function books() {
  const paidOut = PAY_LINES.filter(l => paidIds.has(l.id)).reduce((a, l) => a + l.amount, 0);
  const dueNow = PAY_LINES.filter(l => !paidIds.has(l.id)).reduce((a, l) => a + l.amount, 0);
  const reserved = Z.weeklyRemaining + RESERVED_SPECIALS + RESERVED_PODIUM;
  const balance = Z.pool - paidOut;
  return { paidOut, dueNow, reserved, balance, committed: dueNow + reserved,
           unallocated: balance - (dueNow + reserved),
           paidCount: PAY_LINES.filter(l => paidIds.has(l.id)).length };
}

function renderMoney() {
  const b = books();
  $("tre-stats").innerHTML = [
    { k: "Collected", v: krw(Z.pool), n: `${Z.entry / 1000}k each, ${D.managers.length} players` },
    { k: "Paid out", v: krw(b.paidOut), n: `${b.paidCount} of ${PAY_LINES.length} prizes` },
    { k: "Due now", v: krw(b.dueNow), n: "won, not yet paid", cls: b.dueNow ? "bad" : "good" },
    { k: "Balance", v: krw(b.balance), n: `${krw(b.committed)} still owed` },
  ].map(t => `<div class="stat"><div class="k">${t.k}</div>
    <div class="v money ${t.cls || ""}">${t.v}</div><div class="n">${t.n}</div></div>`).join("");

  const canPay = mode === "shared" || mode === "local";
  let t = `<table><thead><tr><th>GW</th><th>Winner</th><th class="r col-opt">Score</th>
    <th class="r">Amount</th><th>Status</th></tr></thead><tbody>`;
  PAY_LINES.forEach(l => {
    const paid = paidIds.has(l.id);
    t += `<tr class="${l.entry === ME ? "me" : ""}">
      <td class="rank num">${l.gw}</td>
      <td class="team">${esc(l.team)}${l.tied ? ' <span class="badge alt">split</span>' : ""}</td>
      <td class="r num col-opt">${l.points}</td>
      <td class="r krw">${krw(l.amount)}</td>
      <td><button class="btn sm pay ${paid ? "on" : ""}" data-id="${l.id}"
        ${canPay ? "" : "disabled"} type="button">${paid ? "Paid" : "Mark paid"}</button></td>
    </tr>`;
  });
  $("pay-table").innerHTML = t + `</tbody></table>`;

  $("pay-caption").innerHTML = b.dueNow
    ? `<b>${krw(b.dueNow)} KRW</b> owed across ${PAY_LINES.length - b.paidCount} prizes.`
    : `All settled.`;

  const note = $("pay-note");
  if (mode === "loading") note.textContent = "Checking where payments are recorded...";
  else if (mode === "shared") note.innerHTML =
    "Saved with the page, so everyone you share it with sees the same record. Click again to undo." +
    (b.unallocated ? ` <b>Books off by ${krw(b.unallocated)} KRW.</b>` : " Books reconcile.");
  else if (mode === "local") note.innerHTML =
    (BASE_PAID.size
      ? `Ledger from the last build (${BASE_PAID.size} settled). Changes you make here stay in this browser. `
      : "Saved in this browser only - this copy is not the published page. Click again to undo. ") +
    (b.unallocated ? ` <b>Books off by ${krw(b.unallocated)} KRW.</b>` : " Books reconcile.");
  else note.textContent = "Payments are read-only in this view.";

  const ties = Z.weeks.filter(w => w.tied);
  $("tie-warning").innerHTML = ties.length ? `<div class="warn">
    <b>Unsettled:</b> ${ties.map(w => `gameweek ${w.gw} was tied on ${w.points} between
      ${w.winners.map(x => esc(x.team)).join(" and ")}`).join("; ")}.
    The prize sheet does not say how a tie is settled, so the ${krw(ties[0].pot)} KRW is shown split.
    Worth agreeing a rule before it decides real money.</div>` : "";

  $("money-caption").innerHTML =
    `${krw(Z.weeklyRemaining)} KRW is still to play for week by week.
     These are today's positions, not results.`;

  let m = `<table><thead><tr><th>Pos</th><th>Team</th><th class="r col-opt">Won so far</th>
    <th class="r col-opt">If frozen</th><th class="r">Projected</th>
    <th class="r">Net of entry</th></tr></thead><tbody>`;
  Z.rows.forEach(r => {
    m += `<tr class="${r.entry === ME ? "me" : ""}">
      <td class="rank num">${r.rank}</td><td class="team">${esc(r.team)}</td>
      <td class="r krw col-opt">${r.banked ? krw(r.banked) : "-"}</td>
      <td class="r krw col-opt" style="color:var(--ink-3)">${r.provisional ? krw(r.provisional) : "-"}</td>
      <td class="r krw" style="font-weight:700">${krw(r.projected)}</td>
      <td class="r krw" style="color:${r.net >= 0 ? "var(--good)" : "var(--ink-3)"}">
        ${r.net >= 0 ? "+" : "&minus;"}${krw(Math.abs(r.net))}</td></tr>`;
  });
  $("money-table").innerHTML = m + `</tbody></table>`;

  const e = Z.extremes, fifth = D.standings.find(x => x.rank === 5);
  $("awards").innerHTML = [
    { t: `Highest single GW &middot; ${krw(Z.specials.highest)}`,
      h: e.highest ? `${esc(e.highest.team)}, ${e.highest.points}` : "nobody yet",
      d: e.highest ? `gameweek ${e.highest.gw}` : "" },
    { t: `Exactly 111 &middot; ${krw(Z.specials.exact111)}`,
      h: e.exact111.length ? e.exact111.map(x => esc(x.team)).join(", ") : "unclaimed", d: "" },
    { t: `Lowest single GW &middot; ${krw(Z.specials.lowest)}`,
      h: e.lowest ? `${esc(e.lowest.team)}, ${e.lowest.points}` : "nobody yet",
      d: e.lowest ? `gameweek ${e.lowest.gw}, before hits` : "" },
    { t: `5th at season end &middot; ${krw(Z.specials.fifth)}`,
      h: fifth ? esc(fifth.team) : "-", d: "currently 5th" },
  ].map(a => `<div class="award"><div class="t">${a.t}</div>
    <div class="h">${a.h}</div><div class="d">${a.d}</div></div>`).join("");
}

function applyOverrides() {
  paidIds = new Set(BASE_PAID);
  for (const [id, on] of Object.entries(overrides)) {
    on ? paidIds.add(id) : paidIds.delete(id);
  }
}

function saveLocal() {
  try {
    // Drop overrides the build has caught up with, so they do not linger.
    for (const [id, on] of Object.entries(overrides)) {
      if (BASE_PAID.has(id) === on) delete overrides[id];
    }
    Object.keys(overrides).length
      ? localStorage.setItem(LOCAL_KEY, JSON.stringify(overrides))
      : localStorage.removeItem(LOCAL_KEY);
  } catch (e) { /* private mode: the toggle still works for this visit */ }
}

$("pay-table").addEventListener("click", async e => {
  const btn = e.target.closest(".pay");
  if (!btn || btn.disabled) return;
  const line = PAY_LINES.find(l => l.id === btn.dataset.id);
  const nowPaid = !paidIds.has(line.id);

  if (mode === "local") {
    overrides[line.id] = nowPaid;
    applyOverrides(); saveLocal(); renderMoney(); return;
  }
  btn.disabled = true;
  try {
    await store.collection("payments").doc(line.id).set({
      paid: nowPaid, gw: line.gw, entry: line.entry, team: line.team,
      amount: line.amount, at: new Date().toISOString(),
    });
  } catch (err) {
    btn.disabled = false;
    $("pay-note").textContent = "Could not save: " + ((err && err.code) || "unknown error");
  }
});

(async () => {
  const db = await capability("db");
  if (db) {
    store = db;
    db.collection("payments").onSnapshot({
      next: snap => {
        paidIds = new Set(snap.docs.filter(d => (d.data() || {}).paid).map(d => d.id));
        mode = "shared";
        renderMoney();
      },
      error: () => { mode = "readonly"; renderMoney(); },
    });
    return;
  }
  try {
    const saved = JSON.parse(localStorage.getItem(LOCAL_KEY) || "{}");
    if (saved && typeof saved === "object" && !Array.isArray(saved)) overrides = saved;
  } catch (e) { /* private mode */ }
  applyOverrides();
  mode = "local";
  renderMoney();
})();

/* ---------------- workbook ---------------- */
function workbook() {
  const b = books();
  const wb = XLSX.utils.book_new();
  const sheet = (name, rows) =>
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), name);

  sheet("Summary", [
    [`${D.league.name} 2026/27 - prize pool`],
    [`Snapshot ${D.generated.slice(0, 16).replace("T", " ")} UTC`], [],
    ["MONEY IN"], [`Entries (${D.managers.length} x ${Z.entry} KRW)`, Z.pool], [],
    ["MONEY OUT"], ["Paid to weekly winners", b.paidOut],
    ["Due now (weeks won, not yet paid)", b.dueNow], [],
    ["STILL RESERVED"], ["Future weekly prizes", Z.weeklyRemaining],
    ["Special awards", RESERVED_SPECIALS], ["Champion and runner-up", RESERVED_PODIUM], [],
    ["POSITION"], ["Balance on hand", b.balance], ["Total still owed", b.committed],
    ["Unallocated (should be zero)", b.unallocated],
  ]);

  sheet("Prize ledger", [["GW", "Winner", "Score", "Amount", "Status", "Tie"]].concat(
    PAY_LINES.map(l => [l.gw, l.team, l.points, l.amount,
      paidIds.has(l.id) ? "PAID" : "DUE", l.tied ? "split" : ""])));

  const people = Object.fromEntries(D.managers.map(m => [m.entry, m.manager]));
  const got = {}, owed = {};
  PAY_LINES.forEach(l => {
    const bucket = paidIds.has(l.id) ? got : owed;
    bucket[l.entry] = (bucket[l.entry] || 0) + l.amount;
  });
  const byManagerHead = ["Pos", "Team"].concat(HAS_NAMES ? ["Manager"] : [],
    ["Entry paid", "Received", "Still owed"]);
  sheet("By manager", [byManagerHead].concat(D.standings.map(s =>
    [s.rank, s.team].concat(HAS_NAMES ? [people[s.entry] || ""] : [],
      [Z.entry, got[s.entry] || 0, owed[s.entry] || 0]))));

  const gwRows = [["GW", "Pos", "Team", "Manager", "GW pts", "Gross", "Hit", "Bench",
                   "Captain", "C pts", "Season total", "Chip"]];
  D.playedGws.forEach(gw => {
    const totals = Object.fromEntries(D.season[gw].map(x => [x.entry, x.total]));
    D.gameweeks[gw].rows.forEach(r => gwRows.push([gw, r.place, r.team, r.manager || "",
      r.points, r.gross, r.hit ? -r.hit : 0, r.bench,
      (P[r.captain] || {}).name || "", r.captainPoints, totals[r.entry], r.chip || ""]));
  });
  sheet("Gameweeks", gwRows);

  const e = Z.extremes, fifth = D.standings.find(x => x.rank === 5);
  sheet("Special awards", [["Award", "Amount", "Currently", "Detail"],
    ["Highest single gameweek", Z.specials.highest, e.highest ? e.highest.team : "-",
      e.highest ? `${e.highest.points} in GW${e.highest.gw}` : ""],
    ["Exactly 111 in a gameweek", Z.specials.exact111,
      e.exact111.length ? e.exact111.map(x => x.team).join(", ") : "unclaimed", ""],
    ["Lowest single gameweek", Z.specials.lowest, e.lowest ? e.lowest.team : "-",
      e.lowest ? `${e.lowest.points} in GW${e.lowest.gw}, before hits` : ""],
    ["5th at season end", Z.specials.fifth, fifth ? fifth.team : "-", "currently 5th"],
    ["Champion", Z.champion, D.standings[0].team, "currently 1st"],
    ["Runner-up", Z.runnerUp, D.standings[1].team, "currently 2nd"],
  ]);
  return wb;
}

$("xlsx-btn").addEventListener("click", async e => {
  const btn = e.currentTarget, original = btn.textContent;
  const filename = `GME-fantasy-books-GW${D.currentGw}.xlsx`;
  btn.textContent = "Preparing..."; btn.disabled = true;
  try {
    const buf = XLSX.write(workbook(), { bookType: "xlsx", type: "array" });
    const downloads = await capability("downloads");
    if (downloads) {
      await downloads.save({ filename, data: buf });
      btn.textContent = "Saved";
    } else {
      // Plain browser download - works when the page is served locally.
      const url = URL.createObjectURL(new Blob([buf],
        { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      btn.textContent = "Downloaded";
    }
  } catch (err) {
    btn.textContent = (err && err.code === "declined") ? original : "Could not save";
  }
  btn.disabled = false;
  setTimeout(() => { btn.textContent = original; }, 2500);
});

/* ---------------- render ---------------- */
// Everything that depends on who is looking, in one place, so switching
// team redraws the whole board at once.
function renderAll() {
  renderStanding();
  renderStats();
  renderBump();
  renderGw();      // renderGw calls renderDiff
  renderMoney();
}

renderUpcoming();
renderPicks();
renderAll();

/* ---------------- install as an app ---------------- */
// A manifest lets a phone add this to the home screen and open it without
// browser chrome. Built at runtime so the page stays a single file.
(function manifest() {
  const icon =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">' +
    '<rect width="192" height="192" rx="42" fill="#16181D"/>' +
    '<path d="M54 38h84v58a42 42 0 0 1-42 42 42 42 0 0 1-42-42z" fill="#ED1C24"/>' +
    '<path d="M54 84h84v12a42 42 0 0 1-42 42 42 42 0 0 1-42-42z" fill="#16181D"/></svg>';
  const src = "data:image/svg+xml," + encodeURIComponent(icon);
  const doc = {
    name: D.league.name + " Board",
    short_name: "GME Fantasy",
    start_url: ".", scope: ".", display: "standalone", orientation: "portrait-primary",
    background_color: "#F5F6F8", theme_color: "#ED1C24",
    icons: [{ src, sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
  };
  try {
    const link = $("app-manifest");
    link.href = URL.createObjectURL(new Blob([JSON.stringify(doc)],
      { type: "application/manifest+json" }));
    const apple = document.createElement("link");
    apple.rel = "apple-touch-icon"; apple.href = src;
    document.head.appendChild(apple);
  } catch (e) { /* manifests are a nicety, never a requirement */ }
})();

/* ---------------- keyboard shortcuts ---------------- */
const keysDialog = $("keys");
$("keys-btn").addEventListener("click", () => keysDialog.showModal());
keysDialog.addEventListener("click", e => { if (e.target === keysDialog) keysDialog.close(); });

function stepGameweek(delta) {
  const onPlanning = !$("tab-planning").hidden;
  const list = onPlanning ? UP : GWS;
  const current = onPlanning ? activeUp : activeGw;
  const next = list[Math.min(list.length - 1, Math.max(0, list.indexOf(current) + delta))];
  if (next === current) return;
  const bar = onPlanning ? upChips : gwChips;
  const btn = bar.querySelector(`[data-gw="${next}"]`);
  if (btn) btn.click();
}

document.addEventListener("keydown", e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const el = document.activeElement;
  if (el && el.matches("input, textarea, select")) return;
  if (keysDialog.open && e.key !== "?") return;   // Esc is handled by the dialog

  const k = e.key;
  if (k >= "1" && k <= String(TABS.length)) { showTab(TABS[+k - 1].id); e.preventDefault(); }
  else if (k === "?") { keysDialog.open ? keysDialog.close() : keysDialog.showModal(); e.preventDefault(); }
  else if (k === "ArrowLeft") { stepGameweek(-1); e.preventDefault(); }
  else if (k === "ArrowRight") { stepGameweek(1); e.preventDefault(); }
  else if (k === "c" || k === "C") { showTab("planning"); $("copy-btn").click(); e.preventDefault(); }
  else if (k === "e" || k === "E") { showTab("money"); $("xlsx-btn").click(); e.preventDefault(); }
});
