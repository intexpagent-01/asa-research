#!/usr/bin/env python3
"""Render site/search.html: site-wide search page with a client-side index."""
import os, re, json, html as html_mod, glob

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

SKIP = {"situation-2026-slides.html", "search.html"}

PAGE_META = {
    "index.html": ("Home", "Asa: autonomous AI agent working on Pacific aid intelligence"),
    "signal.html": ("Pacific Aid Signal", "Current issue: 14 Pacific island countries, who funds what, what changed"),
    "dashboard.html": ("Dashboard", "Visual overview of Pacific aid: charts, key metrics, funder and sector breakdown"),
    "pipeline.html": ("Pipeline & Outlook", "What is ending, coming, and open: DFAT procurement, NZ tenders, new starts"),
    "sectors.html": ("Sector Analysis", "Where the money goes: sector breakdown across 14 countries"),
    "funders.html": ("Funders", "Per-funder directory: 34 organisations, country presence, data currency"),
    "freshness.html": ("Data Freshness", "How old each funder's data is: funder-by-country heatmap"),
    "trends.html": ("Trends", "How the 90-day picture has moved across all issues"),
    "compare.html": ("Country Comparison", "Compare any two Pacific island countries side by side"),
    "timeline.html": ("Timeline", "What the Signal caught, issue by issue"),
    "methodology.html": ("Methodology", "How the data is collected, weighted, deduplicated, and processed"),
    "challenge.html": ("2031 Challenge", "What Indo-Pacific development challenge could AI solve by 2031?"),
    "findings.html": ("Findings", "Five verifiable findings from reading Pacific aid data"),
    "pitch.html": ("Use Case", "An analyst that never sleeps: the case for persistent AI country analysts"),
    "feedback.html": ("Feedback", "Questions asked, and what changed because someone asked"),
    "about.html": ("About Asa", "What Asa is, how it works, the timeline of the experiment"),
    "pacific-signal.html": ("Region Overview", "All 14 Pacific island countries at a glance"),
    "research.html": ("Research Archive", "17 analyses on what development data actually measures"),
    "download.html": ("Download Data", "Download Pacific aid data as CSV: disbursements, funders, sectors, activities for 14 countries"),
    "explorer.html": ("Data Explorer", "Filter, sort, and search 10,000+ aid activities across 14 Pacific island countries by country, funder, status, and keyword"),
}

COUNTRY_NAMES = {
    "pacific-signal-papua-new-guinea.html": "Papua New Guinea",
    "pacific-signal-fiji.html": "Fiji",
    "pacific-signal-solomon-islands.html": "Solomon Islands",
    "pacific-signal-vanuatu.html": "Vanuatu",
    "pacific-signal-samoa.html": "Samoa",
    "pacific-signal-tonga.html": "Tonga",
    "pacific-signal-kiribati.html": "Kiribati",
    "pacific-signal-tuvalu.html": "Tuvalu",
    "pacific-signal-micronesia.html": "Micronesia",
    "pacific-signal-marshall-islands.html": "Marshall Islands",
    "pacific-signal-palau.html": "Palau",
    "pacific-signal-nauru.html": "Nauru",
    "pacific-signal-niue.html": "Niue",
    "pacific-signal-cook-islands.html": "Cook Islands",
}

RESEARCH_TITLES = {
    "fragmentation-decomposition.html": "Aid Fragmentation",
    "climate-measurement.html": "Climate Finance Measurement",
    "governance-precision.html": "Governance Indicators",
    "poverty-measurement.html": "Poverty Measurement",
    "education-measurement.html": "Education Statistics",
    "sdg-coverage.html": "SDG Coverage",
    "synthesis.html": "IATI Synthesis",
    "aid-timing.html": "Aid Timing",
    "donor-concentration.html": "Donor Concentration",
    "indo-pacific-aid.html": "Indo-Pacific Aid",
    "consequences.html": "Consequences",
    "coordination-blind-spot.html": "Coordination Blind Spot",
    "cross-domain-synthesis.html": "Cross-Domain Synthesis",
    "practitioners-guide.html": "Practitioner's Guide",
    "reporting-expansion.html": "Reporting Expansion",
    "temporal-trends.html": "Temporal Trends",
}


def strip_html(text):
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title(raw_html):
    m = re.search(r"<title>(.*?)</title>", raw_html, re.S)
    return html_mod.unescape(m.group(1)).strip() if m else ""


def build_index():
    entries = []
    for fn in sorted(os.listdir(SITE)):
        if not fn.endswith(".html") or fn in SKIP:
            continue
        path = os.path.join(SITE, fn)
        raw = open(path).read()
        title = extract_title(raw)
        text = strip_html(raw)
        # Truncate to keep the index reasonable
        if len(text) > 2000:
            text = text[:2000]

        if fn in PAGE_META:
            label, desc = PAGE_META[fn]
        elif fn in COUNTRY_NAMES:
            label = COUNTRY_NAMES[fn]
            desc = f"Pacific Aid Signal country page for {COUNTRY_NAMES[fn]}"
        elif fn in RESEARCH_TITLES:
            label = RESEARCH_TITLES[fn]
            desc = f"Research: {RESEARCH_TITLES[fn]}"
        else:
            label = title or fn
            desc = ""

        cat = "signal"
        if fn.startswith("pacific-signal-"):
            cat = "country"
        elif fn in RESEARCH_TITLES:
            cat = "research"
        elif fn in ("index.html", "about.html", "feedback.html"):
            cat = "about"

        entries.append({
            "url": fn,
            "title": label,
            "desc": desc,
            "cat": cat,
            "text": text,
        })
    return entries


index = build_index()
index_json = json.dumps(index, ensure_ascii=False)

extra_css = """
.container{max-width:760px}
h1{margin-bottom:.4rem}
.search-box{position:relative;margin:0 0 1.5rem}
.search-box input{width:100%;padding:.7rem 1rem .7rem 2.6rem;font-size:1rem;border:1px solid var(--border);border-radius:10px;background:var(--surface-card);color:var(--text-primary);box-shadow:var(--card-shadow);outline:none;transition:border-color .2s,box-shadow .2s}
.search-box input:focus{border-color:var(--series-1);box-shadow:0 0 0 3px rgba(13,115,119,.15)}
.search-box .icon{position:absolute;left:.85rem;top:50%;transform:translateY(-50%);color:var(--text-muted);pointer-events:none}
.search-box .clear{position:absolute;right:.7rem;top:50%;transform:translateY(-50%);background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1.1rem;padding:.2rem;display:none}
.search-box .clear:hover{color:var(--text-primary)}
.filters{margin-bottom:1.2rem;display:flex;gap:.5rem;flex-wrap:wrap}
.filters button{padding:.3rem .8rem;font-size:.8rem;border:1px solid var(--border);border-radius:6px;background:var(--surface-card);color:var(--text-secondary);cursor:pointer;transition:all .15s}
.filters button:hover{border-color:var(--series-1);color:var(--series-1)}
.filters button.active{background:var(--series-1);color:#fff;border-color:var(--series-1)}
.result{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1rem 1.2rem;margin-bottom:.7rem;box-shadow:var(--card-shadow);transition:box-shadow .2s,transform .2s}
.result:hover{box-shadow:var(--card-shadow-hover);transform:translateY(-1px)}
.result a{text-decoration:none;color:inherit;display:block}
.result .title{font-size:1rem;font-weight:700;color:var(--series-1);margin-bottom:.2rem}
.result .desc{font-size:.85rem;color:var(--text-secondary);margin-bottom:.3rem}
.result .snippet{font-size:.82rem;color:var(--text-muted);line-height:1.5}
.result .snippet mark{background:rgba(13,115,119,.15);color:var(--text-primary);padding:.05rem .15rem;border-radius:2px}
.result .cat-tag{display:inline-block;font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;padding:.1rem .45rem;border-radius:4px;background:var(--accent-glow);color:var(--text-muted);margin-left:.5rem;vertical-align:middle}
.no-results{text-align:center;padding:2rem;color:var(--text-muted);font-size:.95rem}
.count{font-size:.82rem;color:var(--text-muted);margin-bottom:.8rem}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
p{margin-bottom:.9rem}
a{color:var(--series-1)}
@media (max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .search-box input{font-size:.95rem;padding:.6rem .9rem .6rem 2.3rem}
  .filters{gap:.35rem}
  .filters button{font-size:.75rem;padding:.25rem .6rem}
  .result{padding:.8rem 1rem}
  footer{font-size:.75rem}
}
"""

CAT_LABELS = {"all": "All", "signal": "Signal", "country": "Countries", "research": "Research", "about": "About"}

page_html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Search &mdash; Pacific Aid Signal</title>
<meta name="description" content="Search across all pages: 14 country briefs, analysis pages, research archive, and more.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra_css}</style></head><body><div class="container">
<p style="margin-bottom:.4rem"><a href="index.html" style="color:var(--text-muted);text-decoration:none">&larr; Home</a></p>
<h1>Search</h1>
<p style="font-size:.92rem;color:var(--text-secondary);margin-bottom:1.2rem">Find anything across {len(index)} pages: country briefs, analysis, funders, sectors, tenders, and research.</p>

<div class="search-box">
<span class="icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>
<input type="text" id="q" placeholder="Search countries, funders, topics..." autofocus autocomplete="off">
<button class="clear" id="clear" title="Clear">&times;</button>
</div>

<div class="filters" id="filters">
<button class="active" data-cat="all">All</button>
<button data-cat="signal">Signal</button>
<button data-cat="country">Countries</button>
<button data-cat="research">Research</button>
<button data-cat="about">About</button>
</div>

<div class="count" id="count"></div>
<div id="results"></div>

<footer>
<a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="{REPO}">Code and data</a> &middot;
<a href="feed.xml">RSS feed</a>
</footer>
</div>

<script>
var INDEX = {index_json};
var activeCat = "all";

function norm(s) {{ return s.toLowerCase().replace(/[^a-z0-9\\s]/g, ""); }}

function search(query) {{
  var q = norm(query).trim();
  if (!q) return INDEX.map(function(e) {{ return {{entry: e, score: 0, snippet: e.desc}}; }});
  var words = q.split(/\\s+/).filter(function(w) {{ return w.length > 0; }});
  var results = [];
  for (var i = 0; i < INDEX.length; i++) {{
    var e = INDEX[i];
    var t = norm(e.title + " " + e.desc + " " + e.text);
    var score = 0;
    var allMatch = true;
    for (var j = 0; j < words.length; j++) {{
      var idx = t.indexOf(words[j]);
      if (idx === -1) {{ allMatch = false; break; }}
      var count = 0;
      var pos = 0;
      while ((pos = t.indexOf(words[j], pos)) !== -1) {{ count++; pos += words[j].length; }}
      score += count;
      if (norm(e.title).indexOf(words[j]) !== -1) score += 10;
      if (norm(e.desc).indexOf(words[j]) !== -1) score += 5;
    }}
    if (!allMatch) continue;
    var snippet = findSnippet(e.text, words);
    results.push({{entry: e, score: score, snippet: snippet}});
  }}
  results.sort(function(a, b) {{ return b.score - a.score; }});
  return results;
}}

function findSnippet(text, words) {{
  var lower = text.toLowerCase();
  var best = -1;
  for (var i = 0; i < words.length; i++) {{
    var idx = lower.indexOf(words[i]);
    if (idx !== -1 && (best === -1 || idx < best)) best = idx;
  }}
  if (best === -1) return text.slice(0, 200);
  var start = Math.max(0, best - 60);
  var end = Math.min(text.length, best + 200);
  var s = (start > 0 ? "..." : "") + text.slice(start, end) + (end < text.length ? "..." : "");
  for (var i = 0; i < words.length; i++) {{
    var re = new RegExp("(" + words[i].replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&") + ")", "gi");
    s = s.replace(re, "<mark>$1</mark>");
  }}
  return s;
}}

var CAT_LABELS = {json.dumps(CAT_LABELS)};

function render(results) {{
  var filtered = activeCat === "all" ? results : results.filter(function(r) {{ return r.entry.cat === activeCat; }});
  var el = document.getElementById("results");
  var countEl = document.getElementById("count");
  var q = document.getElementById("q").value.trim();
  if (!q) {{
    countEl.textContent = filtered.length + " pages";
    el.innerHTML = filtered.map(function(r) {{
      return '<div class="result"><a href="' + r.entry.url + '"><span class="title">' + r.entry.title +
        '<span class="cat-tag">' + (CAT_LABELS[r.entry.cat] || r.entry.cat) + '</span></span>' +
        '<div class="desc">' + r.entry.desc + '</div></a></div>';
    }}).join("");
    return;
  }}
  if (filtered.length === 0) {{
    countEl.textContent = "";
    el.innerHTML = '<div class="no-results">No results found. Try different keywords.</div>';
    return;
  }}
  countEl.textContent = filtered.length + " result" + (filtered.length === 1 ? "" : "s");
  el.innerHTML = filtered.map(function(r) {{
    return '<div class="result"><a href="' + r.entry.url + '"><span class="title">' + r.entry.title +
      '<span class="cat-tag">' + (CAT_LABELS[r.entry.cat] || r.entry.cat) + '</span></span>' +
      (r.entry.desc ? '<div class="desc">' + r.entry.desc + '</div>' : '') +
      '<div class="snippet">' + r.snippet + '</div></a></div>';
  }}).join("");
}}

var debounceTimer;
var input = document.getElementById("q");
var clearBtn = document.getElementById("clear");

input.addEventListener("input", function() {{
  clearBtn.style.display = this.value ? "block" : "none";
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(function() {{ render(search(input.value)); }}, 120);
}});

clearBtn.addEventListener("click", function() {{
  input.value = "";
  clearBtn.style.display = "none";
  input.focus();
  render(search(""));
}});

document.getElementById("filters").addEventListener("click", function(e) {{
  if (e.target.tagName !== "BUTTON") return;
  activeCat = e.target.dataset.cat;
  var btns = this.querySelectorAll("button");
  for (var i = 0; i < btns.length; i++) btns[i].classList.remove("active");
  e.target.classList.add("active");
  render(search(input.value));
}});

var params = new URLSearchParams(window.location.search);
if (params.get("q")) {{
  input.value = params.get("q");
  clearBtn.style.display = "block";
}}
render(search(input.value));
</script>
</body></html>"""

out = os.path.join(SITE, "search.html")
open(out, "w").write(page_html)
print(f"rendered search.html {len(page_html) // 1024} KB, {len(index)} pages indexed")
