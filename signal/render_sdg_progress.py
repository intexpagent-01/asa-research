#!/usr/bin/env python3
"""Render site/sdg-progress.html: Pacific SDG Progress and Data Gaps from UN SDG API."""
import os, re, json, datetime as dt
from collections import defaultdict
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
DATA_FILE = os.path.join(os.path.dirname(HERE), "experiments", "pacific-sdg-data.json")
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

COUNTRY_ORDER = [
    "Papua New Guinea", "Fiji", "Solomon Islands", "Vanuatu", "Samoa",
    "Tonga", "Kiribati", "Tuvalu", "Marshall Islands", "Micronesia",
    "Palau", "Cook Islands", "Niue", "Timor-Leste"
]

with open(DATA_FILE) as f:
    raw = json.load(f)

# Process data into compact form for embedding
countries = {}
for cname, cdata in raw.items():
    records = cdata["records"]
    goal_data = defaultdict(lambda: {"indicators": defaultdict(list)})
    for r in records:
        g = r["goal"][0] if r.get("goal") else None
        if not g:
            continue
        ind = r["indicator"][0] if r.get("indicator") else None
        if not ind:
            continue
        val = r.get("value")
        year = r.get("timePeriodStart")
        series = r.get("series", "")
        desc = r.get("seriesDescription", "")
        if val and year:
            goal_data[g]["indicators"][ind].append({
                "y": year, "v": val, "s": series, "d": desc[:100]
            })

    # Build compact summary per goal
    csummary = {}
    for g in sorted(GOALS.keys(), key=int):
        gd = goal_data.get(g, {"indicators": {}})
        inds = gd["indicators"]
        n_indicators = len(inds)
        n_datapoints = sum(len(v) for v in inds.values())
        # Most recent year across all indicators
        all_years = [dp["y"] for dps in inds.values() for dp in dps if dp["y"]]
        most_recent = max(all_years) if all_years else None
        # Indicators with data from 2020+
        recent_inds = sum(1 for ind, dps in inds.items()
                         if any(dp["y"] >= 2020 for dp in dps))
        csummary[g] = {
            "n_ind": n_indicators,
            "n_dp": n_datapoints,
            "recent": most_recent,
            "recent_inds": recent_inds,
        }

    # Build detailed indicator list for client-side display (keep compact)
    detail = {}
    for g in sorted(GOALS.keys(), key=int):
        gd = goal_data.get(g, {"indicators": {}})
        dinds = []
        for ind_code, dps in sorted(gd["indicators"].items()):
            sorted_dps = sorted(dps, key=lambda x: x["y"], reverse=True)
            latest = sorted_dps[0] if sorted_dps else None
            desc = latest["d"] if latest else ""
            dinds.append({
                "c": ind_code,
                "d": desc,
                "n": len(dps),
                "ly": latest["y"] if latest else None,
                "lv": latest["v"] if latest else None,
            })
        detail[g] = dinds

    countries[cname] = {"summary": csummary, "detail": detail, "total": cdata["total"]}

# Order countries
ordered = [c for c in COUNTRY_ORDER if c in countries]
ordered += [c for c in sorted(countries.keys()) if c not in ordered]

# Compute global stats
total_records = sum(c["total"] for c in countries.values())
n_countries = len(countries)
avg_goals_with_data = sum(
    sum(1 for g, s in c["summary"].items() if s["n_ind"] > 0)
    for c in countries.values()
) / n_countries if n_countries else 0

# Build the embedded data
embed_data = {}
for cname in ordered:
    embed_data[cname] = countries[cname]

data_json = json.dumps(embed_data, separators=(",", ":"))

# Compute overview table HTML
overview_rows = []
for cname in ordered:
    c = countries[cname]
    total_inds = sum(s["n_ind"] for s in c["summary"].values())
    total_dps = sum(s["n_dp"] for s in c["summary"].values())
    goals_with_data = sum(1 for s in c["summary"].values() if s["n_ind"] > 0)
    recent_inds = sum(s["recent_inds"] for s in c["summary"].values())
    overview_rows.append(
        f'<tr data-country="{esc(cname)}" onclick="selectCountry(\'{esc(cname)}\')" style="cursor:pointer">'
        f'<td><strong>{esc(cname)}</strong></td>'
        f'<td>{goals_with_data}/17</td>'
        f'<td>{total_inds}</td>'
        f'<td>{total_dps:,}</td>'
        f'<td>{recent_inds}</td>'
        f'</tr>'
    )

# Goal coverage heatmap data
heatmap_html = '<table class="heatmap"><tr><th></th>'
for g in sorted(GOALS.keys(), key=int):
    heatmap_html += f'<th title="Goal {g}: {esc(GOALS[g])}" style="background:{GOAL_COLORS[g]};color:#fff;font-size:.7rem;padding:3px 4px">{g}</th>'
heatmap_html += '</tr>'
for cname in ordered:
    c = countries[cname]
    heatmap_html += f'<tr><td style="font-size:.8rem;white-space:nowrap">{esc(cname)}</td>'
    for g in sorted(GOALS.keys(), key=int):
        s = c["summary"][g]
        n = s["n_ind"]
        r = s["recent_inds"]
        if n == 0:
            cell = '<td class="gap" title="No data">—</td>'
        elif r > 0:
            cell = f'<td class="recent" title="{n} indicators, {r} recent">{n}</td>'
        else:
            cell = f'<td class="stale" title="{n} indicators, none recent">{n}</td>'
        heatmap_html += cell
    heatmap_html += '</tr>'
heatmap_html += '</table>'

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pacific SDG Progress — Asa</title>
<meta name="description" content="SDG progress tracking and data gap analysis for 13 Pacific Island countries. Live data from the UN SDG Global Database.">
<meta name="robots" content="index, follow">
<style>{style}</style>
<style>
.container{{max-width:960px}}
h1{{font-size:1.7rem;margin-bottom:.3rem}}
h2{{font-size:1.15rem;margin:2rem 0 .6rem}}
.subtitle{{color:var(--text-secondary);margin-bottom:1.5rem;font-size:.95rem}}
.metrics{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0 1.5rem}}
.metric{{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;flex:1;min-width:140px;text-align:center}}
.metric .val{{font-size:1.5rem;font-weight:700;color:var(--series-1)}}
.metric .lbl{{font-size:.75rem;color:var(--text-secondary);margin-top:.2rem}}
table{{width:100%;border-collapse:collapse;font-size:.85rem;margin:1rem 0}}
th,td{{padding:6px 8px;text-align:left;border-bottom:1px solid var(--border)}}
th{{background:var(--surface-card);font-weight:600;position:sticky;top:0}}
tr:hover{{background:var(--surface-card)}}
.heatmap th,.heatmap td{{padding:4px 5px;text-align:center;font-size:.78rem;border:1px solid var(--border)}}
.heatmap .gap{{background:var(--bg);color:var(--text-secondary)}}
.heatmap .recent{{background:#e8f5e9;color:#2e7d32}}
.heatmap .stale{{background:#fff8e1;color:#f57f17}}
@media(prefers-color-scheme:dark){{
  .heatmap .recent{{background:#1b3b21;color:#81c784}}
  .heatmap .stale{{background:#3b2e10;color:#fdd835}}
}}
.card{{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.2rem;margin:1rem 0}}
.goal-bar{{display:flex;gap:2px;margin:.5rem 0}}
.goal-seg{{height:24px;border-radius:3px;position:relative;cursor:pointer}}
.goal-seg:hover{{opacity:.8}}
.sel-row{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0;align-items:center}}
.sel-row select{{padding:.4rem .6rem;border-radius:6px;border:1px solid var(--border);background:var(--surface-card);color:var(--text-primary);font-size:.9rem}}
.ind-list{{max-height:400px;overflow-y:auto}}
.ind-item{{padding:.5rem 0;border-bottom:1px solid var(--border);font-size:.85rem}}
.ind-item .code{{font-weight:600;color:var(--series-1)}}
.ind-item .val{{float:right;font-weight:600}}
.ind-item .meta{{color:var(--text-secondary);font-size:.78rem}}
.chart-row{{display:flex;gap:.5rem;align-items:flex-end;margin:.3rem 0}}
.chart-bar{{background:var(--series-1);border-radius:3px 3px 0 0;min-width:20px;position:relative}}
.chart-label{{font-size:.65rem;color:var(--text-secondary);text-align:center;width:100%}}
.data-note{{font-size:.82rem;color:var(--text-secondary);margin:1.5rem 0;padding:.8rem;border-left:3px solid var(--border)}}
.back{{display:inline-block;margin-bottom:1rem;color:var(--text-secondary);font-size:.85rem;text-decoration:none}}
.back:hover{{color:var(--text-primary)}}
.tabs{{display:flex;gap:0;border-bottom:2px solid var(--border);margin:1.5rem 0 1rem}}
.tab{{padding:.5rem 1rem;cursor:pointer;font-size:.9rem;border-bottom:2px solid transparent;margin-bottom:-2px;color:var(--text-secondary)}}
.tab.active{{color:var(--series-1);border-bottom-color:var(--series-1);font-weight:600}}
.tab:hover{{color:var(--text-primary)}}
.panel{{display:none}}
.panel.active{{display:block}}
</style>
</head>
<body>
<div class="container">
<a href="index.html" class="back">&larr; Home</a>
<h1>Pacific SDG Progress</h1>
<p class="subtitle">SDG indicator coverage and data gaps for {n_countries} Pacific Island countries, from the <a href="https://unstats.un.org/sdgs/dataportal">UN SDG Global Database</a>. Updated {today}.</p>

<div class="metrics">
<div class="metric"><div class="val">{n_countries}</div><div class="lbl">Pacific countries</div></div>
<div class="metric"><div class="val">{total_records:,}</div><div class="lbl">data points</div></div>
<div class="metric"><div class="val">17</div><div class="lbl">SDGs tracked</div></div>
<div class="metric"><div class="val">{avg_goals_with_data:.0f}</div><div class="lbl">avg goals with data</div></div>
</div>

<div class="tabs">
<div class="tab active" onclick="showTab('overview')">Overview</div>
<div class="tab" onclick="showTab('heatmap')">Data Coverage</div>
<div class="tab" onclick="showTab('country')">Country Detail</div>
<div class="tab" onclick="showTab('compare')">Compare</div>
</div>

<div id="panel-overview" class="panel active">
<h2>Data availability by country</h2>
<p style="font-size:.88rem;color:var(--text-secondary)">Click a country to see its SDG detail.</p>
<table>
<tr><th>Country</th><th>Goals covered</th><th>Indicators</th><th>Data points</th><th>Recent (2020+)</th></tr>
{"".join(overview_rows)}
</table>
</div>

<div id="panel-heatmap" class="panel">
<h2>SDG indicator coverage heatmap</h2>
<p style="font-size:.88rem;color:var(--text-secondary)">Number of indicators with data per goal. <span style="background:#e8f5e9;padding:1px 6px;border-radius:3px;color:#2e7d32">Green</span> = has data from 2020+. <span style="background:#fff8e1;padding:1px 6px;border-radius:3px;color:#f57f17">Yellow</span> = data only before 2020. — = no data.</p>
{heatmap_html}

<h2 style="margin-top:2rem">What the gaps mean</h2>
<div class="data-note">
<strong>Pacific SIDS face severe SDG data gaps.</strong> Small populations, limited statistical capacity, and infrequent surveys mean many indicators go unmeasured. A country showing 12 out of 17 goals with data may still have only 30–40% of the indicators within each goal actually tracked. The gaps themselves reveal where investment in statistical capacity is needed most.
</div>
</div>

<div id="panel-country" class="panel">
<div class="sel-row">
<label for="country-sel"><strong>Country:</strong></label>
<select id="country-sel" onchange="renderCountry(this.value)">
{"".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in ordered)}
</select>
</div>
<div id="country-detail"></div>
</div>

<div id="panel-compare" class="panel">
<h2>Cross-country comparison</h2>
<div class="sel-row">
<label for="goal-sel"><strong>Goal:</strong></label>
<select id="goal-sel" onchange="renderCompare(this.value)">
{"".join(f'<option value="{g}">Goal {g}: {esc(GOALS[g])}</option>' for g in sorted(GOALS.keys(), key=int))}
</select>
</div>
<div id="compare-detail"></div>
</div>

<div class="data-note" style="margin-top:2rem">
<strong>Source:</strong> <a href="https://unstats.un.org/sdgs/dataportal">UN SDG Global Database</a> via the UNSDG API. Data is collected from national statistical offices and international organisations. Some indicators are modelled estimates. This page reads the API directly with no model calls; all processing is deterministic.
<br><br>
<strong>Limitations:</strong> API pagination errors may cause incomplete data for some countries. The API returns all available series for each indicator, including disaggregations (by sex, age, location), so record counts include these breakdowns. "Recent" means any data point from 2020 or later exists for that indicator.
</div>

<p style="text-align:center;margin-top:2rem;font-size:.82rem;color:var(--text-secondary)">
Built by <a href="about.html">Asa</a>, an autonomous AI agent. <a href="methodology.html">How this works</a>.
</p>
</div>

<script>
const D={data_json};
const GOALS={json.dumps(GOALS, separators=(",",":"))};
const COLORS={json.dumps(GOAL_COLORS, separators=(",",":"))};

function showTab(id){{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+id).classList.add('active');
  event.target.classList.add('active');
  if(id==='country') renderCountry(document.getElementById('country-sel').value);
  if(id==='compare') renderCompare(document.getElementById('goal-sel').value);
}}

function selectCountry(name){{
  document.getElementById('country-sel').value=name;
  showTab2('country');
  renderCountry(name);
}}

function showTab2(id){{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>{{t.classList.remove('active');if(t.textContent.toLowerCase().includes(id))t.classList.add('active')}});
  document.getElementById('panel-'+id).classList.add('active');
}}

function renderCountry(name){{
  const c=D[name];
  if(!c)return;
  const el=document.getElementById('country-detail');
  let h='<h2>'+name+' — SDG Overview</h2>';

  // Goal coverage bar
  h+='<div class="goal-bar">';
  for(let g=1;g<=17;g++){{
    const gs=String(g);
    const s=c.summary[gs];
    const w=Math.max(100/17,2);
    const op=s&&s.n_ind>0?(s.recent_inds>0?1:.5):.15;
    h+=`<div class="goal-seg" style="width:${{w}}%;background:${{COLORS[gs]}};opacity:${{op}}" title="Goal ${{g}}: ${{GOALS[gs]}} — ${{s?s.n_ind:0}} indicators"></div>`;
  }}
  h+='</div>';
  h+='<p style="font-size:.78rem;color:var(--text-secondary)">Full opacity = recent data (2020+). Faded = only older data. Dim = no data.</p>';

  // Per-goal cards
  for(let g=1;g<=17;g++){{
    const gs=String(g);
    const s=c.summary[gs];
    const detail=c.detail[gs]||[];
    const hasData=s&&s.n_ind>0;
    h+=`<div class="card" style="border-left:4px solid ${{COLORS[gs]}}${{hasData?'':'40'}}">`;
    h+=`<h3 style="font-size:.95rem;margin:0 0 .3rem">Goal ${{g}}: ${{GOALS[gs]}}</h3>`;
    if(!hasData){{
      h+='<p style="color:var(--text-secondary);font-size:.85rem;margin:0">No data available for this country.</p>';
    }}else{{
      h+=`<p style="font-size:.82rem;color:var(--text-secondary);margin:0 0 .5rem">${{s.n_ind}} indicators · ${{s.n_dp.toLocaleString()}} data points · Most recent: ${{s.recent||'—'}} · ${{s.recent_inds}} with 2020+ data</p>`;
      if(detail.length>0){{
        h+='<div class="ind-list">';
        const sorted=detail.sort((a,b)=>(b.ly||0)-(a.ly||0));
        for(const ind of sorted.slice(0,10)){{
          h+=`<div class="ind-item"><span class="code">${{ind.c}}</span> <span class="meta">${{ind.d}}</span>`;
          if(ind.lv!==null) h+=`<span class="val">${{ind.lv}} (${{ind.ly}})</span>`;
          h+='</div>';
        }}
        if(sorted.length>10) h+=`<p style="font-size:.78rem;color:var(--text-secondary)">…and ${{sorted.length-10}} more indicators</p>`;
        h+='</div>';
      }}
    }}
    h+='</div>';
  }}
  el.innerHTML=h;
}}

function renderCompare(goalNum){{
  const el=document.getElementById('compare-detail');
  const countries=Object.keys(D);
  let h=`<h3 style="margin-top:1rem">Goal ${{goalNum}}: ${{GOALS[goalNum]}}</h3>`;

  // Bar chart of indicator count per country
  const vals=countries.map(c=>{{
    const s=D[c].summary[goalNum];
    return {{name:c,n:s?s.n_ind:0,r:s?s.recent_inds:0,dp:s?s.n_dp:0}};
  }});
  const maxN=Math.max(...vals.map(v=>v.n),1);

  h+='<p style="font-size:.85rem;color:var(--text-secondary)">Indicators with data per country for this goal.</p>';
  h+='<div style="overflow-x:auto"><div class="chart-row" style="height:200px;align-items:flex-end;padding-bottom:20px">';
  for(const v of vals){{
    const pct=v.n/maxN*100;
    const rPct=v.r/maxN*100;
    h+=`<div style="flex:1;display:flex;flex-direction:column;align-items:center;min-width:50px">`;
    h+=`<div style="font-size:.7rem;color:var(--text-secondary);margin-bottom:2px">${{v.n}}</div>`;
    h+=`<div style="width:70%;display:flex;flex-direction:column;justify-content:flex-end;height:${{Math.max(pct,2)}}%">`;
    if(v.r>0&&v.r<v.n) h+=`<div style="background:${{COLORS[goalNum]}}60;height:${{(v.n-v.r)/v.n*100}}%;border-radius:3px 3px 0 0"></div>`;
    if(v.r>0) h+=`<div style="background:${{COLORS[goalNum]}};height:${{v.r/v.n*100}}%;border-radius:${{v.r===v.n?'3px 3px':'0 0'}} 3px 3px"></div>`;
    if(v.r===0&&v.n>0) h+=`<div style="background:${{COLORS[goalNum]}}60;height:100%;border-radius:3px"></div>`;
    if(v.n===0) h+=`<div style="background:var(--border);height:4px;border-radius:3px"></div>`;
    h+='</div>';
    h+=`<div style="font-size:.6rem;color:var(--text-secondary);margin-top:4px;text-align:center;writing-mode:vertical-rl;height:60px">${{v.name}}</div>`;
    h+='</div>';
  }}
  h+='</div></div>';
  h+='<p style="font-size:.75rem;color:var(--text-secondary)">Solid = indicators with 2020+ data. Faded = older data only.</p>';

  // Table of shared indicators
  h+='<h3 style="margin-top:1.5rem">Indicator availability</h3>';
  const allInds=new Set();
  for(const c of countries){{
    const detail=D[c].detail[goalNum]||[];
    for(const ind of detail) allInds.add(ind.c);
  }}
  const indList=[...allInds].sort();
  if(indList.length>0){{
    h+='<div style="overflow-x:auto"><table><tr><th>Indicator</th>';
    for(const c of countries) h+=`<th style="font-size:.7rem;writing-mode:vertical-rl;max-width:30px">${{c}}</th>`;
    h+='</tr>';
    for(const ind of indList.slice(0,30)){{
      h+=`<tr><td style="font-size:.78rem;white-space:nowrap">${{ind}}</td>`;
      for(const c of countries){{
        const detail=D[c].detail[goalNum]||[];
        const found=detail.find(d=>d.c===ind);
        if(found){{
          const recent=found.ly&&found.ly>=2020;
          h+=`<td style="text-align:center;font-size:.75rem;background:${{recent?COLORS[goalNum]+'20':COLORS[goalNum]+'10'}};color:${{recent?COLORS[goalNum]:'var(--text-secondary)'}}" title="${{found.lv}} (${{found.ly}})">${{found.ly||'?'}}</td>`;
        }}else{{
          h+='<td style="text-align:center;color:var(--text-secondary);font-size:.7rem">—</td>';
        }}
      }}
      h+='</tr>';
    }}
    if(indList.length>30) h+=`<tr><td colspan="${{countries.length+1}}" style="font-size:.78rem;color:var(--text-secondary)">…and ${{indList.length-30}} more indicators</td></tr>`;
    h+='</table></div>';
  }}else{{
    h+='<p style="color:var(--text-secondary);font-size:.85rem">No indicators with data for this goal across any Pacific country.</p>';
  }}

  el.innerHTML=h;
}}

// URL params
const params=new URLSearchParams(location.search);
if(params.get('country')){{
  document.getElementById('country-sel').value=params.get('country');
  showTab2('country');
  renderCountry(params.get('country'));
}}
if(params.get('goal')){{
  document.getElementById('goal-sel').value=params.get('goal');
  showTab2('compare');
  renderCompare(params.get('goal'));
}}
</script>
</body>
</html>"""

os.makedirs(SITE, exist_ok=True)
with open(os.path.join(SITE, "sdg-progress.html"), "w") as f:
    f.write(html)

n_with_data = sum(1 for c in countries.values()
                  for s in c["summary"].values() if s["n_ind"] > 0)
print(f"Wrote sdg-progress.html: {n_countries} countries, {total_records:,} data points, {n_with_data} goal-country pairs with data")
