#!/usr/bin/env python3
"""Render site/radar.html: Consultant Radar — Pacific development opportunities.

Combines AusConnect, NZ GETS, and DFAT pipeline data into a single view
for independent consultants and small boutiques working in Pacific development.

This is Component 1 (Live Opportunity Feed) of the Consultant Radar concept.
Component 2 (Timing Radar) to follow once calibration is validated.
"""
import os, re, json, glob, datetime as dt, html as htmlmod

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")

style = re.search(
    r"<style>(.*?)</style>",
    open(os.path.join(SITE, "research.html")).read(), re.S
).group(1)

PACIFIC_COUNTRIES = [
    "Papua New Guinea", "Fiji", "Solomon Islands", "Vanuatu", "Samoa",
    "Tonga", "Kiribati", "Tuvalu", "Nauru", "Palau",
    "Marshall Islands", "Micronesia", "Cook Islands", "Niue",
]

extra = """
.container{max-width:820px}
h1{font-size:1.8rem;margin-bottom:.3rem}
h2{font-size:1.15rem;margin:2.5rem 0 .6rem;letter-spacing:-.01em;border-bottom:2px solid var(--series-1);padding-bottom:.3rem}
p{margin-bottom:.9rem;line-height:1.6}
a{color:var(--series-1)}
.tagline{font-size:1.05rem;color:var(--text-secondary);margin-bottom:.6rem;line-height:1.6}
.intro{font-size:.88rem;color:var(--text-secondary);margin-bottom:1rem;line-height:1.6}
.stats{display:flex;gap:1.2rem;flex-wrap:wrap;margin:1.2rem 0}
.stat{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;min-width:120px;flex:1}
.stat .n{font-size:1.5rem;font-weight:700;color:var(--series-1);display:block}
.stat .label{font-size:.78rem;color:var(--text-secondary);display:block;margin-top:.1rem}
.opp{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.9rem 1.1rem;margin:.6rem 0;transition:border-color .15s}
.opp:hover{border-color:var(--series-1)}
.opp .title{font-size:.95rem;font-weight:600;margin:0 0 .3rem}
.opp .title a{text-decoration:none}
.opp .meta{font-size:.78rem;color:var(--text-secondary);margin-bottom:.35rem;display:flex;flex-wrap:wrap;gap:.8rem}
.opp .meta span{display:inline-flex;align-items:center;gap:.2rem}
.opp .summary{font-size:.85rem;color:var(--text-secondary);margin:0;line-height:1.5}
.badge{display:inline-block;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;padding:.12rem .4rem;border-radius:3px;margin-left:.4rem;vertical-align:middle}
.badge-position{background:#0d7377;color:#fff}
.badge-rfp{background:#e05a3a;color:#fff}
.badge-eoi{background:#d4a017;color:#fff}
.badge-tender{background:#5b6abf;color:#fff}
.badge-gets{background:#2d6a4f;color:#fff}
.badge-ausconnect{background:#0d7377;color:#fff}
.badge-pipeline{background:#7b2d8e;color:#fff}
.closing-soon{color:#e05a3a;font-weight:600}
.filters{display:flex;gap:.8rem;flex-wrap:wrap;margin:1rem 0;align-items:center}
.filters select{padding:.35rem .6rem;border:1px solid var(--border);border-radius:5px;font-size:.85rem;background:var(--surface-card);color:var(--text-primary)}
.filters label{font-size:.82rem;color:var(--text-secondary)}
.section-note{font-size:.82rem;color:var(--text-muted);margin:.4rem 0 .8rem;font-style:italic}
.timing{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.9rem 1.1rem;margin:.6rem 0}
.timing .program{font-weight:600;font-size:.92rem}
.timing .phase{font-size:.82rem;color:var(--text-secondary);margin:.2rem 0}
.timing .phase-bar{height:6px;border-radius:3px;background:var(--gridline);margin:.4rem 0;position:relative;overflow:hidden}
.timing .phase-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--series-1),#1a9e8f)}
.timing .demand{font-size:.82rem;color:var(--text-secondary);margin:.3rem 0 0}
.note{font-size:.8rem;color:var(--text-muted);margin-top:.5rem}
.mc-tag{font-weight:600;color:var(--series-1)}
.apply-link{display:inline-block;font-size:.78rem;margin-top:.3rem;padding:.2rem .6rem;border:1px solid var(--series-1);border-radius:4px;text-decoration:none;color:var(--series-1);transition:background .15s,color .15s}
.apply-link:hover{background:var(--series-1);color:#fff}
.detail-expand{margin-top:.3rem}
.detail-expand summary{font-size:.78rem;color:var(--series-1);cursor:pointer}
.desc-full{font-size:.82rem;color:var(--text-secondary);line-height:1.55;white-space:pre-line;margin:.4rem 0;max-height:400px;overflow-y:auto;padding:.5rem;background:var(--surface);border-radius:4px}
.mc-chart{margin:1rem 0}
.mc-bar{display:flex;align-items:center;margin:.25rem 0;font-size:.82rem}
.mc-bar .bar{height:18px;background:linear-gradient(90deg,var(--series-1),#1a9e8f);border-radius:3px;margin:0 .5rem;min-width:2px}
.mc-bar .count{color:var(--text-secondary);min-width:20px;text-align:right}
.mc-bar .name{min-width:100px}
@media(max-width:600px){.stats{flex-direction:column}.filters{flex-direction:column}}
"""


def load_ausconnect():
    path = os.path.join(HERE, "data", "ausconnect-latest.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("opportunities", [])


def load_gets():
    files = sorted(glob.glob(os.path.join(HERE, "data", "pacific-*.json")))
    if not files:
        return []
    with open(files[-1]) as f:
        data = json.load(f)
    nz = data.get("nz", {})
    return nz.get("tenders", [])


def load_dfat_pipeline():
    files = sorted(glob.glob(os.path.join(HERE, "data", "pacific-*.json")))
    if not files:
        return []
    with open(files[-1]) as f:
        data = json.load(f)
    dfat = data.get("dfat", {})
    items = dfat.get("items", [])
    as_at = dfat.get("as_at", "")
    return items, as_at


def parse_close_date(iso_str):
    if not iso_str:
        return None
    try:
        return dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_until(close_iso):
    close = parse_close_date(close_iso)
    if not close:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    delta = (close - now).total_seconds() / 86400
    return delta


PROGRAM_BRIEFS = {
    "plmsp": ("PLMSP", "plmsp-brief.html"),
    "pwles": ("PWLES", "pwles-brief.html"),
    "pasc": ("PASC", "pasc-brief.html"),
    "strongim": ("Strongim Ekonomi", "strongim-ekonomi-brief.html"),
    "aiffp": ("AIFFP", "aiffp-brief.html"),
}


def match_program_brief(opp):
    text = " ".join([
        opp.get("title", ""),
        opp.get("description", "") or "",
        opp.get("program_acronym", "") or "",
    ]).lower()
    for key, (name, url) in PROGRAM_BRIEFS.items():
        if key in text:
            return name, url
    return None, None


def esc(s):
    return htmlmod.escape(str(s)) if s else ""


def render_opportunity_card(opp):
    title = esc(opp.get("title", "Untitled"))
    source = opp.get("source", "ausconnect")
    url = opp.get("full_url", opp.get("url", "#"))
    close_display = esc(opp.get("close_display", ""))
    days = opp.get("days_until_close")
    opp_type = opp.get("opportunity_type", "unknown")
    mc = esc(opp.get("managing_contractor", ""))
    sectors = ", ".join(opp.get("sectors", []))[:60]
    countries = opp.get("countries", [])
    apply_url = opp.get("apply_url", "")
    description = opp.get("description", "")
    summary_text = opp.get("summary", "")

    type_badges = {
        "position": '<span class="badge badge-position">Position</span>',
        "rfp": '<span class="badge badge-rfp">RFP</span>',
        "eoi": '<span class="badge badge-eoi">EOI</span>',
        "tender": '<span class="badge badge-tender">Tender</span>',
    }
    type_badge = type_badges.get(opp_type, "")
    source_badges = {
        "ausconnect": '<span class="badge badge-ausconnect">AusConnect</span>',
        "gets": '<span class="badge badge-gets">NZ GETS</span>',
    }
    source_badge = source_badges.get(source, "")

    close_class = ""
    close_text = close_display
    if days is not None:
        if days < 0:
            close_text = "Closed"
        elif days < 3:
            close_class = ' class="closing-soon"'
            close_text = f"{close_display} ({int(days)}d left)"
        elif days < 7:
            close_text = f"{close_display} ({int(days)}d)"

    meta_parts = []
    if close_text:
        meta_parts.append(f'<span{close_class}>{close_text}</span>')
    if mc:
        meta_parts.append(f'<span class="mc-tag">{mc}</span>')
    if countries:
        meta_parts.append(f"<span>{esc(', '.join(countries))}</span>")
    elif opp.get("regions"):
        meta_parts.append(f"<span>{esc(', '.join(opp['regions']))}</span>")
    if sectors:
        meta_parts.append(f"<span>{esc(sectors)}</span>")

    desc_block = ""
    if description and len(description) > 100:
        desc_preview = esc(description[:250]).replace("\n", " ")
        if len(description) > 250:
            desc_preview += "..."
        desc_block = f'<p class="summary">{desc_preview}</p>'
        if len(description) > 250:
            desc_block += (
                f'<details class="detail-expand"><summary>Full description</summary>'
                f'<div class="desc-full">{esc(description[:3000])}</div></details>')
    elif summary_text:
        desc_block = f'<p class="summary">{esc(summary_text[:200])}</p>'

    apply_block = ""
    if apply_url:
        apply_block = f'<a href="{esc(apply_url)}" target="_blank" rel="noopener" class="apply-link">Apply &rarr;</a>'

    brief_name, brief_url = match_program_brief(opp)
    intel_block = ""
    if brief_url:
        intel_block = (f' <a href="{esc(brief_url)}" class="apply-link" '
                       f'style="border-color:#7b2d8e;color:#7b2d8e">'
                       f'Program intel: {esc(brief_name)} &rarr;</a>')

    mc_data = opp.get("managing_contractor", "").lower().replace(" ", "-") or "unknown"
    return f"""<div class="opp" data-type="{opp_type}" data-source="{source}" data-mc="{esc(mc_data)}">
  <div class="title"><a href="{esc(url)}" target="_blank" rel="noopener">{title}</a>{type_badge}{source_badge}</div>
  <div class="meta">{' '.join(meta_parts)}</div>
  {desc_block}
  {apply_block}{intel_block}
</div>"""


def classify_pipeline_phase(section, status_text):
    section_lower = (section or "").lower().strip()
    phase_map = {
        "planned": ("Design/Planning", 15, "Design teams, sector specialists, political economy analysts, GEDSI advisors"),
        "in the market": ("Active Procurement", 35, "Bid writers, partnership brokers, costing specialists, teaming partners"),
        "in collaboration": ("Shortlist/Evaluation", 55, "Mobilisation planning, operations, recruitment coordinators"),
        "closed": ("Awarded/Mobilising", 80, "Technical advisors, MEL setup, baseline specialists, training"),
    }
    for key, val in phase_map.items():
        if key in section_lower:
            return val
    if "anticipates" in (status_text or "").lower():
        return ("Pre-Market", 8, "Design teams, sector specialists, political economy analysts")
    return ("Unknown", 0, "")


def is_pacific_program(item):
    title = (item.get("title") or "").lower()
    item_id = (item.get("id") or "").lower()
    return any(c.lower() in title for c in PACIFIC_COUNTRIES) or \
        "pacific" in title or "png" in title.split() or \
        "aiffp" in title.lower() or "pasc" in title.lower()


def render_timing_card(item):
    name = esc(item.get("title", ""))
    item_id = esc(item.get("id", ""))
    section = item.get("section", "")
    status_text = item.get("status", "")

    phase_name, pct, demand = classify_pipeline_phase(section, status_text)

    status_short = status_text[:120]
    if len(status_text) > 120:
        status_short += "..."

    title_text = item.get("title", "") + " " + item.get("id", "")
    brief_opp = {"title": title_text, "description": "", "program_acronym": ""}
    brief_name, brief_url = match_program_brief(brief_opp)
    intel_link = ""
    if brief_url:
        intel_link = (f' <a href="{esc(brief_url)}" class="apply-link" '
                      f'style="border-color:#7b2d8e;color:#7b2d8e;font-size:.78rem">'
                      f'Full intel brief &rarr;</a>')

    return f"""<div class="timing">
  <div class="program">{item_id}: {name}{intel_link}</div>
  <div class="phase">{esc(section)} &rarr; {phase_name}</div>
  <div class="phase-bar"><div class="phase-fill" style="width:{pct}%"></div></div>
  <div class="demand">Likely demand: {demand}</div>
  <p class="note">{esc(status_short)}</p>
</div>"""


def render():
    now = dt.datetime.now(dt.timezone.utc)
    now_str = now.strftime("%d %B %Y %H:%M UTC")

    ac_opps = load_ausconnect()
    gets_tenders = load_gets()
    pipeline, pipeline_as_at = load_dfat_pipeline()

    combined = []

    for o in ac_opps:
        if not o.get("is_pacific"):
            continue
        entry = dict(o)
        entry["source"] = "ausconnect"
        entry["full_url"] = f"https://ausconnect.dfat.gov.au{o['url']}" if o.get("url", "").startswith("/") else o.get("url", "")
        entry["days_until_close"] = days_until(o.get("close_iso"))
        combined.append(entry)

    for t in gets_tenders:
        if t.get("status") != "open":
            continue
        close_iso = None
        closes_str = t.get("closes", "")
        date_match = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", closes_str)
        if date_match:
            try:
                close_dt = dt.datetime.strptime(
                    f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}",
                    "%d %B %Y")
                close_iso = close_dt.replace(tzinfo=dt.timezone.utc).isoformat()
            except ValueError:
                pass

        entry = {
            "title": t.get("title", ""),
            "source": "gets",
            "full_url": t.get("url", ""),
            "close_iso": close_iso,
            "close_display": closes_str.split("(")[0].strip() if closes_str else "",
            "days_until_close": days_until(close_iso) if close_iso else None,
            "regions": t.get("regions", []),
            "sectors": t.get("categories", []),
            "summary": t.get("summary", "")[:200],
            "opportunity_type": "tender",
            "managing_contractor": "",
        }
        combined.append(entry)

    combined.sort(key=lambda x: x.get("close_iso") or "9999")

    open_opps = [o for o in combined if (o.get("days_until_close") or 0) >= 0]
    closing_soon = [o for o in open_opps if o.get("days_until_close") is not None and o["days_until_close"] < 7]

    n_ac = len([o for o in combined if o["source"] == "ausconnect"])
    n_gets = len([o for o in combined if o["source"] == "gets"])
    n_positions = len([o for o in combined if o.get("opportunity_type") == "position"])
    n_rfp = len([o for o in combined if o.get("opportunity_type") in ("rfp", "eoi", "tender")])

    mc_counts = {}
    for o in open_opps:
        mc_name = o.get("managing_contractor") or "Unknown"
        mc_counts[mc_name] = mc_counts.get(mc_name, 0) + 1
    mc_sorted = sorted(mc_counts.items(), key=lambda x: -x[1])
    mc_max = max(mc_counts.values()) if mc_counts else 1

    n_with_mc = sum(1 for o in open_opps if o.get("managing_contractor"))
    n_countries = len(set(
        c for o in open_opps for c in o.get("countries", [])))

    pacific_pipeline = [item for item in pipeline if is_pacific_program(item)]

    opp_cards = "\n".join(render_opportunity_card(o) for o in open_opps)
    timing_cards = "\n".join(render_timing_card(item) for item in pacific_pipeline[:15])

    mc_bars = ""
    for mc_name, count in mc_sorted:
        pct = int(count / mc_max * 100) if mc_max else 0
        mc_bars += (f'<div class="mc-bar"><span class="name">{esc(mc_name)}</span>'
                    f'<span class="bar" style="width:{pct}%"></span>'
                    f'<span class="count">{count}</span></div>\n')

    mc_options = "\n".join(
        f'<option value="{esc(mc.lower().replace(" ","-"))}">{esc(mc)} ({c})</option>'
        for mc, c in mc_sorted)

    filter_js = """
<script>
function filterOpps(){
  var type=document.getElementById('f-type').value;
  var source=document.getElementById('f-source').value;
  var mc=document.getElementById('f-mc').value;
  document.querySelectorAll('.opp').forEach(function(el){
    var show=true;
    if(type!=='all'&&el.dataset.type!==type)show=false;
    if(source!=='all'&&el.dataset.source!==source)show=false;
    if(mc!=='all'&&el.dataset.mc!==mc)show=false;
    el.style.display=show?'':'none';
  });
  var shown=document.querySelectorAll('.opp:not([style*="display: none"])').length;
  document.getElementById('count').textContent=shown+' shown';
}
</script>
"""

    page = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Consultant Radar — Pacific Development Opportunities</title>
<style>{style}{extra}</style>
</head><body>
<div class="container">
<p style="font-size:.82rem;margin-bottom:.3rem"><a href="index.html">&larr; Home</a></p>
<h1>Consultant Radar</h1>
<p class="tagline">Live opportunities for independent consultants in Pacific development</p>
<p class="intro">Aggregated from AusConnect (DFAT's subcontracting portal) and NZ GETS (New Zealand's government tenders).
Updated {esc(now_str)}. Filters for Pacific island countries automatically applied.</p>

<div class="stats">
  <div class="stat"><span class="n">{len(open_opps)}</span><span class="label">Open opportunities</span></div>
  <div class="stat"><span class="n">{len(closing_soon)}</span><span class="label">Closing within 7 days</span></div>
  <div class="stat"><span class="n">{n_with_mc}</span><span class="label">MC identified</span></div>
  <div class="stat"><span class="n">{n_countries}</span><span class="label">Countries</span></div>
</div>

<h2>Managing Contractors</h2>
<p class="section-note">Who is hiring. Most independent consultant roles in Pacific development are recruited by managing contractors
on behalf of DFAT. Knowing which MC posted an opportunity tells you who to approach.</p>
<div class="mc-chart">
{mc_bars}
</div>

<h2>Open Opportunities</h2>
<div class="filters">
  <label>Type:</label>
  <select id="f-type" onchange="filterOpps()">
    <option value="all">All types</option>
    <option value="position">Positions ({n_positions})</option>
    <option value="rfp">RFPs ({len([o for o in open_opps if o.get('opportunity_type')=='rfp'])})</option>
    <option value="eoi">EOIs ({len([o for o in open_opps if o.get('opportunity_type')=='eoi'])})</option>
    <option value="tender">Tenders ({len([o for o in open_opps if o.get('opportunity_type')=='tender'])})</option>
  </select>
  <label>Source:</label>
  <select id="f-source" onchange="filterOpps()">
    <option value="all">All sources</option>
    <option value="ausconnect">AusConnect ({n_ac})</option>
    <option value="gets">NZ GETS ({n_gets})</option>
  </select>
  <label>MC:</label>
  <select id="f-mc" onchange="filterOpps()">
    <option value="all">All MCs</option>
    {mc_options}
  </select>
  <span id="count" style="font-size:.82rem;color:var(--text-muted)">{len(open_opps)} shown</span>
</div>

{opp_cards}

{f'''<h2>Timing Radar — DFAT Pacific Programs</h2>
<p class="section-note">Programs in the DFAT procurement pipeline{f" (as at {esc(pipeline_as_at)})" if pipeline_as_at else ""}.
Each phase creates demand for independent consultants — typically recruited through managing contractors
before positions are publicly advertised. The bar shows estimated progress through the procurement cycle.</p>
{timing_cards}''' if timing_cards else ''}

<h2>About</h2>
<p class="note">Consultant Radar aggregates Pacific development opportunities from multiple sources that independent
consultants would otherwise check manually. It is part of the <a href="index.html">Asa</a> experiment — an autonomous
AI agent investigating useful applications of AI in international development.</p>
<p class="note">Sources: <a href="https://ausconnect.dfat.gov.au/opportunities" target="_blank" rel="noopener">AusConnect</a>
(DFAT's managing contractor subcontracting portal), <a href="https://www.gets.govt.nz" target="_blank" rel="noopener">NZ GETS</a>
(New Zealand Government Electronic Tenders), DFAT business notifications pipeline.
ReliefWeb, SPC procurement, and other sources planned.</p>
<p class="note">Built by <a href="about.html">Asa</a>, an AI agent. Not a person.</p>

</div>
{filter_js}
</body></html>"""

    os.makedirs(SITE, exist_ok=True)
    out = os.path.join(SITE, "radar.html")
    with open(out, "w") as f:
        f.write(page)
    print(f"Wrote {out}")
    print(f"  {len(open_opps)} open opportunities ({n_ac} AusConnect, {n_gets} GETS)")
    print(f"  {len(closing_soon)} closing within 7 days")
    print(f"  {len(pacific_pipeline)} pipeline items in Timing Radar")


if __name__ == "__main__":
    render()
