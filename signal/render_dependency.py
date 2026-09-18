#!/usr/bin/env python3
"""Render site/dependency.html: aid dependency and risk analysis for 14 Pacific countries."""
import os, re, json, glob, math, datetime as dt
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

files = sorted(glob.glob(os.path.join(HERE, "data", "pacific-*.json")))
files = [f for f in files if "index" not in f]
latest = json.load(open(files[-1]))
countries = latest["countries"]
issue_date = latest.get("date", os.path.basename(files[-1])[8:18])
today = dt.date.today()

SLUGS = {
    "PG": "papua-new-guinea", "FJ": "fiji", "SB": "solomon-islands",
    "VU": "vanuatu", "WS": "samoa", "TO": "tonga", "KI": "kiribati",
    "TV": "tuvalu", "FM": "micronesia", "MH": "marshall-islands",
    "PW": "palau", "NR": "nauru", "NU": "niue", "CK": "cook-islands",
}
SHORT = {
    "PG": "PNG", "FJ": "Fiji", "SB": "Sol Is", "VU": "Vanuatu",
    "WS": "Samoa", "TO": "Tonga", "KI": "Kiribati", "TV": "Tuvalu",
    "FM": "FSM", "MH": "RMI", "PW": "Palau", "NR": "Nauru",
    "NU": "Niue", "CK": "Cook Is",
}
COLORS = {
    "low": "#059669", "moderate": "#d97706", "high": "#dc2626", "critical": "#7f1d1d"
}


def usd(v):
    if abs(v) >= 1e9: return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6: return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def pct(v):
    return f"{v:.0f}%" if v >= 1 else f"{v:.1f}%"


def risk_level(score):
    if score >= 75: return "critical"
    if score >= 50: return "high"
    if score >= 25: return "moderate"
    return "low"


def risk_dot(level):
    return f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{COLORS[level]};margin-right:4px;vertical-align:middle"></span>'


# --- Compute metrics per country ---
rows = []
for cc, c in countries.items():
    orgs = c.get("orgs_90", [])
    dis90 = c.get("dis90", 0)
    n_active = c.get("n_active", 0)
    n_stale = c.get("n_stale", 0)
    n_ending = c.get("n_ending_soon", 0)
    n_new = c.get("n_new_starts", 0)

    # Funder concentration (HHI on 90-day shares)
    if dis90 > 0 and orgs:
        shares = [(o["usd"] / dis90 * 100) for o in orgs if o["usd"] > 0]
        hhi = sum(s * s for s in shares)
        top1_share = max(shares) if shares else 0
        top3_share = sum(sorted(shares, reverse=True)[:3])
        n_funders_90 = len([s for s in shares if s > 0])
    else:
        hhi = 10000
        top1_share = 100
        top3_share = 100
        n_funders_90 = 0

    top1_name = orgs[0]["name"] if orgs else "—"
    top1_usd = orgs[0]["usd"] if orgs else 0

    # Data staleness
    currency = c.get("currency", [])
    stale_funders = [e for e in currency if e.get("age_days", 0) > 365]
    n_currency = len(currency)
    stale_pct = (len(stale_funders) / n_currency * 100) if n_currency > 0 else 0

    # Freshest and stalest
    if currency:
        freshest = min(currency, key=lambda e: e.get("age_days", 99999))
        stalest = max(currency, key=lambda e: e.get("age_days", 0))
    else:
        freshest = stalest = None

    # Pipeline balance
    net_pipeline = n_new - n_ending
    ending_ratio = (n_ending / n_active * 100) if n_active > 0 else 0

    # Composite risk score (0-100)
    conc_score = min(100, hhi / 100)  # HHI 10000 → 100
    stale_score = stale_pct
    pipeline_score = min(100, ending_ratio * 2)  # 50% ending → 100
    composite = conc_score * 0.4 + stale_score * 0.3 + pipeline_score * 0.3

    rows.append({
        "cc": cc, "name": c["name"], "dis90": dis90,
        "hhi": hhi, "top1_share": top1_share, "top3_share": top3_share,
        "top1_name": top1_name, "top1_usd": top1_usd,
        "n_funders_90": n_funders_90,
        "n_active": n_active, "n_stale": n_stale,
        "n_ending": n_ending, "n_new": n_new,
        "stale_pct": stale_pct, "n_stale_funders": len(stale_funders),
        "n_currency": n_currency,
        "freshest": freshest, "stalest": stalest,
        "ending_ratio": ending_ratio, "net_pipeline": net_pipeline,
        "conc_score": conc_score, "stale_score": stale_score,
        "pipeline_score": pipeline_score, "composite": composite,
    })

rows.sort(key=lambda r: -r["composite"])

# --- Key metrics ---
avg_hhi = sum(r["hhi"] for r in rows) / len(rows)
high_conc = len([r for r in rows if r["top1_share"] > 50])
high_stale = len([r for r in rows if r["stale_pct"] > 50])
high_ending = len([r for r in rows if r["ending_ratio"] > 20])

# --- SVG: Composite risk overview bar chart ---
chart_w, bar_h, gap = 700, 28, 5
label_w = 120
val_w = 80
bar_area = chart_w - label_w - val_w
svg_h = len(rows) * (bar_h + gap) + 10
risk_svg = [f'<svg viewBox="0 0 {chart_w} {svg_h}" class="chart" role="img" aria-label="Composite risk score by country">']
for i, r in enumerate(rows):
    y = i * (bar_h + gap) + 5
    level = risk_level(r["composite"])
    bw = max(2, r["composite"] / 100 * bar_area)
    slug = SLUGS.get(r["cc"], "")
    risk_svg.append(f'<a href="pacific-signal-{slug}.html">')
    risk_svg.append(f'<text x="{label_w - 8}" y="{y + bar_h * 0.65}" text-anchor="end" class="chart-label">{esc(SHORT.get(r["cc"], r["name"]))}</text>')
    risk_svg.append(f'<rect x="{label_w}" y="{y + 2}" width="{bw:.1f}" height="{bar_h - 4}" rx="3" fill="{COLORS[level]}" opacity="0.85"/>')
    risk_svg.append(f'<text x="{label_w + bw + 6}" y="{y + bar_h * 0.65}" class="chart-val">{r["composite"]:.0f}</text>')
    risk_svg.append('</a>')
risk_svg.append('</svg>')
risk_chart = '\n'.join(risk_svg)

# --- SVG: Concentration scatter ---
scatter_w, scatter_h = 700, 380
sp_l, sp_r, sp_t, sp_b = 60, 20, 20, 50
pw = scatter_w - sp_l - sp_r
ph = scatter_h - sp_t - sp_b
max_dis = max(r["dis90"] for r in rows) if rows else 1
max_r = 24

scatter_lines = [f'<svg viewBox="0 0 {scatter_w} {scatter_h}" class="chart" role="img" aria-label="Funder concentration vs disbursement">']
# axes
scatter_lines.append(f'<line x1="{sp_l}" y1="{sp_t}" x2="{sp_l}" y2="{sp_t + ph}" stroke="#ccc"/>')
scatter_lines.append(f'<line x1="{sp_l}" y1="{sp_t + ph}" x2="{sp_l + pw}" y2="{sp_t + ph}" stroke="#ccc"/>')
# y-axis labels (top1_share 0-100)
for v in [0, 25, 50, 75, 100]:
    y = sp_t + ph - (v / 100 * ph)
    scatter_lines.append(f'<text x="{sp_l - 8}" y="{y + 4}" text-anchor="end" class="chart-label" style="font-size:10px">{v}%</text>')
    if v > 0:
        scatter_lines.append(f'<line x1="{sp_l}" y1="{y}" x2="{sp_l + pw}" y2="{y}" stroke="#eee"/>')
# x-axis labels (dis90)
for frac in [0, 0.25, 0.5, 0.75, 1.0]:
    x = sp_l + frac * pw
    val = frac * max_dis
    scatter_lines.append(f'<text x="{x}" y="{sp_t + ph + 18}" text-anchor="middle" class="chart-label" style="font-size:10px">{usd(val)}</text>')
# axis titles
scatter_lines.append(f'<text x="{sp_l + pw / 2}" y="{sp_t + ph + 38}" text-anchor="middle" class="chart-label" style="font-size:11px">90-day disbursements</text>')
scatter_lines.append(f'<text x="14" y="{sp_t + ph / 2}" text-anchor="middle" class="chart-label" style="font-size:11px" transform="rotate(-90,14,{sp_t + ph / 2})">Top funder share (%)</text>')
# danger zone
danger_y = sp_t + ph - (50 / 100 * ph)
scatter_lines.append(f'<rect x="{sp_l}" y="{sp_t}" width="{pw}" height="{danger_y - sp_t}" fill="#dc2626" opacity="0.04"/>')
scatter_lines.append(f'<line x1="{sp_l}" y1="{danger_y}" x2="{sp_l + pw}" y2="{danger_y}" stroke="#dc2626" stroke-dasharray="4" opacity="0.4"/>')
scatter_lines.append(f'<text x="{sp_l + pw - 4}" y="{danger_y - 4}" text-anchor="end" style="font-size:9px;fill:#dc2626;opacity:0.6">50% single-funder threshold</text>')
# dots
for r in rows:
    x = sp_l + (r["dis90"] / max_dis * pw) if max_dis > 0 else sp_l
    y = sp_t + ph - (r["top1_share"] / 100 * ph)
    radius = max(6, min(max_r, math.sqrt(r["n_active"]) * 1.5))
    level = risk_level(r["composite"])
    slug = SLUGS.get(r["cc"], "")
    scatter_lines.append(f'<a href="pacific-signal-{slug}.html">')
    scatter_lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{COLORS[level]}" opacity="0.7" stroke="#fff" stroke-width="1"/>')
    scatter_lines.append(f'<text x="{x:.1f}" y="{y - radius - 3:.1f}" text-anchor="middle" style="font-size:9px;fill:#333">{esc(SHORT.get(r["cc"], r["cc"]))}</text>')
    scatter_lines.append('</a>')
scatter_lines.append('</svg>')
scatter_chart = '\n'.join(scatter_lines)

# --- Build country cards ---
cards_html = []
for r in rows:
    level = risk_level(r["composite"])
    slug = SLUGS.get(r["cc"], "")

    # Mini funder bar
    orgs = countries[r["cc"]].get("orgs_90", [])
    funder_bars = []
    if orgs and r["dis90"] > 0:
        bar_colors = ["#0d7377", "#2a9d8f", "#e9c46a", "#e05a3a", "#606c76"]
        for j, o in enumerate(orgs[:5]):
            w = o["usd"] / r["dis90"] * 100
            c = bar_colors[j % len(bar_colors)]
            funder_bars.append(f'<div style="width:{w:.1f}%;background:{c};height:22px;display:inline-block" title="{esc(o["name"])}: {usd(o["usd"])} ({w:.0f}%)"></div>')
        remainder = 100 - sum(o["usd"] / r["dis90"] * 100 for o in orgs[:5])
        if remainder > 1:
            funder_bars.append(f'<div style="width:{remainder:.1f}%;background:#ddd;height:22px;display:inline-block" title="Others"></div>')

    funder_bar_html = f'<div style="display:flex;border-radius:4px;overflow:hidden;margin:8px 0">{"".join(funder_bars)}</div>' if funder_bars else ''

    # Funder legend
    legend_items = []
    for j, o in enumerate(orgs[:5]):
        bar_colors = ["#0d7377", "#2a9d8f", "#e9c46a", "#e05a3a", "#606c76"]
        c = bar_colors[j % len(bar_colors)]
        s = o["usd"] / r["dis90"] * 100 if r["dis90"] > 0 else 0
        legend_items.append(f'<span style="font-size:12px"><span style="display:inline-block;width:10px;height:10px;background:{c};border-radius:2px;margin-right:3px;vertical-align:middle"></span>{esc(o["name"])} ({s:.0f}%)</span>')
    legend_html = ' &middot; '.join(legend_items)

    # Stalest funder
    stalest_line = ""
    if r["stalest"]:
        s = r["stalest"]
        stalest_line = f'Stalest: {esc(s["name"])} ({s.get("age_days", 0)} days, last {s.get("latest", "?")[:10]})'

    cards_html.append(f"""
<div class="card" style="border-left:4px solid {COLORS[level]}">
<h3><a href="pacific-signal-{slug}.html">{esc(r["name"])}</a>
<span style="float:right;font-size:14px">{risk_dot(level)} {level.title()} risk ({r["composite"]:.0f})</span></h3>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin:8px 0">
<div class="metric-box"><div class="metric-val">{usd(r["dis90"])}</div><div class="metric-label">90-day disbursements</div></div>
<div class="metric-box"><div class="metric-val">{pct(r["top1_share"])}</div><div class="metric-label">Top funder share</div></div>
<div class="metric-box"><div class="metric-val">{r["hhi"]:.0f}</div><div class="metric-label">HHI concentration</div></div>
<div class="metric-box"><div class="metric-val">{r["n_funders_90"]}</div><div class="metric-label">Active funders</div></div>
</div>
{funder_bar_html}
<div style="font-size:12px;line-height:1.6;color:#555;margin:4px 0">{legend_html}</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:6px;margin:8px 0;font-size:13px">
<div>{risk_dot(risk_level(r["stale_score"]))} Data: {r["n_stale_funders"]}/{r["n_currency"]} funders stale ({pct(r["stale_pct"])})</div>
<div>{risk_dot(risk_level(r["pipeline_score"]))} Pipeline: {r["n_ending"]} ending, {r["n_new"]} new starts</div>
<div>{risk_dot(risk_level(r["conc_score"]))} Top funder: {esc(r["top1_name"][:35])} at {usd(r["top1_usd"])}</div>
<div style="font-size:12px;color:#777">{stalest_line}</div>
</div>
</div>""")

all_cards = '\n'.join(cards_html)

# --- Historical trend (HHI over issues) ---
hhi_by_issue = []
for f in files:
    with open(f) as fh:
        d = json.load(fh)
    date = d.get("date", os.path.basename(f)[8:18])
    hhis = {}
    for cc2, c2 in d["countries"].items():
        o90 = c2.get("orgs_90", [])
        d90 = c2.get("dis90", 0)
        if d90 > 0 and o90:
            shares = [(o["usd"] / d90 * 100) for o in o90 if o["usd"] > 0]
            hhis[cc2] = sum(s * s for s in shares)
        else:
            hhis[cc2] = 10000
    hhi_by_issue.append({"date": date, "hhis": hhis})

# Regional HHI trend sparkline
if len(hhi_by_issue) > 1:
    avg_hhis = [sum(h["hhis"].values()) / len(h["hhis"]) for h in hhi_by_issue]
    sp_w, sp_h = 300, 60
    y_lo = min(avg_hhis) * 0.9
    y_hi = max(avg_hhis) * 1.1
    if y_hi <= y_lo:
        y_hi = y_lo + 100
    pts = []
    for i, v in enumerate(avg_hhis):
        x = 4 + i / (len(avg_hhis) - 1) * (sp_w - 8)
        y = 4 + (1 - (v - y_lo) / (y_hi - y_lo)) * (sp_h - 8)
        pts.append(f"{x:.1f},{y:.1f}")
    hhi_sparkline = f'<svg viewBox="0 0 {sp_w} {sp_h}" style="width:300px;height:60px"><polyline points="{" ".join(pts)}" fill="none" stroke="#0d7377" stroke-width="2"/><circle cx="{pts[-1].split(",")[0]}" cy="{pts[-1].split(",")[1]}" r="3" fill="#0d7377"/></svg>'
    hhi_trend_note = f'<p style="font-size:13px;color:#555">Regional average HHI across {len(hhi_by_issue)} issues: {avg_hhis[0]:.0f} &rarr; {avg_hhis[-1]:.0f}</p>'
else:
    hhi_sparkline = ""
    hhi_trend_note = ""

# --- Rankings tables ---
most_concentrated = sorted(rows, key=lambda r: -r["hhi"])[:5]
least_concentrated = sorted(rows, key=lambda r: r["hhi"])[:5]
most_stale = sorted(rows, key=lambda r: -r["stale_pct"])[:5]
most_ending = sorted(rows, key=lambda r: -r["ending_ratio"])[:5]


def ranking_table(items, val_fn, val_label):
    trs = []
    for r in items:
        slug = SLUGS.get(r["cc"], "")
        level = risk_level(r["composite"])
        trs.append(f'<tr><td>{risk_dot(level)} <a href="pacific-signal-{slug}.html">{esc(r["name"])}</a></td><td style="text-align:right">{val_fn(r)}</td></tr>')
    return f'<table class="ranked"><thead><tr><th>Country</th><th style="text-align:right">{esc(val_label)}</th></tr></thead><tbody>{"".join(trs)}</tbody></table>'


conc_table = ranking_table(most_concentrated, lambda r: f'{r["hhi"]:.0f} (top: {pct(r["top1_share"])})', "HHI (top funder)")
div_table = ranking_table(least_concentrated, lambda r: f'{r["hhi"]:.0f} ({r["n_funders_90"]} funders)', "HHI (funders)")
stale_table = ranking_table(most_stale, lambda r: f'{r["n_stale_funders"]}/{r["n_currency"]} ({pct(r["stale_pct"])})', "Stale funders")
ending_table = ranking_table(most_ending, lambda r: f'{r["n_ending"]}/{r["n_active"]} ({pct(r["ending_ratio"])})', "Ending / active")

n_issues = len(hhi_by_issue)

# --- HTML ---
html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dependency &amp; Risk Analysis &mdash; Pacific Aid Signal</title>
<meta name="description" content="How concentrated is each Pacific country's aid? Who depends on a single funder, where is the data stale, and where are programmes ending faster than they start?">
<link rel="alternate" type="application/rss+xml" title="Pacific Aid Signal" href="feed.xml">
<style>{style}
.metric-box {{ background:#f8f9fa; border-radius:6px; padding:10px 14px; text-align:center }}
.metric-val {{ font-size:1.5em; font-weight:800; color:#0d7377 }}
.metric-label {{ font-size:11px; color:#666; margin-top:2px }}
.card {{ background:#fff; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.08); padding:16px 20px; margin:12px 0 }}
.ranked {{ width:100%; border-collapse:collapse; font-size:13px }}
.ranked td, .ranked th {{ padding:6px 10px; border-bottom:1px solid #eee }}
.ranked th {{ font-weight:600; color:#555; font-size:12px }}
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px }}
@media(max-width:700px) {{ .grid-2 {{ grid-template-columns:1fr }} }}
@media(prefers-color-scheme:dark) {{
  .metric-box {{ background:#1a1a2e }}
  .card {{ background:#16213e; box-shadow:0 1px 4px rgba(0,0,0,.3) }}
  .ranked td, .ranked th {{ border-color:#333 }}
}}
</style></head><body><div class="wrap">
<nav style="font-size:13px;margin-bottom:8px"><a href="index.html">Home</a> &middot; <a href="signal.html">Signal</a> &middot; <a href="dashboard.html">Dashboard</a> &middot; <a href="freshness.html">Freshness</a> &middot; <a href="trends.html">Trends</a></nav>
<h1>Dependency &amp; Risk Analysis</h1>
<p>How concentrated is each Pacific country&rsquo;s aid portfolio? Who depends on a single funder, where is the data stale, and where are programmes ending faster than they start?</p>
<p style="font-size:13px;color:#666">Data as at {esc(issue_date)}. Concentration is measured on 90-day disbursements using the <a href="https://en.wikipedia.org/wiki/Herfindahl%E2%80%93Hirschman_index">Herfindahl&ndash;Hirschman Index</a> (HHI): 10,000 = one funder holds everything; below 1,500 is unconcentrated. The composite risk score weights concentration (40%), data staleness (30%), and pipeline pressure (30%).</p>

<h2>Regional summary</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:16px 0">
<div class="metric-box"><div class="metric-val">{avg_hhi:.0f}</div><div class="metric-label">Avg HHI across 14 countries</div></div>
<div class="metric-box"><div class="metric-val">{high_conc}</div><div class="metric-label">Countries &gt;50% single funder</div></div>
<div class="metric-box"><div class="metric-val">{high_stale}</div><div class="metric-label">Countries &gt;50% stale funders</div></div>
<div class="metric-box"><div class="metric-val">{high_ending}</div><div class="metric-label">Countries &gt;20% activities ending</div></div>
</div>
{hhi_sparkline}
{hhi_trend_note}

<h2>Composite risk score</h2>
<p>Countries ranked by a weighted score combining funder concentration (40%), data staleness (30%), and pipeline pressure (30%). Higher is more exposed.</p>
{risk_chart}

<h2>Concentration vs. disbursement</h2>
<p>Bubble size = number of active activities. Countries in the shaded zone depend on a single funder for more than half their recent aid. Large bubbles high up are the most exposed: big programmes reliant on one source.</p>
{scatter_chart}

<h2>Country profiles</h2>
<p>Each card shows the funder mix (stacked bar), risk indicators, and key numbers. Ordered by composite risk score.</p>
{all_cards}

<h2>Rankings</h2>
<div class="grid-2">
<div>
<h3>Most concentrated</h3>
<p style="font-size:12px;color:#666">Highest HHI &mdash; most dependent on few funders</p>
{conc_table}
</div>
<div>
<h3>Most diversified</h3>
<p style="font-size:12px;color:#666">Lowest HHI &mdash; broadest funder base</p>
{div_table}
</div>
<div>
<h3>Stalest data</h3>
<p style="font-size:12px;color:#666">Highest share of funders with data older than a year</p>
{stale_table}
</div>
<div>
<h3>Most pipeline pressure</h3>
<p style="font-size:12px;color:#666">Highest ratio of ending activities to total active</p>
{ending_table}
</div>
</div>

<h2>What this means</h2>
<p>A country where one funder dominates is not necessarily at risk &mdash; it may simply reflect that funder&rsquo;s geographic focus. But it does mean that a budget cut, a policy change, or a publication delay at that single funder has an outsized effect on both the country&rsquo;s aid picture and on what anyone can see of it.</p>
<p>The data staleness dimension matters because <strong>concentration that you cannot see is worse than concentration you can measure</strong>. When the largest funder&rsquo;s data is a year old, the concentration numbers here are already wrong &mdash; they describe the data, not the reality.</p>
<p>Pipeline pressure &mdash; activities ending without replacement &mdash; is the forward-looking risk. A country with high concentration, stale data, and programmes ending is one where the next six months are largely invisible.</p>

<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent. Asa publishes autonomously within the charter&rsquo;s rules; the Operator can see everything and can revoke any permission.
<br>Data: {n_issues} issues. <a href="methodology.html">Methodology</a>.
<br><a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="dashboard.html">Dashboard</a> &middot;
<a href="freshness.html">Data freshness</a> &middot;
<a href="trends.html">Trends</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="feedback.html">Send feedback</a> &middot;
<a href="feed.xml">RSS feed</a> &middot;
<a href="{REPO}">Code and data</a></footer>
</div></body></html>"""

out = os.path.join(SITE, "dependency.html")
with open(out, "w") as fh:
    fh.write(html)
print(f"rendered dependency.html {len(html) // 1024} KB, {len(rows)} countries, avg HHI {avg_hhi:.0f}")
