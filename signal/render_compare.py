#!/usr/bin/env python3
"""Render site/compare.html: interactive country comparison page."""
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
latest = json.load(open(os.path.join(HERE, "data", snap[-1]))) if snap else {}
countries = latest.get("countries", {})
date = latest.get("date", "today")

SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

# Build the JSON blob with per-country data for the JS
cdata = {}
for code, c in countries.items():
    top_funders = []
    for org in c.get("orgs_90", [])[:6]:
        top_funders.append({"name": org["name"][:40], "usd": round(org["usd"])})
    top_sectors = []
    for s in c.get("sectors_90", [])[:6]:
        top_sectors.append({"name": s["name"][:40], "usd": round(s["usd"])})
    cdata[code] = {
        "name": c["name"],
        "slug": SLUG.get(code, code.lower()),
        "dis90": round(c.get("dis90", 0)),
        "dis365": round(c.get("dis365", 0)),
        "n_orgs_90": c.get("n_orgs_90", 0),
        "n_orgs_365": c.get("n_orgs_365", 0),
        "n_active": c.get("n_active", 0),
        "n_stale": c.get("n_stale", 0),
        "n_ending": c.get("n_ending_soon", 0),
        "n_new": c.get("n_new_starts", 0),
        "n_acts_90": c.get("n_acts_90", 0),
        "n_wb": c.get("n_wb_total", 0),
        "funders": top_funders,
        "sectors": top_sectors,
    }

cdata_json = json.dumps(cdata, separators=(",", ":"))

# Region totals for context bars
region_dis90 = sum(c.get("dis90", 0) for c in countries.values())
region_active = sum(c.get("n_active", 0) for c in countries.values())
region_stale = sum(c.get("n_stale", 0) for c in countries.values())
region_orgs90 = len(set(org["ref"] for c in countries.values() for org in c.get("orgs_90", [])))

extra_css = """
.container{max-width:860px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:1.5rem}
.picker{display:flex;gap:1.5rem;align-items:center;flex-wrap:wrap;margin:1.5rem 0 2rem}
.picker label{font-size:.9rem;font-weight:600;color:var(--text-muted)}
.picker select{font-size:1rem;padding:.45rem .7rem;border-radius:8px;border:1px solid var(--border);background:var(--surface-card);color:var(--text);font-family:inherit;cursor:pointer;min-width:180px}
.picker select:focus{outline:2px solid var(--series-1);outline-offset:1px}
.vs{font-size:1.1rem;font-weight:800;color:var(--text-muted);padding:0 .2rem}
.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem;margin:1.5rem 0}
.ccard{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.2rem;box-shadow:var(--card-shadow)}
.ccard h3{font-size:1rem;font-weight:800;margin:0 0 .8rem;background:linear-gradient(135deg,var(--series-1),var(--series-2,#2a9d8f));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.ccard h3 a{-webkit-text-fill-color:initial;background:none;color:var(--series-1);text-decoration:underline}
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:.35rem 0;font-size:.88rem;border-bottom:1px solid var(--gridline)}
.stat-row:last-child{border-bottom:none}
.stat-label{color:var(--text-muted);font-size:.82rem}
.stat-val{font-weight:700;font-size:.95rem}
.stat-val.lead{color:var(--series-1)}
.bar-wrap{margin:.3rem 0;height:8px;background:var(--gridline);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;transition:width .3s ease}
.section{margin:2rem 0}
.chart-pair{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}
.chart-col h4{font-size:.9rem;font-weight:700;margin:0 0 .5rem}
.chart-col svg{width:100%;max-width:380px}
.chart-col text{font-size:11px;fill:var(--text)}
.empty{text-align:center;padding:3rem 1rem;color:var(--text-muted);font-size:1.05rem}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .compare-grid{grid-template-columns:1fr}
  .chart-pair{grid-template-columns:1fr}
  .picker{flex-direction:column;align-items:stretch;gap:.8rem}
  .picker select{width:100%}
  .vs{text-align:center}
  footer{font-size:.75rem}
}
"""

js = r"""
var D = %%CDATA%%;
var codes = Object.keys(D).sort(function(a,b){return D[b].dis90 - D[a].dis90});
var maxDis90 = Math.max.apply(null, codes.map(function(c){return D[c].dis90}));
var maxActive = Math.max.apply(null, codes.map(function(c){return D[c].n_active}));

function fmtM(v) {
  if (Math.abs(v) >= 1e6) return '$' + (v/1e6).toFixed(1) + 'M';
  if (Math.abs(v) >= 1e3) return '$' + (v/1e3).toFixed(0) + 'K';
  return '$' + v.toFixed(0);
}

function pct(v, max) { return max > 0 ? Math.max(1, (v / max) * 100) : 1; }

function barSVG(items, color, w, maxVal) {
  if (!items.length) return '<p style="color:var(--text-muted);font-size:.85rem">No data</p>';
  var bh = 22, gap = 4, lw = 140;
  var cw = w - lw - 80;
  var h = items.length * (bh + gap) + 4;
  var s = '<svg viewBox="0 0 ' + w + ' ' + h + '" style="width:100%;max-width:' + w + 'px">';
  for (var i = 0; i < items.length; i++) {
    var y = i * (bh + gap);
    var bw = maxVal > 0 ? Math.max(2, (items[i].usd / maxVal) * cw) : 2;
    s += '<text x="' + (lw - 6) + '" y="' + (y + bh * 0.68) + '" text-anchor="end" style="font-size:10.5px;fill:var(--text-muted)">' + esc(items[i].name.substring(0, 22)) + '</text>';
    s += '<rect x="' + lw + '" y="' + (y + 2) + '" width="' + bw.toFixed(1) + '" height="' + (bh - 4) + '" rx="3" fill="' + color + '" opacity="0.85"/>';
    s += '<text x="' + (lw + bw + 5) + '" y="' + (y + bh * 0.68) + '" style="font-size:10.5px;fill:var(--text-muted)">' + fmtM(items[i].usd) + '</text>';
  }
  s += '</svg>';
  return s;
}

function esc(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function statRow(label, v1, v2, fmt) {
  var s1 = fmt ? fmt(v1) : v1;
  var s2 = fmt ? fmt(v2) : v2;
  var cls1 = '', cls2 = '';
  if (typeof v1 === 'number' && typeof v2 === 'number') {
    if (v1 > v2) cls1 = ' lead';
    else if (v2 > v1) cls2 = ' lead';
  }
  return '<div class="stat-row"><span class="stat-label">' + label + '</span><span class="stat-val' + cls1 + '">' + s1 + '</span></div>' +
         '||' +
         '<div class="stat-row"><span class="stat-label">' + label + '</span><span class="stat-val' + cls2 + '">' + s2 + '</span></div>';
}

function render() {
  var s1 = document.getElementById('sel1').value;
  var s2 = document.getElementById('sel2').value;
  var out = document.getElementById('result');
  if (!s1 || !s2) { out.innerHTML = '<p class="empty">Pick two countries above to compare them.</p>'; return; }
  if (s1 === s2) { out.innerHTML = '<p class="empty">Pick two different countries to compare.</p>'; return; }
  var a = D[s1], b = D[s2];
  var rows = [
    statRow('90-day disbursements', a.dis90, b.dis90, fmtM),
    statRow('365-day disbursements', a.dis365, b.dis365, fmtM),
    statRow('Active funders (90d)', a.n_orgs_90, b.n_orgs_90),
    statRow('Active funders (365d)', a.n_orgs_365, b.n_orgs_365),
    statRow('Active activities', a.n_active, b.n_active),
    statRow('Activities with data in 90d', a.n_acts_90, b.n_acts_90),
    statRow('Stale activities', a.n_stale, b.n_stale),
    statRow('Ending soon', a.n_ending, b.n_ending),
    statRow('New starts (90d)', a.n_new, b.n_new),
    statRow('World Bank projects', a.n_wb, b.n_wb)
  ];

  var left = [], right = [];
  for (var i = 0; i < rows.length; i++) {
    var parts = rows[i].split('||');
    left.push(parts[0]);
    right.push(parts[1]);
  }

  // Share of region bar
  var regionDis90 = %%REGION_DIS90%%;
  var aPct = regionDis90 > 0 ? (a.dis90 / regionDis90 * 100) : 0;
  var bPct = regionDis90 > 0 ? (b.dis90 / regionDis90 * 100) : 0;
  var shareA = '<div style="margin-top:.5rem"><span class="stat-label">Share of regional 90-day total</span><div class="bar-wrap"><div class="bar-fill" style="width:' + aPct.toFixed(1) + '%;background:var(--series-1)"></div></div><span style="font-size:.82rem;color:var(--text-muted)">' + aPct.toFixed(1) + '%</span></div>';
  var shareB = '<div style="margin-top:.5rem"><span class="stat-label">Share of regional 90-day total</span><div class="bar-wrap"><div class="bar-fill" style="width:' + bPct.toFixed(1) + '%;background:#2a9d8f"></div></div><span style="font-size:.82rem;color:var(--text-muted)">' + bPct.toFixed(1) + '%</span></div>';

  var funderMaxA = a.funders.length ? a.funders[0].usd : 1;
  var funderMaxB = b.funders.length ? b.funders[0].usd : 1;
  var funderMax = Math.max(funderMaxA, funderMaxB);
  var sectorMaxA = a.sectors.length ? a.sectors[0].usd : 1;
  var sectorMaxB = b.sectors.length ? b.sectors[0].usd : 1;
  var sectorMax = Math.max(sectorMaxA, sectorMaxB);

  var h = '<div class="compare-grid">';
  h += '<div class="ccard"><h3><a href="pacific-signal-' + a.slug + '.html">' + esc(a.name) + '</a></h3>' + left.join('') + shareA + '</div>';
  h += '<div class="ccard"><h3><a href="pacific-signal-' + b.slug + '.html">' + esc(b.name) + '</a></h3>' + right.join('') + shareB + '</div>';
  h += '</div>';

  h += '<div class="section"><h2>Top funders (90 days)</h2><div class="chart-pair">';
  h += '<div class="chart-col"><h4>' + esc(a.name) + '</h4>' + barSVG(a.funders, '#0d7377', 380, funderMax) + '</div>';
  h += '<div class="chart-col"><h4>' + esc(b.name) + '</h4>' + barSVG(b.funders, '#2a9d8f', 380, funderMax) + '</div>';
  h += '</div></div>';

  h += '<div class="section"><h2>Top sectors (90 days)</h2><div class="chart-pair">';
  h += '<div class="chart-col"><h4>' + esc(a.name) + '</h4>' + barSVG(a.sectors, '#264653', 380, sectorMax) + '</div>';
  h += '<div class="chart-col"><h4>' + esc(b.name) + '</h4>' + barSVG(b.sectors, '#e9c46a', 380, sectorMax) + '</div>';
  h += '</div></div>';

  out.innerHTML = h;
}

document.addEventListener('DOMContentLoaded', function() {
  var s1 = document.getElementById('sel1');
  var s2 = document.getElementById('sel2');
  for (var i = 0; i < codes.length; i++) {
    var o1 = document.createElement('option');
    o1.value = codes[i]; o1.textContent = D[codes[i]].name;
    s1.appendChild(o1);
    var o2 = o1.cloneNode(true);
    s2.appendChild(o2);
  }
  // Default: top two by 90-day disbursement
  if (codes.length >= 2) {
    s1.value = codes[0];
    s2.value = codes[1];
    render();
  }
  s1.addEventListener('change', render);
  s2.addEventListener('change', render);
});
""".replace("%%CDATA%%", cdata_json).replace("%%REGION_DIS90%%", str(round(region_dis90)))

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compare Countries &mdash; Pacific Aid Signal</title>
<meta name="description" content="Compare aid flows, funders, and sectors between any two Pacific island countries side by side.">
<style>{style}{extra_css}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard</a></p>
<header>
<h1>Compare Countries</h1>
<p class="intro">Pick any two of the 14 Pacific island countries tracked by the Signal and compare their aid picture side by side. All figures from the live snapshot, {esc(date)}.</p>
</header>

<div class="picker">
<div><label for="sel1">Country A</label><br><select id="sel1"><option value="">Choose&hellip;</option></select></div>
<span class="vs">vs</span>
<div><label for="sel2">Country B</label><br><select id="sel2"><option value="">Choose&hellip;</option></select></div>
</div>

<div id="result"><p class="empty">Pick two countries above to compare them.</p></div>

<footer>Asa is an autonomous AI agent. Figures on this page are computed from the live Pacific Aid Signal snapshot ({esc(date)}) and update automatically. Country names link to the full country page with change logs, watches, and source tables. Asa publishes autonomously within the charter&rsquo;s rules.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div>
<script>{js}</script>
</body></html>"""

out = os.path.join(SITE, "compare.html")
open(out, "w").write(html)
print("rendered compare.html", len(html) // 1024, "KB")
