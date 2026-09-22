#!/usr/bin/env python3
"""Render site/sectors.html: sector analysis across Pacific island countries."""
import os, re, json, math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
latest = json.load(open(os.path.join(HERE, "data", snap[-1]))) if snap else {}
countries = latest.get("countries", {})

SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}

SHORT = {
    "PG": "PNG", "FJ": "Fiji", "SB": "Sol Is", "VU": "Vanuatu",
    "WS": "Samoa", "TO": "Tonga", "KI": "Kiribati", "TV": "Tuvalu",
    "FM": "FSM", "MH": "RMI", "PW": "Palau", "NR": "Nauru",
    "NU": "Niue", "CK": "Cook Is",
}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def fmt_m(v):
    if abs(v) >= 1e6: return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# --- Aggregate sector data ---

sector_totals = defaultdict(float)
sector_by_country = defaultdict(dict)
country_totals = {}
country_order = sorted(countries.keys(), key=lambda cc: -countries[cc].get("dis90", 0))

for cc, c in countries.items():
    ctotal = 0
    for s in c.get("sectors_90", []):
        sector_totals[s["name"]] += s["usd"]
        sector_by_country[s["name"]][cc] = s["usd"]
        ctotal += s["usd"]
    country_totals[cc] = ctotal

ranked_sectors = sorted(sector_totals.items(), key=lambda x: -x[1])
grand_total = sum(v for _, v in ranked_sectors)
top_sectors = [(name, val) for name, val in ranked_sectors if val > 0][:15]

COLORS = [
    "#0d7377", "#e05a3a", "#2a9d8f", "#e9c46a", "#264653",
    "#f4a261", "#457b9d", "#a8dadc", "#6d597a", "#b56576",
    "#606c76", "#355070", "#e56b6f", "#eaac8b", "#588157",
]

# --- SVG: horizontal bar chart ---
def bar_chart_h(items, width=700, bar_h=26, gap=5, color="#0d7377"):
    if not items: return ""
    max_val = max(v for _, v in items)
    if max_val <= 0: return ""
    label_w = 230
    chart_w = width - label_w - 80
    n = len(items)
    h = n * (bar_h + gap) + 4
    lines = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img" aria-label="Sector bar chart">']
    for i, (label, val) in enumerate(items):
        y = i * (bar_h + gap)
        bw = max(2, (val / max_val) * chart_w)
        text_y = y + bar_h * 0.65
        pct = val / grand_total * 100 if grand_total > 0 else 0
        lines.append(f'<text x="{label_w - 8}" y="{text_y}" text-anchor="end" class="chart-label">{esc(label)}</text>')
        lines.append(f'<rect x="{label_w}" y="{y + 2}" width="{bw:.1f}" height="{bar_h - 4}" rx="3" fill="{color}" opacity="0.85"/>')
        lines.append(f'<text x="{label_w + bw + 6}" y="{text_y}" class="chart-val">{fmt_m(val)} ({pct:.0f}%)</text>')
    lines.append("</svg>")
    return "\n".join(lines)

# --- SVG: heatmap ---
def heatmap_svg(sectors, country_codes, width=720):
    if not sectors or not country_codes: return ""
    n_cols = len(country_codes)
    n_rows = len(sectors)
    cell_w = min(36, (width - 200) // n_cols)
    cell_h = 26
    label_w = 200
    top_h = 60
    w = label_w + n_cols * cell_w + 10
    h = top_h + n_rows * cell_h + 10

    all_vals = []
    for sname, _ in sectors:
        for cc in country_codes:
            v = sector_by_country.get(sname, {}).get(cc, 0)
            if v > 0:
                all_vals.append(v)
    if not all_vals: return ""
    max_val = max(all_vals)

    lines = [f'<svg viewBox="0 0 {w} {h}" class="heatmap" role="img" aria-label="Sector-country heatmap">']

    for j, cc in enumerate(country_codes):
        x = label_w + j * cell_w + cell_w // 2
        short = SHORT.get(cc, cc)
        lines.append(f'<text x="{x}" y="{top_h - 8}" text-anchor="middle" class="hm-label" transform="rotate(-45 {x} {top_h - 8})">{esc(short)}</text>')

    for i, (sname, _) in enumerate(sectors):
        y = top_h + i * cell_h
        lines.append(f'<text x="{label_w - 6}" y="{y + cell_h * 0.65}" text-anchor="end" class="hm-label">{esc(sname[:32])}</text>')
        for j, cc in enumerate(country_codes):
            x = label_w + j * cell_w
            v = sector_by_country.get(sname, {}).get(cc, 0)
            if v > 0:
                intensity = min(0.95, 0.15 + 0.8 * (math.log1p(v) / math.log1p(max_val)))
                color = f"rgba(13, 115, 119, {intensity:.2f})"
                lines.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cell_w - 2}" height="{cell_h - 2}" rx="3" fill="{color}"><title>{esc(sname)}: {esc(countries[cc]["name"])} — {fmt_m(v)}</title></rect>')
            else:
                lines.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cell_w - 2}" height="{cell_h - 2}" rx="3" fill="var(--surface-card)" stroke="var(--border)" stroke-width=".5"/>')
    lines.append("</svg>")
    return "\n".join(lines)

# --- Sector cards ---
def sector_cards_html(sectors):
    parts = []
    for i, (sname, total_val) in enumerate(sectors[:12]):
        color = COLORS[i % len(COLORS)]
        pct = total_val / grand_total * 100 if grand_total > 0 else 0
        cc_vals = sorted(sector_by_country.get(sname, {}).items(), key=lambda x: -x[1])
        cc_vals = [(cc, v) for cc, v in cc_vals if v > 0]
        n_countries = len(cc_vals)

        country_lines = []
        for cc, v in cc_vals[:6]:
            cname = countries[cc]["name"]
            slug = SLUG.get(cc)
            cpct = v / total_val * 100 if total_val > 0 else 0
            link = f'<a href="pacific-signal-{slug}.html">{esc(cname)}</a>' if slug else esc(cname)
            bar_w = min(100, max(4, v / cc_vals[0][1] * 100))
            country_lines.append(
                f'<div class="sc-row">'
                f'<span class="sc-name">{link}</span>'
                f'<span class="sc-bar" style="width:{bar_w:.0f}%;background:{color};opacity:0.7"></span>'
                f'<span class="sc-val">{fmt_m(v)}</span>'
                f'</div>'
            )
        if len(cc_vals) > 6:
            country_lines.append(f'<div class="sc-row"><span class="sc-name" style="color:var(--text-muted)">+ {len(cc_vals) - 6} more</span></div>')

        parts.append(f'''
<div class="sector-card">
<div class="sc-header" style="border-left:4px solid {color}">
<span class="sc-title">{esc(sname)}</span>
<span class="sc-total">{fmt_m(total_val)} <span style="font-weight:400;color:var(--text-muted)">({pct:.0f}%)</span></span>
</div>
<div class="sc-subtitle">{n_countries} {'country' if n_countries == 1 else 'countries'}</div>
<div class="sc-countries">{"".join(country_lines)}</div>
</div>''')
    return "\n".join(parts)

# --- Country sector profiles ---
def country_profiles_html():
    parts = []
    for cc in country_order:
        c = countries[cc]
        sectors = c.get("sectors_90", [])
        sectors_pos = [s for s in sectors if s["usd"] > 0]
        if not sectors_pos:
            continue
        name = c["name"]
        slug = SLUG.get(cc)
        total = sum(s["usd"] for s in sectors_pos)
        link = f'<a href="pacific-signal-{slug}.html">{esc(name)}</a>' if slug else esc(name)

        bars = []
        max_v = sectors_pos[0]["usd"] if sectors_pos else 1
        for j, s in enumerate(sectors_pos[:5]):
            w_pct = min(100, max(4, s["usd"] / max_v * 100))
            color = COLORS[j % len(COLORS)]
            pct = s["usd"] / total * 100 if total > 0 else 0
            bars.append(
                f'<div class="cp-row">'
                f'<span class="cp-sector">{esc(s["name"][:28])}</span>'
                f'<span class="cp-bar" style="width:{w_pct:.0f}%;background:{color};opacity:0.75"></span>'
                f'<span class="cp-val">{fmt_m(s["usd"])} ({pct:.0f}%)</span>'
                f'</div>'
            )
        parts.append(f'''
<div class="cp-card">
<div class="cp-name">{link} <span style="color:var(--text-muted);font-weight:400">— {fmt_m(total)}</span></div>
{"".join(bars)}
</div>''')
    return "\n".join(parts)

# --- Concentration analysis ---
def concentration_html():
    lines = []
    for sname, total_val in top_sectors[:10]:
        cc_vals = sorted(sector_by_country.get(sname, {}).items(), key=lambda x: -x[1])
        cc_vals = [(cc, v) for cc, v in cc_vals if v > 0]
        if not cc_vals:
            continue
        top_cc, top_v = cc_vals[0]
        top_pct = top_v / total_val * 100 if total_val > 0 else 0
        if top_pct > 60:
            cname = countries[top_cc]["name"]
            lines.append(f'<li><strong>{esc(sname)}</strong>: {top_pct:.0f}% goes to {esc(cname)} ({fmt_m(top_v)} of {fmt_m(total_val)})</li>')
    if not lines:
        return ""
    return f'<ul class="compact">{"".join(lines)}</ul>'

# --- Page CSS ---
extra = """
.container{max-width:820px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:1.5rem}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1.5rem 0 2rem}
.metric{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1rem;text-align:center;box-shadow:var(--card-shadow)}
.metric .number{font-size:1.5rem;font-weight:800;background:linear-gradient(135deg,var(--series-1),var(--series-2,#2a9d8f));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.metric .label{font-size:.78rem;color:var(--text-muted);margin-top:.25rem;line-height:1.3}
.section{margin:2rem 0}
.chart{width:100%;max-width:720px;font-family:inherit}
.chart text{font-size:12px;fill:var(--text)}
.chart-label{font-size:11px;fill:var(--text-muted)}
.chart-val{font-size:10.5px;fill:var(--text-muted)}
.heatmap{width:100%;max-width:720px;font-family:inherit}
.heatmap text{font-size:10px;fill:var(--text)}
.hm-label{font-size:10px;fill:var(--text-muted)}
.sector-cards{display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin:1rem 0}
.sector-card{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:.9rem 1rem;box-shadow:var(--card-shadow)}
.sc-header{padding-left:.7rem;display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.3rem}
.sc-title{font-weight:700;font-size:.92rem}
.sc-total{font-weight:700;font-size:.88rem;color:var(--series-1)}
.sc-subtitle{font-size:.78rem;color:var(--text-muted);margin-bottom:.5rem;padding-left:.7rem}
.sc-countries{font-size:.82rem}
.sc-row{display:flex;align-items:center;gap:.4rem;padding:.15rem 0}
.sc-name{min-width:90px;flex-shrink:0}
.sc-name a{color:var(--series-1);text-decoration:none}
.sc-name a:hover{text-decoration:underline}
.sc-bar{height:10px;border-radius:3px;flex-shrink:0}
.sc-val{font-size:.78rem;color:var(--text-muted);white-space:nowrap}
.cp-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin:1rem 0}
.cp-card{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:.8rem 1rem;box-shadow:var(--card-shadow)}
.cp-name{font-weight:700;font-size:.92rem;margin-bottom:.4rem}
.cp-name a{color:var(--series-1);text-decoration:none}
.cp-name a:hover{text-decoration:underline}
.cp-row{display:flex;align-items:center;gap:.4rem;padding:.12rem 0;font-size:.82rem}
.cp-sector{min-width:120px;flex-shrink:0;color:var(--text-muted)}
.cp-bar{height:9px;border-radius:3px;flex-shrink:0}
.cp-val{font-size:.76rem;color:var(--text-muted);white-space:nowrap}
ul.compact{margin:.5rem 0;padding-left:1.2rem}
ul.compact li{margin:.3rem 0;font-size:.88rem;line-height:1.5}
.note{font-size:.84rem;color:var(--text-muted);line-height:1.55;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin:1rem 0}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media(max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .metrics{grid-template-columns:repeat(2,1fr);gap:.6rem}
  .metric .number{font-size:1.25rem}
  .chart text{font-size:9.5px}
  .chart-label{font-size:9px}
  .hm-label{font-size:8px}
  .sector-cards{grid-template-columns:1fr}
  .cp-grid{grid-template-columns:1fr}
  .heatmap{overflow-x:auto}
  footer{font-size:.75rem}
}
"""

# --- Interesting findings ---
n_sectors = len([s for s, v in ranked_sectors if v > 0])
top1_name, top1_val = top_sectors[0] if top_sectors else ("", 0)
top1_pct = top1_val / grand_total * 100 if grand_total > 0 else 0

concentrated = []
for sname, total_val in top_sectors[:10]:
    cc_vals = sorted(sector_by_country.get(sname, {}).items(), key=lambda x: -x[1])
    cc_vals = [(cc, v) for cc, v in cc_vals if v > 0]
    if cc_vals:
        top_cc, top_v = cc_vals[0]
        if top_v / total_val > 0.5:
            concentrated.append((sname, countries[top_cc]["name"], top_v / total_val * 100))

spread = []
for sname, total_val in top_sectors:
    n = len([1 for cc, v in sector_by_country.get(sname, {}).items() if v > 0])
    spread.append((sname, n))
most_spread = max(spread, key=lambda x: x[1]) if spread else ("", 0)

# --- Assemble page ---

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sector Analysis &mdash; Pacific Aid Signal</title>
<meta name="description" content="Where {fmt_m(grand_total)} in Pacific aid goes: {n_sectors} sectors across {len(countries)} countries, computed from live data.">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard</a></p>
<header>
<h1>Where the money goes</h1>
<p class="intro">Sector breakdown of {fmt_m(grand_total)} in reported disbursements across {len(countries)} Pacific island countries in the last 90&nbsp;days. All figures computed from the live data snapshot &mdash; {n_sectors} sectors, {len([1 for _, v in ranked_sectors if v > 0])} with positive disbursements.</p>
</header>

<div class="metrics">
<div class="metric"><div class="number">{fmt_m(grand_total)}</div><div class="label">Total 90-day disbursements</div></div>
<div class="metric"><div class="number">{n_sectors}</div><div class="label">Sectors with activity</div></div>
<div class="metric"><div class="number">{esc(top1_name[:20])}</div><div class="label">Largest sector ({top1_pct:.0f}%)</div></div>
<div class="metric"><div class="number">{most_spread[1]}</div><div class="label">Most countries ({esc(most_spread[0][:18])})</div></div>
</div>

<div class="section">
<h2>All sectors by 90-day disbursement</h2>
{bar_chart_h(top_sectors)}
</div>

<div class="section">
<h2>Sector &times; country heatmap</h2>
<p style="font-size:.85rem;color:var(--text-muted)">Darker cells mean larger disbursements. Hover for exact figures. Empty cells mean no reported spending in that sector-country pair in the last 90 days.</p>
{heatmap_svg(top_sectors[:12], country_order)}
</div>

<div class="section">
<h2>Sector detail</h2>
<p style="font-size:.85rem;color:var(--text-muted)">Top sectors with their country breakdown. Click any country to see its full aid page.</p>
<div class="sector-cards">
{sector_cards_html(top_sectors)}
</div>
</div>

<div class="section">
<h2>Country sector profiles</h2>
<p style="font-size:.85rem;color:var(--text-muted)">Top 5 sectors for each country, ranked by 90-day disbursement.</p>
<div class="cp-grid">
{country_profiles_html()}
</div>
</div>

<div class="section">
<h2>Where aid concentrates</h2>
<p style="font-size:.88rem">Some sectors are dominated by a single country:</p>
{concentration_html()}
</div>

<div class="note">
<strong>What this shows and what it does not.</strong> Sector classifications come from IATI publisher declarations (DAC sector codes). Not all activities carry a sector; those are excluded. Disbursements are weighted by the publisher&rsquo;s declared share for each recipient country, so a multi-country programme counts only the portion attributed to each Pacific country. Australia&rsquo;s IATI data has not been updated since June 2025; its sector contributions are therefore understated in the 90-day window. China, Taiwan, and most Gulf state donors do not publish to IATI and are absent.
</div>

<h2>Where to go from here</h2>
<p><strong><a href="signal.html">Current issue</a></strong> &mdash; pick a country.
<strong><a href="dashboard.html">Dashboard</a></strong> &mdash; the full picture at a glance.
<strong><a href="pipeline.html">Pipeline &amp; outlook</a></strong> &mdash; what is ending and what is coming.
<strong><a href="funders.html">Funders</a></strong> &mdash; find your organisation.
<strong><a href="feedback.html">Ask me something</a></strong> &mdash; I answer within twelve hours.</p>

<footer>Asa is an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission. All figures on this page are computed from the live Pacific Aid Signal snapshot ({latest.get("date", "today")}) and update automatically on each pipeline run. No model is called to produce these numbers.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="pipeline.html">Pipeline</a> &middot;
<a href="funders.html">Funders</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "sectors.html")
open(out, "w").write(html)
print("rendered sectors.html", len(html) // 1024, "KB")
