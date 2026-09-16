#!/usr/bin/env python3
"""Render individual funder profile pages: site/funder-{slug}.html"""
import os, re, json, gzip, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap_file = sorted(f for f in os.listdir(os.path.join(HERE, "data"))
                   if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)[-1]
with open(os.path.join(HERE, "data", snap_file)) as fh:
    snap = json.load(fh)
countries = snap.get("countries", {})
issue_date = snap.get("date", snap.get("generated", "")[:10])

idx_file = snap_file.replace(".json", ".index.json.gz")
with gzip.open(os.path.join(HERE, "data", idx_file), "rt") as f:
    idx = json.load(f)

NAMES = {
    "PG": "Papua New Guinea", "FJ": "Fiji", "SB": "Solomon Islands",
    "VU": "Vanuatu", "WS": "Samoa", "TO": "Tonga", "KI": "Kiribati",
    "TV": "Tuvalu", "FM": "Micronesia", "MH": "Marshall Islands",
    "PW": "Palau", "NR": "Nauru", "NU": "Niue", "CK": "Cook Islands",
}
SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}
STATUS_LABELS = {1: "Pipeline", 2: "Implementation", 3: "Finalisation"}

MIN_ACTIVITIES = 5

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def fmt_m(v):
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

def ref_to_slug(ref):
    return re.sub(r'[^a-z0-9]+', '-', ref.lower()).strip('-')

# --- Aggregate data per funder from index and snapshot ---

funders = {}
for code, cdata in idx.items():
    cols = cdata["cols"]
    ci = {c: i for i, c in enumerate(cols)}
    for row in cdata["rows"]:
        ref = row[ci["ref"]]
        org = row[ci["org"]]
        if ref not in funders:
            funders[ref] = {
                "name": org, "activities": [], "by_country": defaultdict(list),
                "total_spend": 0, "spend_90": 0,
                "n_impl": 0, "n_pipe": 0, "n_fin": 0,
                "countries": set(), "latest_data": None, "age_days": 0,
            }
        act = {
            "country": code,
            "aid": row[ci["aid"]],
            "title": row[ci["title"]],
            "status": row[ci["st"]],
            "start": row[ci["start"]],
            "end": row[ci["end"]],
            "spend": row[ci["spend"]] or 0,
            "pct": row[ci["pct"]],
            "stale": row[ci["stale"]],
        }
        funders[ref]["activities"].append(act)
        funders[ref]["by_country"][code].append(act)
        funders[ref]["total_spend"] += act["spend"]
        funders[ref]["countries"].add(code)
        st = act["status"]
        if st == 1: funders[ref]["n_pipe"] += 1
        elif st == 2: funders[ref]["n_impl"] += 1
        elif st == 3: funders[ref]["n_fin"] += 1

# Enrich with snapshot data (90-day spend, currency)
for code, c in countries.items():
    for org in c.get("orgs_90", []):
        ref = org["ref"]
        if ref in funders:
            funders[ref]["spend_90"] += org["usd"]
    for cur in c.get("currency", []):
        if not isinstance(cur, dict):
            continue
        ref = cur.get("ref", "")
        if ref in funders:
            lat = cur.get("latest", "")
            age = cur.get("age_days", 0)
            if lat and (funders[ref]["latest_data"] is None or lat > funders[ref]["latest_data"]):
                funders[ref]["latest_data"] = lat
            if age > funders[ref]["age_days"]:
                funders[ref]["age_days"] = age

# --- CSS ---
extra = """
.container{max-width:860px}
h1{font-size:1.5rem;margin-bottom:.3rem}
h2{font-size:1.12rem;margin:2rem 0 .6rem}
h3{font-size:.98rem;margin:1.2rem 0 .4rem}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.subtitle{font-size:.92rem;color:var(--text-muted);margin-bottom:1.5rem}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1.2rem 0 1.8rem}
.metric{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:.9rem;text-align:center;box-shadow:var(--card-shadow)}
.metric .number{font-size:1.4rem;font-weight:800;background:linear-gradient(135deg,var(--series-1),var(--series-2,#2a9d8f));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.metric .label{font-size:.75rem;color:var(--text-muted);margin-top:.2rem;line-height:1.3}
.bar-section{margin:1.2rem 0}
.bar-row{display:flex;align-items:center;gap:.5rem;margin-bottom:6px}
.bar-label{font-size:.82rem;width:130px;text-align:right;flex-shrink:0}
.bar-label a{color:var(--series-1);text-decoration:none}
.bar-label a:hover{text-decoration:underline}
.bar-track{flex:1;height:16px;background:var(--surface);border-radius:4px;overflow:hidden;max-width:400px}
.bar-fill{height:100%;border-radius:4px}
.bar-fill.spend{background:linear-gradient(90deg,#0d7377,#2a9d8f)}
.bar-fill.acts{background:linear-gradient(90deg,#2a9d8f,#4ec6c1)}
.bar-val{font-size:.78rem;color:var(--text-muted);min-width:70px}
.status-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:1rem 0}
.status-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem;text-align:center}
.status-card .st-n{font-size:1.3rem;font-weight:700}
.status-card .st-l{font-size:.75rem;color:var(--text-muted);margin-top:.15rem}
.st-pipe .st-n{color:#e9c46a}
.st-impl .st-n{color:#2a9d8f}
.st-fin .st-n{color:#264653}
.presence-row{display:flex;flex-wrap:wrap;gap:6px;margin:1rem 0}
.presence-chip{display:inline-flex;align-items:center;gap:4px;font-size:.8rem;padding:.3rem .7rem;border-radius:6px;background:var(--surface-card);border:1px solid var(--border);text-decoration:none;color:var(--text);transition:all .15s}
.presence-chip:hover{border-color:var(--series-1);box-shadow:0 2px 8px rgba(0,0,0,.08)}
.presence-chip .chip-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.chip-dot.active{background:#0d7377}
.chip-dot.present{background:#2a9d8f;opacity:.5}
.act-table{width:100%;border-collapse:collapse;font-size:.82rem;margin-top:.6rem}
.act-table th{text-align:left;font-size:.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;padding:.4rem .5rem;border-bottom:2px solid var(--border);position:sticky;top:0;background:var(--surface)}
.act-table td{padding:.4rem .5rem;border-bottom:1px solid var(--border);vertical-align:top}
.act-table tr:hover td{background:rgba(13,115,119,.03)}
.cell-title{max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.status-badge{font-size:.68rem;padding:.15rem .4rem;border-radius:3px;font-weight:600;white-space:nowrap}
.status-pipeline{background:rgba(233,196,74,.15);color:#b8860b}
.status-implementation{background:rgba(42,157,143,.12);color:#1a7a6d}
.status-finalisation{background:rgba(38,70,83,.1);color:#264653}
.status-stale{background:rgba(224,90,58,.1);color:#c0392b}
.data-note{font-size:.85rem;padding:.8rem 1rem;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;margin:1rem 0;line-height:1.5}
.data-note.stale{border-left:3px solid #e05a3a}
.data-note.fresh{border-left:3px solid #2a9d8f}
.country-section{margin-top:1.5rem;padding-top:1rem;border-top:1px solid var(--border)}
.country-section:first-of-type{border-top:none;padding-top:0}
.act-toggle{font-size:.8rem;color:var(--series-1);cursor:pointer;border:none;background:none;padding:.2rem 0;margin-top:.3rem}
.act-toggle:hover{text-decoration:underline}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media(max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .metrics{grid-template-columns:repeat(2,1fr);gap:.6rem}
  .metric .number{font-size:1.2rem}
  .status-grid{grid-template-columns:repeat(3,1fr);gap:.5rem}
  .bar-label{width:90px;font-size:.75rem}
  .bar-val{font-size:.72rem;min-width:50px}
  .cell-title{max-width:180px}
  .act-table{font-size:.75rem}
  footer{font-size:.75rem}
}
"""

def freshness_note(latest, age):
    if not latest or latest == "unknown":
        return '<div class="data-note stale">No data date available for this funder.</div>'
    if age <= 90:
        return f'<div class="data-note fresh">Data is <strong>current</strong> &mdash; most recent transaction dated {esc(latest)} ({age} days ago).</div>'
    if age <= 365:
        return f'<div class="data-note stale">Data is <strong>{age} days old</strong> &mdash; most recent transaction dated {esc(latest)}.</div>'
    return f'<div class="data-note stale">Data is <strong>{age} days old</strong> &mdash; most recent transaction dated {esc(latest)}. This funder has not published a transaction in over a year.</div>'

# --- Generate pages ---

generated = 0
funder_pages = {}

for ref, fd in sorted(funders.items(), key=lambda x: -(x[1]["spend_90"] or x[1]["total_spend"])):
    n_acts = len(fd["activities"])
    if n_acts < MIN_ACTIVITIES:
        continue

    slug = ref_to_slug(ref)
    filename = f"funder-{slug}.html"
    funder_pages[ref] = {"slug": slug, "filename": filename, "name": fd["name"]}

    name = fd["name"]
    n_countries = len(fd["countries"])
    total_spend = fd["total_spend"]
    spend_90 = fd["spend_90"]
    latest = fd["latest_data"] or "unknown"
    age = fd["age_days"]

    # Country breakdown — spend and activity count
    country_spend = {}
    country_acts = {}
    for code in sorted(fd["countries"], key=lambda c: -sum(a["spend"] for a in fd["by_country"][c])):
        acts = fd["by_country"][code]
        country_spend[code] = sum(a["spend"] for a in acts)
        country_acts[code] = len(acts)

    sorted_by_spend = sorted(country_spend.items(), key=lambda x: -x[1])
    max_spend = sorted_by_spend[0][1] if sorted_by_spend and sorted_by_spend[0][1] > 0 else 1

    sorted_by_acts = sorted(country_acts.items(), key=lambda x: -x[1])
    max_acts = sorted_by_acts[0][1] if sorted_by_acts else 1

    # Spend bars
    spend_bars = ""
    for code, usd in sorted_by_spend:
        if usd <= 0 and country_acts[code] < 3:
            continue
        cname = NAMES.get(code, code)
        cslug = SLUG.get(code)
        pct = min(100, (usd / max_spend) * 100) if max_spend > 0 else 0
        spend_bars += f'''<div class="bar-row">
<div class="bar-label"><a href="pacific-signal-{cslug}.html">{esc(cname)}</a></div>
<div class="bar-track"><div class="bar-fill spend" style="width:{pct:.0f}%"></div></div>
<div class="bar-val">{fmt_m(usd)}</div>
</div>\n'''

    # Activity count bars
    act_bars = ""
    for code, n in sorted_by_acts:
        if n < 1:
            continue
        cname = NAMES.get(code, code)
        cslug = SLUG.get(code)
        pct = min(100, (n / max_acts) * 100)
        act_bars += f'''<div class="bar-row">
<div class="bar-label"><a href="pacific-signal-{cslug}.html">{esc(cname)}</a></div>
<div class="bar-track"><div class="bar-fill acts" style="width:{pct:.0f}%"></div></div>
<div class="bar-val">{n}</div>
</div>\n'''

    # Country presence chips
    chips = ""
    for code in sorted(fd["countries"], key=lambda c: -country_spend.get(c, 0)):
        cname = NAMES.get(code, code)
        cslug = SLUG.get(code)
        has_90 = country_spend.get(code, 0) > 0 and spend_90 > 0
        dot_cls = "active" if has_90 else "present"
        chips += f'<a href="pacific-signal-{cslug}.html" class="presence-chip"><span class="chip-dot {dot_cls}"></span>{esc(cname)}</a>\n'

    # Top activities table (top 30 by spend)
    top_acts = sorted(fd["activities"], key=lambda a: -a["spend"])[:30]
    act_rows = ""
    for a in top_acts:
        cname = NAMES.get(a["country"], a["country"])
        cslug = SLUG.get(a["country"])
        st = a["status"]
        if a["stale"]:
            badge = '<span class="status-badge status-stale">Stale</span>'
        else:
            st_cls = STATUS_LABELS.get(st, "Pipeline").lower()
            badge = f'<span class="status-badge status-{st_cls}">{STATUS_LABELS.get(st, "?")}</span>'
        pct_note = f' ({a["pct"]}%)' if a["pct"] and a["pct"] < 100 else ""
        act_rows += f'''<tr>
<td><a href="pacific-signal-{cslug}.html">{esc(a["country"])}</a></td>
<td class="cell-title" title="{esc(a["title"])}">{esc(a["title"])}</td>
<td>{badge}</td>
<td>{esc(a["start"] or "—")}</td>
<td>{esc(a["end"] or "—")}</td>
<td style="text-align:right">{fmt_m(a["spend"])}{esc(pct_note)}</td>
</tr>\n'''

    remaining = n_acts - 30
    remaining_note = f'<p style="font-size:.82rem;color:var(--text-muted);margin-top:.5rem">Showing top 30 of {n_acts:,} activities by spend. <a href="explorer.html?org={esc(name)}">See all in the Data Explorer</a>.</p>' if remaining > 0 else ""

    # Per-country activity sections
    country_sections = ""
    for code in sorted(fd["countries"], key=lambda c: -country_spend.get(c, 0)):
        cname = NAMES.get(code, code)
        cslug = SLUG.get(code)
        acts = sorted(fd["by_country"][code], key=lambda a: -a["spend"])
        n_impl = sum(1 for a in acts if a["status"] == 2)
        n_pipe = sum(1 for a in acts if a["status"] == 1)
        n_fin = sum(1 for a in acts if a["status"] == 3)
        n_stale = sum(1 for a in acts if a["stale"])
        cspend = country_spend[code]
        status_parts = []
        if n_impl: status_parts.append(f"{n_impl} implementing")
        if n_pipe: status_parts.append(f"{n_pipe} pipeline")
        if n_fin: status_parts.append(f"{n_fin} finalisation")
        if n_stale: status_parts.append(f"{n_stale} stale")
        status_text = ", ".join(status_parts) if status_parts else "—"

        top_3 = acts[:3]
        act_lines = ""
        for a in top_3:
            act_lines += f'<li>{esc(a["title"][:80])} &mdash; {fmt_m(a["spend"])}</li>'

        country_sections += f'''<div class="country-section">
<h3><a href="pacific-signal-{cslug}.html">{esc(cname)}</a></h3>
<p style="font-size:.83rem;color:var(--text-muted)">{len(acts)} activities &middot; {fmt_m(cspend)} lifetime &middot; {status_text}</p>
<ul style="font-size:.83rem;margin:.4rem 0 .3rem 1.2rem;line-height:1.5">{act_lines}</ul>
{"<p style='font-size:.8rem;color:var(--text-muted)'>and " + str(len(acts)-3) + " more</p>" if len(acts) > 3 else ""}
</div>\n'''

    # Assemble
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name)} &mdash; Pacific Aid Profile &mdash; Asa</title>
<meta name="description" content="{esc(name)}: {n_acts:,} activities across {n_countries} Pacific countries, {fmt_m(total_spend)} lifetime spend. Full portfolio profile.">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="funders.html">All funders</a> &middot; <a href="signal.html">Signal</a></p>

<h1>{esc(name)}</h1>
<p class="subtitle">Pacific aid portfolio &middot; IATI ref: <code>{esc(ref)}</code></p>

<div class="metrics">
<div class="metric"><div class="number">{fmt_m(total_spend)}</div><div class="label">Lifetime spend</div></div>
<div class="metric"><div class="number">{fmt_m(spend_90) if spend_90 > 0 else "—"}</div><div class="label">90-day disbursement</div></div>
<div class="metric"><div class="number">{n_acts:,}</div><div class="label">Activities</div></div>
<div class="metric"><div class="number">{n_countries}</div><div class="label">Countries</div></div>
</div>

{freshness_note(latest, age)}

<div class="status-grid">
<div class="status-card st-pipe"><div class="st-n">{fd["n_pipe"]}</div><div class="st-l">Pipeline</div></div>
<div class="status-card st-impl"><div class="st-n">{fd["n_impl"]}</div><div class="st-l">Implementation</div></div>
<div class="status-card st-fin"><div class="st-n">{fd["n_fin"]}</div><div class="st-l">Finalisation</div></div>
</div>

<h2>Country presence</h2>
<div class="presence-row">{chips}</div>

<h2>Spend by country</h2>
<div class="bar-section">{spend_bars}</div>

<h2>Activities by country</h2>
<div class="bar-section">{act_bars}</div>

<h2>Top activities</h2>
<div style="overflow-x:auto">
<table class="act-table">
<thead><tr><th>Country</th><th>Activity</th><th>Status</th><th>Start</th><th>End</th><th style="text-align:right">Spend</th></tr></thead>
<tbody>{act_rows}</tbody>
</table>
</div>
{remaining_note}

<h2>Country detail</h2>
{country_sections}

<p style="font-size:.85rem;margin-top:1.5rem"><a href="explorer.html?org={esc(name)}">View all {n_acts:,} activities in the Data Explorer &rarr;</a></p>

<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
<br>Data as at issue {esc(issue_date)}.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="funders.html">All funders</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="download.html">Download data</a> &middot;
<a href="explorer.html">Data Explorer</a> &middot;
<a href="methodology.html">Methodology</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="search.html">Search</a> &middot;
<a href="feed.xml">RSS feed</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

    out = os.path.join(SITE, filename)
    with open(out, "w") as fh:
        fh.write(html)
    generated += 1

# --- Update funders.html to link to profile pages ---
# Write a JSON manifest for use by other renderers
manifest_path = os.path.join(HERE, "data", "funder-pages.json")
with open(manifest_path, "w") as fh:
    json.dump(funder_pages, fh, indent=2, default=str)

print(f"rendered {generated} funder profile pages ({MIN_ACTIVITIES}+ activities threshold)")
print(f"manifest written to {manifest_path}")
