"""Fetch layer for the FPL API, with a disk cache.

The API is public and needs no key, but it is undocumented and unofficial,
so we cache hard and never hammer it. The rule that makes this cheap:
a finished gameweek never changes, so its data is cached forever.
"""
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://fantasy.premierleague.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (fpl-analyzer)"}
CACHE_DIR = Path(os.environ.get("FPL_CACHE", Path.home() / ".cache" / "fpl-analyzer"))

FOREVER = None      # ttl sentinel: never re-fetch
LIVE_TTL = 60       # a gameweek still in progress

HOUR = 3600
DAY = 86400


class NotAvailable(Exception):
    """The endpoint returned 404 — usually a gameweek that hasn't happened yet."""


def _cache_file(path):
    safe = path.strip("/").replace("/", "_").replace("?", "_").replace("=", "_")
    return CACHE_DIR / f"{safe}.json"


def _download(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NotAvailable(path) from exc
        raise


def get(path, ttl=HOUR):
    """Return JSON for an API path, from cache when it is still fresh.

    ttl=FOREVER means a cached copy is always accepted.
    """
    cached = _cache_file(path)
    if cached.exists():
        fresh = ttl is FOREVER or (time.time() - cached.stat().st_mtime) < ttl
        if fresh:
            try:
                return json.loads(cached.read_text())
            except json.JSONDecodeError:
                pass  # corrupt cache entry, fall through and re-fetch

    data = _download(path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(data))
    return data


def parallel(fn, items, workers=10):
    """Map fn over items concurrently. Used to pull all rivals at once."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


# --- endpoints ------------------------------------------------------------

def bootstrap():
    """All players, teams and gameweek states. ~1.7MB, so cache for an hour."""
    return get("bootstrap-static/", ttl=HOUR)


def fixtures():
    return get("fixtures/", ttl=DAY)


def league(league_id):
    return get(f"leagues-classic/{league_id}/standings/", ttl=5 * 60)


def history(entry_id):
    return get(f"entry/{entry_id}/history/", ttl=5 * 60)


def picks(entry_id, gw):
    return get(f"entry/{entry_id}/event/{gw}/picks/", ttl=_gw_ttl(gw))


def live(gw):
    return get(f"event/{gw}/live/", ttl=_gw_ttl(gw))


# --- gameweek state -------------------------------------------------------

def events():
    return bootstrap()["events"]


def _gw_ttl(gw):
    return FOREVER if is_finished(gw) else LIVE_TTL


def is_finished(gw):
    for event in events():
        if event["id"] == gw:
            return bool(event["finished"])
    return False


def current_gw():
    """The gameweek in progress, or the most recent one that started."""
    started = [e["id"] for e in events() if e["is_current"]]
    if started:
        return started[0]
    played = [e["id"] for e in events() if e["finished"]]
    return max(played) if played else 1


def next_gw():
    upcoming = [e for e in events() if e["is_next"]]
    return upcoming[0]["id"] if upcoming else current_gw() + 1


def latest_played_gw():
    """Highest gameweek we can actually pull picks for."""
    played = [e["id"] for e in events() if e["finished"] or e["is_current"]]
    return max(played) if played else 1
