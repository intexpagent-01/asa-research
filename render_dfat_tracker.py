#!/usr/bin/env python3
"""Render site/dfat-tracker.html: DFAT procurement pipeline tracker with progression history."""
import os, re, json, glob
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

files = sorted(glob.glob(os.path.join(HERE, "data", "pacific-*.json")))
files = [f for f in files if "index" not in f]

PACIFIC_COUNTRIES = [
    "Papua New Guinea", "PNG", "Fiji", "Solomon Islands", "Vanuatu",
    "Samoa", "Tonga", "Kiribati", "Tuvalu", "Micronesia", "Marshall Islands",
    "Palau", "Nauru", "Niue", "Cook Islands", "Pacific", "Timor-Leste",
]
PACIFIC_RE = re.compile(r'\b(' + '|'.join(re.escape(c) for c in PACIFIC_COUNTRIES) + r')\b', re.IGNORECASE)

SECTION_ORDER = ["In the market", "Planned", "In collaboration", "Closed"]
SECTION_COLORS = {
    "In the market": "#e05a3a",
    "Planned": "#e9c46a",
    "In collaboration": "#2a9d8f",
    "Closed": "#264653",
}


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def is_pacific(item):
    text = item.get("title", "") + " " + item.get("status", "")
    return bool(PACIFIC_RE.search(text))


def pacific_countries_in(item):
    text = item.get("title", "") + " " + item.get("status", "")
    return list(set(PACIFIC_RE.findall(text)))


# --- Load all snapshots for history tracking ---

all_issues = []
for f in files:
    with open(f) as fh:
        d = json.load(fh)
    date = d.get("date", os.path.basename(f)[8:18])
    dfat = d.get("dfat", {})
    all_issues.append({
        "date": date,
        "num": len(all_issues) + 1,
        "as_at": dfat.get("as_at", ""),
        "items": {item["id"]: item for item in dfat.get("items", [])},
        "notices": dfat.get("notices", []),
    })

n_issues = len(all_issues)
curr = all_issues[-1]
prev = all_issues[-2] if n_issues >= 2 else curr

# --- Track each item across all issues ---

all_item_ids = set()
for iss in all_issues:
    all_item_ids.update(iss["items"].keys())

item_history = {}
for iid in sorted(all_item_ids):
    history = []
    first_seen = None
    last_seen = None
    for iss in all_issues:
        if iid in iss["items"]:
            item = iss["items"][iid]
            history.append({
                "date": iss["date"],
                "num": iss["num"],
                "section": item["section"],
                "status": item.get("status", ""),
            })
            if first_seen is None:
                first_seen = iss["date"]
            last_seen = iss["date"]
        else:
            history.append({"date": iss["date"], "num": iss["num"], "section": None, "status": ""})

    current_item = curr["items"].get(iid) or prev["items"].get(iid)
    if not current_item:
        for iss in reversed(all_issues):
            if iid in iss["items"]:
                current_item = iss["items"][iid]
                break

    item_history[iid] = {
        "id": iid,
        "title": current_item["title"] if current_item else iid,
        "current_section": curr["items"][iid]["section"] if iid in curr["items"] else "(removed)",
        "current_status": curr["items"][iid].get("status", "") if iid in curr["items"] else "",
        "history": history,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "is_pacific": is_pacific(current_item) if current_item else False,
        "pacific_countries": pacific_countries_in(current_item) if current_item else [],
        "active": iid in curr["items"],
    }

# --- Detect changes this issue ---

changes = []
new_items = set(curr["items"].keys()) - set(prev["items"].keys())
gone_items = set(prev["items"].keys()) - set(curr["items"].keys())
for iid in new_items:
    changes.append({"id": iid, "type": "new", "detail": f"New item appeared: {curr['items'][iid]['section']}"})
for iid in gone_items:
    changes.append({"id": iid, "type": "removed", "detail": f"Removed from pipeline (was: {prev['items'][iid]['section']})"})
for iid in set(curr["items"].keys()) & set(prev["items"].keys()):
    ci = curr["items"][iid]
    pi = prev["items"][iid]
    if ci["section"] != pi["section"]:
        changes.append({"id": iid, "type": "moved", "detail": f"{pi['section']} → {ci['section']}"})
    elif ci.get("status", "") != pi.get("status", ""):
        changes.append({"id": iid, "type": "updated", "detail": "Status text updated"})

# --- Notices (most recent first, Pacific highlighted) ---

notices = curr.get("notices", [])
notices_with_dates = [n for n in notices if n.get("date")]
notices_with_dates.sort(key=lambda n: n["date"], reverse=True)

# --- Section counts ---

section_counts = defaultdict(int)
pacific_by_section = defaultdict(int)
for iid, item in curr["items"].items():
    sec = item["section"]
    section_counts[sec] += 1
    if item_history[iid]["is_pacific"]:
        pacific_by_section[sec] += 1

n_pacific = sum(1 for ih in item_history.values() if ih["is_pacific"] and ih["active"])
n_total = len(curr["items"])

# --- Build HTML ---

# Changes section
changes_html = ""
if changes:
    for ch in changes:
        iid = ch["id"]
        ih = item_history.get(iid, {})
        title = ih.get("title", iid)
        pac_badge = '<span class="pac-badge">Pacific</span>' if ih.get("is_pacific") else ""
        type_cls = {"new": "change-new", "removed": "change-removed", "moved": "change-moved", "updated": "change-updated"}.get(ch["type"], "")
        changes_html += f'''<div class="change-row {type_cls}">
<div class="change-id">{esc(iid)}</div>
<div class="change-body"><strong>{esc(title)}</strong> {pac_badge}<br><span class="change-detail">{esc(ch["detail"])}</span></div>
</div>\n'''
else:
    changes_html = '<p style="color:var(--text-muted);font-size:.9rem">No changes in this issue.</p>'

# Pipeline items grouped by section
pipeline_html = ""
for sec in SECTION_ORDER:
    items_in_sec = [(iid, item) for iid, item in sorted(curr["items"].items()) if item["section"] == sec]
    if not items_in_sec:
        continue
    color = SECTION_COLORS.get(sec, "#666")
    pipeline_html += f'<h3 style="margin-top:1.5rem"><span class="section-dot" style="background:{color}"></span> {esc(sec)} ({len(items_in_sec)})</h3>\n'
    for iid, item in items_in_sec:
        ih = item_history[iid]
        pac_badge = '<span class="pac-badge">Pacific</span>' if ih["is_pacific"] else ""
        countries = ", ".join(ih["pacific_countries"]) if ih["pacific_countries"] else ""
        countries_note = f'<span class="country-note">{esc(countries)}</span>' if countries else ""

        # History dots
        dots = ""
        for h in ih["history"]:
            if h["section"] is None:
                dots += '<span class="hist-dot absent" title="Not in pipeline"></span>'
            else:
                hcolor = SECTION_COLORS.get(h["section"], "#666")
                dots += f'<span class="hist-dot" style="background:{hcolor}" title="Issue #{h["num"]} ({h["date"]}): {esc(h["section"])}"></span>'

        pipeline_html += f'''<div class="item-card{'  pacific' if ih['is_pacific'] else ''}">
<div class="item-head">
<span class="item-id">{esc(iid)}</span>
<span class="item-title">{esc(item["title"])}</span>
{pac_badge} {countries_note}
</div>
<div class="item-status">{esc(item.get("status", ""))}</div>
<div class="item-history"><span class="hist-label">History:</span> {dots}</div>
</div>\n'''

# History progression chart — all items across all issues
prog_svg_w, prog_svg_h = 750, max(120, len(item_history) * 18 + 60)
prog_rows = ""
row_y = 40
sorted_items = sorted(item_history.values(), key=lambda x: (
    SECTION_ORDER.index(x["current_section"]) if x["current_section"] in SECTION_ORDER else 99,
    x["id"]
))

for ih in sorted_items:
    if not ih["active"] and ih["last_seen"] < all_issues[-3]["date"] if n_issues >= 3 else True:
        continue  # skip items that disappeared long ago

    label = ih["id"]
    pac = " ★" if ih["is_pacific"] else ""
    prog_rows += f'<text x="58" y="{row_y + 4}" text-anchor="end" font-size="9" fill="var(--text-muted)">{esc(label)}{esc(pac)}</text>\n'

    for i, h in enumerate(ih["history"]):
        x = 65 + i * (650 / max(1, n_issues - 1)) if n_issues > 1 else 65
        if h["section"] is None:
            prog_rows += f'<circle cx="{x:.0f}" cy="{row_y}" r="3" fill="var(--border)" opacity=".4"/>\n'
        else:
            color = SECTION_COLORS.get(h["section"], "#666")
            prog_rows += f'<circle cx="{x:.0f}" cy="{row_y}" r="5" fill="{color}"/>\n'
    row_y += 18

prog_svg_h = row_y + 30

# Issue labels at bottom
issue_labels = ""
for i, iss in enumerate(all_issues):
    x = 65 + i * (650 / max(1, n_issues - 1)) if n_issues > 1 else 65
    issue_labels += f'<text x="{x:.0f}" y="25" text-anchor="middle" font-size="9" fill="var(--text-muted)">{iss["date"][5:]}</text>\n'

prog_svg = f"""<svg viewBox="0 0 {prog_svg_w} {prog_svg_h}" style="width:100%;max-width:{prog_svg_w}px" xmlns="http://www.w3.org/2000/svg">
{issue_labels}
{prog_rows}
</svg>"""

# Notices table (most recent 30)
notices_html = ""
for n in notices_with_dates[:30]:
    title = n.get("title", "")
    date = n.get("date", "")
    summary = n.get("summary", "")[:150]
    url = n.get("url", "")
    is_pac = bool(PACIFIC_RE.search(title + " " + summary))
    pac_cls = ' class="pac-notice"' if is_pac else ""
    link = f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(title[:80])}</a>' if url else esc(title[:80])
    notices_html += f'<tr{pac_cls}><td>{esc(date)}</td><td>{link}</td><td>{esc(summary)}</td></tr>\n'

# As-at history
as_at_changes = []
prev_as_at = None
for iss in all_issues:
    if iss["as_at"] != prev_as_at:
        as_at_changes.append({"date": iss["date"], "num": iss["num"], "as_at": iss["as_at"]})
        prev_as_at = iss["as_at"]

as_at_html = ""
for ac in as_at_changes:
    as_at_html += f'<div class="as-at-row"><span class="as-at-date">Issue #{ac["num"]} ({ac["date"]})</span> → pipeline "as at {esc(ac["as_at"])}"</div>\n'

# --- CSS ---

extra = """
.container{max-width:900px}
h1{font-size:1.5rem;margin-bottom:.3rem}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem}
h3{font-size:1rem;margin:1.5rem 0 .5rem}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1rem;line-height:1.65;margin-bottom:1.5rem}
.status-row{display:flex;gap:.7rem;margin:1.2rem 0;flex-wrap:wrap}
.status-pill{display:flex;align-items:center;gap:.4rem;padding:.5rem 1rem;border-radius:8px;background:var(--surface-card);border:1px solid var(--border);font-size:.9rem}
.status-pill .pill-n{font-size:1.3rem;font-weight:800}
.status-pill .pill-label{font-size:.78rem;color:var(--text-muted)}
.section-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:.3rem;vertical-align:middle}
.change-row{display:flex;gap:.6rem;padding:.6rem .8rem;margin:.4rem 0;border-radius:8px;background:var(--surface-card);border:1px solid var(--border)}
.change-new{border-left:3px solid #059669}
.change-removed{border-left:3px solid #e05a3a}
.change-moved{border-left:3px solid #2563eb}
.change-updated{border-left:3px solid #e9c46a}
.change-id{font-size:.82rem;font-weight:700;color:var(--text-muted);min-width:80px;padding-top:2px}
.change-body{flex:1;font-size:.9rem}
.change-detail{font-size:.82rem;color:var(--text-muted)}
.pac-badge{font-size:.68rem;padding:.12rem .4rem;border-radius:3px;background:rgba(13,115,119,.12);color:#0d7377;font-weight:600;vertical-align:middle;margin-left:.3rem}
.country-note{font-size:.78rem;color:var(--text-muted);margin-left:.3rem}
.item-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin:.5rem 0;transition:box-shadow .15s}
.item-card:hover{box-shadow:0 2px 10px rgba(0,0,0,.06)}
.item-card.pacific{border-left:3px solid #0d7377}
.item-head{margin-bottom:.3rem}
.item-id{font-size:.78rem;font-weight:700;color:var(--text-muted);margin-right:.4rem}
.item-title{font-size:.92rem;font-weight:600}
.item-status{font-size:.85rem;color:var(--text-muted);line-height:1.5;margin:.3rem 0}
.item-history{font-size:.78rem;color:var(--text-muted);margin-top:.4rem;display:flex;align-items:center;gap:3px}
.hist-label{margin-right:.3rem}
.hist-dot{display:inline-block;width:10px;height:10px;border-radius:50%;cursor:help}
.hist-dot.absent{background:var(--border);opacity:.4}
.chart-wrap{margin:1.2rem 0;overflow-x:auto;-webkit-overflow-scrolling:touch}
.as-at-row{font-size:.85rem;padding:.3rem 0;color:var(--text-muted)}
.as-at-date{font-weight:600;color:var(--text-primary)}
.notice-table{width:100%;border-collapse:collapse;font-size:.82rem;margin:.8rem 0}
.notice-table th{text-align:left;font-size:.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;padding:.4rem .5rem;border-bottom:2px solid var(--border)}
.notice-table td{padding:.4rem .5rem;border-bottom:1px solid var(--border);vertical-align:top}
.notice-table tr:hover td{background:rgba(13,115,119,.03)}
tr.pac-notice td{background:rgba(13,115,119,.04)}
.legend{display:flex;gap:1rem;flex-wrap:wrap;margin:.5rem 0;font-size:.82rem}
.legend-item{display:flex;align-items:center;gap:.3rem}
.legend-dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.filter-input{width:100%;padding:.5rem .8rem;border:1px solid var(--border);border-radius:6px;font-size:.88rem;background:var(--surface-card);color:var(--text);margin-bottom:.8rem}
.filter-input:focus{outline:none;border-color:var(--series-1)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media(max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .status-row{gap:.4rem}
  .status-pill{padding:.4rem .7rem}
  .status-pill .pill-n{font-size:1.1rem}
  .item-card{padding:.6rem .8rem}
  .change-row{flex-direction:column;gap:.2rem}
  .change-id{min-width:auto}
  .notice-table{font-size:.75rem}
  footer{font-size:.75rem}
}
"""

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DFAT Pipeline Tracker &mdash; Pacific Aid Signal &mdash; Asa</title>
<meta name="description" content="Track {n_total} DFAT procurement items across {n_issues} issues. {n_pacific} Pacific-relevant. See what moved, what&rsquo;s new, and the full history.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="signal.html">&larr; Signal</a> &middot; <a href="pipeline.html">Pipeline &amp; outlook</a> &middot; <a href="dashboard.html">Dashboard</a></p>

<header>
<h1>DFAT Pipeline Tracker</h1>
<p class="intro">Tracking {n_total} DFAT procurement items across {n_issues} issues of the Pacific Aid Signal. The pipeline was last updated <strong>&ldquo;as at {esc(curr['as_at'])}&rdquo;</strong>. {n_pacific} items name a Pacific country. This page shows what moved since the previous issue and the full progression history.</p>
</header>

<div class="status-row">
{''.join(f'<div class="status-pill"><span class="section-dot" style="background:{SECTION_COLORS.get(sec, "#666")}"></span><span class="pill-n">{section_counts.get(sec, 0)}</span><span class="pill-label">{esc(sec)}</span></div>' for sec in SECTION_ORDER)}
</div>

<div class="legend">
{''.join(f'<span class="legend-item"><span class="legend-dot" style="background:{SECTION_COLORS[sec]}"></span>{esc(sec)}</span>' for sec in SECTION_ORDER)}
<span class="legend-item"><span class="legend-dot" style="background:var(--border);opacity:.4"></span>Not in pipeline</span>
</div>

<h2>What changed this issue</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Pipeline updated from &ldquo;as at {esc(prev['as_at'])}&rdquo; to &ldquo;as at {esc(curr['as_at'])}&rdquo;. {len(changes)} {'change' if len(changes) == 1 else 'changes'} detected.</p>
{changes_html}

<h2>Pipeline update history</h2>
<p style="font-size:.88rem;color:var(--text-muted)">When DFAT updated the pipeline &ldquo;as at&rdquo; date across {n_issues} issues.</p>
{as_at_html}

<h2>Progression chart</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Each dot is one issue. Color shows the item&rsquo;s section at that point. ★ = Pacific-relevant. Grey = not yet in the pipeline.</p>
<div class="chart-wrap">
{prog_svg}
</div>

<h2>All pipeline items</h2>
{pipeline_html}

<h2>Recent business notifications</h2>
<p style="font-size:.88rem;color:var(--text-muted)">The 30 most recent DFAT business notifications by date. Pacific-relevant rows are highlighted. {len(notices)} total notifications tracked.</p>
<input type="text" class="filter-input" id="noticeFilter" placeholder="Filter notices..." oninput="filterNotices()">
<div style="overflow-x:auto">
<table class="notice-table" id="noticeTable">
<thead><tr><th>Date</th><th>Title</th><th>Summary</th></tr></thead>
<tbody>
{notices_html}
</tbody>
</table>
</div>

<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
<br>DFAT pipeline data from <a href="https://www.dfat.gov.au/about-us/business-opportunities/business-notifications" target="_blank" rel="noopener">DFAT Business Notifications</a>.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="pipeline.html">Pipeline</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="feed.xml">RSS feed</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div>
<script>
function filterNotices(){{
  var q = document.getElementById('noticeFilter').value.toLowerCase();
  var rows = document.querySelectorAll('#noticeTable tbody tr');
  rows.forEach(function(r){{
    r.style.display = r.textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
  }});
}}
</script>
</body></html>"""

out = os.path.join(SITE, "dfat-tracker.html")
with open(out, "w") as fh:
    fh.write(html)
print(f"rendered dfat-tracker.html {len(html)//1024} KB, {n_total} items, {n_pacific} Pacific, {len(changes)} changes, {len(notices)} notices")
