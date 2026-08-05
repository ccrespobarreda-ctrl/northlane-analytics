#!/usr/bin/env python3
"""
Build the static dashboard.

Injects the exported payload into docs/index.template.html and writes
docs/index.html. The data is embedded rather than fetched so the page works from
file://, from GitHub Pages, and on a phone with no connection — no CORS, no
loading state, no failure mode to design around.

    python src/export_dashboard_data.py > powerbi/dashboard_data.json
    python src/build_dashboard.py

Because every figure comes from the payload and none is typed into the HTML, a
data refresh is `make dashboard` rather than an editing session.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Set these before publishing, or the links go nowhere:
#   REPO_URL=https://github.com/you/northlane-analytics \
#   CONTACT_URL=https://www.upwork.com/freelancers/~you \
#   CONTACT_LABEL="Get in touch" make dashboard
REPO_URL = os.environ.get("REPO_URL", "")
CONTACT_URL = os.environ.get("CONTACT_URL", "")
CONTACT_LABEL = os.environ.get("CONTACT_LABEL", "Get in touch")

TEMPLATE = Path("docs/index.template.html")
PAYLOAD = Path("powerbi/dashboard_data.json")
OUTPUT = Path("docs/index.html")
PLACEHOLDER = "/*__DATA__*/"


def main() -> int:
    for p in (TEMPLATE, PAYLOAD):
        if not p.exists():
            print(f"Missing {p}", file=sys.stderr)
            return 2

    html = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        print(f"Template has no {PLACEHOLDER} placeholder", file=sys.stderr)
        return 2

    data = json.loads(PAYLOAD.read_text(encoding="utf-8"))

    # Compact JSON: the payload is embedded in a script tag, so bytes matter more
    # than readability. </script> inside a string literal would close the tag
    # early, so it is escaped defensively even though this data contains none.
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")

    out = html.replace(PLACEHOLDER, blob)

    if REPO_URL:
        out = out.replace('href="https://github.com/" id="repoLink"',
                          f'href="{REPO_URL}" id="repoLink"')
    else:
        print("  note: REPO_URL unset, masthead link points at github.com")

    if CONTACT_URL:
        out = out.replace('id="ctaButton" href="#"',
                          f'id="ctaButton" href="{CONTACT_URL}"')
        out = out.replace(">Get in touch →</a>", f">{CONTACT_LABEL} →</a>")
    else:
        print("  note: CONTACT_URL unset, the closing button says so on the page")

    OUTPUT.write_text(out, encoding="utf-8")

    kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT} ({kb:.0f} KB, payload {len(blob) / 1024:.0f} KB)")

    # Cheap structural checks. A dashboard that silently renders nothing is
    # worse than one that fails loudly.
    problems = []
    if "/*__DATA__*/" in out:
        problems.append("placeholder still present")
    for element_id in re.findall(r'getElementById\("([^"]+)"\)', html):
        if f'id="{element_id}"' not in html:
            problems.append(f"script targets #{element_id}, which no element defines")
    if problems:
        for p in sorted(set(problems)):
            print(f"  WARNING: {p}", file=sys.stderr)
        return 1
    print("  structure ok: every scripted element id exists in the markup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
