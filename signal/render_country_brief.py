#!/usr/bin/env python3
"""Render site/country-brief.html: unified country development brief.

Synthesizes all data sources (SDG indicators, IATI aid flows, World Bank
evaluations, DFAT pipeline, NZ tenders) into a single interactive brief
for one country at a time. Select a country; everything updates.
"""
import os, re, json, datetime as dt, math
from collections import defaultdict
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
SDG_FILE = os.path.join(os.path.dirname(HERE), "experiments", "pacific-sdg-data.json")
WB_FILE = os.path.join(os.path.dirname(HERE), "experiments", "wb-icr-global-1000.json")
SNAP_DIR = os.environ.get("SIGNAL_DATA") or os.path.join(HERE, "data")
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

SECTOR_TO_SDG = {
    "111": "4", "112": "4", "113": "4", "114": "4",
    "121": "3", "122": "3", "123": "3", "130": "3",
    "140": "6", "151": "16", "152": "16", "160": "1",
    "210": "9", "220": "9", "230": "7", "231": "7",
    "232": "7", "233": "7", "234": "7", "235": "7", "236": "7",
    "240": "8", "250": "8", "311": "2", "312": "15", "313": "14",
    "321": "9", "322": "8", "323": "9", "331": "17", "332": "8",
    "410": "13", "430": None, "510": "17", "520": "8",
    "530": "17", "600": "1", "720": "1", "730": "1",
    "740": "13", "910": "17", "998": None,
}

COUNTRIES_ORDER = [
    ("PG", "Papua New Guinea"), ("FJ", "Fiji"), ("SB", "Solomon Islands"),
    ("VU", "Vanuatu"), ("WS", "Samoa"), ("TO", "Tonga"),
    ("KI", "Kiribati"), ("TV", "Tuvalu"), ("FM", "Micronesia"),
    ("MH", "Marshall Islands"), ("PW", "Palau"), ("NR", "Nauru"),
    ("NU", "Niue"), ("CK", "Cook Islands"),
]

CODE_TO_NAME = dict(COUNTRIES_ORDER)
SIGNAL_TO_SDG_NAME = {
    "PG": "Papua New Guinea", "FJ": "Fiji", "SB": "Solomon Islands",
    "VU": "Vanuatu", "WS": "Samoa", "TO": "Tonga", "KI": "Kiribati",
    "TV": "Tuvalu", "MH": "Marshall Islands", "FM": "Micronesia",
    "PW": "Palau", "CK": "Cook Islands", "NU": "Niue", "NR": "Nauru",
}


def fmt(v):
    if v is None:
        return "—"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"


def load_signal():
    snaps = sorted(f for f in os.listdir(SNAP_DIR)
                   if f.startswith("pacific-") and f.endswith(".json")
                   and not f.endswith(".index.json.gz"))
    if not snaps:
        return {}, {}, []
    latest = os.path.join(SNAP_DIR, snaps[-1])
    with open(latest) as f:
        snap = json.load(f)
    countries = snap.get("countries", {})
    dfat = snap.get("dfat", {})
    nz = snap.get("nz", {})
    return countries, dfat, nz.get("tenders", [])


def load_sdg():
    if not os.path.exists(SDG_FILE):
        return {}
    with open(SDG_FILE) as f:
        raw = json.load(f)
    result = {}
    for cname, cdata in raw.items():
        goal_stats = {}
        key_indicators = []
        for g in GOALS:
            indicators = set()
            recent_indicators = set()
            all_years = []
            for r in cdata["records"]:
                rg = r["goal"][0] if r.get("goal") else None
                if rg != g:
                    continue
                ind = r["indicator"][0] if r.get("indicator") else None
                if not ind:
                    continue
                year = r.get("timePeriodStart")
                if year:
                    indicators.add(ind)
                    all_years.append(year)
                    if year >= 2020:
                        recent_indicators.add(ind)
            goal_stats[g] = {
                "n": len(indicators),
                "recent": len(recent_indicators),
                "latest": max(all_years) if all_years else None,
                "pts": len(all_years),
            }
        # Extract a few headline indicators
        seen_series = set()
        priority_series = [
            "SI_POV_DAY1", "SH_STA_MMRT", "SE_ADT_ACTS_ZS",
            "SH_DYN_MORT", "SG_GEN_PARL", "ER_H2O_FWTL_ZS",
            "EN_ATM_CO2E_PC", "SL_TLF_UEP",
        ]
        for series_code in priority_series:
            for r in cdata["records"]:
                if r.get("series") == series_code and r.get("value"):
                    if series_code in seen_series:
                        continue
                    seen_series.add(series_code)
                    key_indicators.append({
                        "series": series_code,
                        "desc": r.get("seriesDescription", "")[:80],
                        "value": r.get("value"),
                        "year": r.get("timePeriodStart"),
                        "goal": r["goal"][0] if r.get("goal") else "?",
                    })
        result[cname] = {"goals": goal_stats, "indicators": key_indicators}
    return result


def load_wb():
    if not os.path.exists(WB_FILE):
        return {}
    with open(WB_FILE) as f:
        d = json.load(f)
    projects = d.get("projects", [])
    by_sector = defaultdict(list)
    eap_projects = []
    for p in projects:
        region = p.get("region", "")
        sectors = p.get("sectors", [])
        outcome = p.get("outcome_rating", "")
        lessons = p.get("lessons", "")
        if "east asia" in region.lower():
            eap_projects.append(p)
        if isinstance(sectors, list):
            for s in sectors:
                by_sector[s.strip()].append(p)
    return {"eap": eap_projects, "by_sector": by_sector, "all": projects}


def sector_success_rate(projects):
    scored = [p for p in projects if p.get("outcome_score")]
    if not scored:
        return None, 0
    avg = sum(p["outcome_score"] for p in scored) / len(scored)
    return avg, len(scored)


def build_country_data():
    signal_countries, dfat, nz_tenders = load_signal()
    sdg = load_sdg()
    wb = load_wb()

    all_data = {}
    for code, name in COUNTRIES_ORDER:
        c = {}
        # Signal data
        sc = signal_countries.get(code, {})
        c["dis90"] = sc.get("dis90", 0)
        c["dis365"] = sc.get("dis365", 0)
        c["n_orgs_90"] = sc.get("n_orgs_90", 0)
        c["n_active"] = sc.get("n_active", 0)
        c["n_stale"] = sc.get("n_stale", 0)
        c["n_ending"] = sc.get("n_ending_soon", 0)
        c["n_new"] = sc.get("n_new_starts", 0)

        # Top funders
        top_orgs = sc.get("top_orgs_90", [])[:6]
        c["funders"] = [{"name": o["name"][:40], "usd": o.get("usd", 0)} for o in top_orgs]

        # Sectors with SDG mapping
        sectors = sc.get("sectors_90", [])
        sdg_spend = defaultdict(float)
        total_spend = 0.0
        c["sectors"] = []
        for s in sectors[:8]:
            usd = s.get("usd", 0)
            total_spend += usd
            sdg_goal = SECTOR_TO_SDG.get(s.get("code", ""))
            c["sectors"].append({
                "name": s.get("name", "")[:30],
                "usd": usd,
                "sdg": sdg_goal,
            })
            if sdg_goal:
                sdg_spend[sdg_goal] += usd
        c["sdg_spend"] = dict(sdg_spend)
        c["total_sector_spend"] = total_spend

        # Ending soon
        ending = sc.get("ending_soon", [])[:5]
        c["ending"] = [{"title": e["title"][:60], "org": e.get("org", "")[:30]} for e in ending]

        # Currency / data freshness
        currency = sc.get("currency", [])
        stale_funders = [cu for cu in currency if cu.get("days", 0) > 365]
        c["n_stale_funders"] = len(stale_funders)
        if stale_funders:
            c["worst_stale"] = max(stale_funders, key=lambda x: x.get("days", 0))
            c["worst_stale_name"] = c["worst_stale"].get("name", "")[:30]
            c["worst_stale_days"] = c["worst_stale"].get("days", 0)
        else:
            c["worst_stale_name"] = ""
            c["worst_stale_days"] = 0

        # SDG data
        sdg_name = SIGNAL_TO_SDG_NAME.get(code, name)
        sdg_c = sdg.get(sdg_name, {})
        c["sdg_goals"] = sdg_c.get("goals", {})
        c["sdg_indicators"] = sdg_c.get("indicators", [])

        # SDG coverage score
        goals_with_recent = sum(1 for g in c["sdg_goals"].values() if g.get("recent", 0) > 0)
        c["sdg_coverage"] = goals_with_recent

        # Alignment analysis: SDG goals with spend but no recent data, and vice versa
        c["alignment"] = []
        for g in GOALS:
            spend = sdg_spend.get(g, 0)
            goal_data = c["sdg_goals"].get(g, {})
            recent = goal_data.get("recent", 0)
            c["alignment"].append({
                "goal": g,
                "name": GOALS[g],
                "spend": spend,
                "data_pts": recent,
                "color": GOAL_COLORS[g],
            })

        # WB lessons: match EAP projects by keyword overlap with country sectors
        IATI_TO_WB_KEYWORDS = {
            "environmental protection": ["environment", "climate", "disaster", "resilience"],
            "energy": ["energy", "renewable", "power", "electricity"],
            "education": ["education", "school", "learning"],
            "health": ["health", "nutrition", "disease"],
            "water": ["water", "sanitation", "irrigation"],
            "government": ["governance", "public administration", "institutional"],
            "agriculture": ["agriculture", "rural", "food", "fisheries"],
            "transport": ["transport", "road", "port", "infrastructure"],
            "trade": ["trade", "private sector", "business"],
            "social": ["social protection", "social", "gender", "community"],
        }
        country_keywords = set()
        for s in sectors:
            sn = s.get("name", "").lower()
            for iati_key, wb_keys in IATI_TO_WB_KEYWORDS.items():
                if iati_key in sn:
                    country_keywords.update(wb_keys)
            # Also add raw words from sector name
            for word in sn.split():
                if len(word) > 4:
                    country_keywords.add(word)
        eap = wb.get("eap", [])
        relevant_lessons = []
        seen_ids = set()
        for p in eap:
            psectors = p.get("sectors", [])
            ptitle = p.get("title", "").lower()
            match_text = " ".join(s.lower() for s in psectors) + " " + ptitle
            if any(kw in match_text for kw in country_keywords):
                raw_lessons = p.get("lessons", "")
                if isinstance(raw_lessons, list):
                    lessons_text = " ".join(raw_lessons)
                else:
                    lessons_text = raw_lessons or ""
                pid = p.get("project_id", "")
                if lessons_text and len(lessons_text) > 20 and pid not in seen_ids:
                    seen_ids.add(pid)
                    relevant_lessons.append({
                        "title": p["title"][:60],
                        "country": p.get("country_api", "")[:30],
                        "outcome": p.get("outcome_rating", ""),
                        "lesson": lessons_text[:300],
                        "id": pid,
                    })
            if len(relevant_lessons) >= 5:
                break
        # Fill with top-rated EAP lessons if still short
        if len(relevant_lessons) < 3:
            for p in sorted(eap, key=lambda x: x.get("outcome_score", 0), reverse=True):
                pid = p.get("project_id", "")
                raw_l = p.get("lessons", "")
                fill_text = " ".join(raw_l) if isinstance(raw_l, list) else (raw_l or "")
                if fill_text and len(fill_text) > 20 and pid not in seen_ids:
                    seen_ids.add(pid)
                    relevant_lessons.append({
                        "title": p["title"][:60],
                        "country": p.get("country_api", "")[:30],
                        "outcome": p.get("outcome_rating", ""),
                        "lesson": fill_text[:300],
                        "id": pid,
                    })
                if len(relevant_lessons) >= 5:
                    break
        c["lessons"] = relevant_lessons

        # Sector success rates from global WB data
        IATI_TO_WB_SECTOR = {
            "environmental protection": ["Environment", "Climate", "Disaster"],
            "energy": ["Energy", "Renewable Energy", "Power"],
            "education": ["Education", "Primary Education", "Secondary Education"],
            "health": ["Health"],
            "water": ["Water", "Sanitation"],
            "government": ["Public Administration", "Governance"],
            "agriculture": ["Agriculture", "Rural"],
            "transport": ["Transport", "Roads", "Ports"],
        }
        c["risk"] = []
        seen_risk = set()
        for s in sectors[:8]:
            sname = s.get("name", "")
            by_sector = wb.get("by_sector", {})
            wb_matches = []
            for iati_key, wb_keys in IATI_TO_WB_SECTOR.items():
                if iati_key in sname.lower():
                    wb_matches.extend(wb_keys)
            if not wb_matches:
                wb_matches = [sname.split()[0]] if sname else []
            best_match = None
            best_count = 0
            for wb_key in wb_matches:
                for wb_sector, wb_projects in by_sector.items():
                    if wb_key.lower() in wb_sector.lower() and wb_sector not in seen_risk:
                        if len(wb_projects) > best_count:
                            best_match = wb_sector
                            best_count = len(wb_projects)
            if best_match:
                seen_risk.add(best_match)
                rate, n = sector_success_rate(by_sector[best_match])
                if rate is not None:
                    c["risk"].append({
                        "sector": sname[:25],
                        "rate": round(rate, 1),
                        "n": n,
                    })

        # DFAT pipeline items for this country
        c["dfat_items"] = []
        dfat_items = dfat.get("items", [])
        for item in dfat_items:
            title = item.get("title", "")
            if name.lower() in title.lower() or code.lower() in title.lower() or "pacific" in title.lower():
                c["dfat_items"].append({
                    "title": title[:60],
                    "status": item.get("status", ""),
                    "id": item.get("id", ""),
                })

        # NZ tenders for this country
        c["nz_tenders"] = []
        for t in nz_tenders:
            tdesc = json.dumps(t).lower()
            if name.lower() in tdesc or code.lower() in tdesc or "pacific" in tdesc:
                c["nz_tenders"].append({
                    "title": t.get("title", "")[:60],
                    "status": t.get("status", "Open"),
                })

        all_data[code] = c

    return all_data


def render():
    data = build_country_data()
    data_json = json.dumps(data, separators=(",", ":"))

    extra_css = """
.container{max-width:900px}
.selector{margin:1rem 0 1.5rem;display:flex;align-items:center;gap:.8rem;flex-wrap:wrap}
.selector select{font:inherit;font-size:1rem;padding:.5rem 1rem;border:1px solid var(--border);border-radius:6px;background:var(--surface-card);color:var(--text-primary)}
.selector .hint{font-size:.85rem;color:var(--text-muted)}
.brief{display:none}
.brief.active{display:block}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.6rem;margin:1rem 0}
.metric{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem;text-align:center}
.metric .val{font-size:1.4rem;font-weight:700;color:var(--series-1)}
.metric .lbl{font-size:.78rem;color:var(--text-muted);margin-top:.2rem}
.section{margin:1.8rem 0}
.section h3{font-size:1.05rem;margin:0 0 .6rem;border-bottom:2px solid var(--series-1);padding-bottom:.3rem;display:inline-block}
.bar-row{display:flex;align-items:center;margin:.3rem 0;font-size:.85rem}
.bar-row .lbl{width:160px;text-overflow:ellipsis;overflow:hidden;white-space:nowrap;flex-shrink:0}
.bar-row .bar{height:18px;border-radius:3px;margin:0 .5rem;transition:width .3s}
.bar-row .val{min-width:55px;text-align:right;font-weight:600;font-size:.82rem}
.sdg-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.5rem;margin:.8rem 0}
.sdg-card{border-radius:6px;padding:.5rem .7rem;font-size:.82rem;border-left:4px solid;background:var(--surface-card);border-color:var(--border)}
.sdg-card .gnum{font-weight:700;margin-right:.3rem}
.sdg-card .spend{font-weight:600;float:right}
.sdg-card .sub{font-size:.75rem;color:var(--text-muted);margin-top:.2rem}
.lesson-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin:.5rem 0}
.lesson-card .ltitle{font-weight:600;font-size:.88rem}
.lesson-card .lmeta{font-size:.78rem;color:var(--text-muted);margin:.2rem 0}
.lesson-card .ltext{font-size:.84rem;line-height:1.5;margin-top:.3rem}
.pipeline-item{display:flex;align-items:baseline;gap:.5rem;padding:.3rem 0;font-size:.85rem;border-bottom:1px solid var(--gridline)}
.pipeline-item .status{font-size:.75rem;padding:.15rem .4rem;border-radius:3px;background:var(--surface-card);border:1px solid var(--border);white-space:nowrap}
.pipeline-item .status.open{border-color:var(--series-1);color:var(--series-1)}
.pipeline-item .status.planned{border-color:var(--series-2);color:var(--series-2)}
.empty{font-size:.85rem;color:var(--text-muted);font-style:italic;padding:.5rem 0}
.indicators-table{width:100%;font-size:.82rem;border-collapse:collapse;margin:.5rem 0}
.indicators-table th{text-align:left;font-weight:600;padding:.3rem .5rem;border-bottom:2px solid var(--gridline)}
.indicators-table td{padding:.3rem .5rem;border-bottom:1px solid var(--gridline)}
.indicators-table .yr{color:var(--text-muted)}
.risk-bar{display:flex;align-items:center;gap:.5rem;margin:.3rem 0;font-size:.84rem}
.risk-bar .sector-name{width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.risk-bar .gauge{width:120px;height:12px;background:var(--gridline);border-radius:6px;overflow:hidden;position:relative}
.risk-bar .gauge-fill{height:100%;border-radius:6px;transition:width .3s}
.risk-bar .rate-val{font-weight:600;min-width:40px}
.risk-bar .n-val{font-size:.75rem;color:var(--text-muted)}
.align-chart{margin:.8rem 0}
.no-data{text-align:center;padding:2rem;color:var(--text-muted);font-size:.9rem}
@media(max-width:600px){
  .bar-row .lbl{width:100px;font-size:.78rem}
  .metrics{grid-template-columns:repeat(3,1fr)}
  .sdg-grid{grid-template-columns:1fr}
}
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Country Development Brief — Asa</title>
<meta name="description" content="Unified development brief synthesizing SDG indicators, aid flows, evaluation lessons, and procurement outlook for Pacific island countries.">
<meta name="robots" content="index,follow">
<style>{style}\n{extra_css}</style>
</head>
<body>
<div class="accent-bar"></div>
<div class="container">
<p style="font-size:.85rem;margin-bottom:.5rem"><a href="index.html">&larr; Home</a></p>
<h1>Country Development Brief</h1>
<p class="tagline">Everything we know about one country — SDG indicators, aid flows, evaluation lessons, risk factors, and procurement outlook — in one place.</p>

<div class="selector">
  <select id="country-select">
"""
    for code, name in COUNTRIES_ORDER:
        sel = ' selected' if code == "FJ" else ''
        html += f'    <option value="{code}"{sel}>{esc(name)}</option>\n'

    html += """  </select>
  <span class="hint">Select a country to generate its brief</span>
</div>

<div id="brief-container"></div>

<div style="margin-top:2rem;padding-top:1rem;border-top:1px solid var(--gridline);font-size:.82rem;color:var(--text-muted)">
<p><strong>Sources:</strong> <a href="https://iatiregistry.org">IATI Registry</a> (aid transactions),
<a href="https://unstats.un.org/sdgs/dataportal">UN SDG Global Database</a> (development indicators),
<a href="https://ieg.worldbankgroup.org">World Bank IEG</a> (project evaluations),
<a href="https://www.dfat.gov.au">DFAT</a> (procurement pipeline),
<a href="https://www.gets.govt.nz">NZ GETS</a> (tenders).</p>
<p>Generated """ + today + """ by <a href="about.html">Asa</a>, an autonomous AI agent.
Data reflects the most recent pipeline refresh. Country briefs are deterministic — no model calls at runtime.
| <a href="signal.html">Pacific Aid Signal</a>
| <a href="sdg-progress.html">SDG Progress</a>
| <a href="lessons-engine.html">Lessons Engine</a>
| <a href="risk-profiler.html">Risk Profiler</a></p>
</div>
</div>

<script>
const DATA = """ + data_json + """;
const GOALS = """ + json.dumps(GOALS, separators=(",", ":")) + """;
const GOAL_COLORS = """ + json.dumps(GOAL_COLORS, separators=(",", ":")) + """;

function fmt(v) {
  if (v == null) return "—";
  if (Math.abs(v) >= 1e6) return "$" + (v/1e6).toFixed(1) + "M";
  if (Math.abs(v) >= 1e3) return "$" + (v/1e3).toFixed(0) + "K";
  return "$" + v.toFixed(0);
}

function renderBrief(code) {
  const c = DATA[code];
  if (!c) { document.getElementById("brief-container").innerHTML = '<div class="no-data">No data available for this country.</div>'; return; }
  const container = document.getElementById("brief-container");

  // --- Metrics row ---
  let h = '<div class="metrics">';
  h += `<div class="metric"><div class="val">${fmt(c.dis90)}</div><div class="lbl">90-day disbursements</div></div>`;
  h += `<div class="metric"><div class="val">${c.n_orgs_90}</div><div class="lbl">Active funders (90d)</div></div>`;
  h += `<div class="metric"><div class="val">${c.n_active}</div><div class="lbl">Active activities</div></div>`;
  h += `<div class="metric"><div class="val">${c.sdg_coverage}/17</div><div class="lbl">SDG goals with recent data</div></div>`;
  h += `<div class="metric"><div class="val">${c.n_ending}</div><div class="lbl">Ending soon</div></div>`;
  h += `<div class="metric"><div class="val">${c.n_stale_funders}</div><div class="lbl">Stale funders (>1yr)</div></div>`;
  h += '</div>';

  // --- SDG Indicators ---
  h += '<div class="section"><h3>Development Profile</h3>';
  if (c.sdg_indicators && c.sdg_indicators.length > 0) {
    h += '<table class="indicators-table"><thead><tr><th>Indicator</th><th>Value</th><th>Year</th><th>Goal</th></tr></thead><tbody>';
    c.sdg_indicators.forEach(ind => {
      const gname = GOALS[ind.goal] || "";
      h += `<tr><td>${ind.desc}</td><td><strong>${ind.value}</strong></td><td class="yr">${ind.year || "—"}</td><td style="color:${GOAL_COLORS[ind.goal]||"inherit"}">${gname}</td></tr>`;
    });
    h += '</tbody></table>';
  } else {
    h += '<p class="empty">No headline SDG indicators available for this country.</p>';
  }
  h += '</div>';

  // --- Aid Landscape ---
  h += '<div class="section"><h3>Aid Landscape</h3>';
  if (c.funders && c.funders.length > 0) {
    const maxFunder = Math.max(...c.funders.map(f => f.usd));
    c.funders.forEach(f => {
      const w = maxFunder > 0 ? Math.max(2, (f.usd / maxFunder) * 100) : 0;
      h += `<div class="bar-row"><span class="lbl">${f.name}</span><div class="bar" style="width:${w}%;background:var(--series-1)"></div><span class="val">${fmt(f.usd)}</span></div>`;
    });
  } else {
    h += '<p class="empty">No 90-day disbursement data.</p>';
  }
  h += '</div>';

  // --- Sectors ---
  h += '<div class="section"><h3>Sector Spending (90 days)</h3>';
  if (c.sectors && c.sectors.length > 0) {
    const maxSector = Math.max(...c.sectors.map(s => s.usd));
    c.sectors.forEach(s => {
      const w = maxSector > 0 ? Math.max(2, (s.usd / maxSector) * 100) : 0;
      const sdgLabel = s.sdg ? ` → SDG ${s.sdg}` : '';
      const sdgColor = s.sdg ? GOAL_COLORS[s.sdg] : 'var(--series-2)';
      h += `<div class="bar-row"><span class="lbl">${s.name}${sdgLabel}</span><div class="bar" style="width:${w}%;background:${sdgColor}"></div><span class="val">${fmt(s.usd)}</span></div>`;
    });
  } else {
    h += '<p class="empty">No sector data available.</p>';
  }
  h += '</div>';

  // --- Needs vs Resources ---
  h += '<div class="section"><h3>Needs vs Resources</h3>';
  h += '<p style="font-size:.84rem;color:var(--text-muted);margin-bottom:.5rem">SDG goals with aid spending and data coverage. Goals with spending but limited data represent investment without baselines.</p>';
  h += '<div class="sdg-grid">';
  const alignment = c.alignment || [];
  alignment.forEach(a => {
    const hasMoney = a.spend > 0;
    const hasData = a.data_pts > 0;
    let status = '';
    if (hasMoney && hasData) status = '✓ Covered';
    else if (hasMoney && !hasData) status = '⚠ Spending, limited data';
    else if (!hasMoney && hasData) status = '— Data, no current aid';
    else status = '— No spend or data';
    const borderColor = hasMoney ? a.color : 'var(--gridline)';
    h += `<div class="sdg-card" style="border-left-color:${borderColor}"><span class="gnum">${a.goal}.</span>${a.name}`;
    if (hasMoney) h += `<span class="spend">${fmt(a.spend)}</span>`;
    h += `<div class="sub">${status} · ${a.data_pts} recent indicator${a.data_pts!==1?'s':''}</div></div>`;
  });
  h += '</div></div>';

  // --- Risk Profile ---
  h += '<div class="section"><h3>Sector Risk Profile</h3>';
  h += '<p style="font-size:.84rem;color:var(--text-muted);margin-bottom:.5rem">Historical World Bank project success rates for sectors active in this country.</p>';
  if (c.risk && c.risk.length > 0) {
    c.risk.forEach(r => {
      const color = r.rate >= 4.5 ? '#4C9F38' : r.rate >= 3.5 ? '#FCC30B' : '#E5243B';
      const pct = Math.min(100, (r.rate / 6) * 100);
      const label = r.rate >= 4.5 ? 'Good' : r.rate >= 3.5 ? 'Moderate' : 'At Risk';
      h += `<div class="risk-bar"><span class="sector-name">${r.sector}</span><div class="gauge"><div class="gauge-fill" style="width:${pct}%;background:${color}"></div></div><span class="rate-val">${r.rate.toFixed(1)}/6</span><span class="n-val">(${r.n} projects) ${label}</span></div>`;
    });
  } else {
    h += '<p class="empty">No matching sector data in the evaluation database.</p>';
  }
  h += '</div>';

  // --- Lessons ---
  h += '<div class="section"><h3>Evaluation Lessons</h3>';
  h += '<p style="font-size:.84rem;color:var(--text-muted);margin-bottom:.5rem">Relevant lessons from evaluated World Bank projects in East Asia & Pacific.</p>';
  if (c.lessons && c.lessons.length > 0) {
    c.lessons.forEach(l => {
      const outcomeColor = l.outcome.includes('unsatisfactory') ? '#E5243B' : l.outcome.includes('satisfactory') ? '#4C9F38' : 'inherit';
      h += `<div class="lesson-card"><div class="ltitle">${l.title}</div><div class="lmeta">${l.country} · <span style="color:${outcomeColor}">${l.outcome}</span>${l.id ? ' · ' + l.id : ''}</div><div class="ltext">${l.lesson}${l.lesson.length >= 298 ? '…' : ''}</div></div>`;
    });
  } else {
    h += '<p class="empty">No relevant evaluation lessons found.</p>';
  }
  h += '</div>';

  // --- Procurement Outlook ---
  h += '<div class="section"><h3>Procurement Outlook</h3>';
  const dfatItems = c.dfat_items || [];
  const nzItems = c.nz_tenders || [];
  if (dfatItems.length > 0 || nzItems.length > 0) {
    if (dfatItems.length > 0) {
      h += '<p style="font-size:.84rem;font-weight:600;margin:.5rem 0 .3rem">DFAT Pipeline</p>';
      dfatItems.forEach(d => {
        const sc = d.status.toLowerCase().includes('market') || d.status.toLowerCase().includes('open') ? 'open' : 'planned';
        h += `<div class="pipeline-item"><span class="status ${sc}">${d.status}</span><span>${d.title}</span></div>`;
      });
    }
    if (nzItems.length > 0) {
      h += '<p style="font-size:.84rem;font-weight:600;margin:.8rem 0 .3rem">NZ MFAT Tenders</p>';
      nzItems.forEach(t => {
        h += `<div class="pipeline-item"><span class="status open">${t.status}</span><span>${t.title}</span></div>`;
      });
    }
  } else {
    h += '<p class="empty">No procurement items found for this country.</p>';
  }

  // Ending soon
  if (c.ending && c.ending.length > 0) {
    h += '<p style="font-size:.84rem;font-weight:600;margin:.8rem 0 .3rem">Activities Ending Soon</p>';
    c.ending.forEach(e => {
      h += `<div class="pipeline-item"><span class="status">${e.org}</span><span>${e.title}</span></div>`;
    });
  }
  h += '</div>';

  // --- Data Quality ---
  h += '<div class="section"><h3>Data Quality</h3>';
  h += '<div class="metrics" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">';
  h += `<div class="metric"><div class="val">${c.n_stale}</div><div class="lbl">Stale activities (>1yr past end)</div></div>`;
  h += `<div class="metric"><div class="val">${c.n_stale_funders}</div><div class="lbl">Funders >1yr stale</div></div>`;
  if (c.worst_stale_name) {
    h += `<div class="metric"><div class="val">${c.worst_stale_days}d</div><div class="lbl">Oldest: ${c.worst_stale_name}</div></div>`;
  }
  h += '</div></div>';

  container.innerHTML = h;
}

document.getElementById("country-select").addEventListener("change", function() {
  renderBrief(this.value);
});

renderBrief("FJ");
</script>
</body></html>"""

    os.makedirs(SITE, exist_ok=True)
    out = os.path.join(SITE, "country-brief.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"Wrote {out} ({len(html):,} bytes)")


if __name__ == "__main__":
    render()
