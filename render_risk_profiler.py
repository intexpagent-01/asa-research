#!/usr/bin/env python3
"""Render site/risk-profiler.html: Project Risk Profiler from WB ICR evaluations."""
import os, re, json, datetime as dt
from collections import Counter, defaultdict
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

CORPUS_CANDIDATES = [
    os.path.join(os.path.dirname(HERE), "experiments", "wb-icr-global-1000.json"),
    os.path.join(os.path.dirname(HERE), "experiments", "wb-icr-global-300.json"),
]
DATA_FILE = next((f for f in CORPUS_CANDIDATES if os.path.exists(f)), CORPUS_CANDIDATES[-1])
with open(DATA_FILE) as f:
    corpus = json.load(f)

projects = corpus["projects"]
synth = corpus["synthesis"]
all_lessons = synth["all_lessons"]
today = dt.date.today().isoformat()

SECTOR_MAP = {
    "Health": ["Health", "health", "Public Administration - Health", "Nutrition"],
    "Education": ["Education", "education", "Public Administration - Education"],
    "Agriculture": ["Agriculture", "agriculture", "Fishing", "Forestry", "Agricultural", "Agri", "Livestock", "Crops", "Irrigation"],
    "Transport": ["Transport", "Roads", "road", "Aviation", "Ports", "Railway", "Shipping"],
    "Water & Sanitation": ["Water Supply", "Sanitation", "Waste", "Sewerage", "Other Water"],
    "Energy": ["Energy", "Power", "Electricity", "Renewable", "Thermal", "Hydropower", "Solar"],
    "Social Protection": ["Social Protection", "Social Assistance", "Safety Net", "Pension"],
    "Governance": ["Central Government", "Sub-National", "Public Administration", "Judicial", "Legal"],
    "Finance": ["Banking", "Financial", "Finance", "Microfinance", "Insurance", "Capital Markets"],
    "Trade & Industry": ["Trade", "Industry", "Manufacturing", "Mining", "SME", "Enterprise"],
    "Environment": ["Climate", "Environment", "Biodiversity", "Disaster", "Flood", "Natural Resource"],
    "ICT": ["Information", "ICT", "Digital", "Telecom", "E-Government"],
    "Urban Development": ["Urban", "Housing", "Land Administration", "Municipal"],
}

def categorize_sectors(sector_list):
    cats = set()
    for s in sector_list:
        sl = s.lower()
        for cat, keywords in SECTOR_MAP.items():
            if any(kw.lower() in sl for kw in keywords):
                cats.add(cat)
                break
    return sorted(cats) if cats else ["Other"]

FAIL_SET = {"unsatisfactory", "highly unsatisfactory", "moderately unsatisfactory"}
SUCCESS_SET = {"satisfactory", "highly satisfactory"}

# Build compact project data for embedding
slim_projects = []
for p in projects:
    cats = categorize_sectors(p.get("sectors", []))
    region = p.get("region", "")
    outcome = p.get("outcome_rating", "")
    score = p.get("outcome_score")
    lessons_data = []
    for l_text in p.get("lessons", []):
        if len(l_text) > 40:
            lessons_data.append(l_text[:400])
    slim_projects.append({
        "s": cats,
        "r": region,
        "o": outcome,
        "sc": score,
        "t": p.get("title", "")[:120],
        "c": p.get("country", ""),
        "pid": p.get("project_id", ""),
        "l": lessons_data[:5],
    })

n_projects = len(projects)
n_countries = len(set(p.get("country", "") for p in projects if p.get("country")))
n_lessons = len(all_lessons)

# Global stats
global_scores = [p.get("outcome_score") for p in projects if p.get("outcome_score")]
global_avg = sum(global_scores) / len(global_scores) if global_scores else 0
global_sat_pct = len([s for s in global_scores if s >= 4]) / len(global_scores) * 100 if global_scores else 0

# Sector stats for overview
sector_stats = {}
for cat in sorted(SECTOR_MAP.keys()):
    cat_projects = [p for p in slim_projects if cat in p["s"]]
    if not cat_projects:
        continue
    scores = [p["sc"] for p in cat_projects if p["sc"]]
    if not scores:
        continue
    sector_stats[cat] = {
        "n": len(cat_projects),
        "avg": round(sum(scores) / len(scores), 2),
        "sat_pct": round(len([s for s in scores if s >= 4]) / len(scores) * 100),
        "fail_pct": round(len([s for s in scores if s <= 2]) / len(scores) * 100),
    }

# Region stats
region_stats = {}
for p in slim_projects:
    r = p["r"]
    if not r or r == "Other":
        continue
    if r not in region_stats:
        region_stats[r] = {"scores": []}
    if p["sc"]:
        region_stats[r]["scores"].append(p["sc"])

for r in region_stats:
    scores = region_stats[r]["scores"]
    region_stats[r] = {
        "n": len(scores),
        "avg": round(sum(scores) / len(scores), 2) if scores else 0,
        "sat_pct": round(len([s for s in scores if s >= 4]) / len(scores) * 100) if scores else 0,
    }

all_regions = sorted(set(p["r"] for p in slim_projects if p["r"] and p["r"] != "Other"))
all_sectors = sorted(SECTOR_MAP.keys())

projects_json = json.dumps(slim_projects, separators=(",", ":"))

# Pre-compute the sector stats overview HTML
sector_rows = ""
for cat in sorted(sector_stats.keys(), key=lambda c: sector_stats[c]["sat_pct"]):
    s = sector_stats[cat]
    bar_color = "#27ae60" if s["sat_pct"] >= 80 else "#f39c12" if s["sat_pct"] >= 65 else "#e74c3c"
    sector_rows += f"""<tr>
<td style="font-weight:600">{esc(cat)}</td>
<td style="text-align:center">{s["n"]}</td>
<td style="text-align:center">{s["avg"]}</td>
<td><div style="display:flex;align-items:center;gap:8px"><div style="width:{s["sat_pct"]}%;height:18px;background:{bar_color};border-radius:4px;min-width:2px"></div><span style="font-size:0.85rem">{s["sat_pct"]}%</span></div></td>
<td style="text-align:center;color:{'#e74c3c' if s['fail_pct'] > 15 else '#666'}">{s["fail_pct"]}%</td>
</tr>"""

region_rows = ""
for r in sorted(region_stats.keys(), key=lambda x: region_stats[x]["sat_pct"]):
    s = region_stats[r]
    bar_color = "#27ae60" if s["sat_pct"] >= 80 else "#f39c12" if s["sat_pct"] >= 65 else "#e74c3c"
    region_rows += f"""<tr>
<td style="font-weight:600">{esc(r)}</td>
<td style="text-align:center">{s["n"]}</td>
<td style="text-align:center">{s["avg"]}</td>
<td><div style="display:flex;align-items:center;gap:8px"><div style="width:{s["sat_pct"]}%;height:18px;background:{bar_color};border-radius:4px;min-width:2px"></div><span style="font-size:0.85rem">{s["sat_pct"]}%</span></div></td>
</tr>"""

sector_options = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in all_sectors)
region_options = "".join(f'<option value="{esc(r)}">{esc(r)}</option>' for r in all_regions)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Project Risk Profiler — Asa</title>
<meta name="description" content="Assess project risk using historical outcome data from {n_projects} World Bank project evaluations. Select a sector and region to see success rates, failure patterns, and lessons.">
<meta name="robots" content="index, follow">
<style>
{style}
.profiler-controls {{ max-width: 800px; margin: 0 auto 2rem; }}
.control-row {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; align-items: center; }}
.control-row select {{ padding: 10px 14px; border-radius: 8px; border: 2px solid #0d7377; font-size: 1rem; background: #fff; cursor: pointer; min-width: 200px; }}
.control-row select:focus {{ border-color: #e05a3a; box-shadow: 0 0 0 3px rgba(224,90,58,0.15); outline: none; }}
.control-row button {{ padding: 10px 20px; border-radius: 8px; border: none; background: #0d7377; color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer; }}
.control-row button:hover {{ background: #0a5c5f; }}
.risk-panel {{ max-width: 800px; margin: 0 auto; padding: 24px; background: #f8f9fa; border-radius: 12px; border: 1px solid #eee; }}
.risk-header {{ display: flex; align-items: center; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }}
.risk-gauge {{ width: 120px; height: 120px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-direction: column; flex-shrink: 0; }}
.risk-gauge .pct {{ font-size: 2rem; font-weight: 700; }}
.risk-gauge .lbl {{ font-size: 0.75rem; opacity: 0.8; }}
.risk-title {{ flex: 1; }}
.risk-title h3 {{ margin: 0 0 6px; font-size: 1.3rem; }}
.risk-title p {{ margin: 0; color: #666; font-size: 0.95rem; }}
.dist-row {{ display: flex; height: 28px; border-radius: 6px; overflow: hidden; margin: 16px 0 8px; }}
.dist-seg {{ display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 600; color: #fff; min-width: 1px; }}
.dist-legend {{ display: flex; flex-wrap: wrap; gap: 10px; font-size: 0.82rem; color: #666; margin-bottom: 20px; }}
.dist-legend span::before {{ content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }}
.pattern-section {{ margin: 20px 0 0; }}
.pattern-section h4 {{ font-size: 1.05rem; margin: 0 0 12px; color: #0d7377; }}
.lesson-item {{ padding: 12px 16px; margin: 8px 0; background: #fff; border-radius: 8px; border-left: 4px solid #0d7377; font-size: 0.9rem; line-height: 1.5; }}
.lesson-item.fail {{ border-left-color: #e74c3c; }}
.lesson-item .meta {{ font-size: 0.78rem; color: #999; margin-top: 6px; }}
.lesson-item .meta a {{ color: #0d7377; }}
.comparison-bar {{ display: flex; align-items: center; gap: 10px; margin: 6px 0; }}
.comparison-bar .bar-track {{ flex: 1; height: 20px; background: #eee; border-radius: 4px; position: relative; }}
.comparison-bar .bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
.comparison-bar .bar-label {{ font-size: 0.82rem; min-width: 50px; }}
.comparison-bar .marker {{ position: absolute; top: -4px; bottom: -4px; width: 3px; background: #333; border-radius: 2px; }}
.no-data {{ text-align: center; padding: 40px; color: #999; font-size: 1.1rem; }}
.overview-table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
.overview-table th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid #0d7377; font-size: 0.9rem; color: #0d7377; }}
.overview-table td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.9rem; }}
.overview-table tr:hover {{ background: #f0f8f8; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin: 20px 0; }}
.stat-card {{ text-align: center; padding: 16px; background: #f8f9fa; border-radius: 10px; border: 1px solid #eee; }}
.stat-card .num {{ font-size: 1.8rem; font-weight: 700; color: #0d7377; }}
.stat-card .label {{ font-size: 0.82rem; color: #666; margin-top: 4px; }}
@media (prefers-color-scheme: dark) {{
  .risk-panel {{ background: #1a1a2e; border-color: #333; }}
  .lesson-item {{ background: #16213e; }}
  .overview-table th {{ border-bottom-color: #0d7377; }}
  .overview-table tr:hover {{ background: #16213e; }}
  .control-row select {{ background: #16213e; color: #e0e0e0; border-color: #0d7377; }}
  .stat-card {{ background: #1a1a2e; border-color: #333; }}
  .comparison-bar .bar-track {{ background: #333; }}
}}
</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#0d7377,#14919b);height:4px"></div>
<div style="max-width:900px;margin:0 auto;padding:2rem 1.5rem">

<p style="margin:0 0 4px"><a href="index.html" style="color:#0d7377;text-decoration:none;font-size:0.9rem">&larr; Home</a>
&nbsp; <a href="lessons-engine.html" style="color:#0d7377;text-decoration:none;font-size:0.9rem">Lessons Engine</a>
&nbsp; <a href="pipeline.html" style="color:#0d7377;text-decoration:none;font-size:0.9rem">Pipeline</a></p>

<h1 style="font-size:2rem;margin:0.5rem 0">Project Risk Profiler</h1>
<p style="color:#666;font-size:1.05rem;margin:0 0 1.5rem">Assess project risk using historical outcomes from <strong>{n_projects}</strong> World Bank evaluations across <strong>{n_countries}</strong> countries. Select a sector and region to see what typically succeeds, what fails, and why.</p>

<div class="stats-grid">
<div class="stat-card"><div class="num">{n_projects}</div><div class="label">Evaluated projects</div></div>
<div class="stat-card"><div class="num">{n_lessons:,}</div><div class="label">Lessons extracted</div></div>
<div class="stat-card"><div class="num">{global_sat_pct:.0f}%</div><div class="label">Global success rate</div></div>
<div class="stat-card"><div class="num">{global_avg:.1f}/6</div><div class="label">Average outcome</div></div>
</div>

<div class="profiler-controls">
<h2 style="font-size:1.3rem;margin:1.5rem 0 0.5rem">Select a project profile</h2>
<div class="control-row">
<select id="sector-select"><option value="">All sectors</option>{sector_options}</select>
<select id="region-select"><option value="">All regions</option>{region_options}</select>
<button onclick="updateProfile()">Analyze risk</button>
</div>
</div>

<div id="profile-output"></div>

<h2 style="font-size:1.3rem;margin:2rem 0 0.5rem">Historical success rates by sector</h2>
<p style="font-size:0.9rem;color:#666;margin:0 0 8px">Sorted by success rate (% rated Satisfactory or above). Global average: {global_sat_pct:.0f}%.</p>
<table class="overview-table">
<tr><th>Sector</th><th style="text-align:center">Projects</th><th style="text-align:center">Avg score</th><th>Success rate</th><th style="text-align:center">Fail rate</th></tr>
{sector_rows}
</table>

<h2 style="font-size:1.3rem;margin:2rem 0 0.5rem">Historical success rates by region</h2>
<table class="overview-table">
<tr><th>Region</th><th style="text-align:center">Projects</th><th style="text-align:center">Avg score</th><th>Success rate</th></tr>
{region_rows}
</table>

<hr style="margin:2rem 0;border:none;border-top:1px solid #eee">
<p style="font-size:0.82rem;color:#999">
Data: {n_projects} World Bank ICR (Implementation Completion and Results) Reviews accessed via the <a href="https://documents.worldbank.org" style="color:#0d7377">WB Documents API</a>.
Success = rated Satisfactory or Highly Satisfactory. Fail = rated Unsatisfactory or Highly Unsatisfactory.
Sector categories are mapped from WB sector classifications. A project may appear in multiple sectors.
Updated {today}. Built by <a href="about.html" style="color:#0d7377">Asa</a>, an autonomous AI agent.
</p>
</div>

<script>
const P={projects_json};
const FAIL=new Set(["unsatisfactory","highly unsatisfactory","moderately unsatisfactory"]);
const SUCC=new Set(["satisfactory","highly satisfactory"]);
const RATINGS={{"highly satisfactory":6,"satisfactory":5,"moderately satisfactory":4,"moderately unsatisfactory":3,"unsatisfactory":2,"highly unsatisfactory":1}};
const COLORS={{"highly satisfactory":"#1a7a3a","satisfactory":"#27ae60","moderately satisfactory":"#f39c12","moderately unsatisfactory":"#e67e22","unsatisfactory":"#e74c3c","highly unsatisfactory":"#8b0000"}};
const GLOBAL_SAT={global_sat_pct:.1f};
const GLOBAL_AVG={global_avg:.2f};

function updateProfile(){{
  const sec=document.getElementById("sector-select").value;
  const reg=document.getElementById("region-select").value;
  const out=document.getElementById("profile-output");

  let filtered=P;
  if(sec) filtered=filtered.filter(p=>p.s.includes(sec));
  if(reg) filtered=filtered.filter(p=>p.r===reg);

  if(filtered.length<3){{
    out.innerHTML='<div class="no-data">Not enough data for this combination. Try a broader selection.</div>';
    return;
  }}

  const scores=filtered.filter(p=>p.sc).map(p=>p.sc);
  const avg=scores.reduce((a,b)=>a+b,0)/scores.length;
  const satPct=Math.round(scores.filter(s=>s>=4).length/scores.length*100);
  const failPct=Math.round(scores.filter(s=>s<=2).length/scores.length*100);

  // Outcome distribution
  const dist={{}};
  filtered.forEach(p=>{{if(p.o)dist[p.o]=(dist[p.o]||0)+1;}});
  const ratingOrder=["highly satisfactory","satisfactory","moderately satisfactory","moderately unsatisfactory","unsatisfactory","highly unsatisfactory"];
  const total=filtered.length;

  let distHTML='<div class="dist-row">';
  ratingOrder.forEach(r=>{{
    const n=dist[r]||0;
    if(n>0){{
      const pct=n/total*100;
      distHTML+=`<div class="dist-seg" style="width:${{pct}}%;background:${{COLORS[r]}}">${{pct>=8?n:""}}</div>`;
    }}
  }});
  distHTML+='</div><div class="dist-legend">';
  ratingOrder.forEach(r=>{{
    const n=dist[r]||0;
    if(n>0) distHTML+=`<span style="--c:${{COLORS[r]}}"><span style="background:${{COLORS[r]}};width:10px;height:10px;display:inline-block;border-radius:2px;margin-right:4px;vertical-align:middle"></span>${{r}} (${{n}})</span>`;
  }});
  distHTML+='</div>';

  // Gauge color
  const gaugeColor=satPct>=80?"#27ae60":satPct>=65?"#f39c12":"#e74c3c";
  const riskLevel=satPct>=80?"Lower risk":satPct>=65?"Moderate risk":"Higher risk";

  // Comparison to global
  const label=sec?(reg?`${{sec}} in ${{reg}}`:sec):(reg||"All projects");
  const compHTML=`
    <div style="margin:16px 0">
      <div style="font-size:0.9rem;font-weight:600;margin-bottom:8px">Compared to global average (${{GLOBAL_SAT.toFixed(0)}}% success rate)</div>
      <div class="comparison-bar">
        <div class="bar-label" style="font-weight:600;color:${{gaugeColor}}">${{satPct}}%</div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${{satPct}}%;background:${{gaugeColor}}"></div>
          <div class="marker" style="left:${{GLOBAL_SAT}}%;background:#333" title="Global average: ${{GLOBAL_SAT.toFixed(0)}}%"></div>
        </div>
      </div>
      <div style="font-size:0.78rem;color:#999;margin-top:2px">Black marker = global average. ${{satPct>GLOBAL_SAT?satPct-GLOBAL_SAT.toFixed(0)+" points above average":GLOBAL_SAT.toFixed(0)-satPct+" points below average"}}.</div>
    </div>`;

  // Failure lessons
  const failProjects=filtered.filter(p=>FAIL.has(p.o));
  const succProjects=filtered.filter(p=>SUCC.has(p.o));

  let failLessons=[];
  failProjects.forEach(p=>{{
    p.l.forEach(l=>failLessons.push({{text:l,title:p.t,country:p.c,pid:p.pid}}));
  }});

  let succLessons=[];
  succProjects.forEach(p=>{{
    p.l.forEach(l=>succLessons.push({{text:l,title:p.t,country:p.c,pid:p.pid}}));
  }});

  const renderLessons=(lessons,cls,max)=>{{
    if(lessons.length===0) return '<p style="color:#999;font-size:0.9rem">No lessons in this category for the selected combination.</p>';
    return lessons.slice(0,max).map(l=>{{
      const link=l.pid?` <a href="https://projects.worldbank.org/en/projects-operations/project-detail/${{l.pid}}" target="_blank" rel="noopener">${{l.pid}}</a>`:"";
      return `<div class="lesson-item ${{cls}}"><div>${{escHTML(l.text)}}</div><div class="meta">${{escHTML(l.title)}} &mdash; ${{escHTML(l.country)}}${{link}}</div></div>`;
    }}).join("")+(lessons.length>max?`<p style="font-size:0.85rem;color:#666">+ ${{lessons.length-max}} more lessons in this category</p>`:"");
  }};

  out.innerHTML=`
    <div class="risk-panel">
      <div class="risk-header">
        <div class="risk-gauge" style="background:${{gaugeColor}}20;border:3px solid ${{gaugeColor}}">
          <div class="pct" style="color:${{gaugeColor}}">${{satPct}}%</div>
          <div class="lbl" style="color:${{gaugeColor}}">success</div>
        </div>
        <div class="risk-title">
          <h3>${{escHTML(label)}}</h3>
          <p>${{filtered.length}} evaluated projects &middot; Avg outcome ${{avg.toFixed(1)}}/6 &middot; ${{riskLevel}}</p>
          <p style="font-size:0.85rem;margin-top:4px">${{failProjects.length}} failed (${{failPct}}%) &middot; ${{succProjects.length}} succeeded &middot; ${{filtered.length-failProjects.length-succProjects.length}} moderate</p>
        </div>
      </div>
      ${{distHTML}}
      ${{compHTML}}
      <div class="pattern-section">
        <h4 style="color:#e74c3c">&#9888; Lessons from failed projects (${{failProjects.length}})</h4>
        ${{renderLessons(failLessons,"fail",5)}}
      </div>
      <div class="pattern-section">
        <h4 style="color:#27ae60">&#10003; Lessons from successful projects (${{succProjects.length}})</h4>
        ${{renderLessons(succLessons,"",5)}}
      </div>
    </div>`;

  // Update URL
  const params=new URLSearchParams();
  if(sec) params.set("sector",sec);
  if(reg) params.set("region",reg);
  const qs=params.toString();
  history.replaceState(null,"",qs?("?"+qs):location.pathname);
}}

function escHTML(s){{
  const d=document.createElement("div");
  d.textContent=s;
  return d.innerHTML;
}}

// On load: check URL params
(function(){{
  const params=new URLSearchParams(location.search);
  const sec=params.get("sector");
  const reg=params.get("region");
  if(sec) document.getElementById("sector-select").value=sec;
  if(reg) document.getElementById("region-select").value=reg;
  if(sec||reg) updateProfile();
}})();
</script>
</body>
</html>"""

os.makedirs(SITE, exist_ok=True)
with open(os.path.join(SITE, "risk-profiler.html"), "w") as f:
    f.write(html)
print(f"rendered {os.path.join(SITE, 'risk-profiler.html')} {len(html)//1024}KB")
