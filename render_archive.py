#!/usr/bin/env python3
"""Render site/archive.html: browsable archive of all published issues."""
import os, re, json, glob, datetime as dt
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

files = sorted(glob.glob(os.path.join(HERE, "data", "pacific-*.json")))
files = [f for f in files if "index" not in f]

snaps = []
for f in files:
    with open(f) as fh:
        d = json.load(fh)
    snaps.append(d)

SLUGS = {
    "Papua New Guinea": "papua-new-guinea", "Fiji": "fiji",
    "Solomon Islands": "solomon-islands", "Vanuatu": "vanuatu",
    "Samoa": "samoa", "Tonga": "tonga", "Kiribati": "kiribati",
    "Tuvalu": "tuvalu", "Micronesia (Fed. States)": "micronesia",
    "Marshall Islands": "marshall-islands", "Palau": "palau",
    "Nauru": "nauru", "Niue": "niue", "Cook Islands": "cook-islands",
}

SHORT = {
    "Papua New Guinea": "PNG", "Fiji": "Fiji", "Solomon Islands": "Solomon Is",
    "Vanuatu": "Vanuatu", "Samoa": "Samoa", "Tonga": "Tonga",
    "Kiribati": "Kiribati", "Tuvalu": "Tuvalu",
    "Micronesia (Fed. States)": "Micronesia", "Marshall Islands": "Marshall Is",
    "Palau": "Palau", "Nauru": "Nauru", "Niue": "Niue",
    "Cook Islands": "Cook Is",
}


def usd(v):
    if abs(v) >= 1e9: return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6: return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def snap_date(s):
    return s.get("date", s.get("generated", "")[:10])


def tot90(s):
    return sum(c["dis90"] for c in s["countries"].values())


def n_active(s):
    return sum(c.get("n_active", 0) for c in s["countries"].values())


def n_stale(s):
    return sum(c.get("n_stale", 0) for c in s["countries"].values())


def n_funders_90(s):
    names = set()
    for c in s["countries"].values():
        for o in c.get("top_orgs_90", []):
            names.add(o["name"])
    return len(names)


def n_new_starts(s):
    return sum(c.get("n_new_starts", 0) for c in s["countries"].values())


def n_ending(s):
    return sum(c.get("n_ending_soon", 0) for c in s["countries"].values())


def dfat_as_at(s):
    return s.get("dfat", {}).get("as_at", "?")


def nz_count(s):
    return len(s.get("nz", {}).get("tenders", []))


def format_date(d):
    try:
        return dt.date.fromisoformat(d).strftime("%-d %B %Y")
    except Exception:
        return d


n_issues = len(snaps)

# --- SVG mini chart: regional 90-day total across issues ---
chart_w, chart_h = 700, 140
pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 32
plot_w = chart_w - pad_l - pad_r
plot_h = chart_h - pad_t - pad_b

totals = [tot90(s) for s in snaps]
y_min = min(totals) * 0.92
y_max = max(totals) * 1.05
y_rng = y_max - y_min if y_max > y_min else 1

pts = []
for i, v in enumerate(totals):
    x = pad_l + (i / max(len(totals) - 1, 1)) * plot_w
    y = pad_t + plot_h - ((v - y_min) / y_rng) * plot_h
    pts.append((x, y, v, i + 1))

polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)
dots = ""
for x, y, v, n in pts:
    dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--series-1)" class="dot" data-issue="{n}"/>'
    dots += f'<text x="{x:.1f}" y="{y:.1f}-16" text-anchor="middle" font-size="10" fill="var(--text-muted)">{usd(v)}</text>'.replace('y="' + f"{y:.1f}" + '-16"', f'y="{y - 16:.1f}"')

xlabels = ""
for x, _, _, n in pts:
    xlabels += f'<text x="{x:.1f}" y="{chart_h - 5}" text-anchor="middle" font-size="10" fill="var(--text-muted)">#{n}</text>'

ylabels = ""
for tick in range(3):
    v = y_min + tick * y_rng / 2
    y = pad_t + plot_h - (tick * plot_h / 2)
    ylabels += f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="var(--text-muted)">{usd(v)}</text>'
    ylabels += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{chart_w - pad_r}" y2="{y:.1f}" stroke="var(--gridline)" stroke-dasharray="3,3"/>'

area_pts = f"{pts[0][0]:.1f},{pad_t + plot_h} " + polyline + f" {pts[-1][0]:.1f},{pad_t + plot_h}"

trend_svg = f"""<svg viewBox="0 0 {chart_w} {chart_h}" style="width:100%;max-width:{chart_w}px" xmlns="http://www.w3.org/2000/svg">
{ylabels}
<polygon points="{area_pts}" fill="var(--series-1)" opacity="0.08"/>
<polyline points="{polyline}" fill="none" stroke="var(--series-1)" stroke-width="2.5"/>
{dots}
{xlabels}
</svg>"""

# --- Issue cards, newest first ---
cards_html = []
for idx in range(len(snaps) - 1, -1, -1):
    s = snaps[idx]
    issue_num = idx + 1
    d = snap_date(s)
    total = tot90(s)
    prev_total = tot90(snaps[idx - 1]) if idx > 0 else None
    delta = total - prev_total if prev_total is not None else None
    delta_pct = (delta / prev_total * 100) if (prev_total and abs(prev_total) > 1000) else None

    active = n_active(s)
    stale = n_stale(s)
    funders = n_funders_90(s)
    new = n_new_starts(s)
    ending = n_ending(s)
    dfat = dfat_as_at(s)
    nzt = nz_count(s)

    # Delta badge
    delta_html = ""
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        color = "var(--series-1)" if delta >= 0 else "var(--series-2, #e05a3a)"
        pct_str = f" ({sign}{delta_pct:.1f}%)" if delta_pct is not None else ""
        delta_html = f'<span class="delta" style="color:{color}">{sign}{usd(delta)}{pct_str} from previous issue</span>'

    # Metrics row
    metrics = f"""<div class="metrics">
<span>90-day total: <b>{usd(total)}</b></span>
<span>Active: <b>{active:,}</b></span>
<span>Stale: <b>{stale:,}</b></span>
<span>Funders: <b>{funders}</b></span>
<span>New starts: <b>{new}</b></span>
<span>Ending soon: <b>{ending:,}</b></span>
<span>DFAT: <b>as at {esc(str(dfat))}</b></span>"""
    if nzt:
        metrics += f'\n<span>NZ tenders: <b>{nzt}</b></span>'
    metrics += "</div>"

    # Per-country breakdown table (in a <details>)
    countries = sorted(s["countries"].values(), key=lambda c: -c["dis90"])
    max_dis = max((c["dis90"] for c in countries), default=1)
    if max_dis <= 0:
        max_dis = 1

    rows = ""
    for c in countries:
        name = c["name"]
        slug = SLUGS.get(name, "")
        short = SHORT.get(name, name)
        dis = c["dis90"]
        bar_w = max(dis / max_dis * 100, 0) if dis > 0 else 0
        n_act = c.get("n_active", 0)
        n_st = c.get("n_stale", 0)
        n_orgs = c.get("n_orgs_90", 0)

        prev_c = None
        if idx > 0:
            prev_s = snaps[idx - 1]
            for pc in prev_s["countries"].values():
                if pc["name"] == name:
                    prev_c = pc
                    break
        c_delta = ""
        if prev_c is not None:
            cd = dis - prev_c["dis90"]
            if abs(cd) > 1000:
                csign = "+" if cd >= 0 else ""
                ccolor = "var(--series-1)" if cd >= 0 else "var(--series-2, #e05a3a)"
                c_delta = f' <span style="color:{ccolor};font-size:.78rem">{csign}{usd(cd)}</span>'

        rows += f"""<tr>
<td><a href="pacific-signal-{slug}.html">{esc(short)}</a></td>
<td style="text-align:right">{usd(dis)}{c_delta}</td>
<td><div class="bar-bg"><div class="bar-fill" style="width:{bar_w:.1f}%"></div></div></td>
<td style="text-align:right">{n_orgs}</td>
<td style="text-align:right">{n_act:,}</td>
<td style="text-align:right">{n_st:,}</td>
</tr>"""

    country_table = f"""<details class="country-detail">
<summary>Country breakdown ({len(countries)} countries)</summary>
<table class="ctable">
<thead><tr><th>Country</th><th style="text-align:right">90-day</th><th style="width:30%">Share</th><th style="text-align:right">Funders</th><th style="text-align:right">Active</th><th style="text-align:right">Stale</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</details>"""

    # Snapshot link
    snap_fname = f"pacific-{d}.json"
    snap_link = f'<a href="{REPO}/blob/main/signal/data/{snap_fname}" class="snap-link">View raw snapshot data &rarr;</a>'

    is_latest = (idx == len(snaps) - 1)
    latest_badge = ' <span class="latest-badge">current</span>' if is_latest else ""

    cards_html.append(f"""<div class="issue-card" id="issue-{issue_num}">
<div class="issue-header">
<h3>Issue {issue_num}{latest_badge}</h3>
<div class="date">{format_date(d)}</div>
</div>
{delta_html}
{metrics}
{country_table}
<div class="card-footer">{snap_link}</div>
</div>""")


extra = """
.container{max-width:820px}
h1{margin-bottom:.3rem}
.subtitle{font-size:1.02rem;color:var(--text-muted);margin-bottom:2rem;line-height:1.6}
.summary-row{display:flex;gap:1.5rem;flex-wrap:wrap;margin:1rem 0 2rem;padding:1rem;background:var(--surface-card);border:1px solid var(--border);border-radius:8px}
.summary-row .stat{text-align:center;min-width:80px}
.summary-row .stat .val{font-size:1.3rem;font-weight:700;color:var(--text-primary)}
.summary-row .stat .lbl{font-size:.78rem;color:var(--text-muted);margin-top:.15rem}
.chart-area{margin:1.5rem 0 2.5rem}
.issue-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:1.2rem 1.5rem;margin:1rem 0}
.issue-card:hover{border-color:var(--series-1);box-shadow:0 2px 8px rgba(0,0,0,.06)}
.issue-header{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.5rem}
.issue-card h3{margin:0;font-size:1.05rem}
.issue-card .date{font-size:.85rem;color:var(--text-muted)}
.latest-badge{background:var(--series-1);color:#fff;font-size:.7rem;padding:2px 7px;border-radius:10px;vertical-align:middle;font-weight:600}
.delta{display:block;font-size:.85rem;margin:.4rem 0 .2rem;font-weight:500}
.metrics{display:flex;gap:.9rem 1.4rem;flex-wrap:wrap;margin:.6rem 0;font-size:.83rem}
.metrics span{color:var(--text-muted)}
.metrics b{color:var(--text-primary)}
.country-detail{margin:.6rem 0 .3rem}
.country-detail summary{font-size:.85rem;color:var(--series-1);cursor:pointer;font-weight:500}
.ctable{width:100%;border-collapse:collapse;font-size:.82rem;margin:.5rem 0}
.ctable th{text-align:left;font-weight:600;font-size:.78rem;color:var(--text-muted);border-bottom:1px solid var(--gridline);padding:.35rem .4rem}
.ctable td{padding:.3rem .4rem;border-bottom:1px solid var(--gridline)}
.ctable a{color:var(--series-1);text-decoration:none}
.ctable a:hover{text-decoration:underline}
.bar-bg{background:var(--gridline);border-radius:3px;height:10px;overflow:hidden}
.bar-fill{height:100%;background:var(--series-1);border-radius:3px;min-width:1px}
.card-footer{margin-top:.6rem;padding-top:.5rem;border-top:1px solid var(--gridline);font-size:.82rem}
.snap-link{color:var(--series-1);text-decoration:none}
.snap-link:hover{text-decoration:underline}
.jump-nav{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0 1.5rem;font-size:.85rem}
.jump-nav a{color:var(--series-1);text-decoration:none;padding:.25rem .6rem;border:1px solid var(--border);border-radius:5px}
.jump-nav a:hover{background:var(--series-1);color:#fff}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .issue-card{padding:.9rem 1rem}
  .summary-row{gap:.8rem;padding:.8rem}
  .summary-row .stat .val{font-size:1.1rem}
  .metrics{gap:.6rem .9rem}
}
"""

# Summary stats
latest = snaps[-1]
first = snaps[0]
first_date = format_date(snap_date(first))
latest_date = format_date(snap_date(latest))
start_d = dt.date.fromisoformat(snap_date(first))
end_d = dt.date.fromisoformat(snap_date(latest))
days_span = (end_d - start_d).days

# Jump nav
jump_links = " ".join(f'<a href="#issue-{i+1}">#{i+1}</a>' for i in range(len(snaps) - 1, -1, -1))

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Issue Archive &mdash; Pacific Aid Signal &mdash; Asa</title>
<meta name="description" content="Browse all {n_issues} published issues of Pacific Aid Signal: per-country breakdowns, change deltas, and raw snapshot data for each issue.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a></p>
<header>
<h1>Issue Archive</h1>
<p class="subtitle">{n_issues}&nbsp;issues published over {days_span}&nbsp;days, from {first_date} to {latest_date}. Each issue is a complete snapshot of aid flows to 14&nbsp;Pacific island countries, with per-country breakdowns and change tracking.</p>
</header>

<div class="summary-row">
<div class="stat"><div class="val">{n_issues}</div><div class="lbl">Issues</div></div>
<div class="stat"><div class="val">{days_span}</div><div class="lbl">Days</div></div>
<div class="stat"><div class="val">14</div><div class="lbl">Countries</div></div>
<div class="stat"><div class="val">{usd(tot90(latest))}</div><div class="lbl">Latest 90-day</div></div>
<div class="stat"><div class="val">{usd(tot90(first))}</div><div class="lbl">First 90-day</div></div>
<div class="stat"><div class="val">{n_funders_90(latest)}</div><div class="lbl">Funders</div></div>
</div>

<div class="chart-area">
<p style="font-size:.85rem;color:var(--text-muted);margin-bottom:.5rem">Regional 90-day disbursements by issue</p>
{trend_svg}
</div>

<h2 style="font-size:1.05rem;margin-bottom:.3rem">Jump to issue</h2>
<div class="jump-nav">{jump_links}</div>

{''.join(cards_html)}

<footer>Asa is an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
Every number on this page is computed from the dated snapshot files. Each issue&rsquo;s raw data is available in the repository.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="trends.html">Trends</a> &middot;
<a href="timeline.html">Timeline</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="download.html">Download data</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "archive.html")
open(out, "w").write(html)
print(f"rendered archive.html {len(html) // 1024} KB, {n_issues} issues")
