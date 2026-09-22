#!/usr/bin/env python3
"""Render site/freshness.html: data freshness across funders and countries."""
import os, re, json, datetime as dt
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

snap_file = sorted(f for f in os.listdir(os.path.join(HERE, "data"))
                   if f.startswith("pacific-") and f.endswith(".json") and "index" not in f)[-1]
with open(os.path.join(HERE, "data", snap_file)) as fh:
    snap = json.load(fh)

issue_date = snap.get("date", snap.get("generated", "")[:10])
today = dt.date.today()

countries = sorted(snap["countries"].items(), key=lambda x: -x[1]["dis90"])
codes = [c[0] for c in countries]
names = {c[0]: c[1]["name"] for c in countries}
short_names = {
    "PG": "PNG", "FJ": "Fiji", "SB": "SIs", "VU": "Van", "WS": "Samoa",
    "TO": "Tonga", "KI": "Kiri", "TV": "Tuv", "FM": "Micro", "MH": "RMI",
    "PW": "Palau", "NR": "Nauru", "NU": "Niue", "CK": "Cook"
}

funder_map = {}
for code, c in snap["countries"].items():
    for entry in c.get("currency", []):
        name = entry["name"]
        if name not in funder_map:
            funder_map[name] = {"by_country": {}, "total_life": 0}
        funder_map[name]["by_country"][code] = {
            "age": entry.get("age_days"),
            "latest": entry.get("latest"),
            "lifetime": entry.get("lifetime_usd", 0),
        }
        funder_map[name]["total_life"] += entry.get("lifetime_usd", 0)

top_funders = sorted(funder_map.items(), key=lambda x: -x[1]["total_life"])[:25]


def usd(v):
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.0f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def age_color(age):
    if age is None:
        return "var(--text-muted)"
    if age <= 90:
        return "#0d9e4f"
    if age <= 180:
        return "#8bb833"
    if age <= 365:
        return "#e09e0a"
    return "#e05a3a"


def age_label(age):
    if age is None:
        return "no data"
    if age <= 90:
        return "current"
    if age <= 180:
        return "recent"
    if age <= 365:
        return "aging"
    return "stale"


# Build heatmap SVG
n_funders = len(top_funders)
n_countries = len(codes)
cell_w, cell_h = 44, 26
label_w = 280
header_h = 60
svg_w = label_w + n_countries * cell_w + 20
svg_h = header_h + n_funders * cell_h + 10

cells = []
for fi, (fname, fdata) in enumerate(top_funders):
    y = header_h + fi * cell_h
    cells.append(f'<text x="{label_w - 8}" y="{y + cell_h // 2 + 4}" text-anchor="end" '
                 f'font-size="11" fill="var(--text-primary)">{esc(fname[:35])}</text>')
    total = fdata["total_life"]
    cells.append(f'<text x="{label_w - 8}" y="{y + cell_h // 2 + 14}" text-anchor="end" '
                 f'font-size="9" fill="var(--text-muted)">{usd(total)}</text>')
    for ci, code in enumerate(codes):
        x = label_w + ci * cell_w
        cd = fdata["by_country"].get(code)
        if cd:
            age = cd["age"]
            color = age_color(age)
            opacity = "1" if age is not None and age <= 365 else ".85"
            age_text = f'{age}d' if age is not None else "?"
            cells.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cell_w - 2}" height="{cell_h - 2}" '
                         f'rx="3" fill="{color}" opacity="{opacity}"/>')
            cells.append(f'<text x="{x + cell_w // 2}" y="{y + cell_h // 2 + 4}" text-anchor="middle" '
                         f'font-size="10" fill="white" font-weight="600">{age_text}</text>')
        else:
            cells.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cell_w - 2}" height="{cell_h - 2}" '
                         f'rx="3" fill="var(--surface-card)" stroke="var(--gridline)" stroke-width="1"/>')

col_headers = []
for ci, code in enumerate(codes):
    x = label_w + ci * cell_w + cell_w // 2
    col_headers.append(f'<text x="{x}" y="{header_h - 8}" text-anchor="middle" '
                       f'font-size="10" fill="var(--text-muted)" font-weight="600">'
                       f'{short_names.get(code, code)}</text>')

legend_y = header_h + n_funders * cell_h + 2
legend = f"""<g transform="translate({label_w}, {legend_y - 20})">
<rect x="0" y="0" width="14" height="14" rx="3" fill="#0d9e4f"/><text x="18" y="11" font-size="10" fill="var(--text-muted)">&le;90d</text>
<rect x="60" y="0" width="14" height="14" rx="3" fill="#8bb833"/><text x="78" y="11" font-size="10" fill="var(--text-muted)">&le;180d</text>
<rect x="130" y="0" width="14" height="14" rx="3" fill="#e09e0a"/><text x="148" y="11" font-size="10" fill="var(--text-muted)">&le;365d</text>
<rect x="200" y="0" width="14" height="14" rx="3" fill="#e05a3a"/><text x="218" y="11" font-size="10" fill="var(--text-muted)">&gt;365d</text>
<rect x="280" y="0" width="14" height="14" rx="3" fill="var(--surface-card)" stroke="var(--gridline)" stroke-width="1"/><text x="298" y="11" font-size="10" fill="var(--text-muted)">not listed</text>
</g>"""

heatmap_svg = f"""<svg viewBox="0 0 {svg_w} {svg_h + 10}" style="width:100%;max-width:{svg_w}px;overflow-x:auto" xmlns="http://www.w3.org/2000/svg">
{''.join(col_headers)}
{''.join(cells)}
{legend}
</svg>"""

# Key findings
stale_big = []
for fname, fdata in top_funders:
    ages = [fdata["by_country"][c]["age"] for c in fdata["by_country"] if fdata["by_country"][c]["age"] is not None]
    if ages and max(ages) > 365 and fdata["total_life"] > 100e6:
        worst = max(ages)
        stale_big.append((fname, worst, fdata["total_life"], len(fdata["by_country"])))
stale_big.sort(key=lambda x: -x[2])

current_big = []
for fname, fdata in top_funders[:10]:
    ages = [fdata["by_country"][c]["age"] for c in fdata["by_country"] if fdata["by_country"][c]["age"] is not None]
    if ages and max(ages) <= 90:
        current_big.append((fname, max(ages), fdata["total_life"], len(fdata["by_country"])))

# Country freshness summary
country_fresh = []
for code, c in countries:
    cur = c.get("currency", [])
    if not cur:
        continue
    current_count = sum(1 for e in cur if e.get("age_days") is not None and e["age_days"] <= 90)
    stale_count = sum(1 for e in cur if e.get("age_days") is not None and e["age_days"] > 365)
    total_count = len(cur)
    country_fresh.append((code, names[code], current_count, stale_count, total_count))

stale_findings = ""
for fname, worst, total, nc in stale_big[:6]:
    stale_findings += f'<li><strong>{esc(fname)}</strong> &mdash; {usd(total)} across {nc} {"country" if nc == 1 else "countries"}, newest record {worst} days old</li>\n'

current_findings = ""
for fname, best, total, nc in current_big[:5]:
    current_findings += f'<li><strong>{esc(fname)}</strong> &mdash; {usd(total)} across {nc} {"country" if nc == 1 else "countries"}, data within {best} days</li>\n'

# Country freshness cards
country_cards = ""
for code, name, cur, stale, total in country_fresh:
    pct_current = cur / total * 100 if total else 0
    pct_stale = stale / total * 100 if total else 0
    bar_green = f'<span style="display:inline-block;width:{pct_current:.0f}%;height:8px;background:#0d9e4f;border-radius:4px 0 0 4px"></span>'
    bar_red = f'<span style="display:inline-block;width:{pct_stale:.0f}%;height:8px;background:#e05a3a;border-radius:0 4px 4px 0"></span>'
    bar_mid = f'<span style="display:inline-block;width:{100-pct_current-pct_stale:.0f}%;height:8px;background:#e09e0a"></span>'
    country_cards += f"""<div class="cf-card">
<a href="pacific-signal-{name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('.', '')}.html"><strong>{esc(name)}</strong></a>
<span class="cf-bar">{bar_green}{bar_mid}{bar_red}</span>
<span class="cf-nums">{cur}/{total} current, {stale} stale</span>
</div>\n"""

n_total_funders = len(funder_map)
n_stale = sum(1 for _, fd in funder_map.items()
              if any(fd["by_country"][c]["age"] is not None and fd["by_country"][c]["age"] > 365
                     for c in fd["by_country"]))

extra = """
.container{max-width:820px}
h2{font-size:1.15rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
p{margin-bottom:1rem;line-height:1.65}
a{color:var(--series-1)}
.intro{font-size:1.05rem;line-height:1.65;margin-bottom:2rem}
.key-stat{display:inline-block;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.6rem 1rem;margin:.3rem .4rem .3rem 0;font-size:.9rem}
.key-stat b{font-size:1.1rem;display:block;margin-bottom:.15rem}
.findings{margin:1rem 0 1.5rem}
.findings li{margin-bottom:.5rem;line-height:1.5}
.heatmap-wrap{overflow-x:auto;margin:1.5rem 0;-webkit-overflow-scrolling:touch}
.cf-grid{display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:.6rem;margin:1rem 0}
.cf-card{background:var(--surface-card);border:1px solid var(--border);border-radius:6px;padding:.6rem .8rem;font-size:.85rem}
.cf-card a{text-decoration:none}
.cf-bar{display:flex;width:100%;margin:.3rem 0;border-radius:4px;overflow:hidden}
.cf-nums{font-size:.78rem;color:var(--text-muted)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .intro{font-size:.95rem}
  .heatmap-wrap{margin:1rem -.9rem;padding:0 .9rem}
  .cf-grid{grid-template-columns:1fr}
}
"""

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data freshness &mdash; Pacific Aid Signal &mdash; Asa</title>
<meta name="description" content="How current is the aid data for 14 Pacific island countries? A funder-by-country freshness heatmap showing who publishes on time and who doesn't.">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}{extra}</style></head><body><div class="container">
<p style="font-size:.85rem"><a href="index.html">&larr; Asa</a></p>
<header>
<h1>Data freshness</h1>
<p class="intro">The Pacific Aid Signal reads five sources every twelve hours. But reading data and having <em>current</em> data are not the same thing. This page shows how old each funder&rsquo;s records are, country by country. Green means the funder published something dated within the last 90 days. Red means the newest record is more than a year old. Empty means the funder has no recorded activity in that country.</p>
</header>

<div class="key-stat"><b>{n_total_funders}</b> funders tracked</div>
<div class="key-stat"><b>{n_stale}</b> with stale data (&gt;1 year)</div>
<div class="key-stat"><b>442 days</b> Australia&rsquo;s IATI gap</div>
<div class="key-stat"><b>{len(codes)}</b> countries</div>

<h2>Freshness heatmap</h2>
<p>Each cell shows how many days old the funder&rsquo;s newest IATI record is for that country. Funders are ranked by lifetime spend. Scroll right on mobile to see all countries.</p>

<div class="heatmap-wrap">
{heatmap_svg}
</div>

<h2>Who is publishing current data</h2>
<ul class="findings">
{current_findings}
</ul>

<h2>Who is not</h2>
<p>These are among the largest funders by lifetime spend in the Pacific. Their data is more than a year old, which means the 90-day picture on each country page is missing their current activity entirely.</p>
<ul class="findings">
{stale_findings}
</ul>

<h2>What this means</h2>
<p>When a funder&rsquo;s data goes stale, their spending disappears from the 90-day picture &mdash; not because they stopped spending, but because they stopped publishing. The Signal&rsquo;s 90-day figures for any country are therefore a lower bound: they show what has been <em>reported</em>, not what has been <em>spent</em>. The gap between the two is largest where the biggest funders have the oldest data.</p>
<p>For Australia, the single largest bilateral funder in 9 of these 14 countries, the newest IATI record is dated 30 June 2025. That is why the Signal reads DFAT&rsquo;s business notifications directly: they are the only source that says what Australia is doing now.</p>

<h2>Freshness by country</h2>
<div class="cf-grid">
{country_cards}
</div>

<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
<br>Data as at issue {snap.get('date', 'unknown')}. Freshness is computed from the newest transaction date per funder per country in IATI.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="feed.xml">RSS feed</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "freshness.html")
with open(out, "w") as fh:
    fh.write(html)
print(f"rendered freshness.html {len(html) // 1024} KB, {n_total_funders} funders, {n_stale} stale")
