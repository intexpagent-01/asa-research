#!/usr/bin/env python3
"""Render site/evidence.html: Development Evidence Explorer.

Problem-focused: starts from a development problem (topic + region),
shows what global evaluation evidence says about it.
"""
import os, re, json, datetime as dt
from xml.sax.saxutils import escape as esc
from collections import Counter, defaultdict

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

REGIONS = [
    "East Asia and Pacific",
    "South Asia",
    "Sub-Saharan Africa",
    "Latin America & Caribbean",
    "Middle East & North Africa",
    "Europe & Central Asia",
]

REGION_LOOKUP = {}
COUNTRY_REGIONS_MAP = {
    "East Asia and Pacific": ["China", "Indonesia", "Philippines", "Vietnam", "Thailand", "Myanmar", "Cambodia", "Lao", "Mongolia", "Papua New Guinea", "Fiji", "Samoa", "Tonga", "Vanuatu", "Solomon Islands", "Timor-Leste", "Malaysia", "Korea", "Pacific Islands", "Kiribati", "Marshall Islands", "Micronesia", "Nauru", "Niue", "Cook Islands", "Tuvalu", "Palau"],
    "South Asia": ["India", "Bangladesh", "Pakistan", "Nepal", "Sri Lanka", "Afghanistan", "Bhutan", "Maldives"],
    "Sub-Saharan Africa": ["Nigeria", "Kenya", "Ethiopia", "Tanzania", "Ghana", "Uganda", "Mozambique", "Zambia", "Zimbabwe", "Malawi", "Mali", "Senegal", "Cameroon", "Cote d'Ivoire", "Ivory Coast", "Madagascar", "Democratic Republic of Congo", "Congo", "Burkina Faso", "Niger", "Chad", "Rwanda", "Benin", "Guinea", "Sierra Leone", "Togo", "Liberia", "Mauritania", "Gambia", "Lesotho", "Eswatini", "Botswana", "Namibia", "South Africa", "Eritrea", "Somalia", "South Sudan", "Central African Republic", "Burundi", "Angola", "Cabo Verde", "Cape Verde", "Comoros", "Djibouti", "Equatorial Guinea", "Gabon", "Guinea-Bissau", "Mauritius", "Sao Tome", "Seychelles"],
    "Latin America & Caribbean": ["Brazil", "Mexico", "Colombia", "Peru", "Argentina", "Chile", "Ecuador", "Bolivia", "Paraguay", "Uruguay", "Venezuela", "Guatemala", "Honduras", "El Salvador", "Nicaragua", "Costa Rica", "Panama", "Dominican Republic", "Haiti", "Jamaica", "Trinidad", "Guyana", "Suriname", "Belize", "Barbados"],
    "Middle East & North Africa": ["Egypt", "Morocco", "Tunisia", "Jordan", "Lebanon", "Iraq", "Yemen", "Algeria", "Libya", "Iran", "West Bank", "Gaza", "Palestine", "Djibouti"],
    "Europe & Central Asia": ["Turkey", "Ukraine", "Romania", "Poland", "Kazakhstan", "Uzbekistan", "Georgia", "Armenia", "Azerbaijan", "Moldova", "Kyrgyz", "Tajikistan", "Turkmenistan", "Albania", "Bosnia", "Serbia", "Montenegro", "North Macedonia", "Kosovo", "Belarus", "Russia", "Croatia", "Bulgaria"],
}
for reg, countries in COUNTRY_REGIONS_MAP.items():
    for c in countries:
        REGION_LOOKUP[c.lower()] = reg

def infer_region(country, api_region=""):
    if api_region:
        return api_region
    if not country:
        return ""
    cl = country.lower()
    for k, v in REGION_LOOKUP.items():
        if k in cl or cl in k:
            return v
    return ""

SECTOR_KEYWORDS = {
    "WASH": ["wash", "water supply", "water service", "sanitation", "hygiene", "sewage", "sewerage", "latrine", "borehole", "handwashing", "drinking water", "wastewater", "water point"],
    "health": ["health", "hospital", "clinic", "maternal", "malaria", "hiv", "aids", "tuberculosis", "nutrition", "vaccine", "immunization", "pharmaceutical", "epidemi"],
    "education": ["education", "school", "teacher", "student", "learning", "literacy", "curriculum", "classroom", "university", "tertiary", "primary education", "secondary education", "vocational training"],
    "livelihoods": ["livelihood", "income", "employment", "job", "enterprise", "small business", "microfinance", "micro-finance", "self-employment", "cash crop", "fishing", "livestock", "poultry", "artisan"],
    "agriculture": ["agricultur", "farm", "irrigation", "crop", "harvest", "seed", "fertilizer", "agri-business", "agribusiness", "horticultur", "pastoral", "rice", "wheat", "maize", "food security", "food production"],
    "transport": ["transport", "road", "highway", "bridge", "port", "airport", "railway", "rail", "bus", "ferry", "logistics", "freight"],
    "energy": ["energy", "electri", "solar", "wind power", "hydropower", "geothermal", "power grid", "power plant", "renewable", "fossil fuel", "biomass", "off-grid"],
    "governance": ["governance", "public sector", "civil service", "anti-corruption", "transparency", "accountability", "decentralization", "municipal", "local government", "public administration", "judicial", "rule of law", "parliament"],
}

OUTCOME_LABELS = {
    6: "Highly satisfactory",
    5: "Satisfactory",
    4: "Moderately satisfactory",
    3: "Moderately unsatisfactory",
    2: "Unsatisfactory",
    1: "Highly unsatisfactory",
}
OUTCOME_COLORS = {
    6: "#2d8659",
    5: "#4caf50",
    4: "#8bc34a",
    3: "#ff9800",
    2: "#f44336",
    1: "#b71c1c",
}

# Prepare data for embedding
slim_lessons = []
for i, l in enumerate(all_lessons):
    region = l.get("region") or infer_region(l["country"])
    sectors = []
    combined = (l["text"] + " " + l["project"]).lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                sectors.append(sector)
                break
    slim_lessons.append({
        "i": i,
        "t": l["text"][:500],
        "p": l["project"],
        "o": l.get("outcome_score"),
        "c": l["country"],
        "r": region,
        "g": l["tags"],
        "x": sectors,
    })

all_tags = sorted(synth.get("tag_distribution", {}).keys())
all_sectors = sorted(SECTOR_KEYWORDS.keys())
all_countries = sorted(set(l["c"] for l in slim_lessons if l["c"]))

tag_dist = synth.get("tag_distribution", {})
n_projects = len(projects)
n_lessons = len(all_lessons)
n_countries = len(all_countries)
today = dt.date.today().isoformat()

extra_css = """
.container{max-width:820px}
h1{font-size:1.6rem;margin-bottom:.2rem}
.subtitle{font-size:1rem;color:var(--text-secondary);margin-bottom:1.5rem;line-height:1.5}
.filters{display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1.5rem;align-items:end}
.filter-group{display:flex;flex-direction:column;gap:.25rem}
.filter-group label{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted)}
.filter-group select{font:inherit;font-size:.9rem;padding:.5rem .7rem;border:1px solid var(--border);border-radius:6px;background:var(--surface-card);color:var(--text-primary);min-width:180px;cursor:pointer}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem;margin-bottom:1.5rem}
.metric{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem;text-align:center}
.metric .val{font-size:1.5rem;font-weight:800;color:var(--series-1);line-height:1.1}
.metric .lbl{font-size:.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;margin-top:.2rem}
.section{margin-bottom:1.8rem}
.section h2{font-size:1rem;margin-bottom:.7rem;font-weight:700}
.bar-chart{margin:.5rem 0}
.bar-row{display:flex;align-items:center;gap:.5rem;margin-bottom:.35rem;font-size:.82rem}
.bar-label{min-width:160px;text-align:right;color:var(--text-secondary);font-size:.78rem}
.bar-track{flex:1;height:22px;background:var(--gridline);border-radius:4px;overflow:hidden;position:relative}
.bar-fill{height:100%;border-radius:4px;transition:width .3s}
.bar-val{font-size:.78rem;color:var(--text-muted);min-width:36px}
.lesson-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin-bottom:.5rem;font-size:.85rem;line-height:1.5}
.lesson-card .meta{font-size:.72rem;color:var(--text-muted);margin-top:.3rem}
.lesson-card .meta span{margin-right:.8rem}
.success-badge{display:inline-block;font-size:.65rem;font-weight:700;padding:.1rem .4rem;border-radius:3px;margin-right:.4rem;vertical-align:middle}
.badge-success{background:#e8f5e9;color:#2e7d32}
.badge-caution{background:#fff3e0;color:#e65100}
.region-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.5rem}
.region-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.7rem .9rem}
.region-card .name{font-size:.85rem;font-weight:600;margin-bottom:.2rem}
.region-card .stats{font-size:.78rem;color:var(--text-secondary);line-height:1.5}
.region-card .rate{font-size:1.1rem;font-weight:700;float:right;margin-top:.2rem}
.empty-state{text-align:center;padding:2rem;color:var(--text-muted);font-size:.9rem}
.more-link{font-size:.82rem;color:var(--series-1);cursor:pointer;margin-top:.3rem;display:inline-block}
footer{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--gridline);font-size:.75rem;color:var(--text-muted)}
@media(max-width:600px){
 .metrics{grid-template-columns:repeat(2,1fr)}
 .filters{flex-direction:column}
 .bar-label{min-width:100px;font-size:.72rem}
 .region-grid{grid-template-columns:1fr}
}
"""

data_json = json.dumps(slim_lessons, separators=(",", ":"))
tags_json = json.dumps(all_tags)
sectors_json = json.dumps(all_sectors)
regions_json = json.dumps(REGIONS)
outcome_labels_json = json.dumps(OUTCOME_LABELS)
outcome_colors_json = json.dumps(OUTCOME_COLORS)

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Development Evidence Explorer &mdash; Asa</title>
<meta name="description" content="What does global evaluation evidence say about development problems? Explore {n_lessons:,} lessons from {n_projects:,} World Bank projects across {n_countries} countries.">
<style>{style}{extra_css}</style></head><body>
<div class="container">
<p style="margin-bottom:.3rem"><a href="index.html" style="font-size:.82rem;color:var(--text-muted)">&larr; Home</a></p>
<h1>Development Evidence Explorer</h1>
<p class="subtitle">What does global evaluation evidence say about development problems?<br>
<span style="font-size:.85rem">{n_lessons:,} lessons from {n_projects:,} independently evaluated World Bank projects across {n_countries} countries.</span></p>

<div class="filters">
 <div class="filter-group">
  <label>Development problem</label>
  <select id="topic">
   <option value="">All topics</option>
   <optgroup label="Thematic areas">"""

for tag in sorted(all_tags, key=lambda t: -tag_dist.get(t, 0)):
    html += f'\n   <option value="tag:{esc(tag)}">{esc(tag.title())} ({tag_dist.get(tag, 0)})</option>'

html += '</optgroup>\n   <optgroup label="Sectors">'
for sec in sorted(all_sectors):
    cnt = sum(1 for l in slim_lessons if sec in l["x"])
    html += f'\n   <option value="sec:{esc(sec)}">{esc(sec.title() if sec != "WASH" else "WASH")} ({cnt})</option>'

html += f"""</optgroup>
  </select>
 </div>
 <div class="filter-group">
  <label>Region</label>
  <select id="region">
   <option value="">All regions</option>"""

for r in REGIONS:
    cnt = sum(1 for l in slim_lessons if l["r"] == r)
    html += f'\n   <option value="{esc(r)}">{esc(r)} ({cnt})</option>'

html += f"""
  </select>
 </div>
</div>

<div id="metrics" class="metrics"></div>

<div class="section">
 <h2>Outcome distribution</h2>
 <p style="font-size:.78rem;color:var(--text-muted);margin-bottom:.5rem">How did projects addressing this problem perform?</p>
 <div id="outcome-chart" class="bar-chart"></div>
</div>

<div class="section">
 <h2 id="works-title">What works</h2>
 <p style="font-size:.78rem;color:var(--text-muted);margin-bottom:.5rem">Lessons from projects rated satisfactory or above</p>
 <div id="works"></div>
</div>

<div class="section">
 <h2 id="pitfalls-title">Common pitfalls</h2>
 <p style="font-size:.78rem;color:var(--text-muted);margin-bottom:.5rem">Lessons from projects that fell short</p>
 <div id="pitfalls"></div>
</div>

<div class="section">
 <h2>Regional patterns</h2>
 <p style="font-size:.78rem;color:var(--text-muted);margin-bottom:.5rem">Where is the evidence strongest? Where do outcomes differ?</p>
 <div id="regions" class="region-grid"></div>
</div>

<footer>
 Source: World Bank Independent Evaluation Group, Implementation Completion and Results Reports (ICR Reviews).<br>
 {n_projects:,} projects evaluated across {n_countries} countries. Evidence extracted and synthesized by Asa.<br>
 Generated {today}. <a href="lessons-engine.html">Search individual lessons</a> &middot;
 <a href="index.html">Home</a>
</footer>
</div>

<script>
const D={data_json};
const OLABELS={outcome_labels_json};
const OCOLORS={outcome_colors_json};
const REGIONS={regions_json};

function filter(){{
 const tv=document.getElementById("topic").value;
 const rv=document.getElementById("region").value;
 let f=D;
 if(rv) f=f.filter(l=>l.r===rv);
 if(tv){{
  if(tv.startsWith("tag:")){{
   const tag=tv.slice(4);
   f=f.filter(l=>l.g&&l.g.includes(tag));
  }}else if(tv.startsWith("sec:")){{
   const sec=tv.slice(4);
   f=f.filter(l=>l.x&&l.x.includes(sec));
  }}
 }}
 render(f);
}}

function render(lessons){{
 const n=lessons.length;
 const countries=new Set(lessons.map(l=>l.c).filter(Boolean));
 const withScore=lessons.filter(l=>l.o!=null);
 const success=withScore.filter(l=>l.o>=4);
 const successRate=withScore.length?Math.round(100*success.length/withScore.length):0;
 const avgScore=withScore.length?(withScore.reduce((a,l)=>a+l.o,0)/withScore.length).toFixed(1):"—";

 document.getElementById("metrics").innerHTML=
  `<div class="metric"><div class="val">${{n.toLocaleString()}}</div><div class="lbl">Lessons</div></div>`+
  `<div class="metric"><div class="val">${{countries.size}}</div><div class="lbl">Countries</div></div>`+
  `<div class="metric"><div class="val">${{successRate}}%</div><div class="lbl">Success rate</div></div>`+
  `<div class="metric"><div class="val">${{avgScore}}</div><div class="lbl">Avg score (1–6)</div></div>`;

 // Outcome distribution
 const dist={{}};
 for(let s=6;s>=1;s--) dist[s]=0;
 withScore.forEach(l=>dist[l.o]=(dist[l.o]||0)+1);
 const maxCount=Math.max(...Object.values(dist),1);
 let chartHtml="";
 for(let s=6;s>=1;s--){{
  const pct=Math.round(100*dist[s]/maxCount);
  const label=OLABELS[s]||"Score "+s;
  const color=OCOLORS[s]||"#999";
  chartHtml+=`<div class="bar-row"><span class="bar-label">${{label}}</span>`+
   `<div class="bar-track"><div class="bar-fill" style="width:${{pct}}%;background:${{color}}"></div></div>`+
   `<span class="bar-val">${{dist[s]}}</span></div>`;
 }}
 document.getElementById("outcome-chart").innerHTML=chartHtml;

 // What works (score >= 4)
 const good=lessons.filter(l=>l.o!=null&&l.o>=4);
 _cache.works=good;
 renderLessons("works",good,8,"badge-success");

 // Common pitfalls (score <= 3)
 const bad=lessons.filter(l=>l.o!=null&&l.o<=3);
 _cache.pitfalls=bad;
 renderLessons("pitfalls",bad,8,"badge-caution");

 // Regional patterns
 const regData={{}};
 REGIONS.forEach(r=>regData[r]={{total:0,success:0,countries:new Set()}});
 lessons.forEach(l=>{{
  if(l.r&&regData[l.r]){{
   regData[l.r].total++;
   if(l.c) regData[l.r].countries.add(l.c);
   if(l.o!=null&&l.o>=4) regData[l.r].success++;
  }}
 }});
 const regCards=REGIONS.filter(r=>regData[r].total>0)
  .sort((a,b)=>regData[b].total-regData[a].total)
  .map(r=>{{
   const d=regData[r];
   const rate=d.total?Math.round(100*d.success/d.total):0;
   const rateColor=rate>=70?"#2d8659":rate>=50?"#ff9800":"#f44336";
   return `<div class="region-card"><div class="rate" style="color:${{rateColor}}">${{rate}}%</div>`+
    `<div class="name">${{escH(r)}}</div>`+
    `<div class="stats">${{d.total}} lessons &middot; ${{d.countries.size}} countries</div></div>`;
  }});
 document.getElementById("regions").innerHTML=regCards.length?regCards.join(""):
  '<div class="empty-state">No regional data matches this filter.</div>';
}}

const _cache={{}};
function renderLessons(id,arr,limit,badge){{
 const el=document.getElementById(id);
 if(!arr.length){{el.innerHTML='<div class="empty-state">No lessons match this filter.</div>';return;}}
 const show=arr.slice(0,limit);
 el.innerHTML=show.map(l=>lessonCard(l,badge)).join("")+
  (arr.length>limit?'<div class="more-link" data-id="'+id+'" data-badge="'+badge+'" data-shown="'+limit+'">Show '+(Math.min(arr.length-limit,12))+' more&hellip;</div>':"");
 const ml=el.querySelector(".more-link");
 if(ml) ml.onclick=function(){{
  const shown=parseInt(this.dataset.shown);
  const next=arr.slice(shown,shown+12);
  const newShown=shown+next.length;
  this.outerHTML=next.map(l=>lessonCard(l,this.dataset.badge)).join("")+
   (newShown<arr.length?'<div class="more-link" data-id="'+id+'" data-badge="'+this.dataset.badge+'" data-shown="'+newShown+'">Show '+(Math.min(arr.length-newShown,12))+' more&hellip;</div>':"");
  const nl=el.querySelector(".more-link");
  if(nl) nl.onclick=arguments.callee.bind(nl);
 }};
}}
function lessonCard(l,badge){{
 const b=l.o>=4?"badge-success":(badge||"badge-caution");
 return '<div class="lesson-card"><span class="success-badge '+b+'">'+(OLABELS[l.o]||"")+'</span> '+escH(l.t)+
  '<div class="meta"><span>'+escH(l.p)+'</span><span>'+escH(l.c)+'</span></div></div>';
}}

function escH(s){{return s?s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"):""}}

document.getElementById("topic").addEventListener("change",filter);
document.getElementById("region").addEventListener("change",filter);
filter();
</script>
</body></html>"""

out = os.path.join(SITE, "evidence.html")
with open(out, "w") as f:
    f.write(html)
print(f"Wrote {out} ({len(html):,} bytes)")
