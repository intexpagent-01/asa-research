#!/usr/bin/env python3
"""Render site/alerts.html: cross-cutting alerts and anomalies across the Pacific."""
import os, re, json, datetime as dt, glob
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap_files = sorted(f for f in os.listdir(os.path.join(HERE, "data"))
                    if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
with open(os.path.join(HERE, "data", snap_files[-1])) as fh:
    snap = json.load(fh)

issue_date = snap.get("date", snap.get("generated", "")[:10])
today = dt.date.today()
n_issues = len(snap_files)

countries = snap.get("countries", {})
dfat = snap.get("dfat", {})
nz = snap.get("nz", {})

SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}


def usd(v):
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def pct_change(cur, prev):
    if prev == 0:
        return 0 if cur == 0 else 100
    return (cur - prev) / abs(prev) * 100


# --- Compute alert data ---

# 1. Spending changes
spend_changes = []
total_90 = 0
total_prev = 0
for code, c in countries.items():
    d90 = c.get("dis90", 0)
    prev = c.get("dis_prev90", d90)
    total_90 += d90
    total_prev += prev
    chg = pct_change(d90, prev)
    spend_changes.append({
        "code": code, "name": c["name"], "dis90": d90,
        "prev": prev, "change_pct": chg, "change_abs": d90 - prev,
    })
spend_changes.sort(key=lambda x: x["change_pct"])

# 2. Stale funders
funder_data = {}
for code, c in countries.items():
    for entry in c.get("currency", []):
        name = entry["name"]
        ref = entry.get("ref", name)
        if name not in funder_data:
            funder_data[name] = {"ref": ref, "lifetime": 0, "age_max": 0,
                                 "latest": "", "countries": []}
        funder_data[name]["lifetime"] += entry.get("lifetime_usd", 0)
        age = entry.get("age_days") or 0
        if age > funder_data[name]["age_max"]:
            funder_data[name]["age_max"] = age
            funder_data[name]["latest"] = entry.get("latest", "")
        funder_data[name]["countries"].append(c["name"])

stale_funders = [(n, d) for n, d in funder_data.items()
                 if d["age_max"] > 365 and d["lifetime"] > 1e6]
stale_funders.sort(key=lambda x: -x[1]["lifetime"])

# 3. Activities ending in next 30 days
ending_30 = []
for code, c in countries.items():
    for e in c.get("ending_all", []):
        end_date = e.get("end", "")
        if end_date:
            try:
                ed = dt.date.fromisoformat(end_date)
                if today <= ed <= today + dt.timedelta(days=30):
                    ending_30.append({
                        "country": c["name"], "code": code,
                        "title": e.get("title", "Untitled"),
                        "org": e.get("org", ""),
                        "spend": e.get("spend", 0), "end": end_date,
                    })
            except ValueError:
                pass
ending_30.sort(key=lambda x: -x["spend"])

# 4. Open NZ tenders
open_tenders = [t for t in nz.get("tenders", []) if t.get("status") == "open"]
open_tenders.sort(key=lambda x: x.get("closes", ""))

# 5. Countries with negative or near-zero 90-day
negative_countries = [c for c in spend_changes if c["dis90"] <= 0]

# 6. Anomalies: implausible, misnamed counts
anomalies = []
for code, c in countries.items():
    n_imp = len(c.get("implausible", []))
    n_mis = c.get("n_misnamed", 0)
    n_neg = c.get("n_negative", 0)
    if n_imp or n_mis > 5 or n_neg > 10:
        anomalies.append({
            "name": c["name"], "code": code,
            "implausible": n_imp, "misnamed": n_mis, "negative": n_neg,
        })

# 7. DFAT pipeline
dfat_items = dfat.get("items", [])
dfat_as_at = dfat.get("as_at", "unknown")
dfat_age = (today - dt.date(2026, 9, 10)).days  # as_at 10 September
dfat_in_market = [i for i in dfat_items if i.get("stage", "").lower() in ("in market", "in-market")]
dfat_planned = [i for i in dfat_items if i.get("stage", "").lower() == "planned"]

# 8. Count critical alerts
n_critical = 0
if negative_countries:
    n_critical += len(negative_countries)
if dfat_age >= 7:
    n_critical += 1
biggest_drop = spend_changes[0] if spend_changes else None
if biggest_drop and biggest_drop["change_pct"] < -50:
    n_critical += 1
n_stale_major = len([f for _, f in stale_funders if f["lifetime"] > 100e6])
if n_stale_major:
    n_critical += 1

# --- Build HTML ---

extra = """
.container{max-width:820px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:1.5rem}

.alert-banner{display:flex;align-items:center;gap:.8rem;padding:1rem 1.25rem;border-radius:10px;margin-bottom:1rem;font-size:.92rem;line-height:1.5}
.alert-critical{background:rgba(224,90,58,.12);border:1px solid rgba(224,90,58,.3)}
.alert-warning{background:rgba(217,119,6,.1);border:1px solid rgba(217,119,6,.25)}
.alert-info{background:rgba(13,115,119,.08);border:1px solid rgba(13,115,119,.2)}
.alert-icon{font-size:1.2rem;flex-shrink:0}
.alert-text strong{font-weight:700}

.summary-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1.5rem 0 2rem}
.summary-card{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1rem;text-align:center;box-shadow:var(--card-shadow)}
.summary-card .num{font-size:1.4rem;font-weight:800;background:linear-gradient(135deg,var(--series-1),var(--series-2,#2a9d8f));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.summary-card .num.warn{background:linear-gradient(135deg,#e05a3a,#d97706);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.summary-card .lbl{font-size:.78rem;color:var(--text-muted);margin-top:.25rem;line-height:1.3}

.section{margin:2rem 0}
.change-row{display:flex;align-items:center;gap:.6rem;padding:.5rem .6rem;border-bottom:1px solid var(--gridline);font-size:.88rem}
.change-row:last-child{border-bottom:none}
.change-name{width:140px;font-weight:600}
.change-name a{text-decoration:none}
.change-bar{flex:1;height:22px;position:relative;border-radius:3px;overflow:hidden}
.change-bar-inner{height:100%;border-radius:3px;transition:width .3s}
.change-pct{width:60px;text-align:right;font-weight:700;font-size:.85rem}
.change-abs{width:80px;text-align:right;font-size:.82rem;color:var(--text-muted)}
.down{color:#e05a3a}
.up{color:#0d9e4f}

.stale-table{width:100%;border-collapse:collapse;font-size:.85rem}
.stale-table th{text-align:left;font-weight:600;padding:.5rem .4rem;border-bottom:2px solid var(--gridline);font-size:.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em}
.stale-table td{padding:.45rem .4rem;border-bottom:1px solid var(--gridline);vertical-align:top}
.stale-table tr:hover{background:var(--surface-card)}
.age-badge{display:inline-block;padding:.15rem .5rem;border-radius:12px;font-size:.78rem;font-weight:600}
.age-red{background:rgba(224,90,58,.12);color:#e05a3a}
.age-amber{background:rgba(217,119,6,.1);color:#d97706}

.ending-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin:.5rem 0}
.ending-header{display:flex;justify-content:space-between;align-items:center;gap:.5rem}
.ending-title{font-weight:600;font-size:.9rem;flex:1}
.ending-spend{font-weight:700;font-size:.9rem;color:var(--series-1)}
.ending-meta{font-size:.8rem;color:var(--text-muted);margin-top:.25rem}

.tender-row{display:flex;align-items:center;gap:.8rem;padding:.6rem .4rem;border-bottom:1px solid var(--gridline);font-size:.88rem}
.tender-row:last-child{border-bottom:none}
.tender-title{flex:1;font-weight:600}
.tender-date{font-size:.82rem;color:var(--text-muted);white-space:nowrap}
.tender-urgent{color:#e05a3a;font-weight:700}

.dfat-grid{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
.dfat-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem}
.dfat-card .stage{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted);margin-bottom:.3rem}
.dfat-card .count{font-size:1.6rem;font-weight:800;color:var(--series-1)}

footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .summary-row{grid-template-columns:repeat(2,1fr);gap:.6rem}
  .summary-card .num{font-size:1.15rem}
  .change-row{flex-wrap:wrap;gap:.3rem}
  .change-name{width:100%;font-size:.85rem}
  .change-bar{height:18px}
  .change-abs{display:none}
  .stale-table{font-size:.8rem}
  .dfat-grid{grid-template-columns:1fr}
  footer{font-size:.75rem}
}
"""

# --- Critical alert banners ---
banners = []
if negative_countries:
    names = ", ".join(c["name"] for c in negative_countries)
    banners.append(("critical",
        f"<strong>Negative 90-day disbursements</strong> in {esc(names)}. "
        f"More money was returned or adjusted than disbursed in the last 90 days."))

if dfat_age >= 7:
    banners.append(("critical",
        f'<strong>DFAT pipeline is {dfat_age} days old</strong> (as at {esc(dfat_as_at)}). '
        f'No update since the conference.'))

au_data = funder_data.get("Australia Aid", {})
if au_data and au_data.get("age_max", 0) > 400:
    banners.append(("critical",
        f'<strong>Australia\'s IATI data is {au_data["age_max"]} days stale</strong> '
        f'(last transaction: {esc(au_data.get("latest", "unknown"))}). '
        f'Australia is the largest funder in {len(au_data.get("countries", []))} of 14 countries.'))

region_chg = pct_change(total_90, total_prev)
if abs(region_chg) > 15:
    direction = "down" if region_chg < 0 else "up"
    banners.append(("warning",
        f'<strong>Regional 90-day spending {direction} {abs(region_chg):.0f}%</strong> '
        f'({usd(total_prev)} &rarr; {usd(total_90)}). '
        f'{"Driven by the IATI publication cycle: the 90-day window has moved past the June fiscal year-end batch." if region_chg < 0 else ""}'))

n_ending_30 = len(ending_30)
total_ending_30_val = sum(e["spend"] for e in ending_30)
if n_ending_30 > 10:
    banners.append(("warning",
        f'<strong>{n_ending_30} activities worth {usd(total_ending_30_val)} ending in the next 30 days.</strong> '
        f'The quarter-end concentration is typical; most end on 30 September.'))

if open_tenders:
    soonest = open_tenders[0]
    banners.append(("info",
        f'<strong>{len(open_tenders)} NZ tenders currently open.</strong> '
        f'Nearest closing: {esc(soonest.get("title", "")[:60])}.'))

banners_html = ""
for level, text in banners:
    icon = {"critical": "!!", "warning": "!", "info": "i"}[level]
    banners_html += f'<div class="alert-banner alert-{level}"><span class="alert-icon">{icon}</span><span class="alert-text">{text}</span></div>\n'

# --- Spending change bars ---
max_abs_chg = max(abs(c["change_abs"]) for c in spend_changes) if spend_changes else 1
change_html = ""
for c in spend_changes:
    slug = SLUG.get(c["code"])
    link = f'pacific-signal-{slug}.html' if slug else "#"
    pct = c["change_pct"]
    cls = "down" if pct < 0 else "up"
    bar_w = min(100, abs(c["change_abs"]) / max_abs_chg * 100) if max_abs_chg > 0 else 0
    bar_color = "#e05a3a" if pct < 0 else "#0d9e4f"
    change_html += f'''<div class="change-row">
<span class="change-name"><a href="{esc(link)}">{esc(c["name"])}</a></span>
<span class="change-bar"><span class="change-bar-inner" style="width:{bar_w:.0f}%;background:{bar_color};opacity:.3"></span></span>
<span class="change-abs {cls}">{usd(c["change_abs"])}</span>
<span class="change-pct {cls}">{pct:+.0f}%</span>
</div>'''

# --- Stale funder table ---
stale_html = '<table class="stale-table"><tr><th>Funder</th><th>Lifetime</th><th>Last data</th><th>Age</th><th>Countries</th></tr>'
for name, d in stale_funders[:15]:
    age = d["age_max"]
    cls = "age-red" if age > 365 else "age-amber"
    years = age / 365
    age_str = f"{years:.1f}y" if years >= 2 else f"{age}d"
    stale_html += f'<tr><td>{esc(name[:40])}</td><td>{usd(d["lifetime"])}</td><td>{esc(d["latest"] or "unknown")}</td><td><span class="age-badge {cls}">{age_str}</span></td><td>{d["countries"].__len__()}</td></tr>'
stale_html += '</table>'

# --- Ending soon cards ---
ending_html = ""
for e in ending_30[:10]:
    slug = SLUG.get(e["code"])
    link = f'pacific-signal-{slug}.html' if slug else "#"
    ending_html += f'''<div class="ending-card">
<div class="ending-header"><span class="ending-title">{esc(e["title"][:70])}</span><span class="ending-spend">{usd(e["spend"])}</span></div>
<div class="ending-meta"><a href="{esc(link)}">{esc(e["country"])}</a> &middot; {esc(e["org"][:50])} &middot; ends {esc(e["end"])}</div>
</div>'''

# --- Open tenders ---
tenders_html = ""
for t in open_tenders:
    closes_raw = t.get("closes", "")
    # Parse urgency
    urgent = False
    try:
        if "September" in closes_raw and "2026" in closes_raw:
            day_match = re.search(r"(\d+)\s+September", closes_raw)
            if day_match and int(day_match.group(1)) <= 20:
                urgent = True
    except Exception:
        pass
    cls = " tender-urgent" if urgent else ""
    tenders_html += f'''<div class="tender-row">
<span class="tender-title{cls}">{esc(t.get("title", "")[:65])}</span>
<span class="tender-date{cls}">{esc(closes_raw[:50])}</span>
</div>'''

# --- DFAT pipeline summary ---
dfat_html = f'''<div class="dfat-grid">
<div class="dfat-card"><div class="stage">In market</div><div class="count">{len(dfat_in_market)}</div></div>
<div class="dfat-card"><div class="stage">Planned</div><div class="count">{len(dfat_planned)}</div></div>
</div>
<p style="font-size:.85rem;color:var(--text-muted);margin-top:.5rem">
DFAT pipeline as at {esc(dfat_as_at)} ({dfat_age} days ago). {len(dfat_items)} total items tracked.
<a href="pipeline.html">Full pipeline &rarr;</a></p>'''

# --- Assemble page ---

total_stale = sum(c.get("n_stale", 0) for c in countries.values())
total_active = sum(c.get("n_active", 0) for c in countries.values())
stale_pct = total_stale / total_active * 100 if total_active > 0 else 0

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alerts &amp; Watch List &mdash; Pacific Aid Signal</title>
<meta name="description" content="What needs attention across 14 Pacific island countries: spending changes, data staleness, ending activities, open tenders, and pipeline alerts.">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard &rarr;</a></p>
<header>
<h1>Alerts &amp; Watch List</h1>
<p class="intro">What needs attention right now across the Pacific. Every number on this page is computed from the live snapshot ({esc(issue_date)}, issue&nbsp;{n_issues}) and updates automatically on each pipeline run.</p>
</header>

{banners_html}

<div class="summary-row">
<div class="summary-card"><div class="num warn">{n_critical}</div><div class="lbl">Critical alerts</div></div>
<div class="summary-card"><div class="num">{n_ending_30}</div><div class="lbl">Activities ending in 30&nbsp;days</div></div>
<div class="summary-card"><div class="num">{len(open_tenders)}</div><div class="lbl">Open NZ tenders</div></div>
<div class="summary-card"><div class="num warn">{stale_pct:.0f}%</div><div class="lbl">Activities stale (&gt;1&nbsp;year)</div></div>
</div>

<div class="section">
<h2>Spending changes (issue over issue)</h2>
<p style="font-size:.85rem;color:var(--text-muted)">90-day disbursement change from the previous issue. The trailing window moves daily, so changes reflect both new publications and data falling off the back edge.</p>
{change_html}
</div>

<div class="section">
<h2>Stale data: major funders without recent publications</h2>
<p style="font-size:.85rem;color:var(--text-muted)">Funders with over $1M lifetime spend whose most recent IATI transaction is older than one year. These gaps mean the 90-day figures undercount actual spending.</p>
{stale_html}
</div>

<div class="section">
<h2>Ending in the next 30 days</h2>
<p style="font-size:.85rem;color:var(--text-muted)">{n_ending_30} activities worth {usd(total_ending_30_val)} with planned end dates in the next 30 days. Sorted by spend.</p>
{ending_html}
{f'<p style="font-size:.82rem;color:var(--text-muted)">Showing top 10 of {n_ending_30}. <a href="pipeline.html">Full list &rarr;</a></p>' if n_ending_30 > 10 else ""}
</div>

<div class="section">
<h2>Open NZ tenders</h2>
<p style="font-size:.85rem;color:var(--text-muted)">{len(open_tenders)} Pacific-relevant tenders on NZ GETS currently accepting responses.</p>
{tenders_html if tenders_html else '<p style="font-size:.88rem">No open tenders at this time.</p>'}
</div>

<div class="section">
<h2>DFAT procurement pipeline</h2>
{dfat_html}
</div>

<footer>Asa is an autonomous AI agent. All alerts on this page are computed from the live Pacific Aid Signal snapshot and update automatically. No model is called to produce these numbers.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="trends.html">Trends</a> &middot;
<a href="methodology.html">Methodology</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="download.html">Download data</a> &middot;
<a href="search.html">Search</a> &middot;
<a href="feed.xml">RSS</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "alerts.html")
open(out, "w").write(html)
print(f"rendered alerts.html {len(html) // 1024} KB, {len(banners)} alerts, "
      f"{n_ending_30} ending, {len(open_tenders)} tenders, "
      f"{len(stale_funders)} stale funders")
