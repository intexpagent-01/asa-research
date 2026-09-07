#!/usr/bin/env python3
"""Pacific Aid Signal — an autonomous, continuously regenerated aid-intelligence page
for 14 Pacific island countries, built from IATI (via d-portal) and World Bank project data.

Every run: fetch the last 365 days of IATI transactions per country (joined to activity
and country tables so recipient-country weighting is applied), fetch World Bank projects,
compute 90-day signals, save a dated snapshot, diff against the previous snapshot, and
render site/pacific-signal.html.

Usage: python3 pacific_signal.py [--no-fetch]   (reuses newest snapshot for rendering)
"""
import json, os, re, sys, time, glob, urllib.request, urllib.parse, datetime as dt
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SITE = os.path.join(os.path.dirname(HERE), "site")
DPORTAL = "https://d-portal.org/q.json"
WB = "https://search.worldbank.org/api/v2/projects"
UA = {"User-Agent": "asa-research/0.5 (pacific-aid-signal)"}

COUNTRIES = [("PG","Papua New Guinea"),("FJ","Fiji"),("SB","Solomon Islands"),("VU","Vanuatu"),
             ("WS","Samoa"),("TO","Tonga"),("KI","Kiribati"),("TV","Tuvalu"),("FM","Micronesia (Fed. States)"),
             ("MH","Marshall Islands"),("PW","Palau"),("NR","Nauru"),("NU","Niue"),("CK","Cook Islands")]
STATUS = {1:"pipeline",2:"implementation",3:"finalisation",4:"closed",5:"cancelled",6:"suspended"}
SECTOR = {"111":"Education (general)","112":"Basic education","113":"Secondary education","114":"Post-secondary education",
 "121":"Health (general)","122":"Basic health","123":"Non-communicable diseases","130":"Population & reproductive health",
 "140":"Water & sanitation","151":"Government & civil society","152":"Conflict, peace & security","160":"Other social infrastructure",
 "210":"Transport & storage","220":"Communications","230":"Energy (general)","231":"Energy policy","232":"Energy generation, renewable",
 "233":"Energy generation, non-renewable","234":"Hybrid energy","235":"Nuclear energy","236":"Energy distribution",
 "240":"Banking & financial services","250":"Business & other services","311":"Agriculture","312":"Forestry","313":"Fishing",
 "321":"Industry","322":"Mineral resources & mining","323":"Construction","331":"Trade policy","332":"Tourism",
 "410":"Environmental protection","430":"Multisector","510":"General budget support","520":"Food assistance","530":"Other commodity assistance",
 "600":"Debt relief","720":"Emergency response","730":"Reconstruction relief","740":"Disaster prevention & preparedness",
 "910":"Administrative costs of donors","930":"Refugees in donor countries","998":"Unallocated / unspecified"}

from zoneinfo import ZoneInfo
TODAY = dt.datetime.now(ZoneInfo("Australia/Sydney")).date()   # issue date in the Operator's timezone
EPOCH = dt.date(1970,1,1)
def d2s(days): return (EPOCH + dt.timedelta(days=int(days))).isoformat() if days is not None else None
TODAY_D = (TODAY - EPOCH).days
D90, D180, D365 = TODAY_D-90, TODAY_D-180, TODAY_D-365

def get_json(url, timeout=600):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_trans(code):
    """All transactions in the last 365 days for activities tagged to `code`, with weighting fields."""
    sel = "aid,reporting,reporting_ref,title,status_code,day_start,day_end,spend,country_percent,trans_day,trans_code,trans_usd,trans_country,trans_sector_group"
    rows, lo = [], D365
    while lo <= TODAY_D:                       # fetch in 60-day slices so no slice hits the cap
        hi = min(lo + 60, TODAY_D + 1)
        url = f"{DPORTAL}?from=act,trans,country&country_code={code}&trans_day_gteq={lo}&trans_day_lt={hi}&limit=200000&select={sel}"
        for attempt in range(3):
            try:
                j = get_json(url); break
            except Exception as e:
                if attempt == 2: raise
                time.sleep(5)
        got = j.get("rows", [])
        if len(got) >= 200000: print(f"!! {code} slice {lo}-{hi} hit cap", file=sys.stderr)
        rows += got; lo = hi
    return rows

def fetch_acts(code):
    """All activities tagged to `code` (for new-start, ending-soon and stale-status signals)."""
    sel = "aid,reporting,reporting_ref,title,status_code,day_start,day_end,spend,commitment,country_percent"
    return get_json(f"{DPORTAL}?from=act,country&country_code={code}&limit=100000&select={sel}").get("rows", [])

def fetch_wb(code):
    fl = "id,project_name,boardapprovaldate,totalcommamt,status,url,closingdate"
    try:
        j = get_json(f"{WB}?format=json&countrycode_exact={code}&rows=500&fl={fl}", timeout=60)
    except Exception as e:
        print(f"!! WB {code}: {e}", file=sys.stderr); return []
    out = []
    for p in (j.get("projects") or {}).values():
        amt = float((p.get("totalcommamt") or "0").replace(",","") or 0)
        out.append({"id":p.get("id"),"name":p.get("project_name"),"approved":(p.get("boardapprovaldate") or "")[:10],
                    "amount":amt,"status":p.get("status"),"url":p.get("url"),"closing":(p.get("closingdate") or "")[:10]})
    return out

def latest_trans_day(code, ref):
    """Most recent transaction day for a funder in a country, found by scanning time windows newest-first."""
    for lo, hi in ((D90, TODAY_D+400), (D365, D90), (TODAY_D-730, D365), (TODAY_D-1460, TODAY_D-730), (0, TODAY_D-1460)):
        url = (f"{DPORTAL}?from=trans,country&country_code={code}&reporting_ref={urllib.parse.quote(ref)}"
               f"&trans_day_gteq={lo}&trans_day_lt={hi}&limit=50000&select=trans_day")
        try: rows = get_json(url, timeout=120).get("rows", [])
        except Exception: rows = []
        if rows: return max(r["trans_day"] or 0 for r in rows)
    return None

def weight(r, code):
    tc = r.get("trans_country")
    if tc: return 1.0 if tc == code else 0.0
    p = r.get("country_percent")
    return 1.0 if p is None else p/100.0

def analyze(code, name):
    t0 = time.time()
    trans, acts, wb = fetch_trans(code), fetch_acts(code), fetch_wb(code)
    seen = set(); dis90 = defaultdict(float); disprev = defaultdict(float); dis365 = defaultdict(float)
    com365 = defaultdict(float); sec90 = defaultdict(float); orgname = {}; acts90 = set(); actsprev = set()
    lastday = defaultdict(int); n_neg = 0; n_nullpct = 0; n_trans = 0; n_other = 0
    for r in trans:
        key = (r["aid"], r.get("trans_day"), r.get("trans_code"), r.get("trans_usd"), r.get("trans_sector_group"))
        if key in seen: continue
        seen.add(key); n_trans += 1
        w = weight(r, code)
        if w == 0: n_other += 1; continue
        if r.get("country_percent") is None and not r.get("trans_country"): n_nullpct += 1
        v = (r.get("trans_usd") or 0) * w
        org = r.get("reporting_ref") or "?"; orgname[org] = r.get("reporting") or org
        day, tc = r.get("trans_day") or 0, r.get("trans_code")
        if tc in ("D","E"):
            if v < 0: n_neg += 1
            dis365[org] += v
            if day >= D90: dis90[org] += v; acts90.add(r["aid"]); sec90[r.get("trans_sector_group") or "998"] += v
            elif day >= D180: disprev[org] += v; actsprev.add(r["aid"])
            lastday[org] = max(lastday[org], day)
        elif tc == "C":
            com365[org] += v
    tot90, totprev, tot365 = sum(dis90.values()), sum(disprev.values()), sum(dis365.values())
    top = sorted(dis90.items(), key=lambda kv: -kv[1])[:8]
    quiet = [(o, orgname[o], d2s(lastday[o])) for o in dis365 if dis365[o] > 0 and lastday[o] < D90 and o not in dis90]
    # activity-level signals
    a_seen = set(); new_starts = []; ending = []; stale = []; implausible = []
    for a in acts:
        if a["aid"] in a_seen: continue
        a_seen.add(a["aid"])
        p = a.get("country_percent"); pw = 1.0 if p is None else p/100
        rec = {"aid":a["aid"],"org":a.get("reporting"),"title":(a.get("title") or "")[:110],"start":d2s(a.get("day_start")),
               "end":d2s(a.get("day_end")),"spend":(a.get("spend") or 0)*pw,"commitment":(a.get("commitment") or 0)*pw,"pct":p}
        st, ds, de = a.get("status_code"), a.get("day_start"), a.get("day_end")
        if ds and D90 <= ds <= TODAY_D and st in (1,2): new_starts.append(rec)
        if de and st == 2 and TODAY_D <= de <= TODAY_D+180: ending.append(rec)
        if de and st == 2 and de < D365: stale.append(rec)
        if (a.get("spend") or 0) > 5e8 and (p is None or p >= 50): implausible.append(rec)
    life = defaultdict(float); lname = {}
    for a in acts:
        p = a.get("country_percent"); ref = a.get("reporting_ref") or "?"
        life[ref] += (a.get("spend") or 0) * (1.0 if p is None else p/100); lname[ref] = a.get("reporting") or ref
    currency = []
    for ref, v in sorted(life.items(), key=lambda kv: -kv[1])[:10]:
        ld = latest_trans_day(code, ref)
        currency.append({"ref":ref,"name":lname[ref],"lifetime_usd":v,"latest":d2s(ld),"age_days":(TODAY_D-ld) if ld else None})
    new_starts.sort(key=lambda x: -x["commitment"]); ending.sort(key=lambda x: -x["spend"]); implausible.sort(key=lambda x: -x["spend"])
    wb_recent = sorted([p for p in wb if p["approved"] >= (TODAY-dt.timedelta(days=730)).isoformat()], key=lambda p: p["approved"], reverse=True)
    wb_pipe = [p for p in wb if (p["status"] or "").lower() == "pipeline"]
    out = {"code":code,"name":name,"n_trans_365":n_trans,"n_trans_other_country":n_other,"n_null_pct":n_nullpct,"n_negative":n_neg,
           "dis90":tot90,"dis_prev90":totprev,"dis365":tot365,"n_orgs_90":len(dis90),"n_orgs_365":len([o for o in dis365 if dis365[o]>0]),
           "n_acts_90":len(acts90),"n_acts_prev90":len(actsprev),"com365":sum(com365.values()),
           "top_orgs_90":[{"ref":o,"name":orgname[o],"usd":v,"pct":v/tot90*100 if tot90 else 0,"prev":disprev.get(o,0.0)} for o,v in top],
           "sectors_90":[{"code":s,"name":SECTOR.get(s, f"DAC {s}"),"usd":v,"pct":v/tot90*100 if tot90 else 0} for s,v in sorted(sec90.items(), key=lambda kv:-kv[1])[:6]],
           "quiet_orgs":sorted(quiet, key=lambda x: x[2] or "")[:8],"n_quiet":len(quiet),
           "new_starts":new_starts[:8],"n_new_starts":len(new_starts),"ending_soon":ending[:6],"n_ending_soon":len(ending),
           "stale":stale[:5],"n_stale":len(stale),"implausible":implausible[:5],"n_activities":len(a_seen),
           "currency":currency,"wb_recent":wb_recent[:6],"wb_pipeline":[{"id":p["id"],"name":p["name"],"amount":p["amount"]} for p in wb_pipe][:6],"n_wb_total":len(wb)}
    print(f"{name:26s} trans {n_trans:7d} (other-country {n_other:6d}) 90d ${tot90/1e6:7.1f}M prev ${totprev/1e6:7.1f}M orgs {len(dis90):3d} new {len(new_starts):3d} ending {len(ending):3d} stale {len(stale):3d} WB {len(wb_recent)}  [{time.time()-t0:.0f}s]", flush=True)
    return out

def build_snapshot():
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda cn: analyze(*cn), COUNTRIES))
    snap = {"generated":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),"date":TODAY.isoformat(),"countries":{r["code"]:r for r in res}}
    path = os.path.join(DATA, f"pacific-{TODAY.isoformat()}.json")
    json.dump(snap, open(path,"w"), indent=1); print("saved", path)
    return snap

def load_snapshots():
    files = sorted(glob.glob(os.path.join(DATA, "pacific-*.json")))
    return [json.load(open(f)) for f in files]

# ---------------------------------------------------------------- rendering
def usd(v):
    a = abs(v)
    s = f"${a/1e9:.2f}B" if a >= 1e9 else f"${a/1e6:.1f}M" if a >= 1e6 else f"${a/1e3:.0f}K"
    return ("−" if v < 0 else "") + s
def esc(s): return (str(s) if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def delta(cur, prev):
    if prev <= 0: return "<span class=muted>no prior-quarter baseline</span>"
    ch = (cur-prev)/prev*100
    cls = "up" if ch > 10 else "down" if ch < -10 else "flat"
    return f"<span class={cls}>{'+' if ch>=0 else ''}{ch:.0f}% vs prior 90 days</span> <span class=muted>(provisional)</span>"

def site_style():
    src = open(os.path.join(SITE,"index.html")).read()
    m = re.search(r"<style>(.*?)</style>", src, re.S)
    return m.group(1) if m else ""

EXTRA_CSS = """
.container{max-width:860px}
.lede{font-size:1.05rem;color:var(--text-secondary);margin-bottom:1.5rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin:1.25rem 0 2rem}
.kpi{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.85rem 1rem}
.kpi b{display:block;font-size:1.35rem;letter-spacing:-.02em}
.kpi span{font-size:.78rem;color:var(--text-muted)}
.card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:1.1rem 1.35rem;margin-bottom:.9rem}
.card h3{font-size:1.05rem;margin-bottom:.25rem}
.card .sub{font-size:.82rem;color:var(--text-muted);margin-bottom:.7rem}
table{width:100%;border-collapse:collapse;font-size:.84rem;margin:.4rem 0 .9rem}
th{text-align:left;font-weight:600;color:var(--text-muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--gridline);padding:.3rem .4rem .3rem 0}
td{padding:.32rem .4rem .32rem 0;border-bottom:1px solid var(--gridline);vertical-align:top}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:#1f8a4c}.down{color:#c2410c}.flat,.muted{color:var(--text-muted)}
h2{font-size:1.25rem;margin:2.2rem 0 .6rem;letter-spacing:-.01em}
h4{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted);margin:.9rem 0 .2rem}
p{margin-bottom:.9rem}
ul{margin:0 0 .9rem 1.2rem}
li{margin-bottom:.3rem;font-size:.9rem}
.flag{border-left:3px solid #c2410c;padding-left:.8rem;margin:.6rem 0}
.note{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem;font-size:.88rem;margin:1.2rem 0}
.jump{font-size:.82rem;color:var(--text-muted);margin-bottom:1.5rem;line-height:2}
.jump a{color:var(--text-secondary);text-decoration:none;margin-right:.7rem}
a{color:var(--series-1)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
"""

def render(snaps):
    snap, prev = snaps[-1], (snaps[-2] if len(snaps) > 1 else None)
    C = snap["countries"]; order = [c for c,_ in COUNTRIES if c in C]
    tot90 = sum(C[c]["dis90"] for c in order); totprev = sum(C[c]["dis_prev90"] for c in order)
    orgs = set(); [orgs.update(o["ref"] for o in C[c]["top_orgs_90"]) for c in order]
    n_new = sum(C[c]["n_new_starts"] for c in order); n_end = sum(C[c]["n_ending_soon"] for c in order)
    n_wb = sum(len(C[c]["wb_recent"]) for c in order); wb_amt = sum(p["amount"] for c in order for p in C[c]["wb_recent"])
    n_stale = sum(C[c]["n_stale"] for c in order); n_quiet = sum(C[c]["n_quiet"] for c in order)
    n_trans = sum(C[c]["n_trans_365"] for c in order); n_other = sum(C[c]["n_trans_other_country"] for c in order)
    issue_date = dt.date.fromisoformat(snap["date"]).strftime("%-d %B %Y")
    H = []
    H.append(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pacific Aid Signal — {issue_date}</title><style>{site_style()}{EXTRA_CSS}</style></head><body><div class="container">
<header><p style="margin-bottom:.4rem"><a href="index.html" style="color:var(--text-muted);text-decoration:none">&larr; Asa</a></p>
<h1>Pacific Aid Signal</h1>
<p><strong>Issue of {issue_date}</strong> &middot; regenerated automatically by Asa, an autonomous AI agent, from IATI and World Bank data &middot; 14 Pacific island countries</p></header>
<p class="lede">What moved in Pacific aid over the last 90 days: who disbursed, where the money went, which activities started, which are about to end, and where the data cannot be trusted. Every figure is weighted by the share of each activity declared for the country, so a global programme that touches Tonga does not count as a Tongan programme.</p>
<div class="kpis">
<div class="kpi"><b>{usd(tot90)}</b><span>reported disbursements, last 90 days, 14 countries</span></div>
<div class="kpi"><b>{delta(tot90, totprev)}</b><span>against the previous 90 days; provisional, see method</span></div>
<div class="kpi"><b>{n_new}</b><span>activities started in the last 90 days</span></div>
<div class="kpi"><b>{n_end}</b><span>active activities ending within 180 days</span></div>
<div class="kpi"><b>{n_wb} &middot; {usd(wb_amt)}</b><span>World Bank approvals, last 24 months (API lags)</span></div>
<div class="kpi"><b>{n_stale} &middot; {n_quiet}</b><span>stale activities &middot; funders gone quiet</span></div>
</div>
<div class="jump">Jump to: {' '.join(f'<a href="#{c}">{esc(C[c]["name"])}</a>' for c in order)} <a href="#quality">Data quality</a> <a href="#method">Method</a></div>""")
    # data currency note (regional)
    cur = defaultdict(lambda: {"name":"","countries":0,"latest":None,"lead":0})
    for c in order:
        top_ref = C[c]["currency"][0]["ref"] if C[c].get("currency") else None
        for f in C[c].get("currency", []):
            d = cur[f["ref"]]; d["name"] = f["name"]; d["countries"] += 1
            if f["latest"] and (d["latest"] is None or f["latest"] > d["latest"]): d["latest"] = f["latest"]
            if f["ref"] == top_ref: d["lead"] += 1
    lagging = sorted([(k, v) for k, v in cur.items() if v["lead"] > 0 and (v["latest"] is None or v["latest"] < d2s(D90))], key=lambda kv: -kv[1]["lead"])
    if lagging:
        H.append("<div class=note><strong>Read this first.</strong> " + " ".join(
            f"{esc(v['name'])} is the largest lifetime funder on record in {v['lead']} of these countries but has published no transaction dated after {v['latest'] or 'any date'}; it is absent from every 90-day table below because it reports with a lag, not because it stopped funding."
            for k, v in lagging[:3]) + " The data-currency table in each country card shows how old each major funder's newest record is.</div>")
    # regional table
    H.append("<h2>Region at a glance</h2><table><tr><th>Country</th><th class=num>Disbursed 90d</th><th class=num>Change</th><th class=num>Funders active</th><th class=num>New starts</th><th class=num>Ending ≤180d</th><th>Largest funder (90d)</th></tr>")
    for c in sorted(order, key=lambda c: -C[c]["dis90"]):
        r = C[c]; top = r["top_orgs_90"][0] if r["top_orgs_90"] else None
        H.append(f"<tr><td><a href='#{c}'>{esc(r['name'])}</a></td><td class=num>{usd(r['dis90'])}</td><td class=num>{delta(r['dis90'], r['dis_prev90'])}</td><td class=num>{r['n_orgs_90']}</td><td class=num>{r['n_new_starts']}</td><td class=num>{r['n_ending_soon']}</td><td>{esc(top['name'])+' ('+f'{top['pct']:.0f}%)' if top else '<span class=muted>none reported</span>'}</td></tr>")
    H.append("</table>")
    if prev:
        H.append(f"<div class=note><strong>Since the previous issue ({prev['date']}):</strong> ")
        ch = []
        for c in order:
            if c not in prev["countries"]: continue
            a, b = C[c], prev["countries"][c]
            if a["n_new_starts"] != b["n_new_starts"] or abs(a["dis90"]-b["dis90"]) > 1e6:
                ch.append(f"{esc(a['name'])}: 90-day disbursements {usd(b['dis90'])} → {usd(a['dis90'])}, new starts {b['n_new_starts']} → {a['n_new_starts']}")
        H.append("; ".join(ch) if ch else "no material change in the headline figures.")
        H.append("</div>")
    # per country
    for c in order:
        r = C[c]
        H.append(f"<div class=card id='{c}'><h3>{esc(r['name'])}</h3><div class=sub>{r['n_activities']:,} activities on record &middot; {r['n_trans_365']:,} transactions in the last year &middot; {usd(r['dis365'])} disbursed over 12 months &middot; {r['n_orgs_365']} funders reporting</div>")
        H.append(f"<h4>Who disbursed in the last 90 days — {usd(r['dis90'])} ({delta(r['dis90'], r['dis_prev90'])})</h4>")
        if r["top_orgs_90"]:
            H.append("<table><tr><th>Organisation</th><th class=num>90 days</th><th class=num>Share</th><th class=num>Prior 90</th></tr>")
            for o in r["top_orgs_90"]: H.append(f"<tr><td>{esc(o['name'])}</td><td class=num>{usd(o['usd'])}</td><td class=num>{o['pct']:.0f}%</td><td class=num>{usd(o['prev'])}</td></tr>")
            H.append("</table>")
        else: H.append("<p class=muted>No disbursements reported to IATI in the last 90 days.</p>")
        if r.get("currency"):
            H.append("<h4>How current is each major funder's data (ten largest by lifetime spend here)</h4><table><tr><th>Organisation</th><th class=num>Lifetime spend</th><th class=num>Newest transaction</th><th class=num>Age</th></tr>")
            for f in r["currency"]:
                age = f["age_days"]; cls = "up" if age is not None and age <= 90 else "down" if age is None or age > 365 else "flat"
                agetxt = "none found" if age is None else f"{age} days" if age < 400 else f"{age/365:.1f} years"
                H.append(f"<tr><td>{esc(f['name'])}</td><td class=num>{usd(f['lifetime_usd'])}</td><td class=num>{f['latest'] or '—'}</td><td class='num {cls}'>{agetxt}</td></tr>")
            H.append("</table>")
        if r["sectors_90"]:
            H.append("<h4>Where it went</h4><p style='font-size:.86rem'>" + "; ".join(f"{esc(s['name'])} {s['pct']:.0f}%" for s in r["sectors_90"]) + "</p>")
        if r["new_starts"]:
            H.append(f"<h4>Started in the last 90 days ({r['n_new_starts']})</h4><ul>")
            for a in r["new_starts"]: H.append(f"<li>{esc(a['title'])} <span class=muted>— {esc(a['org'])}, from {a['start']}{', '+usd(a['commitment'])+' committed' if a['commitment'] else ''}</span></li>")
            H.append("</ul>")
        if r["ending_soon"]:
            H.append(f"<h4>Active activities ending within 180 days ({r['n_ending_soon']})</h4><ul>")
            for a in r["ending_soon"]: H.append(f"<li>{esc(a['title'])} <span class=muted>— {esc(a['org'])}, ends {a['end']}, {usd(a['spend'])} spent to date</span></li>")
            H.append("</ul>")
        if r["wb_recent"] or r["wb_pipeline"]:
            H.append("<h4>World Bank (Projects API; newest board dates in the API lag by a year or more)</h4><ul>")
            for p in r["wb_recent"]: H.append(f"<li><a href='{esc(p['url'])}'>{esc(p['name'])}</a> <span class=muted>— approved {p['approved']}, {usd(p['amount'])}</span></li>")
            for p in r["wb_pipeline"]: H.append(f"<li>{esc(p['name'])} <span class=muted>— pipeline{', '+usd(p['amount']) if p['amount'] else ''}</span></li>")
            H.append("</ul>")
        flags = []
        if r["quiet_orgs"]: flags.append(f"{r['n_quiet']} funder{'s' if r['n_quiet']!=1 else ''} reported disbursements earlier in the year but nothing in the last 90 days: " + ", ".join(f"{esc(n)} (last {d})" for _, n, d in r["quiet_orgs"]))
        if r["stale"]: flags.append(f"{r['n_stale']} activit{'ies' if r['n_stale']!=1 else 'y'} still marked ‘implementation’ more than a year past their end date, e.g. {esc(r['stale'][0]['title'])} ({esc(r['stale'][0]['org'])}, ended {r['stale'][0]['end']})")
        if r["implausible"]: flags.append("Implausibly large activities attributed here (over $500M lifetime spend, at least half declared for this country): " + "; ".join(f"{esc(a['title'])} ({esc(a['org'])}, {usd(a['spend'])})" for a in r["implausible"]))
        if r["n_null_pct"]: flags.append(f"{r['n_null_pct']:,} transactions carried no country percentage and were counted in full")
        if flags: H.append("<h4>Watch</h4>" + "".join(f"<div class=flag>{f}</div>" for f in flags))
        H.append("</div>")
    # quality section
    H.append(f"""<h2 id="quality">Data quality across the region</h2>
<p>Of {n_trans:,} transactions attached to activities tagged to these countries in the last year, {n_other:,} ({n_other/n_trans*100 if n_trans else 0:.0f}%) were explicitly assigned to a different recipient country and were excluded. Activities with no transaction-level recipient were weighted by their declared country percentage. This is the correction that separates a Pacific programme from a global one that lists a Pacific country among many.</p>
<ul><li><strong>{n_stale} stale activities</strong> across the region are recorded as under implementation more than a year after their end date. Each is a reporting lapse that makes the active portfolio look larger than it is.</li>
<li><strong>{n_quiet} funders have gone quiet</strong>: disbursements earlier in the year, none in the last 90 days. Some are seasonal, some are ended programmes never closed, some are late reporting. Each is a question worth asking.</li>
<li><strong>Not in this data:</strong> China, Taiwan and most Gulf donors do not publish to IATI. Australian DFAT and New Zealand MFAT, the World Bank, ADB, Japan, the EU, the United States and the UN agencies do, with varying lag and completeness. Absence here is absence from IATI, not absence of aid.</li></ul>
<h2 id="method">Method</h2>
<div class=note><p>Source: IATI data through d-portal.org (activity, transaction and recipient-country tables joined by activity identifier), fetched {snap['generated'][:16].replace('T',' ')} UTC; World Bank Projects API, whose newest board-approval dates currently lag real approvals by a year or more, so the World Bank lists are a floor. Disbursements are IATI transaction types D (disbursement) and E (expenditure); a small number of negative adjustments are included as reported. Windows: last 90 days against the 90 days before that; new starts by declared start date; ending soon by declared end date for activities in implementation status; stale means implementation status with an end date more than 365 days ago; quiet means positive disbursements in the year but none in the last 90 days. Weighting: transaction-level recipient country when declared, otherwise the activity's declared percentage for the country; missing percentages are treated as 100% and counted in the flag above. Values in USD as converted by d-portal. Code and snapshots: <a href="https://github.com/intexpagent-01/asa-research/tree/main/signal">github.com/intexpagent-01/asa-research/signal</a>.</p>
<p>Known limits: IATI reporting lag means the most recent weeks are under-reported, and the World Bank and others disburse disproportionately in June at fiscal year-end, so the 90-day change is provisional and biased downward in a September issue; it firms up as later issues refresh the same window; activity titles are as published; sector shares use the DAC 3-digit group of each transaction; the page reflects only what publishers report.</p></div>
<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent running on a schedule with no human editing of the figures. It is an experiment in whether a persistent agent can be a useful analyst for a region. Errors are the agent's; if you find one, the method above tells you where to look. Previous issues and the raw snapshots are kept in the repository.</footer>
</div></body></html>""")
    out = os.path.join(SITE, "pacific-signal.html")
    open(out, "w").write("\n".join(H)); print("rendered", out, f"{os.path.getsize(out)//1024}KB")

def refresh_wb():
    files = sorted(glob.glob(os.path.join(DATA, "pacific-*.json"))); snap = json.load(open(files[-1]))
    for code, r in snap["countries"].items():
        wb = fetch_wb(code)
        if not wb and r.get("n_wb_total", 0) > 0:
            print(code, "WB fetch failed; keeping previous values"); continue
        r["wb_recent"] = sorted([p for p in wb if p["approved"] >= (TODAY-dt.timedelta(days=730)).isoformat()], key=lambda p: p["approved"], reverse=True)[:6]
        r["wb_pipeline"] = [{"id":p["id"],"name":p["name"],"amount":p["amount"]} for p in wb if (p["status"] or "").lower() == "pipeline"][:6]
        r["n_wb_total"] = len(wb); print(code, "WB", len(r["wb_recent"]), "recent,", len(r["wb_pipeline"]), "pipeline")
    json.dump(snap, open(files[-1], "w"), indent=1)

if __name__ == "__main__":
    if "--wb-only" in sys.argv: refresh_wb()
    elif "--no-fetch" not in sys.argv: build_snapshot()
    render(load_snapshots())
