#!/usr/bin/env python3
"""Build the live stats SVGs for the GitHub profile README.

Pulls data for 0xPunisher from the GitHub GraphQL API and renders three cards
in the same style as header.svg:

    assets/stats.svg      numbers: stars, commits, contributions, repos, streaks
    assets/languages.svg  top 6 languages by code size in own non-fork repos
    assets/activity.svg   contribution grid for the last 12 months

The token is read from GH_STATS_TOKEN (locally from .env). Run with --demo to
render made-up data without a token or any network calls to the API.

Usage:
    pip install -r requirements.txt
    python3 scripts/build_stats.py            # real data, needs GH_STATS_TOKEN
    python3 scripts/build_stats.py --demo     # fake data, for design checks
"""

import argparse
import datetime as dt
import json
import os
import random
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

from dotenv import load_dotenv

from svgkit import (
    ACCENT,
    ASSETS,
    BG,
    CSS_COLORS,
    CSS_MONO,
    CSS_TEXT,
    LINE,
    MUTED,
    ROOT,
    font_face,
    text_width,
    write,
)

LOGIN = "0xPunisher"
API = "https://api.github.com/graphql"
TOP_LANGUAGES = 6

# Contribution grid: level 0 is an empty day, 1..4 blend from dark gray to the accent
EMPTY_CELL = "#161616"
LEVEL_FROM = "#262626"


class StatsError(Exception):
    pass


# ------------------------------------------------------------------- data

REPOS_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    createdAt
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

YEAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""

CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def graphql(token, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-profile-stats",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise StatsError("GitHub rejected GH_STATS_TOKEN (401). Check that it is valid and not expired.")
        raise StatsError(f"GitHub API returned HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise StatsError(f"could not reach the GitHub API: {e.reason}")
    if payload.get("errors"):
        messages = "; ".join(err.get("message", "?") for err in payload["errors"])
        raise StatsError(f"GitHub API error: {messages}")
    user = payload["data"]["user"]
    if user is None:
        raise StatsError(f"user {LOGIN} not found")
    return user


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(token):
    stars = 0
    languages = {}
    after = None
    while True:
        user = graphql(token, REPOS_QUERY, {"login": LOGIN, "after": after})
        repos = user["repositories"]
        for repo in repos["nodes"]:
            stars += repo["stargazerCount"]
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                languages[name] = languages.get(name, 0) + edge["size"]
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    repo_count = repos["totalCount"]
    created = dt.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))

    year = graphql(token, YEAR_QUERY, {"login": LOGIN})["contributionsCollection"]

    # The API caps one calendar query at a year, so walk back to the account
    # creation date to get the full history for the longest streak.
    days = {}
    now = dt.datetime.now(dt.timezone.utc)
    to = now
    while to > created:
        frm = max(created, to - dt.timedelta(days=364))
        user = graphql(token, CALENDAR_QUERY, {"login": LOGIN, "from": iso(frm), "to": iso(to)})
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                date = dt.date.fromisoformat(day["date"])
                days[date] = max(days.get(date, 0), day["contributionCount"])
        to = frm - dt.timedelta(seconds=1)

    return {
        "stars": stars,
        "repos": repo_count,
        "commits": year["totalCommitContributions"],
        "contributions": year["contributionCalendar"]["totalContributions"],
        "languages": languages,
        "days": days,
        "today": now.date(),
    }


def demo_data():
    rng = random.Random(1337)
    today = dt.datetime.now(dt.timezone.utc).date()
    days = {}
    for i in range(3 * 365):
        date = today - dt.timedelta(days=i)
        busy = 0.82 if date.weekday() < 5 else 0.45
        if i < 23 or 140 <= i < 187 or rng.random() < busy:
            count = 1 + int(rng.expovariate(0.28))
            if rng.random() < 0.04:
                count += rng.randint(12, 30)
            days[date] = count
        else:
            days[date] = 0
    year = sum(days[today - dt.timedelta(days=i)] for i in range(365))
    return {
        "stars": 1284,
        "repos": 37,
        "commits": int(year * 0.78),
        "contributions": year,
        "languages": {
            "Python": 1_482_310,
            "TypeScript": 912_044,
            "Rust": 408_902,
            "Go": 196_515,
            "Solidity": 88_270,
            "Shell": 41_380,
            "Dockerfile": 9_120,
            "HTML": 6_004,
        },
        "days": days,
        "today": today,
    }


def streaks(days, today):
    """Current streak (today may still be empty) and longest streak, in days."""
    current = 0
    date = today if days.get(today, 0) > 0 else today - dt.timedelta(days=1)
    while days.get(date, 0) > 0:
        current += 1
        date -= dt.timedelta(days=1)

    longest = run = 0
    prev = None
    for date in sorted(d for d, c in days.items() if c > 0):
        run = run + 1 if prev is not None and (date - prev).days == 1 else 1
        longest = max(longest, run)
        prev = date
    return current, longest


# ---------------------------------------------------------------- drawing

def fmt(n):
    return f"{n:,}"


def blend(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def card(filename, W, H, label, note, body, *, updated, mono_chars, value_chars="",
         title, desc, css="", defs="", footer_right="", pad=32):
    """Wrap a body in the shared card chrome: background, top row, footer, border."""
    top_y = 42
    footer = f"updated {updated}"
    fonts = font_face("PX Mono", "JetBrainsMono", 400, mono_chars + label + note + footer)
    if value_chars:
        fonts += font_face("PX Text", "SpaceGrotesk", 500, value_chars)
    style = f"{fonts}\n{CSS_MONO}\n{CSS_TEXT}\n{CSS_COLORS}\n.faint{{fill:{MUTED};opacity:.6;}}\n{css}"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">{escape(title)}</title>
<desc id="d">{escape(desc)}</desc>
<defs>
<style>{style}</style>
<clipPath id="card"><rect x="0" y="0" width="{W}" height="{H}" rx="14"/></clipPath>
{defs}</defs>
<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="{BG}"/>
<g clip-path="url(#card)">
<text class="mono muted" x="{pad}" y="{top_y}" font-size="13">{escape(label)}</text>
<text class="mono muted" x="{W - pad}" y="{top_y}" font-size="13" text-anchor="end">{escape(note)}</text>
<line x1="{pad}" y1="66" x2="{W - pad}" y2="66" stroke="{LINE}" stroke-width="1"/>
{body}
<line x1="{pad}" y1="{H - 48}" x2="{W - pad}" y2="{H - 48}" stroke="{LINE}" stroke-width="1"/>
<text class="mono faint" x="{pad}" y="{H - 21}" font-size="11">{escape(footer)}</text>
{footer_right}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="13.5" fill="none" stroke="{LINE}" stroke-width="1"/>
</svg>
"""
    write(filename, svg)


def stat_block(x, y, value, label, size, unit=""):
    """Big number with an optional small unit, small caption under it."""
    unit_svg = ""
    if unit:
        unit_svg = f'<tspan class="mono muted" font-size="{round(size * 0.38)}" dx="6">{escape(unit)}</tspan>'
    return (
        f'<text x="{x:.1f}" y="{y}"><tspan class="value" font-size="{size}">{escape(value)}</tspan>{unit_svg}</text>'
        f'<text class="mono muted" x="{x:.1f}" y="{y + 20}" font-size="11" letter-spacing=".6">{escape(label)}</text>'
    )


def days_unit(n):
    return "day" if n == 1 else "days"


CARD_W, CARD_H = 495, 330
SMALL_PAD = 32


def build_numbers(data, current, longest, updated):
    W, H, PAD = CARD_W, CARD_H, SMALL_PAD
    cells = [
        (fmt(data["stars"]), "STARS EARNED", ""),
        (fmt(data["commits"]), "COMMITS 12 MO", ""),
        (fmt(data["contributions"]), "CONTRIBUTIONS 12 MO", ""),
        (fmt(data["repos"]), "REPOSITORIES", ""),
        (fmt(current), "CURRENT STREAK", days_unit(current)),
        (fmt(longest), "LONGEST STREAK", days_unit(longest)),
    ]
    size = 34
    col_w = (W - 2 * PAD) / 2
    row_h = (H - 48 - 66) / 3
    parts = []
    for i, (value, label, unit) in enumerate(cells):
        row, col = divmod(i, 2)
        top = 66 + row * row_h
        x = PAD + col * (col_w + 24)
        vw = text_width("SpaceGrotesk", 500, value, size)
        if unit:
            vw += 6 + text_width("JetBrainsMono", 400, unit, round(size * 0.38))
        assert vw < col_w - 24, f"stat too wide: {value}"
        parts.append(stat_block(x, round(top + 42), value, label, size, unit))
        if col == 1:
            lx = PAD + col_w
            parts.append(
                f'<line x1="{lx:.1f}" y1="{top + 16:.1f}" x2="{lx:.1f}" y2="{top + row_h - 16:.1f}" stroke="{LINE}" stroke-width="1"/>'
            )
        if row > 0 and col == 0:
            parts.append(f'<line x1="{PAD}" y1="{top:.1f}" x2="{W - PAD}" y2="{top:.1f}" stroke="{LINE}" stroke-width="1"/>')

    desc = ", ".join(f"{label.lower()}: {value}{' ' + unit if unit else ''}" for value, label, unit in cells)
    card(
        "stats.svg", W, H, "[ numbers ]", "github", "\n".join(parts),
        updated=updated,
        mono_chars="".join(c[1] + c[2] for c in cells),
        value_chars="".join(c[0] for c in cells),
        title=f"{LOGIN} GitHub numbers",
        desc=desc.capitalize() + ".",
        pad=PAD,
    )


def build_languages(languages, updated):
    W, H, PAD = CARD_W, CARD_H, SMALL_PAD
    total = sum(languages.values())
    top = sorted(languages.items(), key=lambda kv: -kv[1])[:TOP_LANGUAGES]
    rows = [(name, size * 100 / total) for name, size in top] if total else []

    parts = []
    track_w = W - 2 * PAD
    row_h = 34
    y0 = 76
    for i, (name, pct) in enumerate(rows):
        top_y = y0 + i * row_h
        label = f"{pct:.1f}%"
        fill = ACCENT if i == 0 else MUTED
        bar_w = max(2.0, track_w * pct / 100)
        parts.append(
            f'<text class="value" x="{PAD}" y="{top_y + 18}" font-size="15">{escape(name)}</text>'
            f'<text class="mono muted" x="{W - PAD}" y="{top_y + 18}" font-size="12" text-anchor="end">{label}</text>'
            f'<rect x="{PAD}" y="{top_y + 26}" width="{track_w}" height="3" rx="1.5" fill="{LINE}"/>'
            f'<rect x="{PAD}" y="{top_y + 26}" width="{bar_w:.1f}" height="3" rx="1.5" fill="{fill}"/>'
        )
    if not rows:
        parts.append(f'<text class="mono muted" x="{PAD}" y="{y0 + 18}" font-size="13">no language data yet</text>')

    pct_chars = "".join(f"{pct:.1f}%" for _, pct in rows)
    desc = ", ".join(f"{name} {pct:.1f}%" for name, pct in rows) or "No language data."
    card(
        "languages.svg", W, H, "[ languages ]", "by code size", "\n".join(parts),
        updated=updated,
        mono_chars=pct_chars + "no language data yet",
        value_chars="".join(name for name, _ in rows),
        title=f"{LOGIN} top languages",
        desc=f"Top languages by code size in own repositories: {desc}.",
        pad=PAD,
    )


def build_activity(data, current, longest, updated):
    W, H, PAD = 1000, 382, 40
    days, today = data["days"], data["today"]

    # 53 week columns, Sunday on top, the last column holds today
    weeks = 53
    start = today - dt.timedelta(days=(today.weekday() + 1) % 7 + 7 * (weeks - 1))
    label_w = 32
    gx = PAD + label_w
    gap = 3.2
    pitch = (W - PAD - gx + gap) / weeks
    cell = pitch - gap
    gy = 110

    counts = sorted(c for d, c in days.items() if start <= d <= today and c > 0)

    def quantile(q):
        return counts[min(len(counts) - 1, int(q * len(counts)))] if counts else 0

    q1, q2, q3 = quantile(0.25), quantile(0.5), quantile(0.75)
    levels = [EMPTY_CELL] + [blend(LEVEL_FROM, ACCENT, t) for t in (0.15, 0.35, 0.6, 1.0)]

    def level(c):
        if c <= 0:
            return 0
        return 1 if c <= q1 else 2 if c <= q2 else 3 if c <= q3 else 4

    by_level = {i: [] for i in range(5)}
    today_xy = None
    month_labels = []
    prev_month = None
    for col in range(weeks):
        sunday = start + dt.timedelta(days=7 * col)
        x = gx + col * pitch
        if sunday.month != prev_month:
            month_labels.append((col, sunday.strftime("%b")))
            prev_month = sunday.month
        for row in range(7):
            date = sunday + dt.timedelta(days=row)
            if date > today:
                break
            y = gy + row * pitch
            by_level[level(days.get(date, 0))].append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2.5"/>')
            if date == today:
                today_xy = (x, y)

    # Drop a month label that would collide with the next one (only the first can)
    if len(month_labels) > 1 and month_labels[1][0] - month_labels[0][0] < 3:
        month_labels.pop(0)
    months_svg = "".join(
        f'<text class="mono muted" x="{gx + col * pitch:.1f}" y="{gy - 12}" font-size="11">{name}</text>'
        for col, name in month_labels
        if gx + col * pitch + 24 <= W - PAD
    )
    day_names = "".join(
        f'<text class="mono faint" x="{PAD}" y="{gy + row * pitch + cell - 3:.1f}" font-size="10">{name}</text>'
        for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    grid = "".join(f'<g fill="{levels[i]}">{"".join(rects)}</g>' for i, rects in by_level.items() if rects)

    tx, ty = today_xy
    today_svg = (
        f'<rect class="ring" x="{tx:.1f}" y="{ty:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2.5" fill="none" stroke="{ACCENT}" stroke-width="1.2"/>'
        f'<rect class="today" x="{tx - 0.6:.1f}" y="{ty - 0.6:.1f}" width="{cell + 1.2:.1f}" height="{cell + 1.2:.1f}" rx="3" fill="none" stroke="{ACCENT}" stroke-width="1.2"/>'
    )

    # Stats row under the grid
    stats_top = 252
    col_w = (W - 2 * PAD) / 3
    stats = [
        (fmt(data["contributions"]), "CONTRIBUTIONS", ""),
        (fmt(current), "CURRENT STREAK", days_unit(current)),
        (fmt(longest), "LONGEST STREAK", days_unit(longest)),
    ]
    stats_svg = [f'<line x1="{PAD}" y1="{stats_top}" x2="{W - PAD}" y2="{stats_top}" stroke="{LINE}" stroke-width="1"/>']
    for i, (value, label, unit) in enumerate(stats):
        x = PAD + i * col_w + (0 if i == 0 else 24)
        stats_svg.append(stat_block(x, stats_top + 44, value, label, 30, unit))
        if i > 0:
            lx = PAD + i * col_w
            stats_svg.append(f'<line x1="{lx:.1f}" y1="{stats_top + 16}" x2="{lx:.1f}" y2="{stats_top + 66}" stroke="{LINE}" stroke-width="1"/>')

    # Legend: less [] [] [] [] [] more
    sw, sg = 10, 3
    more_w = text_width("JetBrainsMono", 400, "more", 11)
    lx = W - PAD - more_w - 8 - 5 * sw - 4 * sg
    legend = [f'<text class="mono faint" x="{lx - 8}" y="{H - 21}" font-size="11" text-anchor="end">less</text>']
    for i, color in enumerate(levels):
        legend.append(f'<rect x="{lx + i * (sw + sg):.1f}" y="{H - 30}" width="{sw}" height="{sw}" rx="2" fill="{color}"/>')
    legend.append(f'<text class="mono faint" x="{W - PAD}" y="{H - 21}" font-size="11" text-anchor="end">more</text>')

    scan_dur = 10
    css = f"""
.scan{{animation:scan {scan_dur}s linear infinite;}}
@keyframes scan{{0%{{transform:translateX(-40px);}}100%{{transform:translateX({W + 10}px);}}}}
.today{{animation:breathe 2.4s ease-in-out infinite;}}
@keyframes breathe{{0%,100%{{opacity:.95;}}50%{{opacity:.35;}}}}
.ring{{transform-box:fill-box;transform-origin:center;animation:ring 2.4s ease-out infinite;}}
@keyframes ring{{0%{{transform:scale(1);opacity:.6;}}100%{{transform:scale(2.2);opacity:0;}}}}
@media (prefers-reduced-motion:reduce){{
.scan,.today,.ring{{animation:none;}}
.scan,.ring{{opacity:0;}}
}}"""
    defs = f"""<linearGradient id="scanLine" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
<stop offset=".5" stop-color="{ACCENT}" stop-opacity=".55"/>
<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/>
</linearGradient>
<linearGradient id="scanGlow" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
<stop offset="1" stop-color="{ACCENT}" stop-opacity=".06"/>
</linearGradient>
"""
    scanner = (
        f'<g class="scan"><rect x="-28" y="0" width="28" height="{H}" fill="url(#scanGlow)"/>'
        f'<rect x="0" y="0" width="1" height="{H}" fill="url(#scanLine)"/></g>'
    )
    body = "\n".join([months_svg, day_names, grid, today_svg, "\n".join(stats_svg), scanner])

    card(
        "activity.svg", W, H, "[ activity ]", "last 12 months", body,
        updated=updated,
        mono_chars="".join(n for _, n in month_labels) + "MonWedFri" + "lessmore" + "".join(s[1] + s[2] for s in stats),
        value_chars="".join(s[0] for s in stats),
        title=f"{LOGIN} contribution activity",
        desc=(
            f"Contribution grid for the last 12 months. {stats[0][0]} contributions, "
            f"current streak {current} {days_unit(current)}, longest streak {longest} {days_unit(longest)}."
        ),
        css=css,
        defs=defs,
        footer_right="".join(legend),
        pad=PAD,
    )


# ------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Build the GitHub stats SVGs.")
    parser.add_argument("--demo", action="store_true", help="render made-up data, no token or API calls")
    args = parser.parse_args()

    if args.demo:
        data = demo_data()
    else:
        load_dotenv(ROOT / ".env")
        token = os.environ.get("GH_STATS_TOKEN", "").strip()
        if not token:
            sys.exit(
                "error: GH_STATS_TOKEN is not set.\n"
                "Put it in .env (see .env.example) or export it, "
                "or run with --demo to render made-up data."
            )
        try:
            data = fetch(token)
        except StatsError as e:
            sys.exit(f"error: {e}")

    current, longest = streaks(data["days"], data["today"])
    updated = data["today"].isoformat()

    ASSETS.mkdir(exist_ok=True)
    build_numbers(data, current, longest, updated)
    build_languages(data["languages"], updated)
    build_activity(data, current, longest, updated)


if __name__ == "__main__":
    main()
