#!/usr/bin/env python3
"""Render site/explorer.html: interactive filterable data explorer for all activities."""
import os, re, json, gzip

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap_file = sorted(f for f in os.listdir(os.path.join(HERE, "data"))
                   if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)[-1]
with open(os.path.join(HERE, "data", snap_file)) as fh:
    snap = json.load(fh)

idx_file = snap_file.replace(".json", ".index.json.gz")
idx_path = os.path.join(HERE, "data", idx_file)
with gzip.open(idx_path, "rt") as f:
    idx = json.load(f)

issue_date = snap.get("date", snap.get("generated", "")[:10])

COUNTRY_NAMES = {
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

STATUS_LABELS = {1: "Pipeline", 2: "Implementation", 3: "Finalisation", 4: "Closed"}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

# Build compact data: [country_code, org, title, status, start, end, spend, stale]
all_rows = []
all_orgs = set()
for cc in sorted(idx):
    cols = idx[cc]["cols"]
    for row in idx[cc]["rows"]:
        r = dict(zip(cols, row))
        org = r.get("org", "")
        all_orgs.add(org)
        all_rows.append([
            cc,
            org,
            r.get("title", ""),
            r.get("st", 0),
            r.get("start", ""),
            r.get("end", ""),
            round(r.get("spend", 0)) if r.get("spend") else 0,
            1 if r.get("stale") else 0,
        ])

# Sort orgs for the dropdown, put most common first
from collections import Counter
org_counts = Counter(r[1] for r in all_rows)
sorted_orgs = [o for o, _ in org_counts.most_common()]

# Country options sorted by activity count
country_counts = Counter(r[0] for r in all_rows)
sorted_countries = [c for c, _ in country_counts.most_common()]

data_json = json.dumps(all_rows, separators=(",", ":"))
countries_json = json.dumps({cc: COUNTRY_NAMES.get(cc, cc) for cc in sorted(COUNTRY_NAMES)}, separators=(",", ":"))
orgs_json = json.dumps(sorted_orgs, separators=(",", ":"))

total_spend = sum(r[6] for r in all_rows)
n_impl = sum(1 for r in all_rows if r[3] == 2)
n_stale = sum(1 for r in all_rows if r[7])

extra_css = """
.container{max-width:1100px}
h2{font-size:1.15rem;margin:2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:1rem;line-height:1.65}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:1.5rem}
.filters{display:flex;flex-wrap:wrap;gap:.6rem;margin-bottom:1rem;align-items:end}
.filter-group{display:flex;flex-direction:column;gap:.2rem}
.filter-group label{font-size:.75rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em}
.filter-group select,.filter-group input{padding:.45rem .6rem;border:1px solid var(--border);border-radius:5px;background:var(--surface-card);color:var(--text);font-size:.85rem;min-width:140px}
.filter-group input[type=text]{min-width:200px}
.filter-actions{display:flex;align-items:end;gap:.4rem}
.btn-clear{padding:.45rem .8rem;border:1px solid var(--border);border-radius:5px;background:var(--surface-bg);color:var(--text-secondary);font-size:.82rem;cursor:pointer;font-weight:500}
.btn-clear:hover{background:var(--surface-card)}
.stats-bar{display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;margin-bottom:1rem;font-size:.88rem;color:var(--text-secondary)}
.stats-bar b{color:var(--text)}
.data-table{width:100%;border-collapse:collapse;font-size:.82rem;table-layout:fixed}
.data-table th{position:sticky;top:0;background:var(--surface-card);border-bottom:2px solid var(--border);padding:.5rem .4rem;text-align:left;font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.03em;color:var(--text-muted);cursor:pointer;user-select:none;white-space:nowrap}
.data-table th:hover{color:var(--text)}
.data-table th .sort-icon{font-size:.65rem;margin-left:.2rem;opacity:.4}
.data-table th.sorted .sort-icon{opacity:1;color:var(--series-1)}
.data-table td{padding:.4rem;border-bottom:1px solid var(--gridline);vertical-align:top}
.data-table tr:hover td{background:var(--surface-card)}
.col-country{width:55px}
.col-org{width:160px}
.col-title{width:auto}
.col-status{width:85px}
.col-start{width:80px}
.col-end{width:80px}
.col-spend{width:80px;text-align:right}
.data-table td.col-spend{text-align:right;font-variant-numeric:tabular-nums}
.data-table td.cell-stale{color:var(--series-4)}
.cell-truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:0}
.pagination{display:flex;align-items:center;justify-content:center;gap:.5rem;margin:1.2rem 0;font-size:.85rem}
.pagination button{padding:.35rem .7rem;border:1px solid var(--border);border-radius:4px;background:var(--surface-card);color:var(--text);cursor:pointer;font-size:.82rem}
.pagination button:hover{background:var(--surface-bg)}
.pagination button:disabled{opacity:.4;cursor:default}
.pagination button:disabled:hover{background:var(--surface-card)}
.pagination .page-info{color:var(--text-muted)}
.status-badge{display:inline-block;padding:.1rem .4rem;border-radius:3px;font-size:.72rem;font-weight:600;letter-spacing:.02em}
.status-pipeline{background:#e3f2fd;color:#1565c0}
.status-implementation{background:#e8f5e9;color:#2e7d32}
.status-finalisation{background:#fff3e0;color:#e65100}
.status-stale{background:#ffebee;color:#c62828}
.table-wrap{overflow-x:auto;margin-bottom:.5rem;border:1px solid var(--border);border-radius:8px}
.no-results{text-align:center;padding:2rem;color:var(--text-muted);font-size:.95rem}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media(prefers-color-scheme:dark){
  .status-pipeline{background:#1a3a5c;color:#90caf9}
  .status-implementation{background:#1b3a1b;color:#81c784}
  .status-finalisation{background:#3e2723;color:#ffb74d}
  .status-stale{background:#3e1a1a;color:#ef9a9a}
}
@media(max-width:700px){
  .container{padding:1.5rem .6rem 2.5rem}
  .filters{flex-direction:column}
  .filter-group select,.filter-group input{min-width:100%;width:100%}
  .col-start,.col-end{display:none}
  .col-org{width:100px}
  .col-spend{width:65px}
}
"""

country_options = "".join(
    f'<option value="{esc(cc)}">{esc(COUNTRY_NAMES[cc])}</option>'
    for cc in sorted(COUNTRY_NAMES, key=lambda c: COUNTRY_NAMES[c])
)

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data explorer &mdash; Pacific Aid Signal &mdash; Asa</title>
<meta name="description" content="Explore {len(all_rows):,} aid activities across 14 Pacific island countries: filter by country, funder, status, and keyword.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra_css}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a></p>
<header>
<h1>Data explorer</h1>
<p class="intro">Filter, sort, and search {len(all_rows):,} aid activities across 14 Pacific island countries. Every row comes from IATI data after recipient-country weighting. Data from the issue of {esc(issue_date)}.</p>
</header>

<div class="filters" id="filters">
  <div class="filter-group">
    <label for="f-country">Country</label>
    <select id="f-country"><option value="">All countries</option>{country_options}</select>
  </div>
  <div class="filter-group">
    <label for="f-org">Funder</label>
    <select id="f-org"><option value="">All funders</option></select>
  </div>
  <div class="filter-group">
    <label for="f-status">Status</label>
    <select id="f-status">
      <option value="">All</option>
      <option value="2">Implementation</option>
      <option value="3">Finalisation</option>
      <option value="1">Pipeline</option>
    </select>
  </div>
  <div class="filter-group">
    <label for="f-stale">Data quality</label>
    <select id="f-stale">
      <option value="">All</option>
      <option value="0">Current only</option>
      <option value="1">Stale only</option>
    </select>
  </div>
  <div class="filter-group">
    <label for="f-search">Search</label>
    <input type="text" id="f-search" placeholder="Title or funder…">
  </div>
  <div class="filter-actions">
    <button class="btn-clear" id="btn-clear">Clear filters</button>
  </div>
</div>

<div class="stats-bar" id="stats-bar"></div>

<div class="table-wrap">
<table class="data-table" id="data-table">
<thead><tr>
  <th class="col-country" data-col="0">Country<span class="sort-icon">▲</span></th>
  <th class="col-org cell-truncate" data-col="1">Funder<span class="sort-icon">▲</span></th>
  <th class="col-title cell-truncate" data-col="2">Title<span class="sort-icon">▲</span></th>
  <th class="col-status" data-col="3">Status<span class="sort-icon">▲</span></th>
  <th class="col-start" data-col="4">Start<span class="sort-icon">▲</span></th>
  <th class="col-end" data-col="5">End<span class="sort-icon">▲</span></th>
  <th class="col-spend" data-col="6">Spend (USD)<span class="sort-icon">▲</span></th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>
</div>
<div id="no-results" class="no-results" style="display:none">No activities match your filters.</div>

<div class="pagination" id="pagination"></div>

<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
<br>Data as at issue {esc(issue_date)}.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="download.html">Download data</a> &middot;
<a href="methodology.html">Methodology</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="search.html">Search</a> &middot;
<a href="feed.xml">RSS feed</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div>

<script>
(function() {{
var CN = {countries_json};
var SL = {json.dumps(STATUS_LABELS, separators=(",", ":"))};
var SLUGS = {json.dumps(SLUG, separators=(",", ":"))};
var D = {data_json};
var ORGS = {orgs_json};
var PAGE_SIZE = 50;
var filtered = D;
var sortCol = -1, sortAsc = true;
var page = 0;

var fCountry = document.getElementById("f-country");
var fOrg = document.getElementById("f-org");
var fStatus = document.getElementById("f-status");
var fStale = document.getElementById("f-stale");
var fSearch = document.getElementById("f-search");
var tbody = document.getElementById("tbody");
var statsBar = document.getElementById("stats-bar");
var pagination = document.getElementById("pagination");
var noResults = document.getElementById("no-results");
var table = document.getElementById("data-table");

// Populate funder dropdown
ORGS.forEach(function(o) {{
  var opt = document.createElement("option");
  opt.value = o;
  opt.textContent = o;
  fOrg.appendChild(opt);
}});

function escH(s) {{
  var d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}}

function fmtUSD(v) {{
  if (!v) return "$0";
  if (v >= 1e9) return "$" + (v/1e9).toFixed(1) + "B";
  if (v >= 1e6) return "$" + (v/1e6).toFixed(1) + "M";
  if (v >= 1e3) return "$" + (v/1e3).toFixed(0) + "K";
  return "$" + v.toLocaleString();
}}

function applyFilters() {{
  var cc = fCountry.value;
  var org = fOrg.value;
  var st = fStatus.value ? parseInt(fStatus.value) : 0;
  var stale = fStale.value;
  var q = fSearch.value.trim().toLowerCase();
  var words = q ? q.split(/\\s+/) : [];

  filtered = D.filter(function(r) {{
    if (cc && r[0] !== cc) return false;
    if (org && r[1] !== org) return false;
    if (st && r[3] !== st) return false;
    if (stale === "1" && !r[7]) return false;
    if (stale === "0" && r[7]) return false;
    if (words.length) {{
      var haystack = (r[1] + " " + r[2]).toLowerCase();
      for (var i = 0; i < words.length; i++) {{
        if (haystack.indexOf(words[i]) < 0) return false;
      }}
    }}
    return true;
  }});

  if (sortCol >= 0) doSort();
  page = 0;
  render();
}}

function doSort() {{
  filtered.sort(function(a, b) {{
    var va = a[sortCol], vb = b[sortCol];
    if (sortCol === 6) {{
      va = va || 0; vb = vb || 0;
      return sortAsc ? va - vb : vb - va;
    }}
    if (sortCol === 3) {{
      return sortAsc ? va - vb : vb - va;
    }}
    va = (va || "").toString().toLowerCase();
    vb = (vb || "").toString().toLowerCase();
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  }});
}}

function statusBadge(st, stale) {{
  if (stale) return '<span class="status-badge status-stale">Stale</span>';
  var cls = st === 1 ? "pipeline" : st === 2 ? "implementation" : st === 3 ? "finalisation" : "pipeline";
  return '<span class="status-badge status-' + cls + '">' + (SL[st] || "Unknown") + '</span>';
}}

function render() {{
  var total = filtered.length;
  var totalSpend = 0;
  var orgsSet = {{}};
  for (var i = 0; i < filtered.length; i++) {{
    totalSpend += filtered[i][6] || 0;
    orgsSet[filtered[i][1]] = true;
  }}
  var nOrgs = Object.keys(orgsSet).length;

  statsBar.innerHTML =
    "<span>Showing <b>" + total.toLocaleString() + "</b> activities</span>" +
    "<span><b>" + nOrgs + "</b> funders</span>" +
    "<span>Total spend: <b>" + fmtUSD(totalSpend) + "</b></span>";

  var pages = Math.ceil(total / PAGE_SIZE) || 1;
  if (page >= pages) page = pages - 1;
  var start = page * PAGE_SIZE;
  var end = Math.min(start + PAGE_SIZE, total);

  var html = "";
  for (var i = start; i < end; i++) {{
    var r = filtered[i];
    var slug = SLUGS[r[0]];
    var link = slug ? "pacific-signal-" + slug + ".html" : "#";
    html += "<tr>" +
      '<td class="col-country"><a href="' + link + '" title="' + escH(CN[r[0]] || r[0]) + '">' + escH(r[0]) + "</a></td>" +
      '<td class="col-org cell-truncate" title="' + escH(r[1]) + '">' + escH(r[1]) + "</td>" +
      '<td class="col-title cell-truncate" title="' + escH(r[2]) + '">' + escH(r[2]) + "</td>" +
      '<td class="col-status">' + statusBadge(r[3], r[7]) + "</td>" +
      '<td class="col-start">' + escH(r[4] || "—") + "</td>" +
      '<td class="col-end">' + escH(r[5] || "—") + "</td>" +
      '<td class="col-spend">' + (r[6] ? fmtUSD(r[6]) : "—") + "</td>" +
      "</tr>";
  }}
  tbody.innerHTML = html;

  noResults.style.display = total === 0 ? "block" : "none";
  table.style.display = total === 0 ? "none" : "";

  var pagHtml = "";
  pagHtml += '<button id="pg-first" ' + (page === 0 ? "disabled" : "") + '>&laquo;</button>';
  pagHtml += '<button id="pg-prev" ' + (page === 0 ? "disabled" : "") + '>&lsaquo; Prev</button>';
  pagHtml += '<span class="page-info">' + (start + 1) + "–" + end + " of " + total.toLocaleString() + "</span>";
  pagHtml += '<button id="pg-next" ' + (page >= pages - 1 ? "disabled" : "") + '>Next &rsaquo;</button>';
  pagHtml += '<button id="pg-last" ' + (page >= pages - 1 ? "disabled" : "") + '>&raquo;</button>';
  pagination.innerHTML = pagHtml;

  document.getElementById("pg-first").onclick = function() {{ page = 0; render(); }};
  document.getElementById("pg-prev").onclick = function() {{ if (page > 0) {{ page--; render(); }} }};
  document.getElementById("pg-next").onclick = function() {{ if (page < pages - 1) {{ page++; render(); }} }};
  document.getElementById("pg-last").onclick = function() {{ page = pages - 1; render(); }};

  updateURL();
}}

function updateURL() {{
  var params = [];
  if (fCountry.value) params.push("country=" + encodeURIComponent(fCountry.value));
  if (fOrg.value) params.push("org=" + encodeURIComponent(fOrg.value));
  if (fStatus.value) params.push("status=" + fStatus.value);
  if (fStale.value) params.push("stale=" + fStale.value);
  if (fSearch.value.trim()) params.push("q=" + encodeURIComponent(fSearch.value.trim()));
  var qs = params.length ? "?" + params.join("&") : "";
  if (history.replaceState) history.replaceState(null, "", location.pathname + qs);
}}

function readURL() {{
  var p = new URLSearchParams(location.search);
  if (p.get("country")) fCountry.value = p.get("country");
  if (p.get("org")) fOrg.value = p.get("org");
  if (p.get("status")) fStatus.value = p.get("status");
  if (p.get("stale")) fStale.value = p.get("stale");
  if (p.get("q")) fSearch.value = p.get("q");
}}

// Sort on column header click
document.querySelectorAll(".data-table th").forEach(function(th) {{
  th.addEventListener("click", function() {{
    var col = parseInt(this.dataset.col);
    if (sortCol === col) {{
      sortAsc = !sortAsc;
    }} else {{
      sortCol = col;
      sortAsc = col === 6 ? false : true;
    }}
    doSort();
    document.querySelectorAll(".data-table th").forEach(function(h) {{ h.classList.remove("sorted"); }});
    this.classList.add("sorted");
    this.querySelector(".sort-icon").textContent = sortAsc ? "▲" : "▼";
    page = 0;
    render();
  }});
}});

fCountry.onchange = applyFilters;
fOrg.onchange = applyFilters;
fStatus.onchange = applyFilters;
fStale.onchange = applyFilters;

var searchTimer;
fSearch.oninput = function() {{
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 200);
}};

document.getElementById("btn-clear").onclick = function() {{
  fCountry.value = "";
  fOrg.value = "";
  fStatus.value = "";
  fStale.value = "";
  fSearch.value = "";
  sortCol = -1;
  document.querySelectorAll(".data-table th").forEach(function(h) {{
    h.classList.remove("sorted");
    h.querySelector(".sort-icon").textContent = "▲";
  }});
  applyFilters();
}};

readURL();
applyFilters();
}})();
</script>
</body></html>"""

out = os.path.join(SITE, "explorer.html")
with open(out, "w") as fh:
    fh.write(html)

print(f"rendered explorer.html — {len(html)//1024} KB, {len(all_rows):,} activities, {len(sorted_orgs)} funders")
