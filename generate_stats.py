"""Draws the three statistics cards for the profile README.

Runs inside GitHub Actions (see .github/workflows/stats.yml) and writes:
  assets/stats.svg   - stars, commits, PRs, issues, repos contributed to
  assets/streak.svg  - total contributions, current streak, longest streak
  assets/graph.svg   - contributions over the last 31 days
"""
import datetime as dt
import json
import os
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "safiyakhan46")
NAME = os.environ.get("DISPLAY_NAME", "Safiya")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

BG, BORDER, TEXT, MUTED, WHITE = "#0d1117", "#30363d", "#c9d1d9", "#8b949e", "#ffffff"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


def fetch():
    base = gql(
        """query($login:String!){ user(login:$login){
            repositories(ownerAffiliations:OWNER, privacy:PUBLIC, first:100){ nodes{ stargazerCount } }
            pullRequests{ totalCount } issues{ totalCount }
            repositoriesContributedTo(first:1, contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]){ totalCount }
            contributionsCollection{ contributionYears } } }""",
        {"login": USER},
    )["user"]
    days, commits_this_year = {}, 0
    this_year = dt.date.today().year
    for year in base["contributionsCollection"]["contributionYears"]:
        c = gql(
            """query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
                contributionsCollection(from:$from,to:$to){ totalCommitContributions
                  contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }""",
            {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]
        if year == this_year:
            commits_this_year = c["totalCommitContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
    return {
        "stars": sum(n["stargazerCount"] for n in base["repositories"]["nodes"]),
        "commits": commits_this_year,
        "prs": base["pullRequests"]["totalCount"],
        "issues": base["issues"]["totalCount"],
        "contributed": base["repositoriesContributedTo"]["totalCount"],
        "repos": len(base["repositories"]["nodes"]),
        "days": days,
    }


def fmt(d):
    return d.strftime("%b %-d, %Y")


def streaks(days):
    today = dt.date.today()
    dates = sorted(d for d in days if d <= today)
    first_active = next((d for d in dates if days[d] > 0), today)
    # current streak: today counts if active; otherwise start from yesterday
    cur_end = today if days.get(today, 0) > 0 else today - dt.timedelta(days=1)
    cur, d = 0, cur_end
    while days.get(d, 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    cur_start = cur_end - dt.timedelta(days=cur - 1) if cur else None
    best, best_range, run, start = 0, None, 0, None
    for d in dates:
        if days[d] > 0:
            run, start = run + 1, start or d
            if run > best:
                best, best_range = run, (start, d)
        else:
            run, start = 0, None
    total = sum(days[d] for d in dates)
    return total, first_active, cur, cur_start, cur_end, best, best_range


def card(width, height, inner):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="6" fill="{BG}" stroke="{BORDER}"/>'
            f'<g font-family="{FONT}">{inner}</g></svg>')


def stats_svg(s):
    year = dt.date.today().year
    rows = [("☆", "Total Stars Earned:", s["stars"]), ("⟲", f"Total Commits ({year}):", s["commits"]),
            ("⇄", "Total PRs:", s["prs"]), ("◎", "Total Issues:", s["issues"]),
            ("▣", "Contributed to (last year):", s["contributed"])]
    g = f'<text x="22" y="34" fill="{WHITE}" font-size="16" font-weight="600">{escape(NAME)}\'s GitHub Stats</text>'
    for i, (icon, label, val) in enumerate(rows):
        y = 70 + i * 26
        g += (f'<text x="24" y="{y}" fill="{MUTED}" font-size="13">{icon}</text>'
              f'<text x="46" y="{y}" fill="{TEXT}" font-size="13.5">{label}</text>'
              f'<text x="250" y="{y}" fill="{WHITE}" font-size="13.5" font-weight="600">{val}</text>')
    g += (f'<circle cx="345" cy="112" r="40" fill="none" stroke="{BORDER}" stroke-width="6"/>'
          f'<circle cx="345" cy="112" r="40" fill="none" stroke="{WHITE}" stroke-width="6" '
          f'stroke-dasharray="{min(s["repos"], 20) / 20 * 251:.0f} 251" transform="rotate(-90 345 112)"/>'
          f'<text x="345" y="118" text-anchor="middle" fill="{WHITE}" font-size="22" font-weight="700">{s["repos"]}</text>'
          f'<text x="345" y="172" text-anchor="middle" fill="{MUTED}" font-size="11">public repos</text>')
    return card(420, 200, g)


def streak_svg(s):
    total, first, cur, cs, ce, best, br = streaks(s["days"])
    today = dt.date.today()
    cur_range = f"{cs.strftime('%b %-d')} - {ce.strftime('%b %-d')}" if cur else today.strftime("%b %-d")
    best_range = f"{fmt(br[0])} - {fmt(br[1])}" if br else "—"
    col = lambda x, big, label, sub, bold=False: (
        f'<text x="{x}" y="{95}" text-anchor="middle" fill="{WHITE}" font-size="{30 if bold else 28}" font-weight="700">{big}</text>'
        f'<text x="{x}" y="{135 if bold else 125}" text-anchor="middle" fill="{WHITE}" font-size="13" font-weight="{600 if bold else 400}">{label}</text>'
        f'<text x="{x}" y="{158 if bold else 150}" text-anchor="middle" fill="{MUTED}" font-size="11">{sub}</text>')
    g = col(88, total, "Total Contributions", f"{fmt(first)} - Present")
    g += (f'<line x1="172" y1="30" x2="172" y2="170" stroke="{BORDER}"/><line x1="348" y1="30" x2="348" y2="170" stroke="{BORDER}"/>'
          f'<circle cx="260" cy="86" r="36" fill="none" stroke="{WHITE}" stroke-width="5"/>'
          f'<text x="260" y="44" text-anchor="middle" fill="{WHITE}" font-size="16">◆</text>')
    g += (f'<text x="260" y="97" text-anchor="middle" fill="{WHITE}" font-size="28" font-weight="700">{cur}</text>'
          f'<text x="260" y="145" text-anchor="middle" fill="{WHITE}" font-size="13" font-weight="600">Current Streak</text>'
          f'<text x="260" y="165" text-anchor="middle" fill="{MUTED}" font-size="11">{cur_range}</text>')
    g += col(432, best, "Longest Streak", best_range)
    return card(520, 200, g)


def graph_svg(s):
    today = dt.date.today()
    span = [today - dt.timedelta(days=i) for i in range(30, -1, -1)]
    vals = [s["days"].get(d, 0) for d in span]
    W, H, L, R, T, B = 900, 320, 60, 30, 60, 60
    top = max(max(vals), 4)
    step = max(1, -(-top // 5))
    top = step * 5
    x = lambda i: L + i * (W - L - R) / (len(vals) - 1)
    y = lambda v: H - B - v / top * (H - T - B)
    g = f'<text x="{W/2}" y="34" text-anchor="middle" fill="{WHITE}" font-size="17" font-weight="600">{escape(NAME)}\'s Contribution Graph</text>'
    for k in range(6):
        v = k * step
        g += (f'<line x1="{L}" y1="{y(v):.1f}" x2="{W-R}" y2="{y(v):.1f}" stroke="{BORDER}" stroke-dasharray="3 4"/>'
              f'<text x="{L-10}" y="{y(v)+4:.1f}" text-anchor="end" fill="{MUTED}" font-size="11">{v}</text>')
    for i, d in enumerate(span):
        g += f'<text x="{x(i):.1f}" y="{H-B+20}" text-anchor="middle" fill="{MUTED}" font-size="10">{d.day}</text>'
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    g += f'<polygon points="{L},{y(0):.1f} {pts} {W-R},{y(0):.1f}" fill="{WHITE}" fill-opacity="0.08"/>'
    g += f'<polyline points="{pts}" fill="none" stroke="{WHITE}" stroke-width="2.2" stroke-linejoin="round"/>'
    g += "".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.2" fill="{WHITE}"/>' for i, v in enumerate(vals))
    g += (f'<text x="{W/2}" y="{H-12}" text-anchor="middle" fill="{TEXT}" font-size="12">Days</text>'
          f'<text transform="translate(18 {H/2}) rotate(-90)" text-anchor="middle" fill="{TEXT}" font-size="12">Contributions</text>')
    return card(W, H, g)


if __name__ == "__main__":
    data = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("stats", stats_svg), ("streak", streak_svg), ("graph", graph_svg)):
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(data))
    print("Cards written.")
