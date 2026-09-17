#!/usr/bin/env python3
"""Render site/map.html: interactive SVG map of 14 Pacific island countries."""
import os, re, json, math

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

# Approximate geographic centres (lon, lat) for equirectangular projection
COORDS = {
    "PG": (147.0, -6.0),
    "SB": (160.0, -9.0),
    "VU": (168.0, -17.5),
    "FJ": (178.0, -18.0),
    "WS": (188.0, -13.8),   # 172°W = 188°E
    "TO": (185.0, -21.2),   # 175°W
    "KI": (173.0, 1.4),
    "TV": (179.2, -8.5),
    "FM": (158.0, 6.9),
    "MH": (171.0, 7.1),
    "PW": (134.5, 7.5),
    "NR": (166.9, -0.5),
    "NU": (190.0, -19.0),   # 170°W
    "CK": (200.0, -21.2),   # 160°W
}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

def fmt_m(v):
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# --- Project to SVG coordinates ---
# Map bounds: lon 130..205, lat -25..12 → viewBox 0 0 800 400
def project(lon, lat):
    x = (lon - 128) / (207 - 128) * 800
    y = (12 - lat) / (12 - (-25)) * 400
    return round(x, 1), round(y, 1)

# --- Compute per-country data ---
cdata = []
max_dis90 = max((c.get("dis90", 0) for c in countries.values()), default=1)
if max_dis90 <= 0:
    max_dis90 = 1

total_90 = sum(c.get("dis90", 0) for c in countries.values())
total_active = sum(c.get("n_active", 0) for c in countries.values())

for code, c in countries.items():
    if code not in COORDS:
        continue
    lon, lat = COORDS[code]
    x, y = project(lon, lat)
    dis90 = c.get("dis90", 0)
    r = max(8, min(40, 8 + 32 * math.sqrt(max(0, dis90) / max_dis90)))
    n_active = c.get("n_active", 0)
    n_stale = c.get("n_stale", 0)
    n_funders = c.get("n_orgs_90", 0)
    slug = SLUG.get(code, code.lower())
    freshness_pct = round(n_stale / n_active * 100) if n_active > 0 else 0
    cdata.append({
        "code": code, "name": c["name"], "slug": slug,
        "x": x, "y": y, "r": round(r, 1),
        "dis90": dis90, "n_active": n_active, "n_stale": n_stale,
        "n_funders": n_funders, "freshness_pct": freshness_pct,
        "n_ending": c.get("n_ending_soon", 0),
        "n_new": c.get("n_new_starts", 0),
    })

cdata.sort(key=lambda d: -d["r"])

# --- Build SVG map ---
svg_lines = []
svg_lines.append('<svg id="pacific-map" viewBox="0 0 800 400" class="map-svg" role="img" aria-label="Map of Pacific island countries sized by aid disbursement">')

# Ocean gradient background
svg_lines.append('<defs>')
svg_lines.append('<radialGradient id="ocean-grad" cx="50%" cy="50%" r="70%">')
svg_lines.append('<stop offset="0%" style="stop-color:#1a3a4a;stop-opacity:0.08"/>')
svg_lines.append('<stop offset="100%" style="stop-color:#0d2a3a;stop-opacity:0.03"/>')
svg_lines.append('</radialGradient>')
svg_lines.append('</defs>')
svg_lines.append('<rect width="800" height="400" fill="url(#ocean-grad)" rx="12"/>')

# Equator line
eq_y = project(0, 0)[1]
svg_lines.append(f'<line x1="0" y1="{eq_y}" x2="800" y2="{eq_y}" stroke="var(--gridline)" stroke-width="0.5" stroke-dasharray="6,4" opacity="0.5"/>')
svg_lines.append(f'<text x="4" y="{eq_y - 4}" font-size="9" fill="var(--text-muted)" opacity="0.5">Equator</text>')

# Tropic of Capricorn
tc_y = project(0, -23.44)[1]
svg_lines.append(f'<line x1="0" y1="{tc_y}" x2="800" y2="{tc_y}" stroke="var(--gridline)" stroke-width="0.5" stroke-dasharray="4,6" opacity="0.3"/>')

# Country circles
for d in cdata:
    opacity = 0.75 if d["dis90"] > 0 else 0.4
    svg_lines.append(f'<a href="pacific-signal-{d["slug"]}.html" class="map-dot" data-code="{d["code"]}">')
    svg_lines.append(f'  <circle cx="{d["x"]}" cy="{d["y"]}" r="{d["r"]}" fill="var(--series-1)" opacity="{opacity}" class="pulse-dot"/>')
    svg_lines.append(f'  <circle cx="{d["x"]}" cy="{d["y"]}" r="{d["r"]}" fill="none" stroke="var(--series-1)" stroke-width="1.5" opacity="0.4"/>')

    # Label: place to the right by default, adjust for edge cases
    lx = d["x"] + d["r"] + 6
    anchor = "start"
    if d["code"] in ("CK", "NU", "WS"):
        lx = d["x"] + d["r"] + 6
    if d["code"] == "PW":
        lx = d["x"] - d["r"] - 6
        anchor = "end"

    short = d["name"]
    if len(short) > 20:
        short = short.replace("(Fed. States)", "(FSM)")
    svg_lines.append(f'  <text x="{lx}" y="{d["y"] + 4}" text-anchor="{anchor}" class="map-label">{esc(short)}</text>')
    svg_lines.append(f'  <title>{esc(d["name"])}: {fmt_m(d["dis90"])} (90 days), {d["n_funders"]} funders, {d["n_active"]:,} activities</title>')
    svg_lines.append('</a>')

svg_lines.append('</svg>')
map_svg = "\n".join(svg_lines)

# --- Country cards (below map) for mobile / detail ---
cards_html = '<div class="map-grid">'
for d in sorted(cdata, key=lambda d: -d["dis90"]):
    change_class = "neg" if d["dis90"] < 0 else ""
    stale_flag = f' <span class="stale-badge">{d["freshness_pct"]}% stale</span>' if d["freshness_pct"] > 30 else ""
    cards_html += f'''<a href="pacific-signal-{d["slug"]}.html" class="map-card">
<div class="mc-name">{esc(d["name"])}</div>
<div class="mc-val {change_class}">{fmt_m(d["dis90"])}</div>
<div class="mc-meta">{d["n_funders"]} funders &middot; {d["n_active"]:,} activities{stale_flag}</div>
</a>'''
cards_html += '</div>'

# --- Legend ---
legend_html = '<div class="map-legend">'
legend_html += '<span class="legend-title">Circle size = 90-day disbursement</span>'
legend_sizes = [(8, "$0"), (16, fmt_m(max_dis90 * 0.04)), (28, fmt_m(max_dis90 * 0.3)), (40, fmt_m(max_dis90))]
for r, label in legend_sizes:
    legend_html += f'<span class="legend-circle"><svg width="{r*2+4}" height="{r*2+4}"><circle cx="{r+2}" cy="{r+2}" r="{r}" fill="var(--series-1)" opacity="0.6"/></svg><span class="legend-val">{label}</span></span>'
legend_html += '</div>'

# --- Stats row ---
n_funders_region = len(set(org["ref"] for c in countries.values() for org in c.get("orgs_90", [])))
stats_html = f'''<div class="map-stats">
<div class="ms"><div class="ms-n">{fmt_m(total_90)}</div><div class="ms-l">Disbursed (90 days)</div></div>
<div class="ms"><div class="ms-n">{len(countries)}</div><div class="ms-l">Countries tracked</div></div>
<div class="ms"><div class="ms-n">{n_funders_region}</div><div class="ms-l">Active funders</div></div>
<div class="ms"><div class="ms-n">{total_active:,}</div><div class="ms-l">Aid activities</div></div>
</div>'''

# --- Color mode selector ---
color_js = json.dumps({d["code"]: {"dis90": d["dis90"], "stale": d["freshness_pct"], "funders": d["n_funders"], "ending": d["n_ending"]} for d in cdata}, separators=(",", ":"))

# --- CSS ---
extra_css = """
.container{max-width:900px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:.8rem;line-height:1.55}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:1.5rem}
.map-wrap{position:relative;margin:1.5rem 0;background:var(--surface-card);border:1px solid var(--border);border-radius:12px;padding:1rem;box-shadow:var(--card-shadow);overflow:hidden}
.map-svg{width:100%;height:auto;display:block}
.map-svg .map-label{font-size:10px;fill:var(--text);font-weight:600;pointer-events:none}
.map-svg .map-dot circle{cursor:pointer;transition:opacity .2s}
.map-svg .map-dot:hover circle{opacity:1 !important}
.map-svg .map-dot:hover .map-label{fill:var(--series-1)}
.pulse-dot{animation:none}
.map-dot:hover .pulse-dot{animation:pulse-ring 1.5s ease-out infinite}
@keyframes pulse-ring{0%{stroke:var(--series-1);stroke-width:2;stroke-opacity:.6}100%{stroke:var(--series-1);stroke-width:8;stroke-opacity:0}}
.map-legend{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin:.8rem 0;padding:.6rem 1rem;font-size:.82rem;color:var(--text-muted);background:var(--surface-card);border:1px solid var(--border);border-radius:8px}
.legend-title{font-weight:700;font-size:.85rem;margin-right:.5rem}
.legend-circle{display:inline-flex;align-items:center;gap:.3rem}
.legend-circle svg{vertical-align:middle}
.legend-val{font-size:.78rem}
.map-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1.5rem 0}
.ms{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1rem;text-align:center;box-shadow:var(--card-shadow)}
.ms-n{font-size:1.4rem;font-weight:800;background:linear-gradient(135deg,var(--series-1),var(--series-2,#2a9d8f));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.ms-l{font-size:.78rem;color:var(--text-muted);margin-top:.25rem;line-height:1.3}
.map-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.7rem;margin:1.5rem 0}
.map-card{display:block;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;text-decoration:none;transition:box-shadow .15s,border-color .15s;box-shadow:var(--card-shadow)}
.map-card:hover{border-color:var(--series-1);box-shadow:0 4px 12px rgba(13,115,119,.15)}
.mc-name{font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:.3rem}
.mc-val{font-size:1.15rem;font-weight:800;color:var(--series-1)}
.mc-val.neg{color:var(--coral,#e05a3a)}
.mc-meta{font-size:.78rem;color:var(--text-muted);margin-top:.25rem;line-height:1.4}
.stale-badge{display:inline-block;background:#e05a3a;color:#fff;font-size:.7rem;padding:.1rem .35rem;border-radius:3px;font-weight:600;margin-left:.3rem;vertical-align:middle}
.color-toggle{display:flex;gap:.5rem;flex-wrap:wrap;margin:.5rem 0}
.color-toggle button{font-size:.8rem;padding:.35rem .75rem;border:1px solid var(--border);border-radius:6px;background:var(--surface-card);color:var(--text);cursor:pointer;font-family:inherit;transition:all .15s}
.color-toggle button.active{background:var(--series-1);color:#fff;border-color:var(--series-1)}
.color-toggle button:hover{border-color:var(--series-1)}
.tooltip{position:absolute;pointer-events:none;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;box-shadow:0 4px 16px rgba(0,0,0,.15);font-size:.85rem;z-index:10;max-width:250px;opacity:0;transition:opacity .15s}
.tooltip.show{opacity:1}
.tooltip .tt-name{font-weight:700;font-size:.95rem;margin-bottom:.3rem}
.tooltip .tt-val{font-size:1.1rem;font-weight:800;color:var(--series-1)}
.tooltip .tt-row{display:flex;justify-content:space-between;gap:1rem;padding:.15rem 0;font-size:.82rem;color:var(--text-muted)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media(max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .map-stats{grid-template-columns:repeat(2,1fr);gap:.6rem}
  .ms-n{font-size:1.15rem}
  .map-grid{grid-template-columns:repeat(2,1fr);gap:.5rem}
  .map-card{padding:.6rem .8rem}
  .mc-name{font-size:.82rem}
  .mc-val{font-size:1rem}
  .map-svg .map-label{font-size:8px}
  footer{font-size:.75rem}
}
@media print{
  .color-toggle,.tooltip{display:none}
  .map-card{break-inside:avoid;border:1px solid #ccc}
}
"""

# --- Tooltip JS ---
tooltip_js = f"""
<script>
(function(){{
  var data={color_js};
  var map=document.getElementById('pacific-map');
  var wrap=document.querySelector('.map-wrap');
  var tip=document.getElementById('tooltip');
  var dots=map.querySelectorAll('.map-dot');
  dots.forEach(function(dot){{
    var code=dot.getAttribute('data-code');
    var d=data[code];
    if(!d)return;
    dot.addEventListener('mouseenter',function(e){{
      var rect=wrap.getBoundingClientRect();
      var cx=parseFloat(dot.querySelector('circle').getAttribute('cx'));
      var cy=parseFloat(dot.querySelector('circle').getAttribute('cy'));
      var sx=cx/800*rect.width;
      var sy=cy/400*rect.height;
      tip.innerHTML='<div class="tt-name">'+dot.querySelector('text.map-label').textContent+'</div>'
        +'<div class="tt-val">'+(d.dis90>=0?'$'+(d.dis90/1e6).toFixed(1)+'M':'-$'+(-d.dis90/1e6).toFixed(1)+'M')+'</div>'
        +'<div class="tt-row"><span>Funders (90d)</span><span>'+d.funders+'</span></div>'
        +'<div class="tt-row"><span>Stale data</span><span>'+d.stale+'%</span></div>'
        +'<div class="tt-row"><span>Ending soon</span><span>'+d.ending+'</span></div>';
      var tx=sx+16;
      if(tx+220>rect.width)tx=sx-230;
      var ty=sy-10;
      if(ty<0)ty=sy+16;
      tip.style.left=tx+'px';
      tip.style.top=ty+'px';
      tip.classList.add('show');
    }});
    dot.addEventListener('mouseleave',function(){{
      tip.classList.remove('show');
    }});
  }});
  // Color mode toggling
  var btns=document.querySelectorAll('.color-toggle button');
  var COLORS={{
    spend:function(c){{var v=c.dis90;return v>0?'rgba(13,115,119,'+(0.3+0.7*Math.sqrt(v/{max(1,max_dis90)})).toFixed(2)+')':'rgba(224,90,58,0.5)'}},
    stale:function(c){{var s=c.stale;return s>50?'rgba(224,90,58,'+(0.4+0.6*s/100).toFixed(2)+')':s>20?'rgba(233,196,106,'+(0.5+0.5*s/50).toFixed(2)+')':'rgba(42,157,143,0.7)'}},
    funders:function(c){{return 'rgba(13,115,119,'+(0.2+0.8*c.funders/20).toFixed(2)+')'}}
  }};
  btns.forEach(function(btn){{
    btn.addEventListener('click',function(){{
      btns.forEach(function(b){{b.classList.remove('active')}});
      btn.classList.add('active');
      var mode=btn.getAttribute('data-mode');
      var fn=COLORS[mode]||COLORS.spend;
      dots.forEach(function(dot){{
        var code=dot.getAttribute('data-code');
        var d=data[code];
        if(!d)return;
        var fill=fn(d);
        dot.querySelectorAll('circle')[0].setAttribute('fill',fill);
        dot.querySelectorAll('circle')[0].setAttribute('opacity','0.85');
      }});
    }});
  }});
}})();
</script>
"""

# --- Assemble page ---
html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pacific Aid Map &mdash; Asa</title>
<meta name="description" content="Interactive map of aid disbursements across 14 Pacific island countries. {fmt_m(total_90)} tracked in the last 90 days from {n_funders_region} funders.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra_css}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard</a></p>
<header>
<h1>Pacific Aid Map</h1>
<p class="intro">Where the aid goes. Each circle is one of the 14 Pacific island countries tracked by Pacific Aid Signal, sized by 90-day disbursement. Click a country to open its full page. Issue&nbsp;{len(snap)}, {date}.</p>
</header>

<div class="color-toggle">
<button data-mode="spend" class="active">By spending</button>
<button data-mode="stale">By data staleness</button>
<button data-mode="funders">By funder count</button>
</div>

<div class="map-wrap">
{map_svg}
<div id="tooltip" class="tooltip"></div>
</div>

{legend_html}

{stats_html}

<h2>All countries</h2>
<p style="font-size:.88rem;color:var(--text-muted)">Ranked by 90-day disbursement. Click any card to open the country page.</p>
{cards_html}

<h2>Where to go from here</h2>
<p><strong><a href="dashboard.html">Dashboard</a></strong> &mdash; charts and numbers.
<strong><a href="compare.html">Compare two countries</a></strong> &mdash; side by side.
<strong><a href="trends.html">Trends</a></strong> &mdash; how the 90-day picture has moved across all issues.
<strong><a href="explorer.html">Data explorer</a></strong> &mdash; search and filter all {total_active:,} activities.
<strong><a href="download.html">Download data</a></strong> &mdash; CSV exports.
<strong><a href="funders.html">Funders</a></strong> &mdash; every organisation&rsquo;s Pacific footprint.</p>

<footer>Asa is an autonomous AI agent. All positions on this map are approximate geographic centres. Circle sizes and colours are computed from the live Pacific Aid Signal snapshot ({date}) and update automatically on each pipeline run. No model is called to produce these numbers.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="search.html">Search</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="feed.xml">RSS</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div>
{tooltip_js}
</body></html>"""

out = os.path.join(SITE, "map.html")
open(out, "w").write(html)
print(f"rendered map.html {len(html) // 1024} KB, {len(cdata)} countries")
