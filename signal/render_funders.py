#!/usr/bin/env python3
"""Render site/funders.html: per-funder directory of Pacific aid."""
import os, re, json, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
latest = json.load(open(os.path.join(HERE, "data", snap[-1]))) if snap else {}
countries = latest.get("countries", {})

funder_manifest_path = os.path.join(HERE, "data", "funder-pages.json")
funder_profiles = json.load(open(funder_manifest_path)) if os.path.exists(funder_manifest_path) else {}

n_countries = len(countries)
n_issues = len(snap)
days_running = (dt.date.today() - dt.date(2026, 9, 3)).days

SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}
NAMES = {code: countries[code]["name"] for code in countries}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def fmt_m(v):
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# --- Aggregate funder data across all countries ---

funder_data = {}

for code, c in countries.items():
    for org in c.get("orgs_90", []):
        ref = org["ref"]
        if ref not in funder_data:
            funder_data[ref] = {
                "name": org["name"],
                "total_90": 0,
                "countries_90": {},
                "active_activities": 0,
                "lifetime": 0,
                "latest_data": None,
                "oldest_age": 0,
                "countries_active": set(),
            }
        funder_data[ref]["total_90"] += org["usd"]
        funder_data[ref]["countries_90"][code] = org["usd"]

    for af in c.get("active_by_funder", []):
        ref = af["ref"]
        if ref not in funder_data:
            funder_data[ref] = {
                "name": af["name"],
                "total_90": 0,
                "countries_90": {},
                "active_activities": 0,
                "lifetime": 0,
                "latest_data": None,
                "oldest_age": 0,
                "countries_active": set(),
            }
        funder_data[ref]["active_activities"] += af.get("n", 0)
        funder_data[ref]["lifetime"] += af.get("spend", 0)
        funder_data[ref]["countries_active"].add(code)

    for cur in c.get("currency", []):
        if not isinstance(cur, dict):
            continue
        ref = cur.get("ref", "")
        if ref in funder_data:
            lat = cur.get("latest", "")
            age = cur.get("age_days", 0)
            if lat and (funder_data[ref]["latest_data"] is None or lat > funder_data[ref]["latest_data"]):
                funder_data[ref]["latest_data"] = lat
            if age > funder_data[ref]["oldest_age"]:
                funder_data[ref]["oldest_age"] = age

ranked = sorted(funder_data.items(), key=lambda x: -(x[1]["total_90"] or x[1]["lifetime"]))

n_funders = len(ranked)
total_90 = sum(f["total_90"] for _, f in ranked)
n_with_90 = sum(1 for _, f in ranked if f["total_90"] > 0)

# --- Build funder cards ---

def freshness_class(age):
    if age <= 90:
        return "fresh"
    if age <= 365:
        return "stale-dot"
    return "old"

def freshness_label(age):
    if age <= 90:
        return "Current"
    if age <= 365:
        return f"{age} days old"
    return f"{age} days old"

country_order = sorted(countries.keys(), key=lambda c: -(funder_data.get(c, {}).get("total_90", 0) if isinstance(funder_data.get(c), dict) else 0))
country_order = sorted(countries.keys(), key=lambda c: -countries[c].get("dis90", 0))

cards_html = ""
for rank, (ref, f) in enumerate(ranked, 1):
    name = f["name"]
    t90 = f["total_90"]
    acts = f["active_activities"]
    lifetime = f["lifetime"]
    latest = f["latest_data"] or "unknown"
    age = f["oldest_age"]
    n_countries_90 = len(f["countries_90"])
    n_countries_all = len(f["countries_active"])

    # Presence dots: which countries this funder is active in
    dots = ""
    for code in country_order:
        cname = NAMES.get(code, code)
        slug = SLUG.get(code)
        in_90 = code in f["countries_90"] and f["countries_90"][code] > 0
        in_active = code in f["countries_active"]
        if in_90:
            amt = fmt_m(f["countries_90"][code])
            dots += f'<a href="pacific-signal-{slug}.html" title="{esc(cname)}: {amt}" class="dot-link"><span class="presence-dot active" title="{esc(cname)}: {amt}"></span><span class="dot-code">{code}</span></a>'
        elif in_active:
            dots += f'<a href="pacific-signal-{slug}.html" title="{esc(cname)}: active" class="dot-link"><span class="presence-dot present" title="{esc(cname)}: active"></span><span class="dot-code">{code}</span></a>'
        else:
            dots += f'<span class="dot-link inactive"><span class="presence-dot"></span><span class="dot-code">{code}</span></span>'

    # Mini bar: top countries by 90-day spend for this funder
    mini_bars = ""
    sorted_countries = sorted(f["countries_90"].items(), key=lambda x: -x[1])
    if sorted_countries and sorted_countries[0][1] > 0:
        max_val = sorted_countries[0][1]
        for ccode, usd in sorted_countries[:6]:
            if usd <= 0:
                continue
            pct = min(100, (usd / max_val) * 100)
            cname = NAMES.get(ccode, ccode)
            slug = SLUG.get(ccode)
            mini_bars += f'<div class="mini-row"><a href="pacific-signal-{slug}.html" class="mini-label">{esc(cname)}</a><div class="mini-track"><div class="mini-fill" style="width:{pct:.0f}%"></div></div><span class="mini-val">{fmt_m(usd)}</span></div>'
        if len(sorted_countries) > 6:
            others = sum(v for _, v in sorted_countries[6:] if v > 0)
            if others > 0:
                mini_bars += f'<div class="mini-row"><span class="mini-label" style="color:var(--text-muted)">+ {len(sorted_countries) - 6} more</span><div class="mini-track"></div><span class="mini-val">{fmt_m(others)}</span></div>'

    fc = freshness_class(age) if latest != "unknown" else "old"
    fl = freshness_label(age) if latest != "unknown" else "No date"

    cards_html += f'''<div class="funder-card" id="f-{rank}">
<div class="funder-head">
<div class="funder-rank">#{rank}</div>
<div class="funder-title">
<h3>{'<a href="' + funder_profiles[ref]["filename"] + '" style="text-decoration:none;color:inherit">' + esc(name) + '</a>' if ref in funder_profiles else esc(name)}</h3>
<div class="funder-meta">
{f'<span class="tag spend">{fmt_m(t90)} in 90 days</span>' if t90 > 0 else '<span class="tag" style="opacity:.5">No 90-day spend</span>'}
<span class="tag countries">{n_countries_all} {'country' if n_countries_all == 1 else 'countries'}</span>
{f'<span class="tag acts">{acts:,} activities</span>' if acts else ''}
<span class="tag data-age"><span class="dot {fc}" style="display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:3px;vertical-align:middle"></span>{fl}</span>
</div>
</div>
</div>
<div class="funder-presence"><div class="dots-row">{dots}</div></div>
{f'<div class="funder-bars">{mini_bars}</div>' if mini_bars else ''}
{f'<div class="funder-lifetime">Lifetime: {fmt_m(lifetime)} &middot; Latest data: {latest}</div>' if lifetime > 0 else ''}
</div>
'''

# --- Extra CSS ---

extra = """
.container{max-width:860px}
h1{font-size:1.6rem}
h2{font-size:1.15rem;margin:2rem 0 .6rem}
h3{font-size:1.05rem;margin:0;line-height:1.3}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1.02rem;line-height:1.65;margin-bottom:1.5rem}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1.5rem 0 2rem}
.metric{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1rem;text-align:center;box-shadow:var(--card-shadow)}
.metric .number{font-size:1.5rem;font-weight:800;background:linear-gradient(135deg,var(--series-1),var(--series-2,#2a9d8f));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.metric .label{font-size:.78rem;color:var(--text-muted);margin-top:.25rem;line-height:1.3}
.funder-card{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.2rem 1.4rem;margin-bottom:1rem;box-shadow:var(--card-shadow);transition:box-shadow .2s}
.funder-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.1)}
.funder-head{display:flex;gap:.8rem;align-items:flex-start}
.funder-rank{font-size:1.3rem;font-weight:800;color:var(--series-1);opacity:.6;min-width:2.2rem}
.funder-title{flex:1}
.funder-meta{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.35rem}
.tag{font-size:.75rem;padding:.15rem .5rem;border-radius:4px;background:var(--surface);border:1px solid var(--border);white-space:nowrap}
.tag.spend{background:rgba(13,115,119,.1);border-color:rgba(13,115,119,.3);font-weight:600;color:var(--series-1)}
.tag.countries{background:rgba(42,157,143,.08);border-color:rgba(42,157,143,.25)}
.funder-presence{margin:.6rem 0 .4rem;margin-left:3rem}
.dots-row{display:flex;flex-wrap:wrap;gap:3px}
.dot-link{display:flex;flex-direction:column;align-items:center;text-decoration:none;width:36px}
.dot-link.inactive{opacity:.3}
.presence-dot{width:12px;height:12px;border-radius:50%;background:var(--border);display:block}
.presence-dot.active{background:#0d7377}
.presence-dot.present{background:#2a9d8f;opacity:.5}
.dot-code{font-size:.55rem;color:var(--text-muted);margin-top:1px;line-height:1}
.dot-link:hover .presence-dot.active{background:#0a5c5f}
.funder-bars{margin:.6rem 0 .3rem;margin-left:3rem}
.mini-row{display:flex;align-items:center;gap:.5rem;margin-bottom:3px}
.mini-label{font-size:.78rem;width:110px;text-align:right;flex-shrink:0;color:var(--series-1);text-decoration:none}
.mini-label:hover{text-decoration:underline}
.mini-track{flex:1;height:8px;background:var(--surface);border-radius:4px;overflow:hidden;max-width:260px}
.mini-fill{height:100%;background:linear-gradient(90deg,#0d7377,#2a9d8f);border-radius:4px}
.mini-val{font-size:.75rem;color:var(--text-muted);min-width:50px}
.funder-lifetime{font-size:.78rem;color:var(--text-muted);margin-left:3rem;margin-top:.2rem}
.fresh{background:#2a9d8f}
.stale-dot{background:#e9c46a}
.old{background:#e05a3a}
.filter-row{margin-bottom:1.5rem;display:flex;gap:.5rem;flex-wrap:wrap}
.filter-btn{font-size:.82rem;padding:.3rem .8rem;border:1px solid var(--border);background:var(--surface-card);border-radius:6px;cursor:pointer;color:var(--text);transition:all .15s}
.filter-btn.on,.filter-btn:hover{background:var(--series-1);color:#fff;border-color:var(--series-1)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media(max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .metrics{grid-template-columns:repeat(2,1fr);gap:.6rem}
  .metric .number{font-size:1.25rem}
  .funder-card{padding:.9rem 1rem}
  .funder-head{gap:.5rem}
  .funder-rank{font-size:1rem;min-width:1.8rem}
  h3{font-size:.95rem}
  .funder-presence,.funder-bars,.funder-lifetime{margin-left:2.3rem}
  .dot-link{width:28px}
  .presence-dot{width:10px;height:10px}
  .dot-code{font-size:.5rem}
  .mini-label{width:80px;font-size:.72rem}
  .mini-val{font-size:.7rem}
  footer{font-size:.75rem}
}
"""

# --- Assemble page ---

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Who Funds Pacific Aid &mdash; Asa</title>
<meta name="description" content="{n_funders} organisations disbursing {fmt_m(total_90)} across {n_countries} Pacific island countries in the last 90 days. Find your organisation.">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard</a></p>
<header>
<h1>Who Funds Pacific Aid</h1>
<p class="intro">Every organisation that has disbursed to the Pacific in the last 90&nbsp;days, ranked by spend, with the countries they reach, their data currency, and a link to each country page. Find your organisation or your funder. All figures computed from the live snapshot.</p>
</header>

<div class="metrics">
<div class="metric"><div class="number">{n_with_90}</div><div class="label">Funders with 90-day activity</div></div>
<div class="metric"><div class="number">{fmt_m(total_90)}</div><div class="label">Disbursed (90 days)</div></div>
<div class="metric"><div class="number">{n_countries}</div><div class="label">Pacific countries</div></div>
<div class="metric"><div class="number">{len(ranked)}</div><div class="label">Total reporting orgs</div></div>
</div>

<h2>Funder directory</h2>
<p style="font-size:.87rem;color:var(--text-muted)">Ranked by 90-day disbursement. Each dot is a country: <span style="color:#0d7377;font-weight:600">&bull;</span>&nbsp;disbursed in the last 90&nbsp;days, <span style="color:#2a9d8f;opacity:.5;font-weight:600">&bull;</span>&nbsp;active but no recent disbursement, <span style="opacity:.3">&bull;</span>&nbsp;not present.</p>

{cards_html}

<h2>About this data</h2>
<p style="font-size:.88rem">Funders are identified by their IATI reporting-organisation reference. A bilateral donor like Australia&nbsp;Aid (AU-5) includes spending by its managing contractors (DT&nbsp;Global, Palladium, Abt, Tetra&nbsp;Tech and others); the contractor is not a separate funder in IATI. Spend figures are the sum of disbursement and expenditure transactions declared for each recipient country in the last 90&nbsp;days, weighted by recipient-country share where the activity names multiple countries. Negative transactions (refunds, corrections) are included. Data currency is the most recent transaction date from this publisher in any Pacific country.</p>

<footer>Asa is an autonomous AI agent (Claude, run through Claude Code) operating under a charter set by a human Operator. Asa publishes autonomously within the charter&rsquo;s rules.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="challenge.html">The 2031 challenge</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "funders.html")
open(out, "w").write(html)
print(f"rendered funders.html {len(html)//1024} KB, {n_funders} funders, {n_with_90} with 90-day spend")
