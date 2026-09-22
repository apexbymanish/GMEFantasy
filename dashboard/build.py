#!/usr/bin/env python3
"""Build the dashboard into a self-contained page.

Two destinations with different data:

  dashboard/index.html  full data, including managers' real names. This is
                        what `fpl serve` runs locally, for your eyes.
  docs/index.html       the same page with real names removed, because
                        GitHub Pages is public and those names belong to
                        other people. Team names are pseudonyms; names are not.

The page must be self-contained either way: the FPL API blocks cross-origin
requests, and a published page cannot fetch a sibling file.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent


def redact(raw):
    """Remove managers' real names, keeping everything else intact."""
    data = json.loads(raw)
    for manager in data.get("managers", []):
        manager["manager"] = ""
    for row in data.get("standings", []):
        row["manager"] = ""
    for gw in data.get("gameweeks", {}).values():
        for row in gw.get("rows", []):
            row["manager"] = ""
    return json.dumps(data, separators=(",", ":"))


def main():
    page = HERE.joinpath("page.html").read_text()
    app = HERE.joinpath("app.js").read_text()
    raw = HERE.joinpath("data.json").read_text()

    def render(data):
        return (page.replace("__DATA__", data)
                    .replace('<script src="app.js"></script>', f"<script>\n{app}\n</script>"))

    for path, data, label in (
        (HERE / "index.html", raw, "with names"),
        (ROOT / "docs" / "index.html", redact(raw), "names removed"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(data))
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1024:>5.0f} KB  ({label})")


if __name__ == "__main__":
    main()
