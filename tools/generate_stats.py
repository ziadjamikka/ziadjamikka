#!/usr/bin/env python3
"""
generate_stats.py — renders the GitHub stats cards embedded in README.md
(stats.svg, langs.svg, streak.svg) in the profile's own palette, so the profile
does not depend on third-party card services, which are frequently paused or
rate-limited.

    python tools/generate_stats.py [OUT_DIR]               fetch + render (default: dist)
    python tools/generate_stats.py OUT_DIR --from-cache    re-render from OUT_DIR/data.json

Runs daily from .github/workflows/stats.yml, which publishes OUT_DIR to the
`stats` branch. Standard library only. Set GITHUB_TOKEN to raise the API rate
limit (the workflow passes the Actions token automatically).
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USER = os.environ.get("GITHUB_USER", "ziadjamikka")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"

# ---- Scary Forest palette (same as tools/generate_svgs.py) -------------------
NAVY = "#0c1622"    # background
TEAL = "#23444b"    # secondary / edges
SAGE = "#628d7c"    # accent, labels
MOSS = "#1f2b29"    # dark fills
MIST = "#a7c6ba"    # lighter tint of SAGE for the big numbers
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
LANG_ALIASES = {"Jupyter Notebook": "Jupyter", "Dockerfile": "Docker"}   # keep legend names short
LANG_SHADES = ["#a7c6ba", "#628d7c", "#4f7a6b", "#3d6357", "#2e4f48", "#23444b", "#1f2b29"]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ---- data ---------------------------------------------------------------------
def _get(url: str, *, auth: bool = True, accept: str = "application/vnd.github+json") -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile-stats", "Accept": accept})
    if auth and TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def api(path: str):
    """GET an API path as JSON. Falls back to an unauthenticated call if the token is
    rejected, and waits out a secondary rate limit once."""
    url = API + path
    status, body = _get(url)
    if status in (401, 403, 422) and TOKEN and b"rate limit" not in body.lower():
        status, body = _get(url, auth=False)
    if status in (403, 429) and b"rate limit" in body.lower():
        log("  rate limited, waiting 65s")
        time.sleep(65)
        status, body = _get(url)
    if status != 200:
        raise RuntimeError(f"GET {path} -> HTTP {status}: {body[:200]!r}")
    return json.loads(body)


def paged(path: str) -> list:
    out, page, sep = [], 1, ("&" if "?" in path else "?")
    while True:
        chunk = api(f"{path}{sep}per_page=100&page={page}")
        out.extend(chunk)
        if len(chunk) < 100:
            return out
        page += 1


def fetch_calendar() -> list[list]:
    """[[YYYY-MM-DD, count], ...] for the last year, parsed from the public
    contributions graph (no token needed, same source the snake uses)."""
    status, body = _get(f"https://github.com/users/{USER}/contributions", auth=False, accept="text/html")
    if status != 200:
        raise RuntimeError(f"contributions page -> HTTP {status}")
    html = body.decode("utf-8", "replace")
    days: dict[str, list] = {}
    for tag in re.findall(r'<td[^>]*class="ContributionCalendar-day"[^>]*>', html):
        d = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        i = re.search(r'id="([^"]+)"', tag)
        if d and i:
            days[i.group(1)] = [d.group(1), 0]
    for cid, text in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
        if cid in days:
            m = re.match(r"\s*([\d,]+)\s+contribution", text)
            days[cid][1] = int(m.group(1).replace(",", "")) if m else 0
    cal = sorted(days.values())
    if len(cal) < 300:
        raise RuntimeError(f"calendar parse failed ({len(cal)} days found)")
    return cal


def fetch() -> dict:
    log("profile")
    profile = api(f"/users/{USER}")
    log("repositories")
    repos = paged(f"/users/{USER}/repos?type=owner")
    sources = [r for r in repos if not r["fork"] and not r["archived"] and r["size"] > 0]
    langs: dict[str, int] = {}
    log(f"languages of {len(sources)} repositories")
    for r in sources:
        for name, size in api(f"/repos/{r['full_name']}/languages").items():
            langs[name] = langs.get(name, 0) + size
    log("search counts")
    q = urllib.parse.quote
    commits = api(f"/search/commits?q={q(f'author:{USER}')}&per_page=1")["total_count"]
    prs = api(f"/search/issues?q={q(f'author:{USER} type:pr')}&per_page=1")["total_count"]
    issues = api(f"/search/issues?q={q(f'author:{USER} type:issue')}&per_page=1")["total_count"]
    reviews = api(f"/search/issues?q={q(f'reviewed-by:{USER} type:pr')}&per_page=1")["total_count"]
    since = (date.today() - timedelta(days=365)).isoformat()
    contributed, page = set(), 1
    while True:
        res = api(f"/search/commits?q={q(f'author:{USER} committer-date:>{since}')}&per_page=100&page={page}")
        for it in res["items"]:
            repo = it["repository"]
            if repo["owner"]["login"].lower() != USER.lower():
                contributed.add(repo["full_name"])
        if len(res["items"]) < 100 or page >= 5:
            break
        page += 1
    log("contribution calendar")
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": profile.get("name") or USER,
        "followers": profile["followers"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "commits": commits, "prs": prs, "issues": issues, "reviews": reviews,
        "contributed": len(contributed),
        "languages": dict(sorted(langs.items(), key=lambda kv: -kv[1])),
        "calendar": fetch_calendar(),
    }


# ---- derived numbers --------------------------------------------------------------
def rank(d: dict) -> tuple[str, float]:
    """Port of github-readme-stats' calculateRank: (level, percentile)."""
    exp_cdf = lambda x: 1 - 2 ** (-x)
    log_norm_cdf = lambda x: x / (1 + x)
    parts = [(2, exp_cdf(d["commits"] / 1000)), (3, exp_cdf(d["prs"] / 50)),
             (1, exp_cdf(d["issues"] / 25)), (1, exp_cdf(d["reviews"] / 2)),
             (4, log_norm_cdf(d["stars"] / 50)), (1, log_norm_cdf(d["followers"] / 10))]
    pct = (1 - sum(w * v for w, v in parts) / sum(w for w, _ in parts)) * 100
    for t, lvl in zip([1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100],
                      ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]):
        if pct <= t:
            return lvl, pct
    return "C", pct


def streaks(calendar: list[list]) -> dict:
    counts = {date.fromisoformat(d): c for d, c in calendar}
    today = max(counts)
    end = today if counts[today] > 0 else today - timedelta(days=1)   # an empty today doesn't break a streak yet
    cur, d = 0, end
    while d in counts and counts[d] > 0:
        cur, d = cur + 1, d - timedelta(days=1)
    best, run, start = (0, None, None), 0, None
    for d in sorted(counts):
        if counts[d] > 0:
            run, start = run + 1, (start or d)
            if run > best[0]:
                best = (run, start, d)
        else:
            run, start = 0, None
    return {"total": sum(counts.values()), "first": min(counts), "last": today,
            "current": cur, "current_range": (end - timedelta(days=cur - 1), end) if cur else None,
            "longest": best[0], "longest_range": (best[1], best[2]) if best[0] else None}


def fmt_day(d: date, year: bool = False) -> str:
    return f"{d:%b} {d.day}" + (f", {d.year}" if year else "")


def fmt_range(r: tuple[date, date] | None) -> str:
    if not r:
        return "no streak yet"
    a, b = r
    if a == b:
        return fmt_day(a, a.year != date.today().year)
    return f"{fmt_day(a, a.year != b.year)} - {fmt_day(b, b.year != date.today().year)}"


# ---- SVG helpers ------------------------------------------------------------------
def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card(w: int, h: int, label: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}">
<title>{esc(label)}</title>
<defs>
  <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">
    <circle cx="1.5" cy="1.5" r="1" fill="{TEAL}" opacity="0.5"/>
  </pattern>
</defs>
<style>
  text {{ font-family: {FONT}; }}
  .title {{ font-size: 18px; font-weight: 700; fill: {SAGE}; }}
  .label {{ font-size: 14px; font-weight: 600; fill: {SAGE}; }}
  .value {{ font-size: 14px; font-weight: 700; fill: {MIST}; }}
  .big   {{ font-size: 30px; font-weight: 700; fill: {MIST}; }}
  .sub   {{ font-size: 11px; font-weight: 500; fill: {SAGE}; opacity: 0.85; }}
  .icon  {{ fill: none; stroke: {SAGE}; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }}
</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{NAVY}" stroke="{TEAL}"/>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="url(#dots)"/>
{body}
</svg>
"""


ICONS = {   # 16x16 glyphs, drawn with the .icon stroke style
    "star": '<path d="M8 1.8l1.9 4 4.4.6-3.2 3 .8 4.4L8 11.7l-3.9 2.1.8-4.4-3.2-3 4.4-.6z"/>',
    "commit": '<circle cx="8" cy="8" r="3.2"/><path d="M1.5 8h3.3M11.2 8h3.3"/>',
    "pr": '<circle cx="4" cy="3.5" r="2"/><circle cx="4" cy="12.5" r="2"/><circle cx="12" cy="12.5" r="2"/>'
          '<path d="M4 5.5v5M12 10.5V7a2.5 2.5 0 0 0-2.5-2.5H8.5M10 2.5l-2 2 2 2"/>',
    "issue": '<circle cx="8" cy="8" r="6.2"/><circle cx="8" cy="8" r="1.4" fill="' + SAGE + '"/>',
    "repo": '<path d="M3 2.5h9a1 1 0 0 1 1 1v10.5H4.5a1.5 1.5 0 0 1-1.5-1.5z"/><path d="M3 11.5A1.5 1.5 0 0 1 4.5 10H13M6 5.5h4"/>',
    "flame": '<path d="M8 1.5c.6 2.4 3.8 3.6 3.8 7.2A3.8 3.8 0 0 1 8 12.5a3.8 3.8 0 0 1-3.8-3.8c0-1.6.8-2.6 1.5-3.4'
             '.2 1 .7 1.6 1.4 1.9C7.2 5.4 7.5 3.5 8 1.5z"/>',
}


def icon(name: str, x: float, y: float, scale: float = 1.0) -> str:
    return f'<g class="icon" transform="translate({x},{y}) scale({scale})">{ICONS[name]}</g>'


def ring(cx: float, cy: float, r: float, progress: float, width: float = 7) -> str:
    """Progress ring drawn clockwise from the top; animates in, static fallback is the final state."""
    circ = 2 * math.pi * r
    off = circ * (1 - max(0.0, min(1.0, progress)))
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TEAL}" stroke-width="{width}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{SAGE}" stroke-width="{width}" stroke-linecap="round" '
            f'stroke-dasharray="{circ:.2f}" stroke-dashoffset="{off:.2f}" transform="rotate(-90 {cx} {cy})">'
            f'<animate attributeName="stroke-dashoffset" from="{circ:.2f}" to="{off:.2f}" dur="1.2s" fill="freeze" '
            f'calcMode="spline" keySplines="0.2 0.7 0.3 1"/>'
            f'</circle>')


def sparkline(calendar: list[list], *, x: float, y: float, w: float, h: float) -> str:
    """Weekly contribution totals as a smooth area chart; draws itself in, static fallback is the final state."""
    days = [c for _, c in calendar]
    weeks = [sum(days[i:i + 7]) for i in range(0, len(days), 7)]
    weeks = [sum(weeks[max(0, i - 1):i + 2]) / len(weeks[max(0, i - 1):i + 2]) for i in range(len(weeks))]  # light smoothing
    top = max(weeks) or 1
    n = len(weeks)
    pts = [(x + w * i / (n - 1), y + h - (h - 6) * v / top) for i, v in enumerate(weeks)]
    path = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"          # Catmull-Rom -> cubic Bezier for a soft line
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    area = f"{path} L{pts[-1][0]:.1f},{y + h:.1f} L{pts[0][0]:.1f},{y + h:.1f} Z"
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) * 1.15
    lx, ly = pts[-1]
    return (f'<defs><linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{SAGE}" stop-opacity="0.45"/><stop offset="1" stop-color="{SAGE}" stop-opacity="0"/>'
            f'</linearGradient></defs>'
            f'<line x1="{x}" y1="{y + h}" x2="{x + w}" y2="{y + h}" stroke="{TEAL}"/>'
            f'<path d="{area}" fill="url(#spark)"><animate attributeName="opacity" from="0" to="1" dur="1.4s" fill="freeze"/></path>'
            f'<path d="{path}" fill="none" stroke="{SAGE}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-dasharray="{length:.0f}" stroke-dashoffset="0">'
            f'<animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" dur="1.4s" fill="freeze"/></path>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{MIST}"/>')


# ---- cards ---------------------------------------------------------------------------
def render_stats(d: dict) -> str:
    first = d["name"].split()[0]
    rows = [("star", "Total stars", d["stars"]), ("commit", "Total commits", d["commits"]),
            ("pr", "Total PRs", d["prs"]), ("issue", "Total issues", d["issues"]),
            ("repo", "Contributed to (last year)", d["contributed"])]
    body = [f'<text x="25" y="36" class="title">{esc(first)}\'s GitHub stats</text>']
    for i, (ic, label, value) in enumerate(rows):
        y = 66 + i * 26
        body.append(icon(ic, 25, y - 12))
        body.append(f'<text x="50" y="{y}" class="label">{esc(label)}:</text>')
        body.append(f'<text x="265" y="{y}" class="value">{value:,}</text>')
    body.append(sparkline(d["calendar"], x=305, y=70, w=120, h=78))
    body.append('<text x="365" y="58" text-anchor="middle" class="sub">Contributions · last 12 months</text>')
    return card(450, 195, f"{d['name']}'s GitHub stats", "\n".join(body))


def render_langs(d: dict) -> str:
    total = sum(d["languages"].values()) or 1
    items = list(d["languages"].items())[:6]
    rest = total - sum(v for _, v in items)
    if rest > 0:
        items.append(("Other", rest))
    body = ['<text x="25" y="36" class="title">Most used languages</text>']
    x, bar_w = 25.0, 250.0
    body.append('<clipPath id="bar"><rect x="25" y="52" width="250" height="9" rx="4.5"/></clipPath>'
                '<g clip-path="url(#bar)">')
    for i, (_, v) in enumerate(items):
        w = bar_w * v / total
        body.append(f'<rect x="{x:.2f}" y="52" width="{w:.2f}" height="9" fill="{LANG_SHADES[i % len(LANG_SHADES)]}"/>')
        x += w
    # a NAVY cover that slides away reveals the bar; static renderers see width 0 (no cover)
    body.append(f'<rect x="275" y="52" width="0" height="9" fill="{NAVY}">'
                f'<animate attributeName="width" from="250" to="0" dur="1s" fill="freeze"/>'
                f'<animate attributeName="x" from="25" to="275" dur="1s" fill="freeze"/></rect></g>')
    for i, (name, v) in enumerate(items):
        col, row = i % 2, i // 2
        lx, ly = 25 + col * 130, 88 + row * 26
        body.append(f'<circle cx="{lx + 5}" cy="{ly - 5}" r="5" fill="{LANG_SHADES[i % len(LANG_SHADES)]}"/>')
        body.append(f'<text x="{lx + 17}" y="{ly}" class="value" style="font-size:13px">{esc(LANG_ALIASES.get(name, name))}</text>')
        body.append(f'<text x="{lx + 122}" y="{ly}" text-anchor="end" class="label" '
                    f'style="font-size:12px">{100 * v / total:.1f}%</text>')
    return card(300, 195, "Most used languages", "\n".join(body))


def render_streak(d: dict) -> str:
    s = streaks(d["calendar"])
    body = [f'<line x1="165" y1="30" x2="165" y2="165" stroke="{TEAL}"/>',
            f'<line x1="330" y1="30" x2="330" y2="165" stroke="{TEAL}"/>']
    # total contributions (last 12 months)
    body.append(f'<text x="82.5" y="98" text-anchor="middle" class="big">{s["total"]:,}</text>')
    body.append('<text x="82.5" y="126" text-anchor="middle" class="label">Contributions</text>')
    body.append(f'<text x="82.5" y="146" text-anchor="middle" class="sub">{esc(fmt_day(s["first"], True))} - Present</text>')
    # current streak
    cx, cy, r = 247.5, 88, 40
    body.append(ring(cx, cy, r, 1.0 if s["current"] else 0.0, 6))
    body.append(f'<circle cx="{cx}" cy="{cy - r}" r="11" fill="{NAVY}"/>')
    body.append(f'<g transform="translate({cx - 8},{cy - r - 8})"><g class="icon" style="stroke:{MIST};fill:{SAGE}">'
                f'{ICONS["flame"]}<animateTransform attributeName="transform" type="scale" values="1;1.08;1" '
                f'dur="1.6s" repeatCount="indefinite" additive="sum"/></g></g>')
    body.append(f'<text x="{cx}" y="{cy + 11}" text-anchor="middle" class="big">{s["current"]}</text>')
    body.append(f'<text x="{cx}" y="{cy + r + 22}" text-anchor="middle" class="label">Current streak</text>')
    body.append(f'<text x="{cx}" y="{cy + r + 42}" text-anchor="middle" class="sub">{esc(fmt_range(s["current_range"]))}</text>')
    # longest streak
    body.append(f'<text x="412.5" y="98" text-anchor="middle" class="big">{s["longest"]}</text>')
    body.append('<text x="412.5" y="126" text-anchor="middle" class="label">Longest streak</text>')
    body.append(f'<text x="412.5" y="146" text-anchor="middle" class="sub">{esc(fmt_range(s["longest_range"]))}</text>')
    body.append('<text x="470" y="182" text-anchor="end" class="sub" style="font-size:9px;opacity:0.55">last 12 months</text>')
    return card(495, 195, "Contribution streak", "\n".join(body))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0] if args else "dist")
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "data.json"
    if "--from-cache" in sys.argv and cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        data = fetch()
        cache.write_text(json.dumps(data, indent=1), encoding="utf-8")
    (out / "stats.svg").write_text(render_stats(data), encoding="utf-8")
    (out / "langs.svg").write_text(render_langs(data), encoding="utf-8")
    (out / "streak.svg").write_text(render_streak(data), encoding="utf-8")
    log(f"rendered stats.svg, langs.svg, streak.svg -> {out}")


if __name__ == "__main__":
    main()
