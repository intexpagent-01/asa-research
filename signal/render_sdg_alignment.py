#!/usr/bin/env python3
"""Render site/sdg-alignment.html: Where aid goes vs where development gaps are."""
import os, re, json, datetime as dt
from collections import defaultdict
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
SDG_FILE = os.path.join(os.path.dirname(HERE), "experiments", "pacific-sdg-data.json")
SNAP_DIR = os.environ.get("SIGNAL_DATA") or os.path.join(HERE, "data")
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

today = dt.date.today().isoformat()

GOALS = {
    "1": "No Poverty", "2": "Zero Hunger", "3": "Good Health",
    "4": "Quality Education", "5": "Gender Equality", "6": "Clean Water",
    "7": "Affordable Energy", "8": "Decent Work", "9": "Industry & Innovation",
    "10": "Reduced Inequalities", "11": "Sustainable Cities", "12": "Responsible Consumption",
    "13": "Climate Action", "14": "Life Below Water", "15": "Life on Land",
    "16": "Peace & Justice", "17": "Partnerships",
}

GOAL_COLORS = {
    "1": "#E5243B", "2": "#DDA63A", "3": "#4C9F38", "4": "#C5192D",
    "5": "#FF3A21", "6": "#26BDE2", "7": "#FCC30B", "8": "#A21942",
    "9": "#FD6925", "10": "#DD1367", "11": "#FD9D24", "12": "#BF8B2E",
    "13": "#3F7E44", "14": "#0A97D9", "15": "#56C02B", "16": "#00689D",
    "17": "#19486A",
}

# IATI DAC 3-digit sector → primary SDG goal mapping
# Based on OECD DAC purpose code to SDG alignment
SECTOR_TO_SDG = {
    "111": "4",   # Education, level unspecified
    "112": "4",   # Basic education
    "113": "4",   # Secondary education
    "114": "4",   # Post-secondary education
    "121": "3",   # Health, general
    "122": "3",   # Basic health
    "123": "3",   # Non-communicable diseases
    "130": "3",   # Population/reproductive health
    "140": "6",   # Water supply & sanitation
    "151": "16",  # Government & civil society
    "152": "16",  # Conflict, peace & security
    "160": "1",   # Other social infrastructure
    "210": "9",   # Transport & storage
    "220": "9",   # Communications
    "230": "7",   # Energy policy
    "231": "7",   # Energy policy
    "232": "7",   # Energy generation, renewable
    "233": "7",   # Energy generation, non-renewable
    "234": "7",   # Hybrid energy plants
    "235": "7",   # Nuclear energy plants
    "236": "7",   # Energy distribution
    "240": "8",   # Banking & financial services
    "250": "8",   # Business & other services
    "311": "2",   # Agriculture
    "312": "15",  # Forestry
    "313": "14",  # Fishing
    "321": "9",   # Industry
    "322": "8",   # Mineral resources & mining
    "323": "9",   # Construction
    "331": "17",  # Trade policy
    "332": "8",   # Tourism
    "410": "13",  # Environmental protection
    "430": None,  # Multisector — cannot assign
    "510": "17",  # General budget support
    "520": "8",   # Development food assistance
    "530": "17",  # Other commodity assistance
    "600": "1",   # Action relating to debt
    "720": "1",   # Emergency response
    "730": "1",   # Reconstruction relief
    "740": "13",  # Disaster prevention & preparedness
    "910": "17",  # Administrative costs
    "998": None,  # Unallocated
}

COUNTRY_ORDER = [
    "Papua New Guinea", "Fiji", "Solomon Islands", "Vanuatu", "Samoa",
    "Tonga", "Kiribati", "Tuvalu", "Marshall Islands", "Micronesia",
    "Palau", "Cook Islands", "Niue",
]

# Signal country code → SDG country name mapping
SIGNAL_TO_SDG_NAME = {
    "PG": "Papua New Guinea", "FJ": "Fiji", "SB": "Solomon Islands",
    "VU": "Vanuatu", "WS": "Samoa", "TO": "Tonga", "KI": "Kiribati",
    "TV": "Tuvalu", "MH": "Marshall Islands", "FM": "Micronesia",
    "PW": "Palau", "CK": "Cook Islands", "NU": "Niue",
}


def load_sdg_data():
    with open(SDG_FILE) as f:
        raw = json.load(f)
    result = {}
    for cname, cdata in raw.items():
        goal_coverage = {}
        for g in GOALS:
            indicators = set()
            recent_indicators = set()
            all_years = []
            for r in cdata["records"]:
                rg = r["goal"][0] if r.get("goal") else None
                if rg != g:
                    continue
                ind = r["indicator"][0] if r.get("indicator") else None
                if not ind:
                    continue
                year = r.get("timePeriodStart")
                if year:
                    indicators.add(ind)
                    all_years.append(year)
                    if year >= 2020:
                        recent_indicators.add(ind)
            goal_coverage[g] = {
                "n_indicators": len(indicators),
                "n_recent": len(recent_indicators),
                "latest_year": max(all_years) if all_years else None,
                "n_datapoints": len(all_years),
            }
        result[cname] = goal_coverage
    return result


def load_signal_sectors():
    snaps = sorted(f for f in os.listdir(SNAP_DIR) if f.startswith("pacific-") and f.endswith(".json") and not f.endswith(".index.json.gz"))
    if not snaps:
        return {}
    latest = os.path.join(SNAP_DIR, snaps[-1])
    with open(latest) as f:
        snap = json.load(f)

    result = {}
    for ccode, cdata in snap["countries"].items():
        cname = SIGNAL_TO_SDG_NAME.get(ccode)
        if not cname:
            continue
        sdg_spend = defaultdict(float)
        total_spend = 0.0
        unmapped = 0.0
        for s in cdata.get("sectors_90", []):
            usd = s.get("usd", 0)
            total_spend += usd
            sdg = SECTOR_TO_SDG.get(s["code"])
            if sdg:
                sdg_spend[sdg] += usd
            else:
                unmapped += usd
        result[cname] = {
            "sdg_spend": dict(sdg_spend),
            "total": total_spend,
            "unmapped": unmapped,
        }
    return result


def fmt_usd(v):
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


sdg_data = load_sdg_data()
signal_data = load_signal_sectors()

# Compute regional aggregates
regional_sdg_coverage = {}
regional_sdg_spend = {}
for g in GOALS:
    coverages = [sdg_data[c][g]["n_recent"] for c in sdg_data if sdg_data[c][g]["n_recent"] > 0]
    regional_sdg_coverage[g] = {
        "countries_with_data": len(coverages),
        "avg_recent_indicators": sum(sdg_data[c][g]["n_recent"] for c in sdg_data) / len(sdg_data) if sdg_data else 0,
        "total_indicators": sum(sdg_data[c][g]["n_indicators"] for c in sdg_data),
    }
    total = sum(signal_data.get(c, {}).get("sdg_spend", {}).get(g, 0) for c in COUNTRY_ORDER if c in signal_data)
    regional_sdg_spend[g] = total

total_regional_spend = sum(regional_sdg_spend.values())

# Build embedded data for client-side interactivity
embed = {}
for cname in COUNTRY_ORDER:
    if cname not in sdg_data:
        continue
    e = {"coverage": {}, "spend": {}}
    for g in GOALS:
        e["coverage"][g] = sdg_data[cname][g]
        e["spend"][g] = signal_data.get(cname, {}).get("sdg_spend", {}).get(g, 0)
    e["total_spend"] = signal_data.get(cname, {}).get("total", 0)
    e["unmapped"] = signal_data.get(cname, {}).get("unmapped", 0)
    embed[cname] = e

# Identify alignment gaps at regional level
alignment_findings = []
for g in sorted(GOALS.keys(), key=int):
    spend = regional_sdg_spend.get(g, 0)
    spend_pct = (spend / total_regional_spend * 100) if total_regional_spend else 0
    cov = regional_sdg_coverage[g]
    avg_recent = cov["avg_recent_indicators"]
    countries_with = cov["countries_with_data"]
    alignment_findings.append({
        "goal": g,
        "name": GOALS[g],
        "spend": spend,
        "spend_pct": spend_pct,
        "avg_recent": avg_recent,
        "countries_with_data": countries_with,
        "color": GOAL_COLORS[g],
    })

# Sort by misalignment score: high spend + low coverage or low spend + high coverage
for f in alignment_findings:
    spend_rank = f["spend_pct"]
    coverage_rank = f["avg_recent"]
    f["misalignment"] = abs(spend_rank - coverage_rank * 3)

findings_sorted = sorted(alignment_findings, key=lambda x: x["misalignment"], reverse=True)

# Build the overview table rows
overview_html = []
for cname in COUNTRY_ORDER:
    if cname not in sdg_data:
        continue
    sd = signal_data.get(cname, {})
    total = sd.get("total", 0)
    goals_with_spend = sum(1 for g in GOALS if sd.get("sdg_spend", {}).get(g, 0) > 0)
    goals_with_data = sum(1 for g in GOALS if sdg_data[cname][g]["n_recent"] > 0)
    goals_both = sum(1 for g in GOALS if sd.get("sdg_spend", {}).get(g, 0) > 0 and sdg_data[cname][g]["n_recent"] > 0)
    goals_neither = sum(1 for g in GOALS if sd.get("sdg_spend", {}).get(g, 0) == 0 and sdg_data[cname][g]["n_recent"] == 0)

    overview_html.append(
        f'<tr onclick="selectCountry(\'{esc(cname)}\')" style="cursor:pointer">'
        f'<td><strong>{esc(cname)}</strong></td>'
        f'<td style="text-align:right">{fmt_usd(total)}</td>'
        f'<td style="text-align:center">{goals_with_spend}/17</td>'
        f'<td style="text-align:center">{goals_with_data}/17</td>'
        f'<td style="text-align:center">{goals_both}</td>'
        f'<td style="text-align:center">{goals_neither}</td>'
        f'</tr>'
    )

# Regional alignment chart: paired bars for each SDG goal
chart_w = 760
chart_h = 480
bar_area_top = 40
bar_area_bottom = chart_h - 80
bar_area_h = bar_area_bottom - bar_area_top
n_goals = 17
group_w = chart_w / (n_goals + 1)

max_spend = max(regional_sdg_spend.values()) if regional_sdg_spend else 1
max_coverage = max(regional_sdg_coverage[g]["avg_recent_indicators"] for g in GOALS) if GOALS else 1

bars_svg = []
for i, g in enumerate(sorted(GOALS.keys(), key=int)):
    x = (i + 0.5) * group_w + 20
    spend = regional_sdg_spend.get(g, 0)
    cov = regional_sdg_coverage[g]["avg_recent_indicators"]
    spend_h = (spend / max_spend * bar_area_h * 0.9) if max_spend else 0
    cov_h = (cov / max_coverage * bar_area_h * 0.9) if max_coverage else 0
    bw = group_w * 0.35
    color = GOAL_COLORS[g]
    # Spend bar (left)
    bars_svg.append(
        f'<rect x="{x - bw}" y="{bar_area_bottom - spend_h}" width="{bw - 1}" height="{spend_h}" '
        f'fill="{color}" opacity="0.85"><title>SDG {g}: {fmt_usd(spend)} aid spending</title></rect>'
    )
    # Coverage bar (right) - using a lighter shade
    bars_svg.append(
        f'<rect x="{x + 1}" y="{bar_area_bottom - cov_h}" width="{bw - 1}" height="{cov_h}" '
        f'fill="{color}" opacity="0.35"><title>SDG {g}: {cov:.1f} avg recent indicators</title></rect>'
    )
    # Goal label
    bars_svg.append(
        f'<text x="{x}" y="{bar_area_bottom + 18}" text-anchor="middle" '
        f'font-size="10" fill="#666">{g}</text>'
    )

chart_svg = f'''<svg viewBox="0 0 {chart_w} {chart_h}" style="width:100%;max-width:{chart_w}px;height:auto">
<text x="{chart_w/2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="var(--fg,#222)">Regional Aid Spending vs SDG Data Coverage by Goal</text>
<text x="{chart_w/2}" y="34" text-anchor="middle" font-size="11" fill="#888">Dark = 90-day aid spending (IATI) · Light = avg recent indicators (UN SDG API)</text>
{"".join(bars_svg)}
<line x1="20" y1="{bar_area_bottom}" x2="{chart_w - 10}" y2="{bar_area_bottom}" stroke="#ccc" stroke-width="1"/>
<rect x="180" y="{chart_h - 40}" width="12" height="12" fill="#0d7377" opacity="0.85"/>
<text x="196" y="{chart_h - 30}" font-size="11" fill="#666">Aid spending (IATI, 90-day)</text>
<rect x="380" y="{chart_h - 40}" width="12" height="12" fill="#0d7377" opacity="0.35"/>
<text x="396" y="{chart_h - 30}" font-size="11" fill="#666">SDG data coverage (UN API)</text>
</svg>'''

# Key findings text
findings_html = []

# Find goals with high spend but low data
high_spend_low_data = [f for f in alignment_findings if f["spend_pct"] > 5 and f["avg_recent"] < 3]
low_spend_high_data = [f for f in alignment_findings if f["spend_pct"] < 2 and f["avg_recent"] > 3]
no_spend = [f for f in alignment_findings if f["spend"] == 0]

if high_spend_low_data:
    items = ", ".join(f'SDG {f["goal"]} ({f["name"]})' for f in high_spend_low_data[:3])
    findings_html.append(f'<li><strong>Spending without baselines:</strong> {items} receive substantial aid but have limited recent SDG data across Pacific countries — making it difficult to measure whether aid is addressing actual needs.</li>')

if low_spend_high_data:
    items = ", ".join(f'SDG {f["goal"]} ({f["name"]})' for f in low_spend_high_data[:3])
    findings_html.append(f'<li><strong>Data without investment:</strong> {items} have relatively good SDG data coverage but receive little aid in the 90-day window — either needs are met, aid arrives through other channels, or there is a gap.</li>')

if no_spend:
    items = ", ".join(f'SDG {f["goal"]} ({f["name"]})' for f in no_spend[:4])
    findings_html.append(f'<li><strong>No recent IATI-reported aid:</strong> {items} show no 90-day spending mapped to these goals across all 13 Pacific countries. This may reflect sector coding limitations rather than true absence of support.</li>')

# Total stats
total_with_both = sum(1 for g in GOALS if regional_sdg_spend.get(g, 0) > 0 and regional_sdg_coverage[g]["countries_with_data"] > 0)
total_mapped = sum(1 for g in GOALS if regional_sdg_spend.get(g, 0) > 0)

_unmapped_total = fmt_usd(sum(signal_data.get(c, {}).get("unmapped", 0) for c in COUNTRY_ORDER))

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SDG–Aid Alignment — Pacific Aid Signal</title>
<meta name="description" content="Where aid money goes vs where development gaps are — mapping IATI sector spending to SDG goals across 13 Pacific island countries">
<meta name="robots" content="index,follow">
<style>{style}
.alignment-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
.goal-card {{ border: 1px solid var(--bdr, #ddd); border-radius: 8px; padding: 12px; background: var(--bg, #fff); position: relative; overflow: hidden; }}
.goal-card .goal-bar {{ position: absolute; top: 0; left: 0; height: 4px; }}
.goal-card h4 {{ margin: 0 0 8px; font-size: 13px; }}
.goal-card .metrics {{ display: flex; justify-content: space-between; font-size: 12px; color: #666; }}
.goal-card .metric-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: #999; }}
.goal-card .metric-value {{ font-size: 16px; font-weight: 700; }}
.alignment-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }}
.country-detail {{ display: none; margin: 20px 0; padding: 20px; border: 1px solid var(--bdr, #ddd); border-radius: 8px; background: var(--bg2, #f9f9f9); }}
.country-detail.active {{ display: block; }}
.tab-bar {{ display: flex; gap: 4px; margin: 16px 0; flex-wrap: wrap; }}
.tab-btn {{ padding: 6px 16px; border: 1px solid var(--bdr, #ddd); border-radius: 16px; background: var(--bg, #fff); cursor: pointer; font-size: 13px; }}
.tab-btn.active {{ background: #0d7377; color: #fff; border-color: #0d7377; }}
.caveat {{ font-size: 12px; color: #888; margin-top: 16px; padding: 12px; border-left: 3px solid #dda; background: var(--bg2, #fafaf2); border-radius: 0 8px 8px 0; }}
</style>
</head>
<body>
<div style="max-width:900px;margin:0 auto;padding:20px">
<p style="font-size:13px"><a href="index.html">&larr; Home</a> · <a href="signal.html">Signal</a> · <a href="sdg-progress.html">SDG Progress</a></p>

<h1>SDG–Aid Alignment</h1>
<p style="font-size:15px;color:#666">Where is aid money going — and does it match where development gaps are?</p>

<p>This page maps IATI-reported aid spending (by DAC sector code) to the 17 Sustainable Development Goals, and overlays
it with SDG indicator data coverage from the UN SDG Global Database. The question: <strong>are Pacific island countries
receiving aid in the areas where they face the greatest development challenges — and where they have the data to
measure progress?</strong></p>

<div style="display:flex;flex-wrap:wrap;gap:20px;margin:20px 0">
<div style="flex:1;min-width:180px;padding:16px;background:var(--bg2,#f4f4f4);border-radius:8px;text-align:center">
  <div style="font-size:24px;font-weight:700;color:#0d7377">{fmt_usd(total_regional_spend)}</div>
  <div style="font-size:12px;color:#888">90-day aid mapped to SDGs</div>
</div>
<div style="flex:1;min-width:180px;padding:16px;background:var(--bg2,#f4f4f4);border-radius:8px;text-align:center">
  <div style="font-size:24px;font-weight:700;color:#0d7377">{total_mapped}/17</div>
  <div style="font-size:12px;color:#888">SDG goals receiving aid</div>
</div>
<div style="flex:1;min-width:180px;padding:16px;background:var(--bg2,#f4f4f4);border-radius:8px;text-align:center">
  <div style="font-size:24px;font-weight:700;color:#0d7377">{total_with_both}/17</div>
  <div style="font-size:12px;color:#888">goals with both aid &amp; SDG data</div>
</div>
<div style="flex:1;min-width:180px;padding:16px;background:var(--bg2,#f4f4f4);border-radius:8px;text-align:center">
  <div style="font-size:24px;font-weight:700;color:#0d7377">13</div>
  <div style="font-size:12px;color:#888">Pacific countries analysed</div>
</div>
</div>

<h2>Regional Overview</h2>
{chart_svg}

<h2>Key Findings</h2>
<ul style="line-height:1.8">
{"".join(findings_html)}
<li><strong>Mapping limitations:</strong> IATI sector codes map imperfectly to SDG goals. "Multisector" and "unallocated" spending ({_unmapped_total}) cannot be assigned. A single project may contribute to multiple SDGs but is counted under its primary sector only.</li>
<li><strong>90-day window effect:</strong> Aid spending is from the most recent 90-day IATI window, which captures active disbursements but not committed or planned spending. Sectors with lumpy disbursement patterns may appear absent in any given window.</li>
</ul>

<h2>By SDG Goal</h2>
<div class="alignment-grid">
'''

for g in sorted(GOALS.keys(), key=int):
    spend = regional_sdg_spend.get(g, 0)
    spend_pct = (spend / total_regional_spend * 100) if total_regional_spend else 0
    cov = regional_sdg_coverage[g]
    n_countries = cov["countries_with_data"]
    avg_ind = cov["avg_recent_indicators"]
    color = GOAL_COLORS[g]
    bar_w = min(spend_pct * 5, 100)

    html += f'''<div class="goal-card">
  <div class="goal-bar" style="width:{bar_w}%;background:{color}"></div>
  <h4><span style="color:{color}">SDG {g}</span> {esc(GOALS[g])}</h4>
  <div class="metrics">
    <div><div class="metric-label">Aid (90d)</div><div class="metric-value">{fmt_usd(spend)}</div></div>
    <div><div class="metric-label">Countries w/ data</div><div class="metric-value">{n_countries}/13</div></div>
    <div><div class="metric-label">Avg indicators</div><div class="metric-value">{avg_ind:.1f}</div></div>
  </div>
</div>
'''

html += '''</div>

<h2>By Country</h2>
<p>Click a country to see its SDG-by-SDG breakdown.</p>

<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="border-bottom:2px solid var(--bdr,#ccc)">
<th style="text-align:left;padding:8px">Country</th>
<th style="text-align:right;padding:8px">90-day Aid</th>
<th style="padding:8px">Goals w/ Aid</th>
<th style="padding:8px">Goals w/ SDG Data</th>
<th style="padding:8px">Both</th>
<th style="padding:8px">Neither</th>
</tr></thead>
<tbody>
'''
html += "\n".join(overview_html)
html += '''</tbody></table>

<div id="country-detail" class="country-detail"></div>

<div class="caveat">
<strong>How this works.</strong> IATI transactions are classified by DAC 3-digit sector codes.
Each sector code is mapped to a primary SDG goal using the OECD DAC purpose code alignment.
SDG data coverage comes from the UN SDG Global Database API — it shows how many indicators
have data (especially recent data from 2020+), not whether a country is on or off track.
"Alignment" here means whether aid is flowing to sectors that correspond to SDG goals
where data exists to measure progress. Absence of spending in a 90-day window does not
mean absence of support — it may reflect disbursement timing, sector coding, or channels
outside IATI. This analysis is indicative, not evaluative.
</div>

<h2>Sector-to-SDG Mapping</h2>
<details><summary>View the full IATI sector → SDG goal mapping used</summary>
<table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:12px">
<thead><tr style="border-bottom:1px solid var(--bdr,#ccc)">
<th style="text-align:left;padding:4px">IATI Sector Code</th>
<th style="text-align:left;padding:4px">SDG Goal</th>
</tr></thead><tbody>
'''

for code in sorted(SECTOR_TO_SDG.keys()):
    sdg = SECTOR_TO_SDG[code]
    if sdg:
        html += f'<tr><td style="padding:4px">{code}</td><td style="padding:4px"><span style="color:{GOAL_COLORS[sdg]}">SDG {sdg}</span> {esc(GOALS[sdg])}</td></tr>\n'
    else:
        html += f'<tr><td style="padding:4px">{code}</td><td style="padding:4px;color:#999">Not mapped (multisector/unallocated)</td></tr>\n'

data_json = json.dumps(embed, separators=(",", ":"))
goals_json = json.dumps(GOALS, separators=(",", ":"))
colors_json = json.dumps(GOAL_COLORS, separators=(",", ":"))

html += f'''</tbody></table></details>

<p style="font-size:12px;color:#888;margin-top:24px">
  Sources: <a href="https://iatistandard.org">IATI</a> via d-portal (sector spending),
  <a href="https://unstats.un.org/sdgs/dataportal">UN SDG Global Database</a> (development indicators).
  Generated {today}. Part of <a href="index.html">Asa</a>'s
  <a href="signal.html">Pacific Aid Signal</a>.
</p>
</div>

<script>
const DATA = {data_json};
const GOALS = {goals_json};
const COLORS = {colors_json};

function fmtUsd(v) {{
  if (Math.abs(v) >= 1e6) return "$" + (v/1e6).toFixed(1) + "M";
  if (Math.abs(v) >= 1e3) return "$" + (v/1e3).toFixed(0) + "K";
  return "$" + v.toFixed(0);
}}

function selectCountry(name) {{
  const d = DATA[name];
  if (!d) return;
  const el = document.getElementById("country-detail");
  el.classList.add("active");

  let rows = "";
  const goals = Object.keys(GOALS).sort((a,b) => parseInt(a) - parseInt(b));
  for (const g of goals) {{
    const spend = d.spend[g] || 0;
    const cov = d.coverage[g] || {{}};
    const nInd = cov.n_indicators || 0;
    const nRecent = cov.n_recent || 0;
    const latestYear = cov.latest_year || "—";
    const spendPct = d.total_spend > 0 ? (spend / d.total_spend * 100).toFixed(1) : "0.0";

    const spendBar = d.total_spend > 0 ? Math.min(spend / d.total_spend * 200, 100) : 0;
    const hasSpend = spend > 0;
    const hasData = nRecent > 0;
    let status = "—";
    if (hasSpend && hasData) status = '<span style="color:#3F7E44">&#9679; Both</span>';
    else if (hasSpend) status = '<span style="color:#DDA63A">&#9679; Aid only</span>';
    else if (hasData) status = '<span style="color:#26BDE2">&#9679; Data only</span>';
    else status = '<span style="color:#ccc">&#9679; Neither</span>';

    rows += '<tr style="border-bottom:1px solid var(--bdr,#eee)">' +
      '<td style="padding:6px"><span style="color:' + COLORS[g] + '">SDG ' + g + '</span> ' + GOALS[g] + '</td>' +
      '<td style="text-align:right;padding:6px">' + fmtUsd(spend) + '</td>' +
      '<td style="padding:6px"><div style="background:#eee;height:8px;border-radius:4px;width:100px">' +
        '<div style="background:' + COLORS[g] + ';height:8px;border-radius:4px;width:' + spendBar + 'px"></div></div></td>' +
      '<td style="text-align:center;padding:6px">' + nRecent + '</td>' +
      '<td style="text-align:center;padding:6px">' + latestYear + '</td>' +
      '<td style="text-align:center;padding:6px">' + status + '</td>' +
    '</tr>';
  }}

  el.innerHTML = '<h3>' + name + '</h3>' +
    '<p>Total 90-day aid: <strong>' + fmtUsd(d.total_spend) + '</strong>' +
    (d.unmapped > 0 ? ' (+ ' + fmtUsd(d.unmapped) + ' unmapped)' : '') + '</p>' +
    '<table style="width:100%;border-collapse:collapse;font-size:13px">' +
    '<thead><tr style="border-bottom:2px solid var(--bdr,#ccc)">' +
    '<th style="text-align:left;padding:6px">SDG Goal</th>' +
    '<th style="text-align:right;padding:6px">Aid (90d)</th>' +
    '<th style="padding:6px">Share</th>' +
    '<th style="padding:6px">Recent Indicators</th>' +
    '<th style="padding:6px">Latest Year</th>' +
    '<th style="padding:6px">Status</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>' +
    '<p style="font-size:12px;color:#888;margin-top:12px">Status: ' +
    '<span style="color:#3F7E44">&#9679;</span> Both = aid flowing and SDG data available; ' +
    '<span style="color:#DDA63A">&#9679;</span> Aid only = spending but no recent SDG data; ' +
    '<span style="color:#26BDE2">&#9679;</span> Data only = SDG data but no recent aid; ' +
    '<span style="color:#ccc">&#9679;</span> Neither = no aid or data in this window.</p>';

  el.scrollIntoView({{ behavior: "smooth", block: "start" }});
}}
</script>
</body></html>'''

os.makedirs(SITE, exist_ok=True)
out = os.path.join(SITE, "sdg-alignment.html")
with open(out, "w") as f:
    f.write(html)
print(f"rendered {out} {len(html)//1024}KB")
