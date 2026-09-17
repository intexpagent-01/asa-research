#!/usr/bin/env python3
"""Render site/history-<slug>.html: per-country issue-by-issue history."""
import os, re, json, glob
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

files = sorted(glob.glob(os.path.join(HERE, "data", "pacific-*.json")))
files = [f for f in files if "index" not in f]

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

COLORS = [
    "#0d7377", "#e05a3a", "#2563eb", "#d97706", "#7c3aed",
    "#059669", "#dc2626", "#0284c7", "#ca8a04", "#6d28d9",
    "#0891b2", "#be123c", "#4f46e5", "#ea580c",
]


def usd(v):
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def usd_m(v):
    return f"${v/1e6:.1f}M"


# Load all snapshots
all_issues = []
for f in files:
    with open(f) as fh:
        d = json.load(fh)
    date = d.get("date", os.path.basename(f)[8:18])
    all_issues.append({"date": date, "num": len(all_issues) + 1, "countries": d["countries"]})

n_issues = len(all_issues)
country_codes = list(all_issues[-1]["countries"].keys())
countries_by_spend = sorted(
    country_codes,
    key=lambda c: -all_issues[-1]["countries"][c]["dis90"]
)

extra = """
.container{max-width:860px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:1rem;line-height:1.65}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:2rem}
.key-stat{display:inline-block;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.6rem 1rem;margin:.3rem .4rem .3rem 0;font-size:.9rem}
.key-stat b{font-size:1.1rem;display:block;margin-bottom:.15rem}
.chart-wrap{margin:1.5rem 0;overflow-x:auto;-webkit-overflow-scrolling:touch}
.metrics-table{width:100%;border-collapse:collapse;font-size:.85rem;margin:1rem 0}
.metrics-table th,.metrics-table td{padding:.45rem .6rem;text-align:right;border-bottom:1px solid var(--border)}
.metrics-table th{text-align:left;font-weight:600;color:var(--text-primary);background:var(--surface-card);position:sticky;left:0}
.metrics-table td:first-child{text-align:left;font-weight:600}
.metrics-table tr:hover td{background:var(--surface-card)}
.funder-row{display:flex;align-items:center;gap:.5rem;margin:.3rem 0;font-size:.88rem}
.funder-bar{height:18px;border-radius:3px;min-width:2px}
.funder-name{min-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.funder-val{font-size:.82rem;color:var(--text-muted);min-width:60px;text-align:right}
.issue-nav{display:flex;flex-wrap:wrap;gap:.3rem;margin:.5rem 0}
.issue-nav a{display:inline-block;padding:.2rem .5rem;font-size:.78rem;border:1px solid var(--border);border-radius:4px;text-decoration:none;color:var(--text-muted)}
.issue-nav a:hover{background:var(--surface-card);color:var(--text-primary)}
.funder-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.6rem;margin:1rem 0}
.funder-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.7rem .9rem}
.funder-card h4{margin:0 0 .3rem;font-size:.9rem}
.spark-row{display:flex;align-items:center;gap:.6rem}
.spark-label{font-size:.82rem;color:var(--text-muted);min-width:50px;text-align:right}
.change-pos{color:#059669;font-weight:600}
.change-neg{color:#e05a3a;font-weight:600}
.change-flat{color:var(--text-muted)}
.country-nav{display:flex;flex-wrap:wrap;gap:.3rem;margin:1rem 0}
.country-nav a{display:inline-block;padding:.25rem .6rem;font-size:.82rem;border:1px solid var(--border);border-radius:4px;text-decoration:none;color:var(--text-muted)}
.country-nav a.current{background:var(--series-1);color:#fff;border-color:var(--series-1)}
.country-nav a:hover{background:var(--surface-card);color:var(--text-primary)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .intro{font-size:.95rem}
  .metrics-table{font-size:.78rem}
  .metrics-table th,.metrics-table td{padding:.35rem .4rem}
  .funder-grid{grid-template-columns:1fr}
}
"""

pages_rendered = 0

for code in country_codes:
    name = all_issues[-1]["countries"][code]["name"]
    slug = SLUGS.get(name, name.lower().replace(" ", "-"))
    short = SHORT.get(name, name)

    # Gather time series
    dis90_series = []
    funders_series = []
    active_series = []
    stale_series = []
    new_starts_series = []
    ending_series = []

    for iss in all_issues:
        c = iss["countries"].get(code, {})
        dis90_series.append(c.get("dis90", 0))
        funders_series.append(c.get("n_orgs_90", 0))
        active_series.append(c.get("n_active", 0))
        stale_series.append(c.get("n_stale", 0))
        new_starts_series.append(c.get("n_new_starts", 0))
        ending_series.append(c.get("n_ending_soon", 0))

    cur = all_issues[-1]["countries"][code]
    prev = all_issues[-2]["countries"][code] if n_issues >= 2 else cur

    latest_dis90 = dis90_series[-1]
    peak_dis90 = max(dis90_series)
    trough_dis90 = min(dis90_series)
    first_dis90 = dis90_series[0]
    total_change = latest_dis90 - first_dis90
    total_pct = (total_change / first_dis90 * 100) if first_dis90 != 0 else 0

    # --- Main chart: 90-day disbursement ---
    chart_w, chart_h = 700, 240
    pad_l, pad_r, pad_t, pad_b = 65, 20, 25, 55
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b

    vals = dis90_series
    y_min_raw = min(vals)
    y_max_raw = max(vals)
    margin = (y_max_raw - y_min_raw) * 0.1 if y_max_raw != y_min_raw else abs(y_max_raw) * 0.1 or 1
    y_min = y_min_raw - margin
    y_max = y_max_raw + margin

    def sx(i):
        return pad_l + (i / max(1, n_issues - 1)) * plot_w

    def sy(v):
        return pad_t + (1 - (v - y_min) / (y_max - y_min)) * plot_h

    points = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
    area = (f"{sx(0):.1f},{pad_t + plot_h:.1f} " + points +
            f" {sx(n_issues - 1):.1f},{pad_t + plot_h:.1f}")

    grid = ""
    for gi in range(6):
        gv = y_min + (y_max - y_min) * gi / 5
        gy = sy(gv)
        grid += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{chart_w - pad_r}" y2="{gy:.1f}" stroke="var(--gridline)" stroke-width="1"/>\n'
        grid += f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" font-size="11" fill="var(--text-muted)">{usd(gv)}</text>\n'

    xlabels = ""
    for i, iss in enumerate(all_issues):
        x = sx(i)
        xlabels += f'<text x="{x:.1f}" y="{pad_t + plot_h + 18}" text-anchor="middle" font-size="10" fill="var(--text-muted)">{iss["date"][5:]}</text>\n'
        xlabels += f'<text x="{x:.1f}" y="{pad_t + plot_h + 30}" text-anchor="middle" font-size="9" fill="var(--text-muted)">#{iss["num"]}</text>\n'

    dots = ""
    for i, v in enumerate(vals):
        x, y = sx(i), sy(v)
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--series-1)"/>\n'
        dots += f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-size="10" fill="var(--text-primary)" font-weight="600">{usd(v)}</text>\n'

    main_svg = f"""<svg viewBox="0 0 {chart_w} {chart_h}" style="width:100%;max-width:{chart_w}px" xmlns="http://www.w3.org/2000/svg">
{grid}
<polygon points="{area}" fill="var(--series-1)" opacity=".12"/>
<polyline points="{points}" fill="none" stroke="var(--series-1)" stroke-width="2.5" stroke-linejoin="round"/>
{dots}
{xlabels}
</svg>"""

    # --- Secondary metric charts (small multiples) ---
    sm_w, sm_h = 320, 100
    sm_pad = 30

    def small_chart(values, label, color, fmt="d"):
        vmin = min(0, min(values))
        vmax = max(values) * 1.1 if max(values) > 0 else 1
        def scx(i):
            return sm_pad + (i / max(1, len(values) - 1)) * (sm_w - 2 * sm_pad)
        def scy(v):
            return 8 + (1 - (v - vmin) / (vmax - vmin)) * (sm_h - 30)
        pts = " ".join(f"{scx(i):.1f},{scy(v):.1f}" for i, v in enumerate(values))
        area_pts = (f"{scx(0):.1f},{sm_h - 12:.1f} " + pts +
                    f" {scx(len(values) - 1):.1f},{sm_h - 12:.1f}")
        last_label = f"{values[-1]}" if fmt == "d" else usd(values[-1])
        return f"""<div style="text-align:center">
<div style="font-size:.82rem;color:var(--text-muted);margin-bottom:.2rem">{esc(label)}</div>
<svg viewBox="0 0 {sm_w} {sm_h}" style="width:100%;max-width:{sm_w}px" xmlns="http://www.w3.org/2000/svg">
<polygon points="{area_pts}" fill="{color}" opacity=".1"/>
<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>
<circle cx="{scx(len(values)-1):.1f}" cy="{scy(values[-1]):.1f}" r="3" fill="{color}"/>
<text x="{scx(len(values)-1):.1f}" y="{scy(values[-1]) - 8:.1f}" text-anchor="middle" font-size="11" fill="{color}" font-weight="600">{last_label}</text>
</svg></div>"""

    small_charts = f"""<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.8rem;margin:1.5rem 0">
{small_chart(funders_series, "Active funders (90d)", "#2563eb")}
{small_chart(active_series, "Active activities", "#059669")}
{small_chart(stale_series, "Stale activities", "#e05a3a")}
{small_chart(ending_series, "Ending soon", "#d97706")}
</div>"""

    # --- Metrics table ---
    table_rows = ""
    for i, iss in enumerate(all_issues):
        c = iss["countries"].get(code, {})
        d90 = c.get("dis90", 0)
        prev_d90 = dis90_series[i - 1] if i > 0 else d90
        change = d90 - prev_d90
        pct = (change / prev_d90 * 100) if prev_d90 != 0 else 0
        change_cls = "change-pos" if change > 0 else "change-neg" if change < 0 else "change-flat"
        change_txt = f'<span class="{change_cls}">{pct:+.0f}%</span>' if i > 0 else "&mdash;"

        table_rows += f"""<tr>
<td>#{iss['num']} ({iss['date'][5:]})</td>
<td>{usd_m(d90)}</td>
<td>{change_txt}</td>
<td>{c.get('n_orgs_90', 0)}</td>
<td>{c.get('n_active', 0)}</td>
<td>{c.get('n_stale', 0)}</td>
<td>{c.get('n_new_starts', 0)}</td>
<td>{c.get('n_ending_soon', 0)}</td>
</tr>\n"""

    # --- Top funders evolution ---
    funder_history = {}
    for i, iss in enumerate(all_issues):
        c = iss["countries"].get(code, {})
        for org in c.get("orgs_90", []):
            oname = org[0] if isinstance(org, list) else org.get("name", "")
            oval = org[1] if isinstance(org, list) else org.get("dis", 0)
            if oname not in funder_history:
                funder_history[oname] = [0] * n_issues
            funder_history[oname][i] = oval

    top_funders = sorted(funder_history.items(), key=lambda x: -max(x[1]))[:8]

    funder_cards = ""
    for fi, (fname, fvals) in enumerate(top_funders):
        color = COLORS[fi % len(COLORS)]
        latest = fvals[-1]
        peak = max(fvals)
        first_nonzero = next((v for v in fvals if v > 0), 0)
        total_change = latest - first_nonzero if first_nonzero else 0
        pct = (total_change / first_nonzero * 100) if first_nonzero != 0 else 0
        change_cls = "change-pos" if total_change > 0 else "change-neg" if total_change < 0 else "change-flat"

        fv_min = min(0, min(fvals))
        fv_max = max(fvals) * 1.1 if max(fvals) > 0 else 1

        def fcx(i):
            return 4 + (i / max(1, len(fvals) - 1)) * 152

        def fcy(v):
            return 4 + (1 - (v - fv_min) / (fv_max - fv_min)) * 40

        fpts = " ".join(f"{fcx(i):.1f},{fcy(v):.1f}" for i, v in enumerate(fvals))
        farea = (f"{fcx(0):.1f},48 " + fpts + f" {fcx(len(fvals)-1):.1f},48")

        funder_cards += f"""<div class="funder-card">
<h4>{esc(fname[:45])}</h4>
<div class="spark-row">
<svg viewBox="0 0 160 52" style="width:160px;height:52px;flex-shrink:0" xmlns="http://www.w3.org/2000/svg">
<polygon points="{farea}" fill="{color}" opacity=".1"/>
<polyline points="{fpts}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>
<circle cx="{fcx(len(fvals)-1):.1f}" cy="{fcy(fvals[-1]):.1f}" r="2.5" fill="{color}"/>
</svg>
<div>
<div style="font-size:.9rem;font-weight:600">{usd(latest)}</div>
<div class="{change_cls}" style="font-size:.78rem">{pct:+.0f}% from first</div>
</div></div></div>\n"""

    # --- Country navigation ---
    nav_links = ""
    for nav_code in countries_by_spend:
        nav_name = all_issues[-1]["countries"][nav_code]["name"]
        nav_slug = SLUGS.get(nav_name, nav_name.lower().replace(" ", "-"))
        nav_short = SHORT.get(nav_name, nav_name)
        cls = ' class="current"' if nav_code == code else ""
        nav_links += f'<a href="history-{nav_slug}.html"{cls}>{esc(nav_short)}</a>\n'

    change_word = "rose" if total_change > 0 else "fell" if total_change < 0 else "remained flat"

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name)} History &mdash; Pacific Aid Signal &mdash; Asa</title>
<meta name="description" content="Issue-by-issue history of aid to {esc(name)} across {n_issues} issues of the Pacific Aid Signal.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="pacific-signal-{slug}.html">&larr; {esc(name)} current issue</a> &middot; <a href="trends.html">Regional trends</a></p>
<header>
<h1>{esc(name)}: History</h1>
<p class="intro">How {esc(name)}&rsquo;s aid picture has moved across {n_issues} issues of the Pacific Aid Signal, from {all_issues[0]['date']} to {all_issues[-1]['date']}. The 90-day disbursement {change_word} from {usd_m(first_dis90)} to {usd_m(latest_dis90)} ({total_pct:+.0f}%).</p>
</header>

<div class="country-nav">
{nav_links}
</div>

<div class="key-stat"><b>{usd(latest_dis90)}</b> latest 90d</div>
<div class="key-stat"><b>{usd(peak_dis90)}</b> peak</div>
<div class="key-stat"><b>{total_pct:+.1f}%</b> since issue 1</div>
<div class="key-stat"><b>{cur.get('n_orgs_90', 0)}</b> funders</div>
<div class="key-stat"><b>{cur.get('n_active', 0)}</b> active</div>
<div class="key-stat"><b>{cur.get('n_stale', 0)}</b> stale</div>

<h2>90-day disbursements</h2>
<div class="chart-wrap">
{main_svg}
</div>

<h2>Other metrics</h2>
{small_charts}

<h2>Issue-by-issue metrics</h2>
<div style="overflow-x:auto">
<table class="metrics-table">
<thead><tr><th>Issue</th><th>90d spend</th><th>Change</th><th>Funders</th><th>Active</th><th>Stale</th><th>New</th><th>Ending</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
</div>

<h2>Top funders over time</h2>
<p>The {len(top_funders)} largest funders in {esc(name)}&rsquo;s 90-day table, with their spending trajectory across all issues.</p>
<div class="funder-grid">
{funder_cards}
</div>

<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
<br>Data covers {n_issues} issues from {all_issues[0]['date']} to {all_issues[-1]['date']}.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="pacific-signal-{slug}.html">{esc(name)} current</a> &middot;
<a href="trends.html">Trends</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="feed.xml">RSS feed</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

    out = os.path.join(SITE, f"history-{slug}.html")
    with open(out, "w") as fh:
        fh.write(html)
    pages_rendered += 1

print(f"rendered {pages_rendered} country history pages, {n_issues} issues each")
