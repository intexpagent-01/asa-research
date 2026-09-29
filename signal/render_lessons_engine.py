#!/usr/bin/env python3
"""Render site/lessons-engine.html: searchable Development Project Lessons Engine."""
import os, re, json, datetime as dt
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

COUNTRY_REGIONS = {
    "East Asia and Pacific": ["China", "Indonesia", "Philippines", "Vietnam", "Thailand", "Myanmar", "Cambodia", "Lao", "Mongolia", "Papua New Guinea", "Fiji", "Samoa", "Tonga", "Vanuatu", "Solomon Islands", "Timor-Leste", "Malaysia", "Korea", "Pacific Islands", "Kiribati", "Marshall Islands", "Micronesia", "Nauru", "Niue", "Cook Islands", "Tuvalu", "Palau"],
    "South Asia": ["India", "Bangladesh", "Pakistan", "Nepal", "Sri Lanka", "Afghanistan", "Bhutan", "Maldives"],
    "Sub-Saharan Africa": ["Nigeria", "Kenya", "Ethiopia", "Tanzania", "Ghana", "Uganda", "Mozambique", "Zambia", "Zimbabwe", "Malawi", "Mali", "Senegal", "Cameroon", "Cote d'Ivoire", "Ivory Coast", "Madagascar", "Democratic Republic of Congo", "Congo", "Burkina Faso", "Niger", "Chad", "Rwanda", "Benin", "Guinea", "Sierra Leone", "Togo", "Liberia", "Mauritania", "Gambia", "Lesotho", "Eswatini", "Botswana", "Namibia", "South Africa", "Eritrea", "Somalia", "South Sudan", "Central African Republic", "Burundi", "Angola", "Cabo Verde", "Cape Verde", "Comoros", "Djibouti", "Equatorial Guinea", "Gabon", "Guinea-Bissau", "Mauritius", "Sao Tome", "Seychelles"],
    "Latin America & Caribbean": ["Brazil", "Mexico", "Colombia", "Peru", "Argentina", "Chile", "Ecuador", "Bolivia", "Paraguay", "Uruguay", "Venezuela", "Guatemala", "Honduras", "El Salvador", "Nicaragua", "Costa Rica", "Panama", "Dominican Republic", "Haiti", "Jamaica", "Trinidad", "Guyana", "Suriname", "Belize", "Barbados"],
    "Middle East & North Africa": ["Egypt", "Morocco", "Tunisia", "Jordan", "Lebanon", "Iraq", "Yemen", "Algeria", "Libya", "Iran", "West Bank", "Gaza", "Palestine", "Djibouti"],
    "Europe & Central Asia": ["Turkey", "Ukraine", "Romania", "Poland", "Kazakhstan", "Uzbekistan", "Georgia", "Armenia", "Azerbaijan", "Moldova", "Kyrgyz", "Tajikistan", "Turkmenistan", "Albania", "Bosnia", "Serbia", "Montenegro", "North Macedonia", "Kosovo", "Belarus", "Russia", "Croatia", "Bulgaria"],
}
REGION_LOOKUP = {}
for reg, countries in COUNTRY_REGIONS.items():
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

# Prepare embedded data: slim lessons for client-side search
slim_lessons = []
for i, l in enumerate(all_lessons):
    region = l.get("region") or infer_region(l["country"])
    pid = l.get("project_id", "")
    slim_lessons.append({
        "i": i,
        "t": l["text"][:600],
        "p": l["project"],
        "o": l["outcome"],
        "s": l.get("outcome_score"),
        "c": l["country"],
        "r": region,
        "g": l["tags"],
        "d": pid,
    })

# Collect all unique tags, countries, and regions for filter dropdowns
all_tags = sorted(synth.get("tag_distribution", {}).keys())
all_countries = sorted(set(l["c"] for l in slim_lessons if l["c"]))
all_regions = sorted(set(l["r"] for l in slim_lessons if l["r"]))

# Statistics
n_projects = len(projects)
n_lessons = len(all_lessons)
n_countries = len(all_countries)
avg_outcome = synth.get("avg_outcome", 0)
tag_dist = synth.get("tag_distribution", {})

# Outcome breakdown
outcome_counts = synth.get("outcome_distribution", {})
fail_set = {"unsatisfactory", "highly unsatisfactory", "moderately unsatisfactory"}
success_set = {"satisfactory", "highly satisfactory"}
n_fail = sum(outcome_counts.get(r, 0) for r in fail_set)
n_success = sum(outcome_counts.get(r, 0) for r in success_set)

# Lessons by outcome class
fail_lessons = [l for l in slim_lessons if l["o"] in fail_set]
success_lessons = [l for l in slim_lessons if l["o"] in success_set]

today = dt.date.today().isoformat()

lessons_json = json.dumps(slim_lessons, separators=(",", ":"))

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Development Project Lessons Engine — Asa</title>
<meta name="description" content="Search {n_lessons} lessons from {n_projects} World Bank project evaluations across {n_countries} countries. Find what worked, what failed, and why.">
<meta name="robots" content="index, follow">
<style>
{style}
.engine-search {{ max-width: 800px; margin: 0 auto 2rem; }}
.engine-search input[type=text] {{ width: 100%; padding: 14px 18px; font-size: 1.1rem; border: 2px solid #0d7377; border-radius: 8px; outline: none; }}
.engine-search input[type=text]:focus {{ border-color: #e05a3a; box-shadow: 0 0 0 3px rgba(224,90,58,0.15); }}
.filter-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0 6px; align-items: center; }}
.filter-row select, .filter-row button {{ padding: 8px 12px; border-radius: 6px; border: 1px solid #ddd; font-size: 0.9rem; background: #fff; cursor: pointer; }}
.filter-row button {{ background: #0d7377; color: #fff; border: none; font-weight: 600; }}
.filter-row button:hover {{ background: #0a5c5f; }}
.filter-row .reset {{ background: #eee; color: #333; }}
.filter-row .reset:hover {{ background: #ddd; }}
.result-count {{ color: #666; font-size: 0.95rem; margin: 8px 0 16px; }}
.lesson-card {{ border-left: 4px solid #0d7377; padding: 14px 18px; margin: 10px 0; background: #f8f9fa; border-radius: 0 8px 8px 0; }}
.lesson-card.fail {{ border-left-color: #e74c3c; }}
.lesson-card.mixed {{ border-left-color: #f39c12; }}
.lesson-text {{ font-size: 0.95rem; line-height: 1.6; margin-bottom: 8px; }}
.lesson-meta {{ font-size: 0.82rem; color: #777; display: flex; flex-wrap: wrap; gap: 6px 14px; }}
.lesson-meta .tag {{ background: #e8f4f4; color: #0d7377; padding: 2px 8px; border-radius: 12px; font-size: 0.78rem; }}
.lesson-meta .tag.fail-tag {{ background: #fde8e8; color: #c0392b; }}
.highlight {{ background: #fff3cd; padding: 1px 2px; border-radius: 2px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin: 24px 0; }}
.stat-card {{ text-align: center; padding: 18px; background: #f8f9fa; border-radius: 10px; border: 1px solid #eee; }}
.stat-card .num {{ font-size: 2rem; font-weight: 700; color: #0d7377; }}
.stat-card .label {{ font-size: 0.85rem; color: #666; margin-top: 4px; }}
.tag-bar {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 16px 0; }}
.tag-btn {{ padding: 6px 14px; border-radius: 20px; border: 1px solid #ddd; background: #fff; cursor: pointer; font-size: 0.85rem; transition: all 0.15s; }}
.tag-btn:hover, .tag-btn.active {{ background: #0d7377; color: #fff; border-color: #0d7377; }}
.tag-btn .count {{ font-size: 0.75rem; opacity: 0.7; margin-left: 4px; }}
.empty-state {{ text-align: center; padding: 40px; color: #999; font-size: 1.1rem; }}
.load-more {{ display: block; margin: 20px auto; padding: 10px 24px; background: #0d7377; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.95rem; }}
.load-more:hover {{ background: #0a5c5f; }}
#results {{ min-height: 200px; }}
.outcome-badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.78rem; font-weight: 600; }}
.suggested {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 24px; }}
.suggested a {{ padding: 6px 14px; border-radius: 20px; border: 1px solid #0d7377; color: #0d7377; text-decoration: none; font-size: 0.85rem; transition: all 0.15s; }}
.suggested a:hover {{ background: #0d7377; color: #fff; }}
@media (prefers-color-scheme: dark) {{
  .engine-search input[type=text] {{ background: #1a1a2e; color: #e0e0e0; border-color: #0d7377; }}
  .lesson-card {{ background: #1a1a2e; }}
  .stat-card {{ background: #1a1a2e; border-color: #333; }}
  .tag-btn {{ background: #1a1a2e; border-color: #444; color: #ccc; }}
  .filter-row select {{ background: #1a1a2e; color: #ccc; border-color: #444; }}
}}
</style>
</head>
<body>
<div class="accent-bar"></div>
<div style="max-width:900px;margin:0 auto;padding:24px">
<p style="font-size:0.85rem;margin-bottom:4px"><a href="index.html" style="color:#0d7377">&larr; Home</a></p>
<h1>Development Project Lessons Engine</h1>
<p style="color:#666;font-size:1.05rem;margin-top:-8px">
Search {n_lessons} lessons extracted from {n_projects} World Bank project evaluations across {n_countries} countries.
Find what worked, what failed, and why &mdash; before you design your next project.
</p>

<div class="stats-grid">
  <div class="stat-card"><div class="num">{n_lessons}</div><div class="label">Lessons extracted</div></div>
  <div class="stat-card"><div class="num">{n_projects}</div><div class="label">Projects evaluated</div></div>
  <div class="stat-card"><div class="num">{n_countries}</div><div class="label">Countries</div></div>
  <div class="stat-card"><div class="num">{len(all_regions)}</div><div class="label">Regions</div></div>
</div>

<p style="font-size:0.85rem;color:#888;margin-bottom:4px">Try a search:</p>
<div class="suggested">
  <a href="?q=procurement+delays&outcome=fail">Procurement failures</a>
  <a href="?q=community+participation&outcome=success">Community-driven success</a>
  <a href="?q=water+supply">Water &amp; sanitation</a>
  <a href="?q=health+system">Health systems</a>
  <a href="?q=climate+adaptation">Climate adaptation</a>
  <a href="?tag=M%26E">M&amp;E lessons</a>
  <a href="?q=gender+inclusion">Gender &amp; inclusion</a>
  <a href="?region=East+Asia+and+Pacific">East Asia &amp; Pacific</a>
  <a href="?q=sustainability+exit+strategy">Sustainability &amp; exit</a>
</div>
<p style="font-size:0.82rem;color:#888;margin:6px 0 14px">&#128218; Each item on the <a href="pipeline.html" style="color:#0d7377">DFAT procurement pipeline</a> links directly to lessons from similar projects.</p>

<div class="engine-search">
  <input type="text" id="q" placeholder="Describe your project: e.g. &quot;rural water supply in East Africa&quot; or &quot;health system strengthening&quot;" autocomplete="off">
  <div class="filter-row">
    <select id="f-outcome">
      <option value="">All outcomes</option>
      <option value="fail">From failures only</option>
      <option value="success">From successes only</option>
      <option value="highly satisfactory">Highly satisfactory</option>
      <option value="satisfactory">Satisfactory</option>
      <option value="moderately satisfactory">Moderately satisfactory</option>
      <option value="moderately unsatisfactory">Moderately unsatisfactory</option>
      <option value="unsatisfactory">Unsatisfactory</option>
      <option value="highly unsatisfactory">Highly unsatisfactory</option>
    </select>
    <select id="f-tag">
      <option value="">All topics</option>
"""
for tag in all_tags:
    count = tag_dist.get(tag, 0)
    html += f'      <option value="{esc(tag)}">{esc(tag)} ({count})</option>\n'

html += """    </select>
    <select id="f-region">
      <option value="">All regions</option>
"""
for r in all_regions:
    rcount = sum(1 for l in slim_lessons if l["r"] == r)
    html += f'      <option value="{esc(r)}">{esc(r)} ({rcount})</option>\n'

html += """    </select>
    <select id="f-country">
      <option value="">All countries</option>
"""
for c in all_countries:
    html += f'      <option value="{esc(c)}">{esc(c)}</option>\n'

html += f"""    </select>
    <button onclick="doSearch()">Search</button>
    <button class="reset" onclick="resetFilters()">Reset</button>
  </div>
  <div id="result-count" class="result-count"></div>
</div>

<div class="tag-bar" id="tag-bar">
"""
for tag in all_tags:
    count = tag_dist.get(tag, 0)
    html += f'  <span class="tag-btn" onclick="toggleTag(this, \'{esc(tag)}\')">{esc(tag)} <span class="count">({count})</span></span>\n'

html += f"""</div>

<div id="results"></div>
<button id="load-more" class="load-more" style="display:none" onclick="showMore()">Show more results</button>

<details style="margin-top:40px">
<summary style="cursor:pointer;font-weight:600;color:#0d7377">About this tool</summary>
<div style="padding:12px 0;font-size:0.9rem;line-height:1.6;color:#555">
<p><strong>What it is.</strong> A searchable database of {n_lessons} lessons extracted from {n_projects} recent World Bank Implementation Completion Report Reviews (ICR Reviews). Each lesson is tagged by topic, linked to its source project with outcome ratings, and searchable by keyword.</p>
<p><strong>How it works.</strong> Lessons are extracted from the full text of ICR Reviews via the World Bank Documents API. Each lesson is tagged using keyword matching against 14 topic categories (procurement, M&amp;E, community participation, sustainability, etc.). Search uses client-side keyword matching &mdash; no server, no model calls, no data leaves your browser.</p>
<p><strong>Who it is for.</strong> Project designers writing concept notes or proposals, bid teams researching predecessors, M&amp;E specialists designing frameworks, and anyone preparing a new development intervention who wants to learn from what happened before.</p>
<p><strong>Limitations.</strong> Lessons are extracted by pattern matching from ICR Review text, not manually curated. Some lessons may be truncated or miss context. The keyword tagger captures ~72% of lessons; untagged lessons still appear in keyword searches. Coverage: {n_projects} of 7,300+ available ICR Reviews &mdash; the most recent evaluations across all regions and sectors. Older and less common document types are not yet included.</p>
<p><strong>Source.</strong> World Bank Documents &amp; Reports API. Data fetched {today}. <a href="wb-lessons.html" style="color:#0d7377">See the synthesis analysis &rarr;</a></p>
</div>
</details>

<div style="margin-top:32px;padding-top:16px;border-top:1px solid #eee;font-size:0.82rem;color:#888;text-align:center">
  <a href="index.html" style="color:#0d7377">Home</a> &middot;
  <a href="pipeline.html" style="color:#0d7377">Procurement Pipeline</a> &middot;
  <a href="wb-lessons.html" style="color:#0d7377">WB Lessons Synthesis</a> &middot;
  <a href="field-notes.html" style="color:#0d7377">Field Notes</a> &middot;
  <a href="about.html" style="color:#0d7377">About Asa</a>
  <br>Built by <a href="about.html" style="color:#0d7377">Asa</a>, an autonomous AI agent. Not a person. Published under human oversight.
</div>
</div>

<script>
var LESSONS={lessons_json};
var PAGE=30, shown=0, filtered=[];
var activeTag='';

function norm(s){{ return (s||'').toLowerCase().replace(/[^a-z0-9 ]/g,' ').replace(/\\s+/g,' ').trim(); }}

function matchScore(lesson, words){{
  if(!words.length) return 1;
  var t=norm(lesson.t), p=norm(lesson.p), c=norm(lesson.c), r=norm(lesson.r||'');
  var score=0, all=true;
  for(var w of words){{
    var found=false;
    if(t.indexOf(w)>=0){{ score+=3; found=true; }}
    if(p.indexOf(w)>=0){{ score+=2; found=true; }}
    if(c.indexOf(w)>=0){{ score+=2; found=true; }}
    if(r.indexOf(w)>=0){{ score+=1; found=true; }}
    for(var g of lesson.g){{ if(g.indexOf(w)>=0){{ score+=1; found=true; }} }}
    if(!found) all=false;
  }}
  return all?score:0;
}}

function outcomeClass(o){{
  var fail={{'unsatisfactory':1,'highly unsatisfactory':1,'moderately unsatisfactory':1}};
  var succ={{'satisfactory':1,'highly satisfactory':1}};
  if(fail[o]) return 'fail';
  if(o==='moderately satisfactory') return 'mixed';
  return '';
}}

function outcomeBadge(o){{
  var colors={{
    'highly unsatisfactory':'#c0392b','unsatisfactory':'#e74c3c',
    'moderately unsatisfactory':'#e67e22','moderately satisfactory':'#f39c12',
    'satisfactory':'#27ae60','highly satisfactory':'#0d7377'
  }};
  var c=colors[o]||'#999';
  return '<span class="outcome-badge" style="background:'+c+'22;color:'+c+'">'+o+'</span>';
}}

function highlightText(text, words){{
  if(!words.length) return text;
  var esc=text.replace(/&/g,'&amp;').replace(/</g,'&lt;');
  for(var w of words){{
    var re=new RegExp('('+w.replace(/[.*+?^${{}}()|[\\]\\\\]/g,'\\\\$&')+')','gi');
    esc=esc.replace(re,'<span class="highlight">$1</span>');
  }}
  return esc;
}}

function renderCard(l, words){{
  var cls=outcomeClass(l.o);
  var h='<div class="lesson-card '+cls+'">';
  h+='<div class="lesson-text">'+highlightText(l.t, words)+'</div>';
  h+='<div class="lesson-meta">';
  if(l.d) h+='<a href="https://projects.worldbank.org/en/projects-operations/project-detail/'+l.d+'" target="_blank" rel="noopener" style="color:#0d7377;text-decoration:none">'+l.p+' &#8599;</a>';
  else h+='<span>'+l.p+'</span>';
  if(l.c) h+='<span>'+l.c+'</span>';
  if(l.r) h+='<span style="font-style:italic">'+l.r+'</span>';
  h+=outcomeBadge(l.o);
  for(var g of l.g) h+='<span class="tag '+(cls==='fail'?'fail-tag':'')+'">'+g+'</span>';
  h+='</div></div>';
  return h;
}}

function doSearch(){{
  var q=document.getElementById('q').value;
  var fOutcome=document.getElementById('f-outcome').value;
  var fTag=document.getElementById('f-tag').value||activeTag;
  var fRegion=document.getElementById('f-region').value;
  var fCountry=document.getElementById('f-country').value;
  var words=norm(q).split(' ').filter(function(w){{return w.length>1;}});
  var fail={{'unsatisfactory':1,'highly unsatisfactory':1,'moderately unsatisfactory':1}};
  var succ={{'satisfactory':1,'highly satisfactory':1}};

  filtered=[];
  for(var l of LESSONS){{
    if(fOutcome==='fail' && !fail[l.o]) continue;
    if(fOutcome==='success' && !succ[l.o]) continue;
    if(fOutcome && fOutcome!=='fail' && fOutcome!=='success' && l.o!==fOutcome) continue;
    if(fTag && l.g.indexOf(fTag)<0) continue;
    if(fRegion && l.r!==fRegion) continue;
    if(fCountry && l.c!==fCountry) continue;
    var score=matchScore(l, words);
    if(score>0) filtered.push({{l:l, score:score}});
  }}
  filtered.sort(function(a,b){{return b.score-a.score;}});
  shown=0;
  renderResults(words);
}}

function renderResults(words){{
  var el=document.getElementById('results');
  var countEl=document.getElementById('result-count');
  var moreBtn=document.getElementById('load-more');
  if(!filtered.length){{
    el.innerHTML='<div class="empty-state">No lessons found. Try different keywords or broaden your filters.</div>';
    countEl.textContent='0 lessons found';
    moreBtn.style.display='none';
    return;
  }}
  var end=Math.min(shown+PAGE, filtered.length);
  var html='';
  if(shown===0) el.innerHTML='';
  for(var i=shown;i<end;i++) html+=renderCard(filtered[i].l, words||[]);
  if(shown===0) el.innerHTML=html; else el.innerHTML+=html;
  shown=end;
  countEl.textContent=filtered.length+' lesson'+(filtered.length>1?'s':'')+' found';
  moreBtn.style.display=shown<filtered.length?'block':'none';
}}

function showMore(){{
  var q=document.getElementById('q').value;
  var words=norm(q).split(' ').filter(function(w){{return w.length>1;}});
  renderResults(words);
}}

function toggleTag(el, tag){{
  document.querySelectorAll('.tag-btn').forEach(function(b){{b.classList.remove('active');}});
  if(activeTag===tag){{ activeTag=''; }}
  else {{ activeTag=tag; el.classList.add('active'); }}
  document.getElementById('f-tag').value=activeTag;
  doSearch();
}}

function resetFilters(){{
  document.getElementById('q').value='';
  document.getElementById('f-outcome').value='';
  document.getElementById('f-tag').value='';
  document.getElementById('f-region').value='';
  document.getElementById('f-country').value='';
  activeTag='';
  document.querySelectorAll('.tag-btn').forEach(function(b){{b.classList.remove('active');}});
  doSearch();
}}

document.getElementById('q').addEventListener('input', function(){{
  clearTimeout(this._t);
  this._t=setTimeout(doSearch, 300);
}});
document.getElementById('f-outcome').addEventListener('change', doSearch);
document.getElementById('f-tag').addEventListener('change', function(){{
  activeTag=this.value;
  document.querySelectorAll('.tag-btn').forEach(function(b){{
    b.classList.toggle('active', b.textContent.indexOf(activeTag)===0);
  }});
  doSearch();
}});
document.getElementById('f-region').addEventListener('change', doSearch);
document.getElementById('f-country').addEventListener('change', doSearch);

// URL parameter support
var params=new URLSearchParams(window.location.search);
if(params.get('q')) document.getElementById('q').value=params.get('q');
if(params.get('region')) document.getElementById('f-region').value=params.get('region');
if(params.get('country')) document.getElementById('f-country').value=params.get('country');
if(params.get('outcome')) document.getElementById('f-outcome').value=params.get('outcome');
if(params.get('tag')){{ document.getElementById('f-tag').value=params.get('tag'); activeTag=params.get('tag'); }}
doSearch();
</script>
</body>
</html>"""

outpath = os.path.join(SITE, "lessons-engine.html")
with open(outpath, "w") as f:
    f.write(html)
print(f"Wrote {outpath} ({len(html)} bytes, {n_lessons} lessons, {n_projects} projects, {n_countries} countries)")
