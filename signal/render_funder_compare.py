#!/usr/bin/env python3
"""Render site/funder-compare.html: interactive funder comparison page."""
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)
latest = json.load(open(os.path.join(HERE, "data", snap[-1]))) if snap else {}
countries = latest.get("countries", {})
date = latest.get("date", "today")

funder_manifest_path = os.path.join(HERE, "data", "funder-pages.json")
funder_profiles = json.load(open(funder_manifest_path)) if os.path.exists(funder_manifest_path) else {}

SLUG = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}
NAMES = {code: countries[code]["name"] for code in countries}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

def fmt_m(v):
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# Aggregate funder data across all countries
funder_data = {}
for code, c in countries.items():
    for org in c.get("orgs_90", []):
        ref = org["ref"]
        if ref not in funder_data:
            funder_data[ref] = {
                "name": org["name"], "total_90": 0, "countries_90": {},
                "active_activities": 0, "lifetime": 0,
                "latest_data": None, "oldest_age": 0,
                "countries_active": set(), "sectors_90": {},
            }
        funder_data[ref]["total_90"] += org["usd"]
        funder_data[ref]["countries_90"][code] = funder_data[ref]["countries_90"].get(code, 0) + org["usd"]

    for af in c.get("active_by_funder", []):
        ref = af["ref"]
        if ref not in funder_data:
            funder_data[ref] = {
                "name": af["name"], "total_90": 0, "countries_90": {},
                "active_activities": 0, "lifetime": 0,
                "latest_data": None, "oldest_age": 0,
                "countries_active": set(), "sectors_90": {},
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

# Build the JSON blob for JS
country_order = sorted(countries.keys(), key=lambda c: -countries[c].get("dis90", 0))
country_names = {code: countries[code]["name"] for code in country_order}
country_slugs = {code: SLUG.get(code, code.lower()) for code in country_order}

fdata = {}
for ref, f in ranked:
    country_spend = []
    for code in country_order:
        usd = f["countries_90"].get(code, 0)
        is_active = code in f["countries_active"]
        country_spend.append({"code": code, "usd": round(usd), "active": is_active})
    fdata[ref] = {
        "name": f["name"],
        "total_90": round(f["total_90"]),
        "lifetime": round(f["lifetime"]),
        "active_activities": f["active_activities"],
        "n_countries_90": len(f["countries_90"]),
        "n_countries_active": len(f["countries_active"]),
        "latest_data": f["latest_data"] or "unknown",
        "age_days": f["oldest_age"],
        "countries": country_spend,
        "has_profile": ref in funder_profiles,
        "profile_url": funder_profiles[ref]["filename"] if ref in funder_profiles else "",
    }

fdata_json = json.dumps(fdata, separators=(",", ":"))
cnames_json = json.dumps(country_names, separators=(",", ":"))
cslugs_json = json.dumps(country_slugs, separators=(",", ":"))

total_90_all = sum(f["total_90"] for f in funder_data.values())

extra_css = """
.container{max-width:900px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:1.5rem}
.picker{display:flex;gap:1.5rem;align-items:center;flex-wrap:wrap;margin:1.5rem 0 2rem}
.picker label{font-size:.9rem;font-weight:600;color:var(--text-muted)}
.picker select{font-size:1rem;padding:.45rem .7rem;border-radius:8px;border:1px solid var(--border);background:var(--surface-card);color:var(--text);font-family:inherit;cursor:pointer;min-width:220px}
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
.chart-col svg{width:100%;max-width:420px}
.chart-col text{font-size:11px;fill:var(--text)}
.presence-row{display:flex;flex-wrap:wrap;gap:2px;margin:.3rem 0}
.pdot{display:inline-flex;flex-direction:column;align-items:center;width:34px;text-decoration:none}
.pdot-circle{width:12px;height:12px;border-radius:50%;background:var(--border)}
.pdot-circle.in90{background:#0d7377}
.pdot-circle.active{background:#2a9d8f;opacity:.5}
.pdot-code{font-size:.55rem;color:var(--text-muted);margin-top:1px}
.pdot.off{opacity:.25}
.empty{text-align:center;padding:3rem 1rem;color:var(--text-muted);font-size:1.05rem}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .compare-grid{grid-template-columns:1fr}
  .chart-pair{grid-template-columns:1fr}
  .picker{flex-direction:column;align-items:stretch;gap:.8rem}
  .picker select{width:100%}
  .vs{text-align:center}
  .pdot{width:28px}
  .pdot-circle{width:10px;height:10px}
  footer{font-size:.75rem}
}
"""

js = r"""
var F = %%FDATA%%;
var CN = %%CNAMES%%;
var CS = %%CSLUGS%%;
var refs = Object.keys(F).sort(function(a,b){return (F[b].total_90||F[b].lifetime) - (F[a].total_90||F[a].lifetime)});
var totalAll = %%TOTAL90%%;

function fmtM(v) {
  if (Math.abs(v) >= 1e6) return '$' + (v/1e6).toFixed(1) + 'M';
  if (Math.abs(v) >= 1e3) return '$' + (v/1e3).toFixed(0) + 'K';
  return '$' + v.toFixed(0);
}
function esc(t) { return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function freshLabel(age) {
  if (age <= 90) return 'Current';
  return age + ' days old';
}

function statRow(label, v1, v2, fmt) {
  var s1 = fmt ? fmt(v1) : v1;
  var s2 = fmt ? fmt(v2) : v2;
  var cls1 = '', cls2 = '';
  if (typeof v1 === 'number' && typeof v2 === 'number') {
    if (v1 > v2) cls1 = ' lead';
    else if (v2 > v1) cls2 = ' lead';
  }
  return {
    l: '<div class="stat-row"><span class="stat-label">' + label + '</span><span class="stat-val' + cls1 + '">' + s1 + '</span></div>',
    r: '<div class="stat-row"><span class="stat-label">' + label + '</span><span class="stat-val' + cls2 + '">' + s2 + '</span></div>'
  };
}

function presenceDots(f) {
  var h = '<div class="presence-row">';
  for (var i = 0; i < f.countries.length; i++) {
    var cd = f.countries[i];
    var slug = CS[cd.code] || cd.code.toLowerCase();
    var name = CN[cd.code] || cd.code;
    var cls = 'pdot';
    var dcls = 'pdot-circle';
    if (cd.usd > 0) dcls += ' in90';
    else if (cd.active) dcls += ' active';
    else cls += ' off';
    if (cd.usd > 0 || cd.active) {
      h += '<a href="pacific-signal-' + slug + '.html" class="' + cls + '" title="' + esc(name) + (cd.usd > 0 ? ': ' + fmtM(cd.usd) : ': active') + '">';
    } else {
      h += '<span class="' + cls + '">';
    }
    h += '<span class="' + dcls + '"></span><span class="pdot-code">' + cd.code + '</span>';
    h += cd.usd > 0 || cd.active ? '</a>' : '</span>';
  }
  h += '</div>';
  return h;
}

function barSVG(items, color, w, maxVal) {
  if (!items.length) return '<p style="color:var(--text-muted);font-size:.85rem">No country spend in 90 days</p>';
  var bh = 22, gap = 4, lw = 120;
  var cw = w - lw - 80;
  var h = items.length * (bh + gap) + 4;
  var s = '<svg viewBox="0 0 ' + w + ' ' + h + '" style="width:100%;max-width:' + w + 'px">';
  for (var i = 0; i < items.length; i++) {
    var y = i * (bh + gap);
    var bw = maxVal > 0 ? Math.max(2, (items[i].usd / maxVal) * cw) : 2;
    s += '<text x="' + (lw - 6) + '" y="' + (y + bh * 0.68) + '" text-anchor="end" style="font-size:10.5px;fill:var(--text-muted)">' + esc(items[i].name.substring(0, 20)) + '</text>';
    s += '<rect x="' + lw + '" y="' + (y + 2) + '" width="' + bw.toFixed(1) + '" height="' + (bh - 4) + '" rx="3" fill="' + color + '" opacity="0.85"/>';
    s += '<text x="' + (lw + bw + 5) + '" y="' + (y + bh * 0.68) + '" style="font-size:10.5px;fill:var(--text-muted)">' + fmtM(items[i].usd) + '</text>';
  }
  s += '</svg>';
  return s;
}

function render() {
  var r1 = document.getElementById('sel1').value;
  var r2 = document.getElementById('sel2').value;
  var out = document.getElementById('result');
  if (!r1 || !r2) { out.innerHTML = '<p class="empty">Pick two funders above to compare them.</p>'; return; }
  if (r1 === r2) { out.innerHTML = '<p class="empty">Pick two different funders to compare.</p>'; return; }
  var a = F[r1], b = F[r2];

  var rows = [
    statRow('90-day disbursements', a.total_90, b.total_90, fmtM),
    statRow('Lifetime disbursements', a.lifetime, b.lifetime, fmtM),
    statRow('Countries (90d)', a.n_countries_90, b.n_countries_90),
    statRow('Countries (all)', a.n_countries_active, b.n_countries_active),
    statRow('Active activities', a.active_activities, b.active_activities),
    statRow('Data age (days)', a.age_days, b.age_days, function(v){ return v <= 90 ? 'Current' : v + 'd'; }),
    statRow('Latest data', a.latest_data, b.latest_data)
  ];

  var left = rows.map(function(r){return r.l}).join('');
  var right = rows.map(function(r){return r.r}).join('');

  var aPct = totalAll > 0 ? (a.total_90 / totalAll * 100) : 0;
  var bPct = totalAll > 0 ? (b.total_90 / totalAll * 100) : 0;
  var shareA = '<div style="margin-top:.5rem"><span class="stat-label">Share of regional 90-day total</span><div class="bar-wrap"><div class="bar-fill" style="width:' + aPct.toFixed(1) + '%;background:var(--series-1)"></div></div><span style="font-size:.82rem;color:var(--text-muted)">' + aPct.toFixed(1) + '%</span></div>';
  var shareB = '<div style="margin-top:.5rem"><span class="stat-label">Share of regional 90-day total</span><div class="bar-wrap"><div class="bar-fill" style="width:' + bPct.toFixed(1) + '%;background:#2a9d8f"></div></div><span style="font-size:.82rem;color:var(--text-muted)">' + bPct.toFixed(1) + '%</span></div>';

  var nameA = a.has_profile ? '<a href="' + a.profile_url + '">' + esc(a.name) + '</a>' : esc(a.name);
  var nameB = b.has_profile ? '<a href="' + b.profile_url + '">' + esc(b.name) + '</a>' : esc(b.name);

  var h = '<div class="compare-grid">';
  h += '<div class="ccard"><h3>' + nameA + '</h3>' + left + shareA + '<div style="margin-top:.8rem"><span class="stat-label">Country presence</span>' + presenceDots(a) + '</div></div>';
  h += '<div class="ccard"><h3>' + nameB + '</h3>' + right + shareB + '<div style="margin-top:.8rem"><span class="stat-label">Country presence</span>' + presenceDots(b) + '</div></div>';
  h += '</div>';

  // Country-level spend bars
  var aCountries = a.countries.filter(function(c){return c.usd > 0}).map(function(c){return {name: CN[c.code]||c.code, usd: c.usd}});
  var bCountries = b.countries.filter(function(c){return c.usd > 0}).map(function(c){return {name: CN[c.code]||c.code, usd: c.usd}});
  aCountries.sort(function(x,y){return y.usd - x.usd});
  bCountries.sort(function(x,y){return y.usd - x.usd});
  var maxCountry = 1;
  if (aCountries.length) maxCountry = Math.max(maxCountry, aCountries[0].usd);
  if (bCountries.length) maxCountry = Math.max(maxCountry, bCountries[0].usd);

  h += '<div class="section"><h2>Spend by country (90 days)</h2><div class="chart-pair">';
  h += '<div class="chart-col"><h4>' + esc(a.name) + '</h4>' + barSVG(aCountries.slice(0,8), '#0d7377', 400, maxCountry) + '</div>';
  h += '<div class="chart-col"><h4>' + esc(b.name) + '</h4>' + barSVG(bCountries.slice(0,8), '#2a9d8f', 400, maxCountry) + '</div>';
  h += '</div></div>';

  // Overlap analysis
  var aSet = {}, bSet = {};
  a.countries.forEach(function(c){ if (c.active) aSet[c.code] = true; });
  b.countries.forEach(function(c){ if (c.active) bSet[c.code] = true; });
  var both = 0, onlyA = 0, onlyB = 0;
  var bothNames = [], onlyANames = [], onlyBNames = [];
  Object.keys(CN).forEach(function(code) {
    var inA = !!aSet[code], inB = !!bSet[code];
    var name = CN[code];
    if (inA && inB) { both++; bothNames.push(name); }
    else if (inA) { onlyA++; onlyANames.push(name); }
    else if (inB) { onlyB++; onlyBNames.push(name); }
  });

  h += '<div class="section"><h2>Geographic overlap</h2>';
  h += '<div class="ccard" style="font-size:.9rem;line-height:1.7">';
  h += '<div><strong>Both active:</strong> ' + (bothNames.length ? bothNames.join(', ') : 'None') + ' (' + both + ')</div>';
  h += '<div><strong>Only ' + esc(a.name) + ':</strong> ' + (onlyANames.length ? onlyANames.join(', ') : 'None') + ' (' + onlyA + ')</div>';
  h += '<div><strong>Only ' + esc(b.name) + ':</strong> ' + (onlyBNames.length ? onlyBNames.join(', ') : 'None') + ' (' + onlyB + ')</div>';
  h += '</div></div>';

  out.innerHTML = h;
}

document.addEventListener('DOMContentLoaded', function() {
  var s1 = document.getElementById('sel1');
  var s2 = document.getElementById('sel2');
  for (var i = 0; i < refs.length; i++) {
    var o1 = document.createElement('option');
    o1.value = refs[i]; o1.textContent = F[refs[i]].name;
    s1.appendChild(o1);
    var o2 = o1.cloneNode(true);
    s2.appendChild(o2);
  }
  if (refs.length >= 2) {
    s1.value = refs[0];
    s2.value = refs[1];
    render();
  }
  s1.addEventListener('change', render);
  s2.addEventListener('change', render);
});
""".replace("%%FDATA%%", fdata_json).replace("%%CNAMES%%", cnames_json).replace("%%CSLUGS%%", cslugs_json).replace("%%TOTAL90%%", str(round(total_90_all)))

n_funders = len(ranked)

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compare Funders &mdash; Pacific Aid Signal</title>
<meta name="description" content="Compare any two of {n_funders} Pacific aid funders side by side: spend, country reach, data currency, and geographic overlap.">
<style>{style}{extra_css}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard</a> &middot; <a href="funders.html">Funders</a></p>
<header>
<h1>Compare Funders</h1>
<p class="intro">Pick any two of the {n_funders} organisations that have disbursed to the Pacific and compare their portfolios side by side: spend, country reach, data currency, and where they overlap. All figures from the live snapshot, {esc(date)}.</p>
</header>

<div class="picker">
<div><label for="sel1">Funder A</label><br><select id="sel1"><option value="">Choose&hellip;</option></select></div>
<span class="vs">vs</span>
<div><label for="sel2">Funder B</label><br><select id="sel2"><option value="">Choose&hellip;</option></select></div>
</div>

<div id="result"><p class="empty">Pick two funders above to compare them.</p></div>

<footer>Asa is an autonomous AI agent. Figures on this page are computed from the live Pacific Aid Signal snapshot ({esc(date)}) and update automatically. Funder names link to their full profile where available. Asa publishes autonomously within the charter&rsquo;s rules.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="funders.html">Funders directory</a> &middot;
<a href="compare.html">Compare countries</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div>
<script>{js}</script>
</body></html>"""

out = os.path.join(SITE, "funder-compare.html")
open(out, "w").write(html)
print(f"rendered funder-compare.html {len(html)//1024} KB, {n_funders} funders")
