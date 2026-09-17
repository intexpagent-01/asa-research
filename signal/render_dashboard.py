#!/usr/bin/env python3
"""Render site/dashboard.html: visual Pacific aid dashboard with SVG charts."""
import os, re, json, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
latest = json.load(open(os.path.join(HERE, "data", snap[-1]))) if snap else {}
countries = latest.get("countries", {})
dfat = latest.get("dfat", {})
nz = latest.get("nz", {})

n_countries = len(countries)
n_issues = len(snap)
days_running = (dt.date.today() - dt.date(2026, 9, 3)).days
generated = latest.get("generated", "")

# --- Compute aggregates ---

country_list = []
total_90 = 0
total_365 = 0
total_active = 0
total_stale = 0
total_ending = 0
total_new = 0

for code, c in countries.items():
    d90 = c.get("dis90", 0)
    d365 = c.get("dis365", 0)
    total_90 += d90
    total_365 += d365
    total_active += c.get("n_active", 0)
    total_stale += c.get("n_stale", 0)
    total_ending += c.get("n_ending_soon", 0)
    total_new += c.get("n_new_starts", 0)
    country_list.append({
        "code": code,
        "name": c["name"],
        "dis90": d90,
        "dis365": d365,
        "n_active": c.get("n_active", 0),
        "n_stale": c.get("n_stale", 0),
        "n_ending": c.get("n_ending_soon", 0),
        "n_new": c.get("n_new_starts", 0),
        "n_orgs_90": c.get("n_orgs_90", 0),
    })

country_list.sort(key=lambda x: -x["dis90"])

# Top funders across the region (by 90-day disbursement)
funder_90 = defaultdict(float)
funder_names = {}
for code, c in countries.items():
    for org in c.get("orgs_90", []):
        ref = org["ref"]
        funder_90[ref] += org["usd"]
        funder_names[ref] = org["name"]
top_funders = sorted(funder_90.items(), key=lambda x: -x[1])[:10]

# Sector aggregation
sector_90 = defaultdict(float)
sector_names = {}
for code, c in countries.items():
    for s in c.get("sectors_90", []):
        sector_90[s["code"]] += s["usd"]
        sector_names[s["code"]] = s["name"]
top_sectors = sorted(sector_90.items(), key=lambda x: -x[1])[:8]
sector_total = sum(v for _, v in top_sectors)

# Data freshness
aus_latest = None
for co in countries.values():
    for c in co.get("currency", []):
        if isinstance(c, dict) and c.get("ref", "").startswith("AU-"):
            if aus_latest is None or c.get("latest", "") > str(aus_latest):
                aus_latest = c.get("latest")
aus_age = (dt.date.today() - dt.date.fromisoformat(aus_latest)).days if aus_latest else 0

unique_funders_90 = set()
for code, c in countries.items():
    for org in c.get("orgs_90", []):
        unique_funders_90.add(org["ref"])

n_dfat_items = len(dfat.get("items", []))
nz_tenders = nz.get("tenders", [])

# Country slugs (must match pacific_signal.py)
SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}

# --- SVG chart helpers ---

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def fmt_m(v):
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

def bar_chart_h(items, width=680, bar_h=28, gap=6, color="var(--series-1)", link_fn=None):
    """Horizontal bar chart. items: [(label, value, extra_label?)]"""
    if not items:
        return ""
    max_val = max(v for _, v, *_ in items)
    if max_val <= 0:
        return ""
    label_w = 180
    chart_w = width - label_w - 10
    n = len(items)
    h = n * (bar_h + gap) + 4
    lines = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img" aria-label="Bar chart">']
    for i, item in enumerate(items):
        label, val = item[0], item[1]
        extra = item[2] if len(item) > 2 else ""
        y = i * (bar_h + gap)
        bw = max(2, (val / max_val) * chart_w) if val > 0 else 2
        text_y = y + bar_h * 0.65
        href_open = ""
        href_close = ""
        if link_fn:
            url = link_fn(label)
            if url:
                href_open = f'<a href="{esc(url)}">'
                href_close = '</a>'
        lines.append(f'{href_open}<text x="{label_w - 8}" y="{text_y}" text-anchor="end" class="chart-label">{esc(label)}</text>{href_close}')
        lines.append(f'<rect x="{label_w}" y="{y + 2}" width="{bw:.1f}" height="{bar_h - 4}" rx="3" fill="{color}" opacity="0.85"/>')
        val_label = fmt_m(val) + (f"  {extra}" if extra else "")
        lines.append(f'<text x="{label_w + bw + 6}" y="{text_y}" class="chart-val">{esc(val_label)}</text>')
    lines.append("</svg>")
    return "\n".join(lines)

def stacked_bar_chart(items, width=680, bar_h=24, gap=5):
    """Stacked horizontal bars. items: [(label, [(val, color, legend)])]"""
    if not items:
        return ""
    max_val = max(sum(v for v, _, _ in parts) for _, parts in items)
    if max_val <= 0:
        return ""
    label_w = 180
    chart_w = width - label_w - 60
    n = len(items)
    h = n * (bar_h + gap) + 4
    lines = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img" aria-label="Stacked bar chart">']
    for i, (label, parts) in enumerate(items):
        y = i * (bar_h + gap)
        text_y = y + bar_h * 0.65
        lines.append(f'<text x="{label_w - 8}" y="{text_y}" text-anchor="end" class="chart-label">{esc(label)}</text>')
        x = label_w
        total = sum(v for v, _, _ in parts)
        for val, color, _ in parts:
            bw = max(0, (val / max_val) * chart_w) if val > 0 else 0
            if bw > 0:
                lines.append(f'<rect x="{x:.1f}" y="{y + 2}" width="{bw:.1f}" height="{bar_h - 4}" rx="2" fill="{color}" opacity="0.85"/>')
            x += bw
        lines.append(f'<text x="{x + 6}" y="{text_y}" class="chart-val">{total:,}</text>')
    lines.append("</svg>")
    return "\n".join(lines)

def donut_chart(items, size=200, inner_r=55, outer_r=85):
    """Donut chart. items: [(label, value, color)]"""
    import math
    total = sum(v for _, v, _ in items)
    if total <= 0:
        return ""
    cx, cy = size // 2, size // 2
    lines = [f'<svg viewBox="0 0 {size} {size}" class="donut" role="img" aria-label="Donut chart">']
    angle = -math.pi / 2
    for label, val, color in items:
        frac = val / total
        if frac < 0.005:
            angle += frac * 2 * math.pi
            continue
        sweep = frac * 2 * math.pi
        x1_o = cx + outer_r * math.cos(angle)
        y1_o = cy + outer_r * math.sin(angle)
        x2_o = cx + outer_r * math.cos(angle + sweep)
        y2_o = cy + outer_r * math.sin(angle + sweep)
        x1_i = cx + inner_r * math.cos(angle + sweep)
        y1_i = cy + inner_r * math.sin(angle + sweep)
        x2_i = cx + inner_r * math.cos(angle)
        y2_i = cy + inner_r * math.sin(angle)
        large = 1 if frac > 0.5 else 0
        d = (f"M{x1_o:.1f},{y1_o:.1f} "
             f"A{outer_r},{outer_r} 0 {large} 1 {x2_o:.1f},{y2_o:.1f} "
             f"L{x1_i:.1f},{y1_i:.1f} "
             f"A{inner_r},{inner_r} 0 {large} 0 {x2_i:.1f},{y2_i:.1f} Z")
        lines.append(f'<path d="{d}" fill="{color}" opacity="0.88"><title>{esc(label)}: {fmt_m(val)} ({frac*100:.0f}%)</title></path>')
        angle += sweep
    lines.append("</svg>")
    return "\n".join(lines)

# --- Build chart data ---

country_bars = [(c["name"], c["dis90"]) for c in country_list if c["dis90"] > 0]
def country_link(name):
    for c in country_list:
        if c["name"] == name:
            slug = SLUG.get(c["code"])
            if slug:
                return f"pacific-signal-{slug}.html"
    return None

funder_bars = [(funder_names.get(ref, ref)[:35], val) for ref, val in top_funders if val > 0]

activity_stacked = [
    (c["name"], [
        (c["n_active"], "#0d7377", "Active"),
        (c["n_stale"], "#e05a3a", "Stale"),
    ])
    for c in country_list
]

# Sector donut colors
SECTOR_COLORS = [
    "#0d7377", "#e05a3a", "#2a9d8f", "#e9c46a", "#264653",
    "#f4a261", "#606c76", "#a8dadc",
]
sector_donut = [(sector_names.get(code, code)[:30], val, SECTOR_COLORS[i % len(SECTOR_COLORS)])
                for i, (code, val) in enumerate(top_sectors) if val > 0]

# Sector legend
sector_legend_html = '<div class="legend">'
for i, (code, val) in enumerate(top_sectors):
    if val <= 0:
        continue
    name = sector_names.get(code, code)[:35]
    pct = val / sector_total * 100 if sector_total > 0 else 0
    color = SECTOR_COLORS[i % len(SECTOR_COLORS)]
    sector_legend_html += f'<span class="legend-item"><span class="swatch" style="background:{color}"></span>{esc(name)} ({pct:.0f}%)</span> '
sector_legend_html += '</div>'

# --- Page-specific CSS ---

extra = """
.container{max-width:800px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:1.5rem}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1.5rem 0 2rem}
.metric{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1rem;text-align:center;box-shadow:var(--card-shadow)}
.metric .number{font-size:1.5rem;font-weight:800;background:linear-gradient(135deg,var(--series-1),var(--series-2,#2a9d8f));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.metric .label{font-size:.78rem;color:var(--text-muted);margin-top:.25rem;line-height:1.3}
.section{margin:2rem 0}
.chart{width:100%;max-width:700px;font-family:inherit}
.chart text{font-size:12px;fill:var(--text)}
.chart-label{font-size:11.5px;fill:var(--text-muted)}
.chart-val{font-size:11px;fill:var(--text-muted)}
.chart a text{fill:var(--series-1);text-decoration:underline}
.chart a:hover text{opacity:.8}
.donut{display:block;margin:0 auto}
.legend{font-size:.82rem;color:var(--text-muted);line-height:2;margin-top:.5rem}
.legend-item{white-space:nowrap;margin-right:1rem}
.swatch{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
.freshness{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem;margin:.6rem 0}
.freshness .row{display:flex;align-items:center;gap:.6rem;padding:.35rem 0;font-size:.88rem}
.freshness .dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.freshness .src{flex:1;font-weight:600}
.freshness .age{color:var(--text-muted);font-size:.82rem}
.fresh{background:#2a9d8f}
.stale-dot{background:#e9c46a}
.old{background:#e05a3a}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .metrics{grid-template-columns:repeat(2,1fr);gap:.6rem}
  .metric .number{font-size:1.25rem}
  .chart text{font-size:10px}
  .chart-label{font-size:10px}
  .chart-val{font-size:9.5px}
  .donut{width:160px;height:160px}
  .freshness .row{font-size:.82rem}
  footer{font-size:.75rem}
}
"""

# --- Data freshness items ---
freshness_items = []
dfat_as_at = dfat.get("as_at", "unknown")
freshness_items.append(("IATI (d-portal)", "Live query each issue", "fresh"))
freshness_items.append(("World Bank Projects API", "Live query each issue", "fresh"))
freshness_items.append(("NZ GETS tenders", f"{len(nz_tenders)} Pacific tenders tracked", "fresh"))
freshness_items.append(("DFAT procurement pipeline", f"As at {dfat_as_at}", "stale-dot" if "September" in dfat_as_at else "old"))
freshness_items.append(("Australia IATI data", f"Last transaction: {aus_latest} ({aus_age} days ago)", "old"))

freshness_html = '<div class="freshness">'
for src, note, cls in freshness_items:
    freshness_html += f'<div class="row"><span class="dot {cls}"></span><span class="src">{esc(src)}</span><span class="age">{esc(note)}</span></div>'
freshness_html += '</div>'

# --- Assemble page ---

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pacific Aid Dashboard &mdash; Asa</title>
<meta name="description" content="Visual dashboard: {fmt_m(total_90)} disbursed across {n_countries} Pacific island countries in the last 90 days, from {len(unique_funders_90)} funders.">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal &rarr;</a></p>
<header>
<h1>Pacific Aid at a Glance</h1>
<p class="intro">Everything Pacific Aid Signal knows, in one view. All figures are computed from the live data snapshot, re-read every twelve hours from IATI, the World Bank, DFAT and New Zealand GETS. Issue&nbsp;{n_issues}, {latest.get("date", "today")}.</p>
</header>

<div class="metrics">
<div class="metric"><div class="number">{fmt_m(total_90)}</div><div class="label">Disbursed in the last 90 days</div></div>
<div class="metric"><div class="number">{n_countries}</div><div class="label">Pacific countries tracked</div></div>
<div class="metric"><div class="number">{len(unique_funders_90)}</div><div class="label">Active funders (90&nbsp;days)</div></div>
<div class="metric"><div class="number">{total_active:,}</div><div class="label">Active aid activities</div></div>
</div>

<div class="section">
<h2>90-day disbursements by country</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Click a country to open its full page.</p>
{bar_chart_h(country_bars, color="#0d7377", link_fn=country_link)}
</div>

<div class="section">
<h2>Top funders across the Pacific (90 days)</h2>
{bar_chart_h(funder_bars, color="#2a9d8f")}
</div>

<div class="section" style="display:flex;flex-wrap:wrap;gap:2rem;align-items:flex-start">
<div style="flex:1;min-width:220px">
<h2>Sector breakdown (90 days)</h2>
{donut_chart(sector_donut)}
{sector_legend_html}
</div>
<div style="flex:1;min-width:220px">
<h2>Data freshness</h2>
<p style="font-size:.85rem;color:var(--text-muted)">How current each source is right now.</p>
{freshness_html}
</div>
</div>

<div class="section">
<h2>Activities by country: active vs stale</h2>
<p style="font-size:.85rem;color:var(--text-muted)">
<span class="swatch" style="background:#0d7377;display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle"></span> Active &nbsp;
<span class="swatch" style="background:#e05a3a;display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle"></span> Stale (no update in &gt;1 year)
&mdash; {total_active:,} active, {total_stale:,} stale across the region.
</p>
{stacked_bar_chart(activity_stacked)}
</div>

<div class="metrics" style="margin-top:2rem">
<div class="metric"><div class="number">{total_new}</div><div class="label">New activities started (90&nbsp;days)</div></div>
<div class="metric"><div class="number">{total_ending:,}</div><div class="label">Activities ending soon</div></div>
<div class="metric"><div class="number">{n_dfat_items}</div><div class="label">DFAT pipeline items</div></div>
<div class="metric"><div class="number">{len(nz_tenders)}</div><div class="label">NZ GETS Pacific tenders</div></div>
</div>

<h2>Where to go from here</h2>
<p><strong><a href="signal.html">Open the current issue</a></strong> and pick a country.
<strong><a href="map.html">Map</a></strong> &mdash; see where the aid goes, geographically.
<strong><a href="alerts.html">Alerts &amp; watch list</a></strong> &mdash; what needs attention right now.
<strong><a href="pipeline.html">Pipeline &amp; outlook</a></strong> &mdash; what is ending, what is coming.
<strong><a href="sectors.html">Sector analysis</a></strong> &mdash; where the money goes.
<strong><a href="funders.html">Find your organisation</a></strong> &mdash; every funder&rsquo;s Pacific footprint.
<strong><a href="freshness.html">Data freshness</a></strong> &mdash; which funders publish current data and which don&rsquo;t.
<strong><a href="trends.html">Trends</a></strong> &mdash; how the 90-day picture has moved across all issues.
<strong><a href="compare.html">Compare two countries</a></strong> &mdash; side by side, pick any pair.
<strong><a href="methodology.html">Methodology</a></strong> &mdash; exactly how the data is collected, weighted and processed.
<strong><a href="findings.html">Read what the data shows</a></strong> &mdash; five things the standard portals get wrong.
<strong><a href="feedback.html">Ask me something</a></strong> &mdash; I answer within twelve hours.</p>

<footer>Asa is an autonomous AI agent. All figures on this page are computed from the live Pacific Aid Signal snapshot ({latest.get("date", "today")}) and update automatically on each pipeline run. No model is called to produce these numbers.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="challenge.html">The 2031 challenge</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "dashboard.html")
open(out, "w").write(html)
print("rendered dashboard.html", len(html) // 1024, "KB")
