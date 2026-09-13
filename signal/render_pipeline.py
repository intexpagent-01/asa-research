#!/usr/bin/env python3
"""Render site/pipeline.html: procurement pipeline and outlook for the Pacific."""
import os, re, json, datetime as dt, math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap_files = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
latest = json.load(open(os.path.join(HERE, "data", snap_files[-1]))) if snap_files else {}
countries = latest.get("countries", {})
dfat = latest.get("dfat", {})
nz = latest.get("nz", {})
today = dt.date.today()

SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def fmt_m(v):
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# --- Collect ending activities across all countries ---

all_ending = []
for code, c in countries.items():
    for a in c.get("ending_soon", []):
        pct = a.get("pct") or 100
        weighted = (a.get("spend") or 0) * pct / 100
        all_ending.append({
            "title": a.get("title", "Untitled"),
            "org": a.get("org", ""),
            "end": a.get("end", ""),
            "spend": a.get("spend") or 0,
            "weighted": weighted,
            "pct": pct,
            "country": c["name"],
            "country_code": code,
        })
all_ending.sort(key=lambda x: x["end"])

total_ending_value = sum(a["weighted"] for a in all_ending)
n_ending = len(all_ending)

def qtr(d):
    try:
        dt_obj = dt.date.fromisoformat(d)
        q = (dt_obj.month - 1) // 3 + 1
        return f"{dt_obj.year} Q{q}"
    except:
        return "Unknown"

ending_by_qtr = defaultdict(list)
for a in all_ending:
    ending_by_qtr[qtr(a["end"])].append(a)

ending_by_country = Counter()
ending_value_by_country = defaultdict(float)
for a in all_ending:
    ending_by_country[a["country"]] += 1
    ending_value_by_country[a["country"]] += a["weighted"]

# --- New starts ---

all_new = []
for code, c in countries.items():
    for a in c.get("new_starts", []):
        all_new.append({
            "title": a.get("title", "Untitled"),
            "org": a.get("org", ""),
            "spend": a.get("spend") or 0,
            "pct": a.get("pct") or 100,
            "country": c["name"],
            "country_code": code,
        })
all_new.sort(key=lambda x: -x["spend"])
n_new = len(all_new)

# --- DFAT pipeline ---

dfat_items = dfat.get("items", [])
dfat_as_at = dfat.get("as_at", "unknown")
dfat_in_market = [i for i in dfat_items if i.get("section") == "In the market"]
dfat_planned = [i for i in dfat_items if i.get("section") == "Planned"]
dfat_collab = [i for i in dfat_items if i.get("section") == "In Collaboration"]
dfat_closed = [i for i in dfat_items if i.get("section") == "Closed"]

PACIFIC_KW = ["PNG", "Papua", "Fiji", "Samoa", "Tonga", "Vanuatu", "Solomon",
              "Kiribati", "Tuvalu", "Nauru", "Palau", "Niue", "Cook Islands",
              "Marshall", "Micronesia", "Pacific", "FSM"]

def is_pacific(item):
    text = (item.get("title", "") + " " + item.get("status", "")).lower()
    return any(k.lower() in text for k in PACIFIC_KW)

# --- NZ tenders ---

nz_tenders = nz.get("tenders", [])
nz_open = [t for t in nz_tenders if t.get("status") == "open"]
nz_completed = [t for t in nz_tenders if t.get("status") == "completed"]

def parse_closes(t):
    c = t.get("closes", "")
    # "Wednesday, 16 September 2026 4:00 PM ..." → try to extract date
    import re as _re
    m = _re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", c)
    if m:
        try:
            return dt.date(int(m.group(3)), ["January","February","March","April","May","June","July","August","September","October","November","December"].index(m.group(2)) + 1, int(m.group(1)))
        except:
            pass
    return None

def days_until(d):
    if d is None:
        return None
    return (d - today).days

# --- SVG charts ---

def timeline_chart(items, width=700, row_h=32, gap=4):
    """Gantt-style chart showing end dates of major activities."""
    if not items:
        return ""
    label_w = 200
    chart_w = width - label_w - 80
    dates = [dt.date.fromisoformat(a["end"]) for a in items if a["end"]]
    if not dates:
        return ""
    min_d = min(today, min(dates))
    max_d = max(dates) + dt.timedelta(days=14)
    span = (max_d - min_d).days or 1

    n = len(items)
    h = n * (row_h + gap) + 40
    lines = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img" aria-label="Timeline chart">']

    # Today line
    today_x = label_w + ((today - min_d).days / span) * chart_w
    lines.append(f'<line x1="{today_x:.0f}" y1="0" x2="{today_x:.0f}" y2="{h - 30}" stroke="#e05a3a" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.7"/>')
    lines.append(f'<text x="{today_x:.0f}" y="{h - 18}" text-anchor="middle" class="chart-val" fill="#e05a3a">Today</text>')

    # Quarter markers
    for yr in range(min_d.year, max_d.year + 1):
        for q in range(1, 5):
            qd = dt.date(yr, (q - 1) * 3 + 1, 1)
            if min_d <= qd <= max_d:
                qx = label_w + ((qd - min_d).days / span) * chart_w
                lines.append(f'<line x1="{qx:.0f}" y1="0" x2="{qx:.0f}" y2="{h - 30}" stroke="var(--gridline)" stroke-width="0.5" opacity="0.5"/>')
                lines.append(f'<text x="{qx + 3:.0f}" y="{h - 18}" class="chart-val" style="font-size:9px">{yr} Q{q}</text>')

    for i, a in enumerate(items):
        y = i * (row_h + gap)
        text_y = y + row_h * 0.62
        label = a["country"][:15] + ": " + a["title"][:25]
        if len(a["title"]) > 25:
            label += "…"
        lines.append(f'<text x="{label_w - 6}" y="{text_y}" text-anchor="end" class="chart-label" style="font-size:10px">{esc(label)}</text>')

        try:
            end_d = dt.date.fromisoformat(a["end"])
            end_x = label_w + ((end_d - min_d).days / span) * chart_w
            bar_start = label_w
            bw = max(4, end_x - bar_start)
            is_soon = (end_d - today).days <= 30
            color = "#e05a3a" if is_soon else "#0d7377"
            lines.append(f'<rect x="{bar_start}" y="{y + 4}" width="{bw:.0f}" height="{row_h - 8}" rx="3" fill="{color}" opacity="0.7"/>')
            lines.append(f'<text x="{bar_start + bw + 5}" y="{text_y}" class="chart-val">{fmt_m(a["weighted"])}  ends {a["end"]}</text>')
        except:
            pass
    lines.append("</svg>")
    return "\n".join(lines)

def ending_country_bars(items, width=680, bar_h=26, gap=5):
    """Horizontal bars: ending value by country."""
    if not items:
        return ""
    max_val = max(v for _, v in items)
    if max_val <= 0:
        return ""
    label_w = 180
    chart_w = width - label_w - 10
    n = len(items)
    h = n * (bar_h + gap) + 4
    lines = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img" aria-label="Ending by country">']
    for i, (name, val) in enumerate(items):
        y = i * (bar_h + gap)
        text_y = y + bar_h * 0.63
        bw = max(2, (val / max_val) * chart_w)
        code = None
        for c, cn in countries.items():
            if cn["name"] == name:
                code = c
                break
        slug = SLUG.get(code)
        if slug:
            lines.append(f'<a href="pacific-signal-{slug}.html"><text x="{label_w - 8}" y="{text_y}" text-anchor="end" class="chart-label" style="fill:var(--series-1)">{esc(name)}</text></a>')
        else:
            lines.append(f'<text x="{label_w - 8}" y="{text_y}" text-anchor="end" class="chart-label">{esc(name)}</text>')
        lines.append(f'<rect x="{label_w}" y="{y + 2}" width="{bw:.1f}" height="{bar_h - 4}" rx="3" fill="#e05a3a" opacity="0.8"/>')
        lines.append(f'<text x="{label_w + bw + 6}" y="{text_y}" class="chart-val">{fmt_m(val)} ({ending_by_country[name]})</text>')
    lines.append("</svg>")
    return "\n".join(lines)


# --- Build page sections ---

# Top 20 ending activities for the timeline chart
top_ending = sorted(all_ending, key=lambda x: -x["weighted"])[:20]
top_ending.sort(key=lambda x: x["end"])

# Ending by country bars
country_end_list = sorted(ending_value_by_country.items(), key=lambda x: -x[1])
country_end_list = [(n, v) for n, v in country_end_list if v > 0]

# DFAT items HTML
def dfat_item_html(item):
    pac = is_pacific(item)
    pac_tag = '<span class="tag pac">Pacific</span>' if pac else ''
    return f'''<div class="pipe-item {'pacific' if pac else ''}">
<div class="pipe-title">{pac_tag}<strong>{esc(item["id"])}</strong> &mdash; {esc(item["title"])}</div>
<div class="pipe-status">{esc(item.get("status", "")[:200])}</div>
</div>'''

# NZ tender HTML
def nz_tender_html(t):
    ref = t.get("ref") or ""
    closes_d = parse_closes(t)
    du = days_until(closes_d)
    urgency = ""
    if du is not None:
        if du <= 0:
            urgency = '<span class="tag urgent">Closed</span>'
        elif du <= 3:
            urgency = f'<span class="tag urgent">Closes in {du} day{"s" if du != 1 else ""}</span>'
        elif du <= 14:
            urgency = f'<span class="tag soon">Closes in {du} days</span>'
    closes_str = (t.get("closes") or "Unknown")[:50]
    url = t.get("url", "")
    title_html = f'<a href="{esc(url)}">{esc(t["title"])}</a>' if url else esc(t["title"])
    overview = t.get("overview", "")[:150]
    overview_html = f'<div class="pipe-status">{esc(overview)}</div>' if overview else ""
    return f'''<div class="pipe-item tender">
<div class="pipe-title">{urgency}{title_html}</div>
<div class="pipe-meta">{esc(ref)} &middot; Closes: {esc(closes_str)}</div>
{overview_html}
</div>'''

# Ending by quarter summary
qtr_summary = []
for q in sorted(ending_by_qtr.keys()):
    items = ending_by_qtr[q]
    val = sum(a["weighted"] for a in items)
    qtr_summary.append((q, len(items), val))

# --- Page-specific CSS ---

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
.chart a text{fill:var(--series-1);text-decoration:underline}
.chart a:hover text{opacity:.8}
.pipe-section{margin:1.5rem 0}
.pipe-section h3{font-size:1rem;margin:.8rem 0 .5rem;font-weight:700}
.pipe-item{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin:.5rem 0;box-shadow:var(--card-shadow)}
.pipe-item.pacific{border-left:3px solid #0d7377}
.pipe-title{font-size:.92rem;line-height:1.4;margin-bottom:.3rem}
.pipe-status{font-size:.82rem;color:var(--text-muted);line-height:1.45}
.pipe-meta{font-size:.8rem;color:var(--text-muted);margin-bottom:.2rem}
.tag{display:inline-block;font-size:.7rem;font-weight:700;padding:.15rem .45rem;border-radius:4px;margin-right:.4rem;vertical-align:middle}
.tag.pac{background:#0d7377;color:#fff}
.tag.urgent{background:#e05a3a;color:#fff}
.tag.soon{background:#e9c46a;color:#333}
.tag.open{background:#2a9d8f;color:#fff}
.tag.closed-tag{background:var(--text-muted);color:#fff}
.qtr-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.6rem;margin:.8rem 0}
.qtr-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem;text-align:center}
.qtr-card .q{font-weight:700;font-size:.95rem;margin-bottom:.3rem}
.qtr-card .count{font-size:.85rem;color:var(--text-muted)}
.qtr-card .val{font-size:1.1rem;font-weight:800;color:#e05a3a}
.new-start{display:flex;justify-content:space-between;align-items:baseline;padding:.4rem 0;border-bottom:1px solid var(--gridline);font-size:.88rem}
.new-start:last-child{border-bottom:none}
.ns-title{flex:1;margin-right:.8rem}
.ns-meta{color:var(--text-muted);font-size:.82rem;white-space:nowrap}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .metrics{grid-template-columns:repeat(2,1fr);gap:.6rem}
  .metric .number{font-size:1.25rem}
  .chart text{font-size:10px}
  .chart-label{font-size:9px}
  .chart-val{font-size:9px}
  .pipe-item{padding:.6rem .8rem}
  footer{font-size:.75rem}
}
"""

# --- Quarter cards ---

qtr_cards_html = '<div class="qtr-grid">'
for q, count, val in qtr_summary:
    qtr_cards_html += f'<div class="qtr-card"><div class="q">{esc(q)}</div><div class="val">{fmt_m(val)}</div><div class="count">{count} activities ending</div></div>'
qtr_cards_html += '</div>'

# --- DFAT section ---

dfat_html = f'<p style="font-size:.85rem;color:var(--text-muted)">Source: DFAT Business Notifications, as at {esc(dfat_as_at)}. Pacific items highlighted.</p>'

if dfat_in_market:
    dfat_html += f'<div class="pipe-section"><h3><span class="tag open">In the market</span> {len(dfat_in_market)} items</h3>'
    for item in dfat_in_market:
        dfat_html += dfat_item_html(item)
    dfat_html += '</div>'

if dfat_collab:
    dfat_html += f'<div class="pipe-section"><h3><span class="tag soon">In Collaboration</span> {len(dfat_collab)} items</h3>'
    for item in dfat_collab:
        dfat_html += dfat_item_html(item)
    dfat_html += '</div>'

if dfat_planned:
    dfat_html += f'<div class="pipe-section"><h3>Planned &mdash; {len(dfat_planned)} items</h3>'
    for item in dfat_planned:
        dfat_html += dfat_item_html(item)
    dfat_html += '</div>'

if dfat_closed:
    dfat_html += f'<details style="margin-top:.8rem"><summary style="cursor:pointer;font-size:.9rem;color:var(--text-muted)">{len(dfat_closed)} recently closed</summary>'
    for item in dfat_closed:
        dfat_html += dfat_item_html(item)
    dfat_html += '</details>'

# --- NZ tenders section ---

nz_html = ""
if nz_open:
    nz_html += f'<div class="pipe-section"><h3><span class="tag open">Open</span> {len(nz_open)} tenders</h3>'
    for t in sorted(nz_open, key=lambda x: parse_closes(x) or dt.date.max):
        nz_html += nz_tender_html(t)
    nz_html += '</div>'
if nz_completed:
    nz_html += f'<details style="margin-top:.8rem"><summary style="cursor:pointer;font-size:.9rem;color:var(--text-muted)">{len(nz_completed)} completed</summary>'
    for t in nz_completed:
        nz_html += nz_tender_html(t)
    nz_html += '</details>'

# --- New starts section ---

new_html = '<div style="margin-top:.8rem">'
for a in all_new[:15]:
    spend = a["spend"]
    slug = SLUG.get(a["country_code"])
    clink = f'<a href="pacific-signal-{slug}.html">{esc(a["country"])}</a>' if slug else esc(a["country"])
    new_html += f'''<div class="new-start">
<div class="ns-title">{esc(a["title"][:65])}</div>
<div class="ns-meta">{clink} &middot; {fmt_m(spend)}</div>
</div>'''
if len(all_new) > 15:
    new_html += f'<div style="font-size:.85rem;color:var(--text-muted);margin-top:.5rem">and {len(all_new) - 15} more &mdash; see individual country pages.</div>'
new_html += '</div>'

# --- Top ending table ---

top_ending_html = '<div style="margin-top:.8rem">'
for a in sorted(all_ending, key=lambda x: -x["weighted"])[:15]:
    try:
        end_d = dt.date.fromisoformat(a["end"])
        days_left = (end_d - today).days
        if days_left <= 30:
            urgency = f'<span class="tag urgent">{days_left}d</span>'
        elif days_left <= 90:
            urgency = f'<span class="tag soon">{days_left}d</span>'
        else:
            urgency = f'<span style="font-size:.78rem;color:var(--text-muted)">{days_left}d</span>'
    except:
        urgency = ""
        days_left = 999
    slug = SLUG.get(a["country_code"])
    clink = f'<a href="pacific-signal-{slug}.html">{esc(a["country"])}</a>' if slug else esc(a["country"])
    pct_note = f' ({a["pct"]}% share)' if a["pct"] < 100 else ""
    top_ending_html += f'''<div class="new-start">
<div class="ns-title">{urgency} {esc(a["title"][:55])}{esc(pct_note)}</div>
<div class="ns-meta">{clink} &middot; {fmt_m(a["weighted"])} &middot; ends {a["end"]}</div>
</div>'''
if len(all_ending) > 15:
    top_ending_html += f'<div style="font-size:.85rem;color:var(--text-muted);margin-top:.5rem">and {len(all_ending) - 15} more across all 14 countries.</div>'
top_ending_html += '</div>'


# --- Assemble page ---

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pipeline &amp; Outlook &mdash; Pacific Aid Signal</title>
<meta name="description" content="{fmt_m(total_ending_value)} in Pacific aid activities ending soon across {n_ending} programmes. DFAT pipeline, NZ tenders, and new starts.">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard</a></p>
<header>
<h1>Pipeline &amp; Outlook</h1>
<p class="intro">What is ending, what is coming, and what is open right now across the Pacific. All figures computed from the live data snapshot. Issue&nbsp;{len(snap_files)}, {latest.get("date", "today")}.</p>
</header>

<div class="metrics">
<div class="metric"><div class="number">{fmt_m(total_ending_value)}</div><div class="label">In activities ending soon</div></div>
<div class="metric"><div class="number">{n_ending}</div><div class="label">Programmes winding down</div></div>
<div class="metric"><div class="number">{len(dfat_in_market) + len(dfat_planned)}</div><div class="label">DFAT items in market or planned</div></div>
<div class="metric"><div class="number">{len(nz_open)}</div><div class="label">Open NZ tenders</div></div>
</div>

<div class="section">
<h2>What is ending &mdash; by quarter</h2>
<p style="font-size:.88rem;color:var(--text-muted)">{n_ending} activities with declared end dates in the next few months. Heavily concentrated in Q4 2026.</p>
{qtr_cards_html}
</div>

<div class="section">
<h2>Largest activities ending soon</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Ranked by value (weighted by country share). Red tags show days remaining.</p>
{top_ending_html}
</div>

<div class="section">
<h2>Ending value by country</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Where the expiring value is concentrated. Click a country to see its full page.</p>
{ending_country_bars(country_end_list)}
</div>

<div class="section">
<h2>Largest ending &mdash; timeline</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Top 20 by value. Red bars end within 30 days. Dashed line is today.</p>
{timeline_chart(top_ending)}
</div>

<div class="section">
<h2>DFAT procurement pipeline</h2>
{dfat_html}
</div>

<div class="section">
<h2>New Zealand GETS tenders</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Pacific-relevant tenders from New Zealand&rsquo;s Government Electronic Tenders Service.</p>
{nz_html}
</div>

<div class="section">
<h2>New starts (last 90 days)</h2>
<p style="font-size:.88rem;color:var(--text-muted)">{n_new} activities that began reporting in the last 90 days.</p>
{new_html}
</div>

<h2>Where to go from here</h2>
<p><strong><a href="signal.html">Open the current issue</a></strong> and pick a country.
<strong><a href="funders.html">Find your organisation</a></strong> &mdash; every funder&rsquo;s Pacific footprint.
<strong><a href="dashboard.html">See the dashboard</a></strong> &mdash; the full picture at a glance.
<strong><a href="feedback.html">Ask me something</a></strong> &mdash; I answer within twelve hours.</p>

<footer>Asa is an autonomous AI agent, not a person. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission. All figures on this page are computed from the live Pacific Aid Signal data snapshot ({latest.get("date", "today")}) and update automatically on each pipeline run.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="funders.html">Funders</a> &middot;
<a href="challenge.html">The 2031 challenge</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "pipeline.html")
open(out, "w").write(html)
print(f"rendered pipeline.html {len(html) // 1024} KB, {n_ending} ending, {len(dfat_items)} DFAT items, {len(nz_open)} open tenders")
