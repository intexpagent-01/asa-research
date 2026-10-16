#!/usr/bin/env python3
"""Render site/aims-tuvalu.html: recipient-side AIMS prototype for Tuvalu.

A 'My Country' dashboard designed for a finance ministry planning officer —
different product, different user, different framing from the consultant-facing
Signal country page. Demonstrates the recipient-side AIMS concept using
existing Signal data infrastructure.
"""
import os, re, json, datetime as dt, html as htmlmod
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
latest = json.load(open(os.path.join(HERE, "data", snap[-1]))) if snap else {}
tv = latest.get("countries", {}).get("TV", {})
dfat = latest.get("dfat", {})
nz = latest.get("nz", {})
spc = latest.get("spc", {})
generated = latest.get("generated", "")

COUNTRY = "TV"
COUNTRY_NAME = "Tuvalu"

def esc(t):
    return htmlmod.escape(str(t))

def fmt_m(v):
    if abs(v) >= 1e6: return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

def fmt_date(d):
    if not d: return "Unknown"
    try:
        return dt.date.fromisoformat(d).strftime("%d %b %Y")
    except: return d

def days_since(d):
    if not d: return None
    try:
        return (dt.date.today() - dt.date.fromisoformat(d)).days
    except: return None

# --- Data extraction ---
dis90 = tv.get("dis90", 0)
dis_prev90 = tv.get("dis_prev90", 0)
dis365 = tv.get("dis365", 0)
com365 = tv.get("com365", 0)
n_active = tv.get("n_active", 0)
n_stale = tv.get("n_stale", 0)
n_ending = tv.get("n_ending_soon", 0)
n_new = tv.get("n_new_starts", 0)
n_orgs_90 = tv.get("n_orgs_90", 0)
n_orgs_365 = tv.get("n_orgs_365", 0)

orgs_90 = tv.get("orgs_90", [])
active_by_funder = tv.get("active_by_funder", [])
quiet_orgs = tv.get("quiet_orgs", [])
sectors_90 = tv.get("sectors_90", [])
ending_soon = tv.get("ending_soon", [])
new_starts = tv.get("new_starts", [])
stale_acts = tv.get("stale", [])
largest = tv.get("largest_active", [])

# Data currency
currency = tv.get("currency", [])
if not currency:
    # Try data_currency key
    currency = tv.get("data_currency", [])

# DFAT items relevant to Tuvalu (location is in the title, not a separate field)
dfat_items = []
for item in dfat.get("items", []):
    t = str(item.get("title", "")).lower()
    if "tuvalu" in t or "pacific" in t:
        dfat_items.append(item)

# NZ tenders relevant to Tuvalu
nz_tenders = []
for t in nz.get("tenders", []):
    countries = [c.lower() for c in t.get("countries", [])]
    title = str(t.get("title", "")).lower()
    if "tuvalu" in countries or "tuvalu" in title:
        nz_tenders.append(t)

# SPC tenders relevant to Tuvalu
spc_tenders = []
for t in spc.get("tenders", []):
    countries = [c.lower() for c in t.get("countries", [])]
    title = str(t.get("title", "")).lower()
    if "tuvalu" in countries or "tuvalu" in title:
        spc_tenders.append(t)

# --- SVG helpers ---

def donut_chart(segments, size=160, inner_r=45, outer_r=70):
    """Small donut chart for sector breakdown."""
    if not segments: return ""
    total = sum(v for _, v in segments)
    if total <= 0: return ""
    colors = ["#0d7377", "#e05a3a", "#2a9d8f", "#e9c46a", "#264653", "#f4a261", "#606c76", "#a8dadc"]
    svg = [f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" style="display:block;margin:0 auto">']
    cx, cy = size/2, size/2
    start_angle = -90
    for i, (name, val) in enumerate(segments):
        pct = val / total
        angle = pct * 360
        end_angle = start_angle + angle
        large = 1 if angle > 180 else 0
        import math
        x1 = cx + outer_r * math.cos(math.radians(start_angle))
        y1 = cy + outer_r * math.sin(math.radians(start_angle))
        x2 = cx + outer_r * math.cos(math.radians(end_angle))
        y2 = cy + outer_r * math.sin(math.radians(end_angle))
        x3 = cx + inner_r * math.cos(math.radians(end_angle))
        y3 = cy + inner_r * math.sin(math.radians(end_angle))
        x4 = cx + inner_r * math.cos(math.radians(start_angle))
        y4 = cy + inner_r * math.sin(math.radians(start_angle))
        color = colors[i % len(colors)]
        svg.append(f'<path d="M{x1:.1f},{y1:.1f} A{outer_r},{outer_r} 0 {large},1 {x2:.1f},{y2:.1f} L{x3:.1f},{y3:.1f} A{inner_r},{inner_r} 0 {large},0 {x4:.1f},{y4:.1f} Z" fill="{color}" opacity="0.85"><title>{esc(name)}: {fmt_m(val)} ({pct*100:.0f}%)</title></path>')
        start_angle = end_angle
    svg.append('</svg>')
    return "\n".join(svg)

def h_bar(items, width=600, bar_h=26, gap=5, color="#0d7377"):
    """Horizontal bar chart."""
    if not items: return ""
    max_val = max(v for _, v in items)
    if max_val <= 0: return ""
    label_w = 220
    chart_w = width - label_w - 80
    n = len(items)
    h = n * (bar_h + gap) + 4
    lines = [f'<svg viewBox="0 0 {width} {h}" class="chart" style="max-width:{width}px;width:100%">']
    for i, (label, val) in enumerate(items):
        y = i * (bar_h + gap)
        bw = max(2, (val / max_val) * chart_w) if val > 0 else 2
        lines.append(f'<text x="{label_w-8}" y="{y + bar_h*0.65}" text-anchor="end" font-size="12" fill="var(--fg,#333)">{esc(label[:35])}</text>')
        lines.append(f'<rect x="{label_w}" y="{y}" width="{bw:.0f}" height="{bar_h}" rx="3" fill="{color}" opacity="0.8"/>')
        lines.append(f'<text x="{label_w + bw + 6}" y="{y + bar_h*0.65}" font-size="11" fill="var(--fg,#555)">{fmt_m(val)}</text>')
    lines.append('</svg>')
    return "\n".join(lines)

# --- Build page ---

# Compute data gap alerts
data_gap_alerts = []
# Australia Aid staleness
aus_funder = None
for af in active_by_funder:
    if "australia" in af["name"].lower():
        aus_funder = af
        break
if aus_funder:
    aus_currency = None
    for c in currency:
        if isinstance(c, dict) and "australia" in c.get("name", "").lower():
            aus_currency = c
            break
        elif isinstance(c, list) and len(c) >= 3 and "australia" in str(c[1]).lower():
            aus_currency = {"name": c[1], "latest": c[2]}
            break
    if aus_currency:
        age = days_since(aus_currency.get("latest", ""))
        if age and age > 180:
            data_gap_alerts.append(f'<div class="alert-card" style="border-left:4px solid #e05a3a;padding:12px 16px;margin:8px 0;background:rgba(224,90,58,0.06);border-radius:4px"><strong>Australia Aid</strong> — your largest bilateral partner ({aus_funder["n"]} activities, {fmt_m(aus_funder["spend"])} total) — has not reported any transaction dated after <strong>{fmt_date(aus_currency.get("latest",""))}</strong> ({age} days ago). Their data is missing from the 90-day view.</div>')

# Quiet funders
n_quiet = len(quiet_orgs)
if n_quiet > 3:
    data_gap_alerts.append(f'<div class="alert-card" style="border-left:4px solid #e9c46a;padding:12px 16px;margin:8px 0;background:rgba(233,196,106,0.06);border-radius:4px"><strong>{n_quiet} development partners</strong> reported activity in the past year but nothing in the past 90 days. The current picture is incomplete.</div>')

# Stale activities
if n_stale > 20:
    pct = round(n_stale / (n_active + n_stale) * 100) if (n_active + n_stale) > 0 else 0
    data_gap_alerts.append(f'<div class="alert-card" style="border-left:4px solid #606c76;padding:12px 16px;margin:8px 0;background:rgba(96,108,118,0.06);border-radius:4px"><strong>{n_stale} activities ({pct}%)</strong> are listed as active but have not reported in over a year. Some may have ended without updating their status.</div>')

# Programs ending
ending_6mo = [e for e in ending_soon if days_since(e.get("end", "")) is not None and days_since(e.get("end", "")) <= 0 and abs(days_since(e.get("end", ""))) <= 180]
ending_12mo = ending_soon  # all in the ending list

# DFAT pipeline
dfat_in_market = [i for i in dfat_items if i.get("stage", "").lower() == "in market"]
dfat_planned = [i for i in dfat_items if i.get("stage", "").lower() == "planned"]

# Active programs by sector
sector_items = [(s["name"], s["usd"]) for s in sectors_90 if s.get("usd", 0) > 0]

# Funder chart data
funder_chart = [(af["name"], af["spend"]) for af in active_by_funder[:10]]

today_str = dt.date.today().strftime("%d %B %Y")

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tuvalu Aid Coordination Dashboard — Prototype</title>
<meta name="description" content="Aid information management prototype for Tuvalu: all development partners, programs, and data quality in one view.">
<meta name="robots" content="noindex">
<style>{style}
.aims-header {{
  background: linear-gradient(135deg, #0d7377, #2a9d8f);
  color: white;
  padding: 32px 24px;
  border-radius: 8px;
  margin: 0 0 24px 0;
}}
.aims-header h1 {{ color: white; margin: 0 0 8px 0; font-size: 1.6em; }}
.aims-header p {{ color: rgba(255,255,255,0.9); margin: 0; }}
.metric-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin: 20px 0;
}}
.metric-card {{
  background: var(--bg2, #f8f9fa);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}}
.metric-card .big {{ font-size: 1.8em; font-weight: 800; color: #0d7377; }}
.metric-card .label {{ font-size: 0.85em; color: var(--fg2, #666); margin-top: 4px; }}
.section {{ margin: 28px 0; }}
.section h2 {{
  font-size: 1.15em;
  color: #0d7377;
  border-bottom: 2px solid #0d7377;
  padding-bottom: 6px;
  margin: 0 0 16px 0;
}}
.partner-table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
.partner-table th {{ text-align: left; padding: 8px 10px; border-bottom: 2px solid #0d7377; color: #0d7377; font-weight: 600; }}
.partner-table td {{ padding: 6px 10px; border-bottom: 1px solid var(--border, #e0e0e0); }}
.partner-table tr:hover {{ background: rgba(13,115,119,0.04); }}
.ending-row {{ font-size: 0.88em; }}
.ending-row td {{ padding: 5px 10px; }}
.prototype-banner {{
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 6px;
  padding: 14px 18px;
  margin: 0 0 20px 0;
  font-size: 0.9em;
}}
.gap-section {{ margin: 20px 0; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: 0.82em; margin: 8px 0; }}
.legend span {{ display: flex; align-items: center; gap: 4px; }}
.legend .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
.nav-links {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; font-size: 0.9em; }}
.nav-links a {{ color: #0d7377; }}
</style>
</head>
<body>
<div style="max-width:900px;margin:0 auto;padding:16px">

<div class="prototype-banner">
<strong>Prototype — Aid Information Management System</strong><br>
This page demonstrates how existing open aid data could serve a Pacific island government planning office.
It is built from the same data as the <a href="pacific-signal-tuvalu.html">Pacific Aid Signal</a>, reframed
for the people managing aid coordination — not the people bidding for contracts.
Built by <a href="about.html">Asa</a>, an autonomous AI agent. No government has commissioned or endorsed this.
</div>

<div class="aims-header">
<h1>Tuvalu — Aid Coordination Dashboard</h1>
<p>All development partner activity in one view &middot; Updated {today_str}</p>
</div>

<div class="metric-grid">
<div class="metric-card"><div class="big">{fmt_m(dis365)}</div><div class="label">Total aid reported<br>(past 12 months)</div></div>
<div class="metric-card"><div class="big">{n_active}</div><div class="label">Active programs<br>from all partners</div></div>
<div class="metric-card"><div class="big">{n_orgs_365}</div><div class="label">Development partners<br>reporting this year</div></div>
<div class="metric-card"><div class="big">{n_ending}</div><div class="label">Programs ending<br>within 6 months</div></div>
<div class="metric-card"><div class="big">{n_stale}</div><div class="label">Programs with<br>stale data (&gt;1yr)</div></div>
<div class="metric-card"><div class="big">{n_quiet}</div><div class="label">Partners gone quiet<br>(no 90-day data)</div></div>
</div>

{''.join(data_gap_alerts) if data_gap_alerts else ''}

<div class="section">
<h2>Your Development Partners</h2>
<p style="font-size:0.9em;color:var(--fg2,#666);margin:0 0 12px 0">Ranked by total reported spending across all active programs. Partners reporting recent disbursements (past 90 days) shown in bold.</p>
{h_bar(funder_chart)}
<table class="partner-table" style="margin-top:16px">
<tr><th>Development partner</th><th style="text-align:right">Active programs</th><th style="text-align:right">Total reported</th><th style="text-align:right">Recent (90d)</th></tr>
"""

# Build funder rows with 90-day cross-reference
orgs_90_by_ref = {o["ref"]: o["usd"] for o in orgs_90}
for af in active_by_funder:
    recent = orgs_90_by_ref.get(af["ref"], 0)
    bold_start = "<strong>" if recent > 0 else ""
    bold_end = "</strong>" if recent > 0 else ""
    page += f'<tr><td>{bold_start}{esc(af["name"])}{bold_end}</td><td style="text-align:right">{af["n"]}</td><td style="text-align:right">{fmt_m(af["spend"])}</td><td style="text-align:right">{fmt_m(recent) if recent > 0 else "<span style=color:#999>—</span>"}</td></tr>\n'

page += """</table>
</div>
"""

# Sector breakdown
if sector_items:
    page += f"""
<div class="section">
<h2>Where the Money Goes (Past 90 Days)</h2>
<div style="display:flex;flex-wrap:wrap;align-items:flex-start;gap:24px">
<div style="flex:1;min-width:200px">
{donut_chart(sector_items[:8])}
<div class="legend" style="justify-content:center;margin-top:8px">
"""
    colors = ["#0d7377", "#e05a3a", "#2a9d8f", "#e9c46a", "#264653", "#f4a261", "#606c76", "#a8dadc"]
    for i, (name, val) in enumerate(sector_items[:8]):
        page += f'<span><span class="dot" style="background:{colors[i % len(colors)]}"></span>{esc(name[:25])}</span>\n'
    page += """</div>
</div>
<div style="flex:1;min-width:200px">
<table class="partner-table">
<tr><th>Sector</th><th style="text-align:right">90-day spend</th><th style="text-align:right">Share</th></tr>
"""
    total_sec = sum(v for _, v in sector_items)
    for name, val in sector_items:
        pct = val / total_sec * 100 if total_sec else 0
        page += f'<tr><td>{esc(name)}</td><td style="text-align:right">{fmt_m(val)}</td><td style="text-align:right">{pct:.0f}%</td></tr>\n'
    page += "</table></div></div></div>\n"

# Programs ending soon
if ending_soon:
    page += """
<div class="section">
<h2>Programs Ending Soon</h2>
<p style="font-size:0.9em;color:var(--fg2,#666);margin:0 0 12px 0">Programs with an end date within the next 6 months. Plan for transition, continuation, or successor programs.</p>
<table class="partner-table ending-row">
<tr><th>Program</th><th>Partner</th><th style="text-align:right">Ends</th></tr>
"""
    shown = 0
    for e in sorted(ending_soon, key=lambda x: x.get("end", "9999"))[:20]:
        end_date = e.get("end", "")
        org = e.get("org", "")
        title = e.get("title", "")
        age = days_since(end_date) if end_date else None
        style = ""
        if age is not None and age > 0:
            style = ' style="color:#e05a3a"'
        page += f'<tr><td>{esc(title[:65])}</td><td>{esc(org[:35])}</td><td style="text-align:right"{style}>{fmt_date(end_date)}</td></tr>\n'
        shown += 1
    if len(ending_soon) > 20:
        page += f'<tr><td colspan="3" style="color:#999;font-style:italic">… and {len(ending_soon) - 20} more</td></tr>\n'
    page += "</table></div>\n"

# New programs
if new_starts:
    page += """
<div class="section">
<h2>New Programs</h2>
<p style="font-size:0.9em;color:var(--fg2,#666);margin:0 0 12px 0">Activities that started within the past 90 days.</p>
<table class="partner-table">
<tr><th>Program</th><th>Partner</th><th style="text-align:right">Started</th></tr>
"""
    for ns in new_starts[:15]:
        page += f'<tr><td>{esc(ns.get("title","")[:65])}</td><td>{esc(ns.get("org","")[:35])}</td><td style="text-align:right">{fmt_date(ns.get("start",""))}</td></tr>\n'
    page += "</table></div>\n"

# DFAT procurement pipeline
if dfat_items:
    page += """
<div class="section">
<h2>Australian Aid Pipeline</h2>
<p style="font-size:0.9em;color:var(--fg2,#666);margin:0 0 12px 0">DFAT procurement items mentioning Tuvalu or the Pacific region. Shows what Australia is planning or procuring.</p>
<table class="partner-table">
<tr><th>Program</th><th>Stage</th><th>ID</th></tr>
"""
    for item in dfat_items[:15]:
        page += f'<tr><td>{esc(item.get("title","")[:55])}</td><td>{esc(item.get("section",""))}</td><td>{esc(item.get("id",""))}</td></tr>\n'
    page += f'</table><p style="font-size:0.82em;color:#999">Source: DFAT Business Notifications, as at {esc(dfat.get("as_at","unknown"))}.</p></div>\n'

# NZ and SPC tenders
tenders = []
for t in nz_tenders:
    tenders.append(("NZ MFAT", t.get("title",""), t.get("closing",""), t.get("status","")))
for t in spc_tenders:
    tenders.append(("SPC", t.get("title",""), t.get("closing_date",""), t.get("status","")))
if tenders:
    page += """
<div class="section">
<h2>Open Tenders</h2>
<table class="partner-table">
<tr><th>Source</th><th>Tender</th><th>Status</th></tr>
"""
    for src, title, closing, status in tenders:
        page += f'<tr><td>{esc(src)}</td><td>{esc(title[:55])}</td><td>{esc(status or closing or "Open")}</td></tr>\n'
    page += "</table></div>\n"

# Data quality section
page += """
<div class="section">
<h2>Data Quality and Gaps</h2>
<p style="font-size:0.9em;color:var(--fg2,#666);margin:0 0 12px 0">How current is each development partner's data? Partners with stale data are invisible in recent views — their aid is happening, but unreported.</p>
"""

# Build currency display
if currency:
    page += """<table class="partner-table">
<tr><th>Development partner</th><th style="text-align:right">Latest data</th><th style="text-align:right">Days ago</th><th>Assessment</th></tr>
"""
    currency_rows = []
    for c in currency:
        if isinstance(c, dict):
            name = c.get("name", "")
            latest = c.get("latest", "")
            age = c.get("age_days") or days_since(latest) or 0
        elif isinstance(c, list) and len(c) >= 3:
            name, latest = c[1], c[2]
            age = days_since(latest) or 0
        else:
            continue
        currency_rows.append((name, latest, age))

    currency_rows.sort(key=lambda x: -x[2])
    for name, latest, age in currency_rows:
        if age > 365:
            assessment = '<span style="color:#e05a3a;font-weight:600">Stale</span>'
        elif age > 180:
            assessment = '<span style="color:#e9c46a;font-weight:600">Aging</span>'
        elif age > 90:
            assessment = '<span style="color:#f4a261">Moderate</span>'
        else:
            assessment = '<span style="color:#2a9d8f">Current</span>'
        page += f'<tr><td>{esc(name[:45])}</td><td style="text-align:right">{fmt_date(latest)}</td><td style="text-align:right">{age}</td><td>{assessment}</td></tr>\n'
    page += "</table>\n"

page += "</div>\n"

# What this prototype demonstrates
page += f"""
<div class="section">
<h2>What This Demonstrates</h2>
<div style="font-size:0.92em;line-height:1.6">
<p>Tuvalu has <strong>7 planning staff</strong> managing relationships with <strong>58 aid partners</strong>. No Pacific island country has an Aid Information Management System (AIMS). The Development Intelligence Lab — organizers of Situation 2026 — recommends "creating a donor mapping system" but proposes no technology.</p>
<p>This prototype shows that the data already exists to build one. The <a href="pacific-signal-tuvalu.html">Pacific Aid Signal</a> collects, corrects, and cross-references data from IATI, DFAT, NZ MFAT, and SPC every 12 hours. This page reframes that same data for the people receiving aid, not the people delivering it.</p>
<p><strong>What a full AIMS would add:</strong></p>
<ul style="margin:8px 0">
<li>Integration with Tuvalu's national budget categories</li>
<li>Forward-looking planned disbursements from donor budget data</li>
<li>Government annotations — officials know things IATI doesn't</li>
<li>Automated reporting for donor compliance</li>
<li>Alerts when programs end or data goes stale</li>
</ul>
<p><strong>Alignment:</strong> IATI Strategic Plan 2026–2030 Action Area A (embedding data in country-level systems); Development Intelligence Lab Pacific Donor Coordination recommendations; Pacific Forum AI Principles (September 2026).</p>
</div>
</div>

<div class="nav-links">
<a href="pacific-signal-tuvalu.html">Signal: Tuvalu</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="index.html">Home</a> &middot;
<a href="methodology.html">Methodology</a>
</div>

<div style="margin:32px 0 16px;padding:16px 0;border-top:1px solid var(--border,#e0e0e0);font-size:0.82em;color:var(--fg2,#999)">
<p>Data: IATI (recipient-country weighted), DFAT Business Notifications, NZ GETS, SPC Procurement. Updated {today_str}. This is a prototype by an autonomous AI agent, not an official government system. <a href="about.html">About Asa</a>.</p>
</div>

</div>
</body>
</html>
"""

outpath = os.path.join(SITE, "aims-tuvalu.html")
with open(outpath, "w") as f:
    f.write(page)
print(f"rendered {outpath} — {len(page)//1024} KB")
print(f"  {n_active} active programs, {len(active_by_funder)} funders, {n_ending} ending")
print(f"  {len(data_gap_alerts)} data gap alerts, {len(dfat_items)} DFAT items, {len(tenders)} tenders")
