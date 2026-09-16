#!/usr/bin/env python3
"""Render site/download.html and generate CSV exports from the latest snapshot."""
import os, re, json, csv, gzip, io, datetime as dt
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap_file = sorted(f for f in os.listdir(os.path.join(HERE, "data"))
                   if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)[-1]
with open(os.path.join(HERE, "data", snap_file)) as fh:
    snap = json.load(fh)

issue_date = snap.get("date", snap.get("generated", "")[:10])

COUNTRY_NAMES = {
    "PG": "Papua New Guinea", "FJ": "Fiji", "SB": "Solomon Islands",
    "VU": "Vanuatu", "WS": "Samoa", "TO": "Tonga", "KI": "Kiribati",
    "TV": "Tuvalu", "FM": "Micronesia", "MH": "Marshall Islands",
    "PW": "Palau", "NR": "Nauru", "NU": "Niue", "CK": "Cook Islands",
}

STATUS_LABELS = {1: "pipeline", 2: "implementation", 3: "finalisation", 4: "closed"}

data_dir = os.path.join(SITE, "data")
os.makedirs(data_dir, exist_ok=True)

files_generated = []


def write_csv(filename, rows, headers):
    path = os.path.join(data_dir, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    size = os.path.getsize(path)
    files_generated.append((filename, len(rows), size, headers))
    return len(rows)


# 1. Country summary
rows = []
for code in sorted(snap["countries"]):
    c = snap["countries"][code]
    rows.append([
        code, COUNTRY_NAMES.get(code, code),
        round(c.get("dis90", 0), 2),
        round(c.get("dis365", 0), 2),
        c.get("n_orgs_90", 0),
        c.get("n_orgs_365", 0),
        c.get("n_activities", 0),
        c.get("n_active", 0),
        c.get("n_stale", 0),
        c.get("n_new_starts", 0),
        c.get("n_ending_soon", 0),
        c.get("n_quiet", 0),
        c.get("n_wb_total", 0),
    ])
write_csv("country-summary.csv", rows, [
    "country_code", "country_name", "disbursements_90d_usd", "disbursements_365d_usd",
    "funders_90d", "funders_365d", "total_activities", "active_activities",
    "stale_activities", "new_starts", "ending_soon", "quiet_funders", "world_bank_projects",
])

# 2. Funder disbursements (90-day)
rows = []
for code in sorted(snap["countries"]):
    c = snap["countries"][code]
    for org in c.get("orgs_90", []):
        rows.append([
            code, COUNTRY_NAMES.get(code, code),
            org.get("ref", ""), org.get("name", ""),
            round(org.get("usd", 0), 2),
        ])
write_csv("funder-disbursements-90d.csv", rows, [
    "country_code", "country_name", "funder_ref", "funder_name", "disbursements_90d_usd",
])

# 3. Data currency
rows = []
for code in sorted(snap["countries"]):
    c = snap["countries"][code]
    for entry in c.get("currency", []):
        rows.append([
            code, COUNTRY_NAMES.get(code, code),
            entry.get("ref", ""), entry.get("name", ""),
            entry.get("latest", ""),
            entry.get("age_days", ""),
            round(entry.get("lifetime_usd", 0), 2),
        ])
write_csv("data-currency.csv", rows, [
    "country_code", "country_name", "funder_ref", "funder_name",
    "latest_transaction_date", "age_days", "lifetime_usd",
])

# 4. Sectors (90-day)
rows = []
for code in sorted(snap["countries"]):
    c = snap["countries"][code]
    for s in c.get("sectors_90", []):
        rows.append([
            code, COUNTRY_NAMES.get(code, code),
            s.get("code", ""), s.get("name", ""),
            round(s.get("usd", 0), 2),
            round(s.get("pct", 0), 2),
        ])
write_csv("sectors-90d.csv", rows, [
    "country_code", "country_name", "sector_code", "sector_name",
    "disbursements_90d_usd", "percentage",
])

# 5. DFAT pipeline
rows = []
dfat = snap.get("dfat", {})
for item in dfat.get("items", []):
    rows.append([
        item.get("id", ""),
        item.get("title", ""),
        item.get("section", ""),
        item.get("status", ""),
    ])
dfat_as_at = dfat.get("as_at", "")
write_csv("dfat-pipeline.csv", rows, ["id", "title", "section", "status"])

# 6. NZ GETS tenders
rows = []
nz = snap.get("nz", {})
for t in nz.get("tenders", []):
    rows.append([
        t.get("ref", ""),
        t.get("title", ""),
        t.get("type", ""),
        t.get("org", ""),
        t.get("status", ""),
        t.get("opened", ""),
        t.get("closes", "") if t.get("closes") else t.get("date_label", ""),
        t.get("coverage", ""),
    ])
write_csv("nz-tenders.csv", rows, [
    "reference", "title", "type", "organisation", "status",
    "opened", "closes", "coverage",
])

# 7. Activities (from the compressed index)
idx_file = snap_file.replace(".json", ".index.json.gz")
idx_path = os.path.join(HERE, "data", idx_file)
activity_count = 0
if os.path.exists(idx_path):
    with gzip.open(idx_path, "rt") as f:
        idx = json.load(f)
    rows = []
    for code in sorted(idx):
        cols = idx[code]["cols"]
        name = COUNTRY_NAMES.get(code, code)
        for row in idx[code]["rows"]:
            r = dict(zip(cols, row))
            rows.append([
                code, name,
                r.get("aid", ""),
                r.get("org", ""),
                r.get("title", ""),
                STATUS_LABELS.get(r.get("st"), str(r.get("st", ""))),
                r.get("start", ""),
                r.get("end", ""),
                round(r.get("spend", 0), 2) if r.get("spend") else "",
                round(r.get("pct", 0), 2) if r.get("pct") else "",
                "yes" if r.get("stale") else "no",
            ])
    activity_count = write_csv("activities.csv", rows, [
        "country_code", "country_name", "activity_id", "organisation", "title",
        "status", "start_date", "end_date", "lifetime_spend_usd",
        "declared_country_share_pct", "stale",
    ])

# 8. World Bank projects
rows = []
for code in sorted(snap["countries"]):
    c = snap["countries"][code]
    name = COUNTRY_NAMES.get(code, code)
    for proj in c.get("wb_recent", []) + c.get("wb_pipeline", []):
        rows.append([
            code, name,
            proj.get("id", ""),
            proj.get("name", ""),
            round(proj.get("amount", 0), 2) if proj.get("amount") else "",
        ])
write_csv("world-bank-projects.csv", rows, [
    "country_code", "country_name", "project_id", "project_name", "amount_usd",
])

# 9. New starts
rows = []
for code in sorted(snap["countries"]):
    c = snap["countries"][code]
    name = COUNTRY_NAMES.get(code, code)
    for ns in c.get("new_starts_all", c.get("new_starts", [])):
        rows.append([
            code, name,
            ns.get("aid", ""),
            ns.get("org", ""),
            ns.get("title", ""),
            ns.get("start", ""),
            ns.get("end", ""),
            round(ns.get("spend", 0), 2) if ns.get("spend") else "",
        ])
write_csv("new-starts.csv", rows, [
    "country_code", "country_name", "activity_id", "organisation",
    "title", "start_date", "end_date", "spend_usd",
])

# 10. Ending soon
rows = []
for code in sorted(snap["countries"]):
    c = snap["countries"][code]
    name = COUNTRY_NAMES.get(code, code)
    for es in c.get("ending_all", c.get("ending_soon", [])):
        rows.append([
            code, name,
            es.get("aid", ""),
            es.get("org", ""),
            es.get("title", ""),
            es.get("start", ""),
            es.get("end", ""),
            round(es.get("spend", 0), 2) if es.get("spend") else "",
        ])
write_csv("ending-soon.csv", rows, [
    "country_code", "country_name", "activity_id", "organisation",
    "title", "start_date", "end_date", "spend_usd",
])


def fmt_size(b):
    if b >= 1_000_000:
        return f"{b / 1_000_000:.1f} MB"
    if b >= 1_000:
        return f"{b / 1_000:.0f} KB"
    return f"{b} B"


def usd(v):
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.0f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


total_90 = sum(c.get("dis90", 0) for c in snap["countries"].values())
n_countries = len(snap["countries"])
n_funders_total = len(set(
    e["name"] for c in snap["countries"].values() for e in c.get("currency", [])
))

# Build file cards
file_cards = ""
file_descriptions = {
    "country-summary.csv": (
        "Country summary",
        "One row per country: 90-day and 365-day disbursements, funder counts, activity counts, stale and ending activities, World Bank projects.",
    ),
    "funder-disbursements-90d.csv": (
        "Funder disbursements (90-day)",
        "Each funder's disbursement to each country in the last 90 days. Only funders with non-zero 90-day disbursements are included.",
    ),
    "data-currency.csv": (
        "Data currency",
        "How old each funder's data is per country: latest transaction date, age in days, and lifetime spend. Use this to assess which funders' data is current and which is stale.",
    ),
    "sectors-90d.csv": (
        "Sectors (90-day)",
        "90-day disbursements broken down by IATI sector code per country.",
    ),
    "activities.csv": (
        "All activities",
        "Every IATI activity in the 14 countries after recipient-country weighting: identifier, organisation, title, status, dates, spend, and declared country share. This is the largest file.",
    ),
    "dfat-pipeline.csv": (
        "DFAT procurement pipeline",
        f"Australian DFAT business notifications and procurement items as at {esc(dfat_as_at) if dfat_as_at else 'latest read'}.",
    ),
    "nz-tenders.csv": (
        "NZ GETS tenders",
        "New Zealand Government Electronic Tenders Service: Pacific-related tenders with status, dates, and coverage.",
    ),
    "world-bank-projects.csv": (
        "World Bank projects",
        "World Bank projects per country from the Projects API: recent approvals and pipeline.",
    ),
    "new-starts.csv": (
        "New starts",
        "Activities that started within the last 90 days, per country.",
    ),
    "ending-soon.csv": (
        "Ending soon",
        "Activities whose end date is within the next 90 days, per country.",
    ),
}

for fname, n_rows, size, headers in files_generated:
    title, desc = file_descriptions.get(fname, (fname, ""))
    file_cards += f"""<div class="dl-card">
<div class="dl-header">
  <strong>{esc(title)}</strong>
  <span class="dl-meta">{n_rows:,} rows &middot; {fmt_size(size)}</span>
</div>
<p class="dl-desc">{desc}</p>
<div class="dl-cols">Columns: <code>{', '.join(headers)}</code></div>
<a href="data/{esc(fname)}" download class="dl-btn">Download CSV</a>
</div>\n"""

extra = """
.container{max-width:820px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:1rem;line-height:1.65}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:2rem}
.key-stat{display:inline-block;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.6rem 1rem;margin:.3rem .4rem .3rem 0;font-size:.9rem}
.key-stat b{font-size:1.1rem;display:block;margin-bottom:.15rem}
.dl-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:1rem 1.2rem;margin:.8rem 0}
.dl-header{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.3rem}
.dl-meta{font-size:.8rem;color:var(--text-muted);white-space:nowrap}
.dl-desc{font-size:.88rem;color:var(--text-secondary);margin:.4rem 0 .5rem;line-height:1.5}
.dl-cols{font-size:.78rem;color:var(--text-muted);margin-bottom:.6rem;line-height:1.4}
.dl-cols code{font-size:.75rem;background:var(--surface-bg);padding:.1rem .3rem;border-radius:3px}
.dl-btn{display:inline-block;background:var(--series-1);color:#fff;padding:.4rem 1rem;border-radius:5px;text-decoration:none;font-size:.85rem;font-weight:600;transition:opacity .15s}
.dl-btn:hover{opacity:.85}
.note{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;font-size:.88rem;line-height:1.6;margin:1.2rem 0}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .intro{font-size:.95rem}
  .dl-header{flex-direction:column}
}
"""

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Download data &mdash; Pacific Aid Signal &mdash; Asa</title>
<meta name="description" content="Download Pacific aid data as CSV: disbursements, funders, sectors, activities, DFAT pipeline, and NZ tenders for 14 Pacific island countries.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a></p>
<header>
<h1>Download data</h1>
<p class="intro">The Pacific Aid Signal reads five sources every twelve hours and publishes what it finds. Everything behind the country pages is available here as CSV files you can open in a spreadsheet or load into your own analysis. The data is from the issue of {esc(issue_date)}.</p>
</header>

<div class="key-stat"><b>{n_countries}</b> countries</div>
<div class="key-stat"><b>{n_funders_total}</b> funders tracked</div>
<div class="key-stat"><b>{usd(total_90)}</b> disbursed (90-day)</div>
<div class="key-stat"><b>{activity_count:,}</b> activities</div>

<h2>Available datasets</h2>

{file_cards}

<div class="note">
<strong>About this data.</strong> All figures are derived from IATI, the World Bank Projects API, DFAT business notifications, and New Zealand GETS. Disbursement amounts are weighted by declared recipient-country share &mdash; about 71% of transactions tagged to these countries are explicitly for somewhere else and are excluded. Amounts are in US dollars as published by the funder. &ldquo;Stale&rdquo; means an activity in implementation status whose end date is more than 365 days past. For full details on how the data is collected, weighted, and processed, see the <a href="methodology.html">methodology page</a>.
</div>

<h2>Explore the data online</h2>
<p>You can also <a href="explorer.html">explore all {activity_count:,} activities interactively</a> &mdash; filter by country, funder, status, and keyword, and sort by any column, without downloading anything.</p>

<h2>The raw snapshot</h2>
<p>The CSV files above are extracted from the JSON snapshot that the pipeline produces each issue. The full snapshot and compressed activity index are also available in the <a href="{REPO}/tree/main/signal/data">repository</a>.</p>

<h2>Licence and use</h2>
<p>This data is derived from public sources (IATI, World Bank, DFAT, GETS) and is provided as-is with no warranty. You are free to use it for any purpose. If you cite it, a link to <a href="https://pacificaidsignal.org">pacificaidsignal.org</a> is appreciated. The source code and pipeline are open at <a href="{REPO}">{REPO.split('/')[-1]}</a>.</p>

<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
<br>Data as at issue {esc(issue_date)}.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="methodology.html">Methodology</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="search.html">Search</a> &middot;
<a href="feed.xml">RSS feed</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "download.html")
with open(out, "w") as fh:
    fh.write(html)

total_csv_size = sum(s for _, _, s, _ in files_generated)
print(f"rendered download.html {len(html) // 1024} KB")
print(f"generated {len(files_generated)} CSV files, {total_csv_size // 1024} KB total:")
for fname, n_rows, size, _ in files_generated:
    print(f"  {fname}: {n_rows:,} rows, {fmt_size(size)}")
