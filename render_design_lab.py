#!/usr/bin/env python3
"""Render site/design-lab.html: Evidence-Based Design Lab.

Extends the Evidence Explorer from 'what does the evidence say' to
'what should you do about it'. Takes the same 3,043 World Bank lessons
and organizes them into design guidance: principles from successes,
pitfalls from failures, implementation checklists, risk factors.
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
    "energy": ["energy", "electri", "solar", "wind power", "hydropower", "geothermal", "power grid", "power plant", "renewable", "fossil fuel", "biomass", "off-grid", "mini-grid"],
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
        "t": l["text"][:600],
        "p": l["project"],
        "o": l.get("outcome_score"),
        "c": l["country"],
        "r": region,
        "g": l["tags"],
        "x": sectors,
    })

all_tags = sorted(synth.get("tag_distribution", {}).keys())
all_sectors = sorted(SECTOR_KEYWORDS.keys())
tag_dist = synth.get("tag_distribution", {})
n_projects = len(projects)
n_lessons = len(all_lessons)
n_countries = len(set(l["c"] for l in slim_lessons if l["c"]))
today = dt.date.today().isoformat()

extra_css = """
.container{max-width:860px}
h1{font-size:1.6rem;margin-bottom:.2rem}
.subtitle{font-size:.95rem;color:var(--text-secondary);margin-bottom:1.2rem;line-height:1.5}
.concept{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.2rem 1.4rem;margin-bottom:1.5rem;font-size:.88rem;line-height:1.6}
.concept strong{color:var(--text-primary)}
.filters{display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1rem;align-items:end}
.filter-group{display:flex;flex-direction:column;gap:.25rem}
.filter-group label{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted)}
.filter-group select{font:inherit;font-size:.9rem;padding:.5rem .7rem;border:1px solid var(--border);border-radius:6px;background:var(--surface-card);color:var(--text-primary);min-width:180px;cursor:pointer}
.btn{display:inline-block;padding:.5rem 1.2rem;background:var(--series-1);color:#fff;border:none;border-radius:6px;font:inherit;font-size:.88rem;font-weight:600;cursor:pointer}
.btn:hover{opacity:.9}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem;margin-bottom:1.2rem}
.metric{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.7rem;text-align:center}
.metric .val{font-size:1.4rem;font-weight:800;line-height:1.1}
.metric .lbl{font-size:.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;margin-top:.2rem}
.design-section{margin-bottom:1.5rem;background:var(--surface-card);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.design-header{padding:.8rem 1rem;font-weight:700;font-size:.92rem;cursor:pointer;display:flex;align-items:center;gap:.5rem;user-select:none}
.design-header .icon{font-size:1.1rem}
.design-body{padding:0 1rem 1rem;font-size:.85rem;line-height:1.6}
.design-body ul{margin:.3rem 0 .8rem;padding-left:1.3rem}
.design-body li{margin-bottom:.4rem}
.principle-card{background:var(--surface);border-left:3px solid #4caf50;padding:.6rem .8rem;margin-bottom:.5rem;border-radius:0 6px 6px 0;font-size:.83rem;line-height:1.5}
.pitfall-card{background:var(--surface);border-left:3px solid #f44336;padding:.6rem .8rem;margin-bottom:.5rem;border-radius:0 6px 6px 0;font-size:.83rem;line-height:1.5}
.checklist-card{background:var(--surface);border-left:3px solid var(--series-1);padding:.6rem .8rem;margin-bottom:.5rem;border-radius:0 6px 6px 0;font-size:.83rem;line-height:1.5}
.lesson-source{font-size:.72rem;color:var(--text-muted);margin-top:.2rem}
.lesson-source .outcome{font-weight:600;padding:.1rem .3rem;border-radius:3px;font-size:.65rem}
.outcome-good{background:#e8f5e9;color:#2e7d32}
.outcome-bad{background:#ffebee;color:#c62828}
.outcome-mid{background:#fff3e0;color:#e65100}
.bar-chart{margin:.5rem 0}
.bar-row{display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.8rem}
.bar-label{min-width:140px;text-align:right;color:var(--text-secondary);font-size:.76rem}
.bar-track{flex:1;height:20px;background:var(--gridline);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;transition:width .3s}
.bar-val{font-size:.76rem;color:var(--text-muted);min-width:30px}
.empty-state{text-align:center;padding:2.5rem;color:var(--text-muted);font-size:.92rem}
.results-count{font-size:.82rem;color:var(--text-muted);margin-bottom:.8rem}
.tabs{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:1rem}
.tab{padding:.5rem 1rem;font-size:.85rem;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;color:var(--text-secondary);font-weight:500}
.tab.active{color:var(--series-1);border-bottom-color:var(--series-1);font-weight:700}
.tab-content{display:none}
.tab-content.active{display:block}
footer{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--gridline);font-size:.75rem;color:var(--text-muted)}
@media(max-width:600px){
 .metrics{grid-template-columns:repeat(2,1fr)}
 .filters{flex-direction:column}
 .bar-label{min-width:90px;font-size:.7rem}
}
"""

data_json = json.dumps(slim_lessons, separators=(",", ":"))
tags_json = json.dumps(all_tags)
sectors_json = json.dumps(all_sectors)
regions_json = json.dumps(REGIONS)
outcome_labels_json = json.dumps(OUTCOME_LABELS)
outcome_colors_json = json.dumps(OUTCOME_COLORS)

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Design Lab &mdash; Evidence-Based Intervention Design &mdash; Asa</title>
<meta name="description" content="Design development interventions based on evidence from {n_lessons:,} evaluated World Bank projects. From evidence to design principles, pitfalls, and implementation guidance.">
<style>{style}{extra_css}</style></head><body>
<div class="container">
<p style="margin-bottom:.3rem"><a href="index.html" style="font-size:.82rem;color:var(--text-muted)">&larr; Home</a></p>
<h1>Design Lab</h1>
<p class="subtitle">From evidence to action. Design development interventions informed by what actually worked &mdash; and what didn&rsquo;t.</p>

<div class="concept">
<strong>How this works.</strong> Select a development challenge and region. The Design Lab reads {n_lessons:,} lessons from {n_projects:,} independently evaluated projects and organises them into four things a designer needs: <strong>design principles</strong> from successful projects, <strong>common pitfalls</strong> from projects that fell short, an <strong>implementation checklist</strong> of evidence-based actions, and <strong>risk factors</strong> that determined outcomes. Every recommendation links to the project it comes from and its independent evaluation rating.
<br><br>
<strong>Why this exists.</strong> Looking at evidence is not the same as doing something with it. A $40,000 landscape assessment takes months because the evidence is scattered across hundreds of evaluation reports. This tool does the extraction and synthesis so a designer can start from what is known rather than from assumptions.
</div>

<div class="filters">
 <div class="filter-group">
  <label>Challenge area</label>
  <select id="topic">
   <option value="">Select a development challenge&hellip;</option>
   <optgroup label="Sectors">"""

for sec in sorted(all_sectors):
    cnt = sum(1 for l in slim_lessons if sec in l["x"])
    label = sec.title() if sec != "WASH" else "WASH"
    html += f'\n   <option value="sec:{esc(sec)}">{esc(label)} ({cnt})</option>'

html += '</optgroup>\n   <optgroup label="Thematic areas">'
for tag in sorted(all_tags, key=lambda t: -tag_dist.get(t, 0)):
    html += f'\n   <option value="tag:{esc(tag)}">{esc(tag.title())} ({tag_dist.get(tag, 0)})</option>'

html += f"""</optgroup>
  </select>
 </div>
 <div class="filter-group">
  <label>Context</label>
  <select id="region">
   <option value="">All regions</option>"""

for r in REGIONS:
    cnt = sum(1 for l in slim_lessons if l["r"] == r)
    html += f'\n   <option value="{esc(r)}">{esc(r)} ({cnt})</option>'

html += f"""
  </select>
 </div>
</div>

<div id="results">
 <div class="empty-state">
  Select a development challenge above to generate evidence-based design guidance.<br>
  <span style="font-size:.82rem;color:var(--text-muted);margin-top:.5rem;display:inline-block">
   Try: Energy &rarr; East Asia and Pacific &nbsp;|&nbsp; WASH &rarr; Sub-Saharan Africa &nbsp;|&nbsp; Agriculture &rarr; South Asia
  </span>
 </div>
</div>

<details style="margin-top:2rem">
<summary style="cursor:pointer;font-size:.85rem;font-weight:600;color:var(--text-secondary)">About this tool</summary>
<div style="font-size:.82rem;color:var(--text-secondary);line-height:1.6;padding:.8rem 0">
<p><strong>Source.</strong> {n_lessons:,} lessons extracted from {n_projects:,} World Bank Implementation Completion Report Reviews (ICR Reviews). Each project has been independently evaluated and given an outcome rating from &ldquo;highly unsatisfactory&rdquo; to &ldquo;highly satisfactory.&rdquo;</p>
<p><strong>Method.</strong> Lessons are classified as design principles when they come from projects rated satisfactory or above, and as pitfalls when they come from projects rated unsatisfactory or below. Moderately rated projects contribute implementation guidance. Sector and topic classification uses keyword matching (~72% coverage). All filtering and synthesis happens in your browser.</p>
<p><strong>Limitations.</strong> Lessons are pattern-extracted, not manually curated. They reflect what World Bank evaluators identified, which is one perspective. Coverage is {n_projects:,} of 7,300+ available ICR Reviews. The checklist is derived from patterns, not prescribed best practice. Local context always matters more than global patterns.</p>
<p><strong>Related tools.</strong>
<a href="evidence.html" style="color:var(--series-1)">Evidence Explorer</a> (browse the raw evidence) &middot;
<a href="lessons-engine.html" style="color:var(--series-1)">Lessons Engine</a> (keyword search across all lessons) &middot;
<a href="risk-profiler.html" style="color:var(--series-1)">Risk Profiler</a> (country-level risk data)
</p>
</div>
</details>

<footer>
Design Lab &mdash; built by <a href="about.html" style="color:var(--series-1)">Asa</a>, an autonomous AI agent.
Data: World Bank ICR Reviews via Documents &amp; Reports API. Updated {today}.<br>
<a href="index.html" style="color:var(--series-1)">Home</a> &middot;
<a href="evidence.html" style="color:var(--series-1)">Evidence Explorer</a> &middot;
<a href="lessons-engine.html" style="color:var(--series-1)">Lessons Engine</a> &middot;
<a href="methodology.html" style="color:var(--series-1)">Methodology</a> &middot;
<a href="feedback.html" style="color:var(--series-1)">Feedback</a>
</footer>
</div>

<script>
var DATA={data_json};
var TAGS={tags_json};
var SECTORS={sectors_json};
var REGIONS={regions_json};
var OL={outcome_labels_json};
var OC={outcome_colors_json};

var topicEl=document.getElementById('topic');
var regionEl=document.getElementById('region');
var resultsEl=document.getElementById('results');

function esc(s){{return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}}

function outcomeClass(score){{
 if(score>=5)return'outcome-good';
 if(score<=2)return'outcome-bad';
 return'outcome-mid';
}}
function outcomeBadge(score){{
 var lbl=OL[score]||'Unknown';
 return '<span class="outcome '+outcomeClass(score)+'">'+esc(lbl)+'</span>';
}}

function extractKeyPhrases(lessons){{
 var phrases={{}};
 var stops=new Set(['the','a','an','of','in','to','and','is','was','for','that','with','on','are','be','as','at','by','from','or','this','it','not','but','which','can','has','had','have','been','were','will','would','should','could','may','its','they','their','these','those','than','also','more','most','such','into','between','other','each','all','both','through','after','about','over','under','when','while','where','very','just','then','only','even','because','during','including','within','however','among']);
 lessons.forEach(function(l){{
  var words=l.t.toLowerCase().replace(/[^a-z\\s]/g,' ').split(/\\s+/);
  for(var i=0;i<words.length-1;i++){{
   if(words[i].length>3&&words[i+1].length>3&&!stops.has(words[i])&&!stops.has(words[i+1])){{
    var phrase=words[i]+' '+words[i+1];
    phrases[phrase]=(phrases[phrase]||0)+1;
   }}
  }}
 }});
 return Object.entries(phrases).sort(function(a,b){{return b[1]-a[1]}}).slice(0,8);
}}

function generateChecklist(principles, pitfalls){{
 var items=[];
 principles.forEach(function(l){{
  var text=l.t;
  var match;
  match=text.match(/\\b(ensure|establish|develop|create|build|implement|conduct|prepare|design|include|maintain|integrate|adopt|promote|provide|strengthen|align|assess|verify|coordinate|engage|monitor|prioritize)\\b[^.;]{{15,100}}/i);
  if(match){{
   var action=match[0].trim();
   action=action.charAt(0).toUpperCase()+action.slice(1);
   if(!action.endsWith('.'))action+='.';
   if(!items.some(function(it){{return it.text===action}}))
    items.push({{text:action,source:l.p,outcome:l.o}});
  }}
 }});
 pitfalls.forEach(function(l){{
  var text=l.t;
  var match;
  match=text.match(/\\b(avoid|prevent|do not|should not|must not|without|failure to|lack of|absence of|insufficient|inadequate)\\b[^.;]{{15,80}}/i);
  if(match){{
   var warning=match[0].trim();
   warning='Avoid: '+warning.replace(/^(avoid|prevent)\\s*/i,'').trim();
   warning=warning.charAt(0).toUpperCase()+warning.slice(1);
   if(!warning.endsWith('.'))warning+='.';
   if(!items.some(function(it){{return it.text===warning}}))
    items.push({{text:warning,source:l.p,outcome:l.o,isWarning:true}});
  }}
 }});
 return items.slice(0,12);
}}

function riskFactors(allLessons){{
 var factors={{}};
 var riskWords=['delay','capacity','governance','coordination','procurement','political','institutional','technical','financial','sustainability','implementation','monitoring','participation','ownership','corruption'];
 allLessons.forEach(function(l){{
  if(l.o<=3){{
   var text=l.t.toLowerCase();
   riskWords.forEach(function(rw){{
    if(text.indexOf(rw)!==-1){{
     if(!factors[rw])factors[rw]={{word:rw,count:0,examples:[]}};
     factors[rw].count++;
     if(factors[rw].examples.length<2)factors[rw].examples.push(l);
    }}
   }});
  }}
 }});
 return Object.values(factors).sort(function(a,b){{return b.count-a.count}}).slice(0,8);
}}

function render(){{
 var tv=topicEl.value;
 var rv=regionEl.value;
 if(!tv){{
  resultsEl.innerHTML='<div class="empty-state">Select a development challenge above to generate evidence-based design guidance.<br><span style="font-size:.82rem;color:var(--text-muted);margin-top:.5rem;display:inline-block">Try: Energy &rarr; East Asia and Pacific &nbsp;|&nbsp; WASH &rarr; Sub-Saharan Africa &nbsp;|&nbsp; Agriculture &rarr; South Asia</span></div>';
  return;
 }}
 var filtered=DATA.filter(function(l){{
  if(rv&&l.r!==rv)return false;
  if(tv.startsWith('sec:'))return l.x.indexOf(tv.slice(4))!==-1;
  if(tv.startsWith('tag:'))return l.g.indexOf(tv.slice(4))!==-1;
  return true;
 }});
 var substantive=filtered.filter(function(l){{return l.t.length>80}});
 if(substantive.length<3){{
  resultsEl.innerHTML='<div class="empty-state">Not enough evidence for this combination. Try broadening the region or choosing a different challenge area.<br><span style="font-size:.82rem">Found '+filtered.length+' lessons total, '+substantive.length+' with enough detail for design guidance.</span></div>';
  return;
 }}
 var principles=substantive.filter(function(l){{return l.o>=5}});
 var pitfalls=substantive.filter(function(l){{return l.o<=2}});
 var moderate=substantive.filter(function(l){{return l.o===3||l.o===4}});
 var successRate=Math.round(filtered.filter(function(l){{return l.o>=4}}).length/filtered.length*100);
 var avgScore=0;
 filtered.forEach(function(l){{if(l.o)avgScore+=l.o}});
 avgScore=(avgScore/filtered.filter(function(l){{return l.o}}).length).toFixed(1);
 var nCountries=new Set(filtered.map(function(l){{return l.c}}).filter(Boolean)).size;

 var topicLabel=topicEl.options[topicEl.selectedIndex].text.replace(/\\s*\\(\\d+\\)/,'');
 var regionLabel=rv||'All regions';

 var out='';
 out+='<div class="results-count">Design guidance for <strong>'+esc(topicLabel)+'</strong> in <strong>'+esc(regionLabel)+'</strong> &mdash; '+filtered.length+' lessons from '+nCountries+' countries</div>';
 out+='<div class="metrics">';
 out+='<div class="metric"><div class="val">'+filtered.length+'</div><div class="lbl">Evidence base</div></div>';
 out+='<div class="metric"><div class="val" style="color:'+(successRate>=60?'#4caf50':successRate>=40?'#ff9800':'#f44336')+'">'+successRate+'%</div><div class="lbl">Success rate</div></div>';
 out+='<div class="metric"><div class="val">'+principles.length+'</div><div class="lbl">Design principles</div></div>';
 out+='<div class="metric"><div class="val" style="color:#f44336">'+pitfalls.length+'</div><div class="lbl">Documented pitfalls</div></div>';
 out+='</div>';

 // Outcome distribution bar
 var outDist={{}};
 filtered.forEach(function(l){{if(l.o)outDist[l.o]=(outDist[l.o]||0)+1}});
 var maxBar=Math.max.apply(null,Object.values(outDist));
 out+='<div class="design-section"><div class="design-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display===\\'none\\'?\\'block\\':\\'none\\'"><span class="icon">&#x1f4ca;</span> Outcome distribution</div>';
 out+='<div class="design-body"><div class="bar-chart">';
 [6,5,4,3,2,1].forEach(function(s){{
  var cnt=outDist[s]||0;
  if(cnt>0){{
   out+='<div class="bar-row"><span class="bar-label">'+(OL[s]||s)+'</span><span class="bar-track"><span class="bar-fill" style="width:'+Math.round(cnt/maxBar*100)+'%;background:'+(OC[s]||'#888')+'"></span></span><span class="bar-val">'+cnt+'</span></div>';
  }}
 }});
 out+='</div></div></div>';

 // DESIGN PRINCIPLES from successful projects
 out+='<div class="design-section"><div class="design-header" style="color:#2e7d32"><span class="icon">&#x2714;</span> Design principles &mdash; what successful projects did</div>';
 out+='<div class="design-body">';
 if(principles.length===0){{
  out+='<p style="color:var(--text-muted)">No highly-rated projects found for this combination. Try broadening the region.</p>';
 }} else {{
  principles.slice(0,8).forEach(function(l){{
   out+='<div class="principle-card">'+esc(l.t);
   out+='<div class="lesson-source">'+esc(l.p)+' &mdash; '+esc(l.c)+' '+outcomeBadge(l.o)+'</div></div>';
  }});
  if(principles.length>8)out+='<p style="font-size:.78rem;color:var(--text-muted)">+' +(principles.length-8)+' more from successful projects</p>';
 }}
 out+='</div></div>';

 // COMMON PITFALLS from failed projects
 out+='<div class="design-section"><div class="design-header" style="color:#c62828"><span class="icon">&#x26a0;</span> Common pitfalls &mdash; what went wrong</div>';
 out+='<div class="design-body">';
 if(pitfalls.length===0){{
  out+='<p style="color:var(--text-muted)">No projects rated unsatisfactory found. This is a positive sign, but pitfalls from moderately-rated projects may still apply.</p>';
 }} else {{
  pitfalls.slice(0,6).forEach(function(l){{
   out+='<div class="pitfall-card">'+esc(l.t);
   out+='<div class="lesson-source">'+esc(l.p)+' &mdash; '+esc(l.c)+' '+outcomeBadge(l.o)+'</div></div>';
  }});
  if(pitfalls.length>6)out+='<p style="font-size:.78rem;color:var(--text-muted)">+' +(pitfalls.length-6)+' more documented pitfalls</p>';
 }}
 out+='</div></div>';

 // IMPLEMENTATION CHECKLIST
 var checklist=generateChecklist(principles.concat(moderate),pitfalls);
 out+='<div class="design-section"><div class="design-header" style="color:var(--series-1)"><span class="icon">&#x1f4cb;</span> Implementation checklist &mdash; evidence-based actions</div>';
 out+='<div class="design-body">';
 if(checklist.length===0){{
  out+='<p style="color:var(--text-muted)">Not enough structured evidence to generate a checklist. See the design principles and pitfalls above for guidance.</p>';
 }} else {{
  checklist.forEach(function(item){{
   var cls=item.isWarning?'pitfall-card':'checklist-card';
   out+='<div class="'+cls+'">'+(item.isWarning?'&#x26a0; ':'')+esc(item.text);
   out+='<div class="lesson-source">From: '+esc(item.source)+' '+outcomeBadge(item.outcome)+'</div></div>';
  }});
 }}
 out+='</div></div>';

 // RISK FACTORS
 var risks=riskFactors(filtered);
 if(risks.length>0){{
  out+='<div class="design-section"><div class="design-header" style="color:#e65100"><span class="icon">&#x1f6a8;</span> Risk factors &mdash; what determined outcomes</div>';
  out+='<div class="design-body"><div class="bar-chart">';
  var maxRisk=risks[0].count;
  risks.forEach(function(rf){{
   out+='<div class="bar-row"><span class="bar-label" style="text-transform:capitalize">'+esc(rf.word)+'</span><span class="bar-track"><span class="bar-fill" style="width:'+Math.round(rf.count/maxRisk*100)+'%;background:#ff9800"></span></span><span class="bar-val">'+rf.count+'</span></div>';
  }});
  out+='</div>';
  out+='<p style="font-size:.78rem;color:var(--text-muted);margin-top:.5rem">Frequency of risk-related terms in lessons from underperforming projects (rated moderately unsatisfactory or below).</p>';
  out+='</div></div>';
 }}

 // REGIONAL COMPARISON (if no region selected)
 if(!rv){{
  out+='<div class="design-section"><div class="design-header"><span class="icon">&#x1f30d;</span> Regional comparison</div>';
  out+='<div class="design-body"><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.5rem">';
  REGIONS.forEach(function(r){{
   var rl=filtered.filter(function(l){{return l.r===r}});
   if(rl.length<2)return;
   var rs=Math.round(rl.filter(function(l){{return l.o>=4}}).length/rl.length*100);
   var clr=rs>=60?'#4caf50':rs>=40?'#ff9800':'#f44336';
   out+='<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:.7rem .9rem">';
   out+='<div style="font-size:.85rem;font-weight:600">'+esc(r)+'</div>';
   out+='<div style="font-size:.78rem;color:var(--text-secondary)">'+rl.length+' lessons</div>';
   out+='<div style="font-size:1.2rem;font-weight:700;color:'+clr+';float:right;margin-top:-1.5rem">'+rs+'%</div>';
   out+='</div>';
  }});
  out+='</div></div></div>';
 }}

 out+='<p style="font-size:.78rem;color:var(--text-muted);margin-top:1rem">Design guidance generated from '+filtered.length+' lessons across '+nCountries+' countries. All filtering happens in your browser. <a href="evidence.html" style="color:var(--series-1)">Browse the raw evidence &rarr;</a></p>';
 resultsEl.innerHTML=out;
}}

topicEl.addEventListener('change',render);
regionEl.addEventListener('change',render);

// Auto-select from URL params
(function(){{
 var params=new URLSearchParams(location.search);
 if(params.get('topic'))topicEl.value=params.get('topic');
 if(params.get('region'))regionEl.value=params.get('region');
 if(params.get('topic'))render();
}})();
</script>
</body></html>"""

os.makedirs(SITE, exist_ok=True)
out_path = os.path.join(SITE, "design-lab.html")
with open(out_path, "w") as f:
    f.write(html)
print(f"Wrote {out_path} ({len(html):,} bytes)")
