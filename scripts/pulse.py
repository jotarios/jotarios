#!/usr/bin/env python3
"""Regenerate assets/readme/pulse.svg from live GitHub data.

Runs in CI on a schedule so the profile keeps current numbers without
depending on a third-party badge service staying up. Needs GITHUB_TOKEN
in the environment; the default Actions token is enough for public data.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

USER = "jotarios"
OUT = os.path.join("assets", "readme", "pulse.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes { stargazerCount isFork }
    }
  }
}
"""


def fetch(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-pulse",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def collect(user):
    own = [r for r in user["repositories"]["nodes"] if not r["isFork"]]
    contrib = user["contributionsCollection"]
    return [
        ("CONTRIBUTIONS · 12 MO", f"{contrib['contributionCalendar']['totalContributions']:,}"),
        ("PULL REQUESTS · 12 MO", f"{contrib['totalPullRequestContributions']:,}"),
        ("PUBLIC REPOS", f"{len(own):,}"),
        ("STARS EARNED", f"{sum(r['stargazerCount'] for r in own):,}"),
    ]


def render(cells, stamp):
    W, H, PAD = 1200, 170, 40
    cell_w = (W - PAD * 2) / len(cells)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="pulseTitle pulseDesc">',
        "  <title id=\"pulseTitle\">Pulse</title>",
        "  <desc id=\"pulseDesc\">"
        + ". ".join(f"{label.replace(' · ', ', ')}: {value}" for label, value in cells)
        + f". Regenerated {stamp}.</desc>",
        f'  <rect width="{W}" height="{H}" rx="24" fill="#0a0e13"/>',
        f'  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="23" fill="none" '
        'stroke="#1e262f" stroke-width="1.5"/>',
        '  <g font-family="ui-monospace, SFMono-Regular, Menlo, monospace">',
        f'    <text x="{PAD}" y="36" font-size="18" letter-spacing="2.4" fill="#6e7a86">PULSE</text>',
        f'    <text x="{W - PAD}" y="36" font-size="16" fill="#6e7a86" text-anchor="end">'
        f"UPDATED {stamp}</text>",
        f'    <line x1="0" y1="58" x2="{W}" y2="58" stroke="#1e262f" stroke-width="1.5"/>',
    ]

    for i, (label, value) in enumerate(cells):
        x = PAD + cell_w * i
        if i:
            parts.append(
                f'    <line x1="{x:.0f}" y1="78" x2="{x:.0f}" y2="146" '
                'stroke="#1e262f" stroke-width="1.5"/>'
            )
        tx = x + (24 if i else 0)
        parts.append(f'    <text x="{tx:.0f}" y="98" font-size="16" fill="#6e7a86">{label}</text>')
        parts.append(
            f'    <text x="{tx:.0f}" y="142" font-size="40" font-weight="700" '
            f'fill="#56d364">{value}</text>'
        )

    parts.append("  </g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        try:
            token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            sys.exit("No GITHUB_TOKEN, GH_TOKEN, or usable gh login found.")

    try:
        user = fetch(token)
    except urllib.error.URLError as exc:
        sys.exit(f"Could not reach the GitHub API: {exc}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    svg = render(collect(user), stamp)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
