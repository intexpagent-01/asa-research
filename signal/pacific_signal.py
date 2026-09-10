#!/usr/bin/env python3
"""Pacific Aid Signal — an autonomous, continuously regenerated aid-intelligence service
for 14 Pacific island countries, built from IATI (via d-portal) and World Bank project data.

Every run: fetch the last 365 days of IATI transactions per country (joined to activity
and country tables so recipient-country weighting is applied), fetch all activities and
World Bank projects, compute signals, save a dated snapshot (one issue per Sydney calendar
day; a later run on the same day refreshes that issue), diff against the newest earlier
issue, and render the regional page plus one page per country.

Usage: python3 pacific_signal.py            fetch, snapshot, render
       python3 pacific_signal.py --no-fetch  re-render from the newest snapshot
       python3 pacific_signal.py --wb-only   refresh World Bank data in the newest snapshot, render
       python3 pacific_signal.py --dfat-only refresh DFAT notices and pipeline in the newest snapshot, render
"""
import json, gzip, os, re, sys, time, glob, urllib.request, urllib.parse, datetime as dt
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import dfat_notices
import watches
WATCHES = {}          # code -> list of standing watches, loaded once per render
DATA = os.environ.get("SIGNAL_DATA") or os.path.join(HERE, "data")
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
DPORTAL = "https://d-portal.org/q.json"
WB = "https://search.worldbank.org/api/v2/projects"
REPO = "https://github.com/intexpagent-01/asa-research"
# A short form, hosted and owned by the Operator, that lets someone without a GitHub account leave feedback or
# file a watch (C5). Empty until the Operator creates it; every page's wording adapts to whether it exists.
FEEDBACK_FORM = os.environ.get("SIGNAL_FEEDBACK_FORM", "").strip()
UA = {"User-Agent": "asa-research/0.6 (pacific-aid-signal)"}

COUNTRIES = [("PG","Papua New Guinea","papua-new-guinea"),("FJ","Fiji","fiji"),("SB","Solomon Islands","solomon-islands"),
             ("VU","Vanuatu","vanuatu"),("WS","Samoa","samoa"),("TO","Tonga","tonga"),("KI","Kiribati","kiribati"),
             ("TV","Tuvalu","tuvalu"),("FM","Micronesia (Fed. States)","micronesia"),("MH","Marshall Islands","marshall-islands"),
             ("PW","Palau","palau"),("NR","Nauru","nauru"),("NU","Niue","niue"),("CK","Cook Islands","cook-islands")]
SLUG = {c:s for c,_,s in COUNTRIES}; NAME = {c:n for c,n,_ in COUNTRIES}
def page(code): return f"pacific-signal-{SLUG[code]}.html"
ALIASES = {"PG":["Papua New Guinea","PNG"],"FJ":["Fiji"],"SB":["Solomon Islands","Solomons"],"VU":["Vanuatu"],"WS":["Samoa"],
           "TO":["Tonga"],"KI":["Kiribati"],"TV":["Tuvalu","Vaitupu","Funafuti","Falepili"],"FM":["Micronesia","FSM"],"MH":["Marshall Islands","RMI"],
           "PW":["Palau"],"NR":["Nauru"],"NU":["Niue"],"CK":["Cook Islands"]}
def names_other(title, code):
    """If an activity title names a different Pacific country and not this one, return that country's name.
    Publishers (UNDP's Pacific office in particular) tag activities to the country where the office sits."""
    t = title or ""
    pat = lambda a: r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])"     # underscores and hyphens count as boundaries
    if any(re.search(pat(a), t, re.I) for a in ALIASES[code]): return None
    for c, al in ALIASES.items():
        if c != code and any(re.search(pat(a), t) for a in al): return NAME[c]
    return None
def clean_title(t):
    t = t or ""
    return "(title redacted by USAID)" if t.startswith("USAID redacted this field") else t
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

TODAY = dt.datetime.now(ZoneInfo("Australia/Sydney")).date()   # issue date in the Operator's timezone
EPOCH = dt.date(1970,1,1)
def d2s(days): return (EPOCH + dt.timedelta(days=int(days))).isoformat() if days is not None else None
TODAY_D = (TODAY - EPOCH).days
D90, D180, D365 = TODAY_D-90, TODAY_D-180, TODAY_D-365

# ---------------------------------------------------------------- fetching
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

# ---------------------------------------------------------------- analysis
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
    a_seen = set(); new_starts = []; ending = []; stale = []; implausible = []; active = []; misnamed = []
    index = []            # every activity in pipeline, implementation or finalisation status: what standing watches are matched against
    af_n = defaultdict(int); af_spend = defaultdict(float); af_name = {}
    for a in acts:
        if a["aid"] in a_seen: continue
        a_seen.add(a["aid"])
        p = a.get("country_percent"); pw = 1.0 if p is None else p/100
        rec = {"aid":a["aid"],"org":a.get("reporting"),"ref":a.get("reporting_ref"),"title":clean_title(a.get("title"))[:110],"start":d2s(a.get("day_start")),
               "end":d2s(a.get("day_end")),"spend":(a.get("spend") or 0)*pw,"commitment":(a.get("commitment") or 0)*pw,"pct":p,
               "names":names_other(a.get("title"), code)}
        st, ds, de = a.get("status_code"), a.get("day_start"), a.get("day_end")
        if st in (1,2,3): index.append([rec['aid'], rec['ref'], rec['org'], rec['title'], st, rec['start'], rec['end'], round(rec['spend']), p, rec['names'], bool(de and st == 2 and de < D365)])
        if ds and D90 <= ds <= TODAY_D and st in (1,2): new_starts.append(rec)
        if de and st == 2 and TODAY_D <= de <= TODAY_D+180: ending.append(rec)
        if de and st == 2 and de < D365: stale.append(rec)
        if (a.get("spend") or 0) > 5e8 and (p is None or p >= 50): implausible.append(rec)
        if rec["names"] and st in (1,2) and (p is None or p >= 50): misnamed.append(rec)
        if st == 2 and not (de and de < D365):          # active portfolio: implementation status, not stale
            active.append(rec); ref = a.get("reporting_ref") or "?"
            af_n[ref] += 1; af_spend[ref] += rec["spend"]; af_name[ref] = a.get("reporting") or ref
    life = defaultdict(float); lname = {}
    for a in acts:
        p = a.get("country_percent"); ref = a.get("reporting_ref") or "?"
        life[ref] += (a.get("spend") or 0) * (1.0 if p is None else p/100); lname[ref] = a.get("reporting") or ref
    currency = []
    for ref, v in sorted(life.items(), key=lambda kv: -kv[1])[:10]:
        ld = latest_trans_day(code, ref)
        currency.append({"ref":ref,"name":lname[ref],"lifetime_usd":v,"latest":d2s(ld),"age_days":(TODAY_D-ld) if ld else None})
    # activities whose title names another Pacific country sort last; duplicates by publisher and title collapse to the first
    def dedupe(rows):
        seen = set(); out = []
        for x in rows:
            k = (x["ref"], x["title"])
            if k not in seen: seen.add(k); out.append(x)
        return out
    # counts use the full lists; only the displayed rows are de-duplicated
    new_starts.sort(key=lambda x: (bool(x["names"]), -x["commitment"])); ending.sort(key=lambda x: (bool(x["names"]), -x["spend"]))
    active.sort(key=lambda x: (bool(x["names"]), -x["spend"])); implausible.sort(key=lambda x: -x["spend"]); misnamed.sort(key=lambda x: -x["spend"])
    active_by_funder = [{"ref":r,"name":af_name[r],"n":af_n[r],"spend":af_spend[r]} for r in sorted(af_n, key=lambda r: (-af_n[r], -af_spend[r]))[:8]]
    wb_recent = sorted([p for p in wb if p["approved"] >= (TODAY-dt.timedelta(days=730)).isoformat()], key=lambda p: p["approved"], reverse=True)
    wb_pipe = [p for p in wb if (p["status"] or "").lower() == "pipeline"]
    out = {"code":code,"name":name,"n_trans_365":n_trans,"n_trans_other_country":n_other,"n_null_pct":n_nullpct,"n_negative":n_neg,
           "dis90":tot90,"dis_prev90":totprev,"dis365":tot365,"n_orgs_90":len(dis90),"n_orgs_365":len([o for o in dis365 if dis365[o]>0]),
           "n_acts_90":len(acts90),"n_acts_prev90":len(actsprev),"com365":sum(com365.values()),
           "top_orgs_90":[{"ref":o,"name":orgname[o],"usd":v,"pct":v/tot90*100 if tot90 else 0,"prev":disprev.get(o,0.0)} for o,v in top],
           "sectors_90":[{"code":s,"name":SECTOR.get(s, f"DAC {s}"),"usd":v,"pct":v/tot90*100 if tot90 else 0} for s,v in sorted(sec90.items(), key=lambda kv:-kv[1])[:6]],
           "quiet_orgs":sorted(quiet, key=lambda x: x[2] or "")[:8],"n_quiet":len(quiet),
           "new_starts":dedupe(new_starts)[:8],"n_new_starts":len(new_starts),"ending_soon":dedupe(ending)[:6],"n_ending_soon":len(ending),
           "stale":stale[:5],"n_stale":len(stale),"implausible":implausible[:5],"n_activities":len(a_seen),
           "n_active":len(active),"largest_active":dedupe(active)[:6],"active_by_funder":active_by_funder,
           # full sets for the change log (the displayed lists above are truncated)
           "orgs_90":[{"ref":o,"name":orgname[o],"usd":v} for o,v in sorted(dis90.items(), key=lambda kv: -kv[1])],
           "new_starts_all":[{k:x[k] for k in ("aid","title","org","start","commitment","pct","names")} for x in new_starts],
           "ending_all":[{k:x[k] for k in ("aid","title","org","end","spend","pct","names")} for x in ending],
           "n_misnamed":len(misnamed),"misnamed":misnamed[:4],
           "acts_index":{"cols":["aid","ref","org","title","st","start","end","spend","pct","names","stale"],"rows":index},
           "currency":currency,"wb_recent":wb_recent[:6],"wb_pipeline":[{"id":p["id"],"name":p["name"],"amount":p["amount"]} for p in wb_pipe][:6],"n_wb_total":len(wb)}
    print(f"{name:26s} trans {n_trans:7d} (other-country {n_other:6d}) 90d ${tot90/1e6:7.1f}M prev ${totprev/1e6:7.1f}M orgs {len(dis90):3d} new {len(new_starts):3d} ending {len(ending):3d} active {len(active):4d} stale {len(stale):3d} WB {len(wb_recent)}  [{time.time()-t0:.0f}s]", flush=True)
    return out

def build_snapshot():
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda cn: analyze(cn[0], cn[1]), COUNTRIES))
    snap = {"generated":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),"date":TODAY.isoformat(),"countries":{r["code"]:r for r in res}}
    snap["dfat"] = fetch_dfat_guarded()
    save_snapshot(snap)
    return snap

def save_snapshot(snap):
    """Main snapshot as readable JSON; the activity index (about 2 MB a day) as a compressed sidecar next to it."""
    path = os.path.join(DATA, f"pacific-{snap['date']}.json")
    idx = {c: r.pop("acts_index") for c, r in snap["countries"].items() if "acts_index" in r}
    json.dump(snap, open(path, "w"), indent=1); print("saved", path)
    if idx:
        with gzip.open(path[:-5] + ".index.json.gz", "wt") as f: json.dump(idx, f, separators=(",", ":"))
        for c, i in idx.items(): snap["countries"][c]["acts_index"] = i

def fetch_dfat_guarded():
    """DFAT notices and pipeline; on any failure keep the newest snapshot's block so the section never silently empties."""
    try: return dfat_notices.fetch_all()
    except Exception as e:
        print(f"!! DFAT fetch failed ({e}); keeping previous values", file=sys.stderr)
        files = sorted(glob.glob(os.path.join(DATA, "pacific-*.json")))
        return json.load(open(files[-1])).get("dfat") if files else None

def refresh_dfat():
    files = sorted(glob.glob(os.path.join(DATA, "pacific-*.json"))); snap = json.load(open(files[-1]))
    d = fetch_dfat_guarded()
    if d: snap["dfat"] = d; json.dump(snap, open(files[-1], "w"), indent=1); print("DFAT block refreshed in", files[-1])

def first_seen_dfat(snaps):
    """Issue date on which each pipeline id / notice url first appeared, and the baseline date (first issue with DFAT data)."""
    seen, base = {}, None
    for s in snaps:
        d = s.get("dfat")
        if not d: continue
        base = base or s["date"]
        for k in [p["id"] for p in d.get("items", [])] + [n["url"] for n in d.get("notices", [])]: seen.setdefault(k, s["date"])
    return seen, base

def load_snapshots():
    files = sorted(glob.glob(os.path.join(DATA, "pacific-????-??-??.json"))); out = []
    for f in files:
        s = json.load(open(f)); side = f[:-5] + ".index.json.gz"
        if os.path.exists(side):
            with gzip.open(side, "rt") as g:
                for c, i in json.load(g).items():
                    if c in s["countries"]: s["countries"][c]["acts_index"] = i
        out.append(s)
    return out

# ---------------------------------------------------------------- rendering helpers
def usd(v):
    a = abs(v or 0)
    s = f"${a/1e9:.2f}B" if a >= 1e9 else f"${a/1e6:.1f}M" if a >= 1e6 else f"${a/1e3:.0f}K"
    return ("−" if (v or 0) < 0 else "") + s
def esc(s): return (str(s) if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def longdate(s): return dt.date.fromisoformat(s).strftime("%-d %B %Y")
def sydtime(ts):
    """ISO UTC timestamp -> "9 September 2026, 03:30 AEST" (the issue calendar is Sydney's)."""
    if not ts: return "—"
    t = dt.datetime.fromisoformat(ts.replace("Z","+00:00")).astimezone(ZoneInfo("Australia/Sydney"))
    return t.strftime("%-d %B %Y, %H:%M ") + t.tzname()
def delta(cur, prev):
    if prev <= 0: return "<span class=muted>no prior-quarter baseline</span>"
    ch = (cur-prev)/prev*100
    cls = "up" if ch > 10 else "down" if ch < -10 else "flat"
    return f"<span class={cls}>{'+' if ch>=0 else ''}{ch:.0f}% vs prior 90 days</span> <span class=muted>(provisional)</span>"
def tag(a, code_name):
    """Suffix for an activity row: declared share if partial, and the other country its title names."""
    bits = []
    if a.get("pct") is not None and a["pct"] < 99.5: bits.append(("under 1" if a["pct"] < 1 else f"{a['pct']:.0f}") + f"% declared for {esc(code_name)}")
    if a.get("names"): bits.append(f"title names {esc(a['names'])}")
    return f" <span class=muted>[{'; '.join(bits)}]</span>" if bits else ""
def plural(n, one, many=None): return f"{n:,} {one if n == 1 else (many or one + 's')}"
def joinlist(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""

def site_style():
    src = open(os.path.join(SITE,"research.html")).read()
    m = re.search(r"<style>(.*?)</style>", src, re.S)
    return m.group(1) if m else ""

EXTRA_CSS = """
.container{max-width:860px}
.lede{font-size:1.05rem;color:var(--text-secondary);margin-bottom:1.5rem}
.brief{font-size:1.02rem;line-height:1.6;margin:1rem 0 1.4rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin:1.25rem 0 2rem}
.kpi{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.85rem 1rem}
.kpi b{display:block;font-size:1.35rem;letter-spacing:-.02em}
.kpi span{font-size:.78rem;color:var(--text-muted)}
.card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:1.1rem 1.35rem;margin-bottom:.9rem}
.card h3{font-size:1.05rem;margin-bottom:.25rem}
.card h3 a{text-decoration:none;color:inherit}
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
.change{border-left:3px solid var(--series-1);padding-left:.8rem;margin:.6rem 0;font-size:.92rem}
.note{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem;font-size:.88rem;margin:1.2rem 0}
.jump{font-size:.82rem;color:var(--text-muted);margin-bottom:1.5rem;line-height:2}
.jump a{color:var(--text-secondary);text-decoration:none;margin-right:.7rem}
.jump a.here{font-weight:700;color:var(--text-primary)}
.more{font-size:.84rem;margin-top:.6rem}
a{color:var(--series-1)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
details{margin:.6rem 0 1rem;font-size:.88rem}
details summary{cursor:pointer;color:var(--text-secondary);font-size:.85rem;padding:.2rem 0}
details summary:hover{color:var(--text-primary)}
details[open] summary{margin-bottom:.5rem}
details .note,details p,details ul{font-size:.85rem}
ul.lines{list-style:none;margin:.6rem 0 1.4rem 0}
ul.lines li{margin-bottom:.55rem;font-size:.95rem;line-height:1.5;padding-left:.9rem;border-left:2px solid var(--gridline)}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.7rem;margin:1.6rem 0 2.2rem}
.step{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.9rem 1.1rem}
.step b{display:block;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:.35rem}
.step p{font-size:.9rem;margin:0}
.cgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:.55rem;margin:1rem 0 1.6rem}
.ctile{display:block;background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.7rem .85rem;text-decoration:none;color:inherit}
.ctile:hover{border-color:var(--series-1)}
.ctile b{display:block;font-size:.98rem;letter-spacing:-.01em;margin-bottom:.15rem}
.ctile span{display:block;font-size:.78rem;color:var(--text-muted);font-variant-numeric:tabular-nums}
.ctile em{font-style:normal;color:var(--series-1);font-size:.78rem}
.hero{font-size:1.12rem;line-height:1.55;margin:.2rem 0 1.2rem}
.act{background:var(--surface-card);border:1px solid var(--border);border-left:3px solid var(--series-1);border-radius:8px;padding:1rem 1.25rem;margin:1.4rem 0;font-size:.92rem}
.roles{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.7rem;margin:1.2rem 0 1.8rem}
.role{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.9rem 1.1rem}
.role b{display:block;font-size:.92rem;letter-spacing:-.01em;margin-bottom:.35rem}
.role p{font-size:.86rem;margin:0;color:var(--text-secondary)}
.role p em{font-style:normal;color:var(--text-primary);font-weight:600}
"""

def head(title, back="index.html", backtext="Pacific Aid Signal"):
    up = f'<p style="margin-bottom:.4rem"><a href="{back}" style="color:var(--text-muted);text-decoration:none">&larr; {backtext}</a></p>' if back else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="Who is funding what in 14 Pacific island countries, rebuilt from IATI, World Bank and DFAT data every issue.">
<style>{site_style()}{EXTRA_CSS}</style></head><body><div class="container">
<header>{up}"""

def country_nav(order, here=None):
    return "<div class=jump>" + " ".join(f"<a href='{page(c)}'{' class=here' if c==here else ''}>{esc(NAME[c])}</a>" for c in order) + " <a href='pacific-signal.html'>Region</a></div>"

FOOTER = f"""<footer>Pacific Aid Signal is produced by Asa, an autonomous AI agent running on a schedule with no human editing of the figures. It is an experiment in whether a persistent agent can be a useful analyst for a region. Errors are the agent's; the method tells you where to look. Every issue is kept as a snapshot in the <a href="{REPO}/tree/main/signal/data">repository</a>. Use case: <a href="pitch.html">An analyst that never sleeps</a>. <a href="feedback.html">Tell the agent what would make this useful</a>.</footer>"""

# ---------------------------------------------------------------- narrative
def brief(r, pr, issue_date, dfat=None, as_list=False):
    """Plain-language summary of one country, templated from the snapshot (no model call).

    `as_list` returns the sentences separately, so a page can show them as short lines instead of a paragraph."""
    S = []; n = r["name"]
    if r["dis90"] > 0 and r["top_orgs_90"]:
        t = r["top_orgs_90"]; lead = f"{esc(t[0]['name'])} ({t[0]['pct']:.0f}%)"
        if len(t) > 1 and t[1]["pct"] >= 10: lead += f" and {esc(t[1]['name'])} ({t[1]['pct']:.0f}%)"
        S.append(f"In the 90 days to {issue_date}, {plural(r['n_orgs_90'],'funder')} reported {usd(r['dis90'])} of disbursements to {n} through IATI, led by {lead}.")
        if r["dis_prev90"] > 0:
            ch = (r["dis90"]-r["dis_prev90"])/r["dis_prev90"]*100
            S.append(f"That is {abs(ch):.0f}% {'more' if ch >= 0 else 'less'} than the 90 days before, a provisional comparison because publishers report with a lag and June carries fiscal year-end spikes." if abs(ch) >= 10 else "That is about level with the 90 days before.")
        if r["sectors_90"]:
            S.append("Most of it went to " + joinlist(f"{esc(s['name']).lower() if s['code']!='998' else 'unspecified sectors'} ({s['pct']:.0f}%)" for s in r["sectors_90"][:3]) + ".")
    else:
        S.append(f"No funder reported a disbursement to {n} through IATI in the 90 days to {issue_date}.")
    stale_lead = [f for f in r.get("currency", [])[:3] if f["age_days"] is None or f["age_days"] > 90]
    if stale_lead:
        parts = [f"{esc(f['name'])} (newest record {f['latest'] or 'none found'})" for f in stale_lead]
        S.append(f"{joinlist(parts)} {'is' if len(parts)==1 else 'are'} among the three largest funders on record here but {'has' if len(parts)==1 else 'have'} published nothing dated in the last 90 days, so {'its' if len(parts)==1 else 'their'} current spending is not in these figures.")
    if r["n_new_starts"]:
        big = r["new_starts"][0]     # sorted so activities naming another country come last
        S.append(f"{plural(r['n_new_starts'],'activity','activities')} started in the period" + (f", the largest by commitment being {esc(big['title'])} ({esc(big['org'])}, {usd(big['commitment'])})" if big["commitment"] and not big["names"] else f", including {esc(big['title'])} ({esc(big['org'])})" if not big["names"] else f", though the listed titles name other Pacific countries (publishers tag activities to the country where their office sits)") + ".")
    if r["n_ending_soon"]:
        e = r["ending_soon"][0]
        S.append(f"{plural(r['n_ending_soon'],'active activity','active activities')} {'ends' if r['n_ending_soon']==1 else 'end'} within 180 days, including {esc(e['title'])} ({esc(e['org'])}, ends {e['end']}, {usd(e['spend'])} spent to date).")
    if r["wb_recent"]:
        w = r["wb_recent"][0]
        S.append(f"The World Bank's newest recorded approval is {esc(w['name'])} ({w['approved']}, {usd(w['amount'])})" + (f", with {plural(len(r['wb_pipeline']),'project')} in pipeline" if r["wb_pipeline"] else "") + "; the Bank's API lags real approvals by a year or more.")
    if r["n_stale"]:
        S.append(f"{plural(r['n_stale'],'activity','activities')} {'is' if r['n_stale']==1 else 'are'} still recorded as under implementation more than a year past {'its' if r['n_stale']==1 else 'their'} end date, so the active portfolio is smaller than the record suggests.")
    if dfat:
        cn, rn, cp, rp = dfat_notices.for_country(dfat, r["code"], ALIASES)
        live = [p for p in cp if p["section"].lower() != "closed"]
        if live:
            lead = live[0]
            S.append(f"DFAT's procurement pipeline (as at {esc(dfat.get('as_at') or 'the last read')}) lists {plural(len(live),'item')} naming {n}, including {esc(lead['id'])} {esc(lead['title'])} ({esc(lead['section'].lower())}){'; '+plural(len(rp),'Pacific-wide item')+' also apply' if rp else ''}.")
        elif rp:
            S.append(f"DFAT's procurement pipeline (as at {esc(dfat.get('as_at') or 'the last read')}) names no {n}-specific item; {plural(len(rp),'Pacific-wide item')} apply.")
        recent = [x for x in cn if x.get("date") and x["date"] >= d2s(D90)]
        if recent: S.append(f"DFAT published {plural(len(recent),'business notification')} naming {n} in the last 90 days, newest {esc(recent[0]['title'])} ({longdate(recent[0]['date'])}).")
    return S if as_list else " ".join(S)

def short(t, n):
    """Truncate at a word boundary, drop a trailing full stop so the caller can add its own punctuation."""
    t = (t or "").strip().rstrip(".")
    if len(t) <= n: return t
    cut = t[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "\u2026"

def dfat_changes(code, cn, dfat, pdfat):
    """DFAT pipeline and notice changes for one country since the previous issue (None if either issue lacks DFAT data)."""
    if not dfat or not pdfat: return []
    out = []
    cur_n, cur_rn, cur_p, cur_rp = dfat_notices.for_country(dfat, code, ALIASES)
    prv_n, prv_rn, prv_p, prv_rp = dfat_notices.for_country(pdfat, code, ALIASES)
    pn = {n["url"] for n in prv_n} | {n["url"] for n in prv_rn}
    newn = [n for n in cur_n if n["url"] not in pn]; newr = [n for n in cur_rn if n["url"] not in pn]
    for n in newn[:3]: out.append(f"New DFAT notice naming {cn}: <a href='{esc(n['url'])}'>{esc(n['title'])}</a> ({longdate(n['date']) if n.get('date') else 'undated'}{', '+esc(n['category']) if n.get('category') else ''}).")
    if len(newn) > 3: out[-1] += f" And {len(newn)-3} more."
    for n in newr[:2]: out.append(f"New Pacific-wide DFAT notice: <a href='{esc(n['url'])}'>{esc(n['title'])}</a> ({longdate(n['date']) if n.get('date') else 'undated'}).")
    if len(newr) > 2: out[-1] += f" And {len(newr)-2} more."
    pp = {p["id"]: p for p in prv_p + prv_rp}; cp = {p["id"]: p for p in cur_p + cur_rp}
    for p in cur_p + cur_rp:
        q = pp.get(p["id"]); lbl = f"{esc(p['id'])} {esc(p['title'])}"
        if not q: out.append(f"DFAT pipeline now lists {lbl} under \u201c{esc(p['section'])}\u201d{': '+esc(short(p['status'], 160)) if p['status'] else ''}.")
        elif q["section"] != p["section"]: out.append(f"DFAT pipeline: {lbl} moved from \u201c{esc(q['section'])}\u201d to \u201c{esc(p['section'])}\u201d{': '+esc(short(p['status'], 160)) if p['status'] else ''}.")
        elif q["status"] != p["status"]: out.append(f"DFAT pipeline: {lbl} status updated: {esc(short(p['status'], 200))}.")
    gone = [q for k, q in pp.items() if k not in cp]
    if gone: out.append("No longer on DFAT's pipeline page: " + joinlist(f"{esc(q['id'])} {esc(q['title'])} (was \u201c{esc(q['section'])}\u201d)" for q in gone[:4]) + (f" and {len(gone)-4} more" if len(gone) > 4 else "") + ".")
    return out

def changes(r, pr, days=None, dfat=None, pdfat=None):
    """What changed since the previous issue for one country. Returns a list of HTML strings, most useful first.
    Entries compare full sets where the previous issue stored them (orgs_90, new_starts_all, ending_all) and fall
    back to the displayed rows for older issues. Exits from the funder table are mostly the 90-day window moving,
    so they are grouped in one sentence; count drift below three units or five percent is not reported."""
    if not pr: return None
    out = []; cn = r["name"]; moved = f"the window moved {days} day{'s' if days != 1 else ''} and " if days else ""
    def more(n, what): return f" And {n} more {what}." if n > 0 else ""
    d, p = r["dis90"], pr["dis90"]
    if abs(d-p) > max(1e5, 0.05*max(p,1)):
        out.append(f"90-day disbursements {usd(p)} &rarr; {usd(d)} ({'+' if d>=p else '&minus;'}{usd(abs(d-p))}); {moved}publishers added or revised records.")
    pw = {w["id"] for w in pr["wb_recent"]}
    for w in r["wb_recent"]:
        if w["id"] not in pw: out.append(f"World Bank approval now on record: {esc(w['name'])} ({w['approved']}, {usd(w['amount'])}).")
    pc = {f["ref"]: f for f in pr.get("currency", [])}
    for f in r.get("currency", []):
        q = pc.get(f["ref"])
        if q and f["latest"] and (q["latest"] or "") < f["latest"]:
            out.append(f"{esc(f['name'])} published newer data: newest transaction now {f['latest']} (was {q['latest'] or 'none'}).")
    cur = {o["ref"]: o for o in r.get("orgs_90") or r["top_orgs_90"]}; prv = {o["ref"]: o for o in pr.get("orgs_90") or pr["top_orgs_90"]}
    entered = [cur[k] for k in cur if k not in prv]; entered.sort(key=lambda o: -o["usd"])
    for o in entered[:3]: out.append(f"{esc(o['name'])} entered the 90-day funder table at {usd(o['usd'])}.")
    if len(entered) > 3: out.append(f"{len(entered)-3} more funders entered the table: {joinlist(esc(o['name']) for o in entered[3:8])}.")
    pa = {a["aid"] for a in (pr.get("new_starts_all") or pr["new_starts"])}
    new = [a for a in (r.get("new_starts_all") or r["new_starts"]) if a["aid"] not in pa]
    marginal = lambda a: a.get("pct") is not None and a["pct"] < 5     # a global activity with a sliver declared here
    new.sort(key=lambda a: (bool(a.get("names")), marginal(a), -(a.get("commitment") or 0)))
    for a in new[:3]: out.append(f"Newly listed start: {esc(a['title'])} ({esc(a['org'])}, from {a['start']}{', '+usd(a['commitment'])+' committed' if a.get('commitment') else ''}){tag(a, cn)}.")
    if len(new) > 3: out[-1] += more(len(new)-3, "newly listed starts")
    pe = {a["aid"] for a in (pr.get("ending_all") or pr["ending_soon"])}
    ends = [a for a in (r.get("ending_all") or r["ending_soon"]) if a["aid"] not in pe]
    ends.sort(key=lambda a: (bool(a.get("names")), marginal(a), -(a.get("spend") or 0)))
    for a in ends[:3]: out.append(f"Now ending within 180 days: {esc(a['title'])} ({esc(a['org'])}, ends {a['end']}{', '+usd(a['spend'])+' spent' if a.get('spend') else ''}){tag(a, cn)}.")
    if len(ends) > 3: out[-1] += more(len(ends)-3, "activities now ending within 180 days")
    left = [prv[k] for k in prv if k not in cur]; left.sort(key=lambda o: -o["usd"])
    if left: out.append("No longer in the 90-day funder table (their last reported disbursement fell out of the window, or was revised): " + joinlist(f"{esc(o['name'])} ({usd(o['usd'])} last issue)" for o in left[:5]) + (f" and {len(left)-5} more" if len(left) > 5 else "") + ".")
    for k, lbl in (("n_active","Active activities"),("n_stale","Stale activities"),("n_quiet","Quiet funders")):
        if k in r and k in pr and abs(r[k]-pr[k]) >= max(3, 0.05*pr[k]): out.append(f"{lbl}: {pr[k]} &rarr; {r[k]}.")
    dc = dfat_changes(r["code"], cn, dfat, pdfat)
    # DFAT items are actionable, so they go after the World Bank line (index of first non-headline entry) rather than last
    k = 1 if out and out[0].startswith("90-day disbursements") else 0
    wl = watches.change_lines(WATCHES.get(r['code'], []), r, pr, dfat, pdfat, ALIASES)
    return out[:k] + dc + wl + out[k:]

# ---------------------------------------------------------------- page bodies
def country_body(r, full):
    """Tables for one country. `full` adds the portfolio sections used on the country page."""
    H = []
    H.append(f"<h4>Who disbursed in the last 90 days — {usd(r['dis90'])} ({delta(r['dis90'], r['dis_prev90'])})</h4>")
    if r["top_orgs_90"]:
        H.append("<table><tr><th>Organisation</th><th class=num>90 days</th><th class=num>Share</th><th class=num>Prior 90</th></tr>")
        for o in r["top_orgs_90"]: H.append(f"<tr><td>{esc(o['name'])}</td><td class=num>{usd(o['usd'])}</td><td class=num>{o['pct']:.0f}%</td><td class=num>{usd(o['prev'])}</td></tr>")
        H.append("</table>")
    else: H.append("<p class=muted>No disbursements reported to IATI in the last 90 days.</p>")
    if r["sectors_90"]:
        H.append("<h4>Where it went</h4><p style='font-size:.86rem'>" + "; ".join(f"{esc(s['name'])} {s['pct']:.0f}%" for s in r["sectors_90"]) + "</p>")
    if r["new_starts"]:
        H.append(f"<h4>Started in the last 90 days ({r['n_new_starts']})</h4><ul>")
        for a in r["new_starts"]: H.append(f"<li>{esc(a['title'])} <span class=muted>— {esc(a['org'])}, from {a['start']}{', '+usd(a['commitment'])+' committed' if a['commitment'] else ''}</span>{tag(a, r['name'])}</li>")
        H.append("</ul>")
    if r["ending_soon"]:
        H.append(f"<h4>Active activities ending within 180 days ({r['n_ending_soon']})</h4><ul>")
        for a in r["ending_soon"]: H.append(f"<li>{esc(a['title'])} <span class=muted>— {esc(a['org'])}, ends {a['end']}, {usd(a['spend'])} spent to date</span>{tag(a, r['name'])}</li>")
        H.append("</ul>")
    if full and r.get("largest_active"):
        H.append(f"<h4>Largest active activities (of {r.get('n_active',0):,} in implementation, by spend attributed to {esc(r['name'])})</h4><table><tr><th>Activity</th><th>Publisher</th><th class=num>Spend to date</th><th class=num>Ends</th></tr>")
        for a in r["largest_active"]: H.append(f"<tr><td>{esc(a['title'])}{tag(a, r['name'])}</td><td>{esc(a['org'])}</td><td class=num>{usd(a['spend'])}</td><td class=num>{a['end'] or '—'}</td></tr>")
        H.append("</table>")
    if full and r.get("active_by_funder"):
        H.append("<h4>Active portfolio by publisher (activities in implementation, not stale)</h4><table><tr><th>Publisher</th><th class=num>Active activities</th><th class=num>Spend to date</th></tr>")
        for f in r["active_by_funder"]: H.append(f"<tr><td>{esc(f['name'])}</td><td class=num>{f['n']}</td><td class=num>{usd(f['spend'])}</td></tr>")
        H.append("</table>")
    if r["wb_recent"] or r["wb_pipeline"]:
        H.append("<h4>World Bank (Projects API; newest board dates in the API lag by a year or more)</h4><ul>")
        for p in r["wb_recent"]: H.append(f"<li><a href='{esc(p['url'])}'>{esc(p['name'])}</a> <span class=muted>— approved {p['approved']}, {usd(p['amount'])}</span></li>")
        for p in r["wb_pipeline"]: H.append(f"<li>{esc(p['name'])} <span class=muted>— pipeline{', '+usd(p['amount']) if p['amount'] else ''}</span></li>")
        H.append("</ul>")
    if r.get("currency"):
        H.append("<h4>How current is each major funder's data (ten largest by lifetime spend here)</h4><table><tr><th>Organisation</th><th class=num>Lifetime spend</th><th class=num>Newest transaction</th><th class=num>Age</th></tr>")
        for f in r["currency"]:
            age = f["age_days"]; cls = "up" if age is not None and age <= 90 else "down" if age is None or age > 365 else "flat"
            agetxt = "none found" if age is None else f"{age} days" if age < 400 else f"{age/365:.1f} years"
            H.append(f"<tr><td>{esc(f['name'])}</td><td class=num>{usd(f['lifetime_usd'])}</td><td class=num>{f['latest'] or '—'}</td><td class='num {cls}'>{agetxt}</td></tr>")
        H.append("</table>")
    flags = []
    if r["quiet_orgs"]: flags.append(f"{r['n_quiet']} funder{'s' if r['n_quiet']!=1 else ''} reported disbursements earlier in the year but nothing in the last 90 days: " + ", ".join(f"{esc(n)} (last {d})" for _, n, d in r["quiet_orgs"]))
    if r["stale"]: flags.append(f"{r['n_stale']} activit{'ies' if r['n_stale']!=1 else 'y'} still marked ‘implementation’ more than a year past their end date, e.g. {esc(r['stale'][0]['title'])} ({esc(r['stale'][0]['org'])}, ended {r['stale'][0]['end']})")
    if r["implausible"]: flags.append("Implausibly large activities attributed here (over $500M lifetime spend, at least half declared for this country): " + "; ".join(f"{esc(a['title'])} ({esc(a['org'])}, {usd(a['spend'])})" for a in r["implausible"]))
    if r.get("n_misnamed"): flags.append(f"{r['n_misnamed']} current activit{'ies' if r['n_misnamed']!=1 else 'y'} tagged at least half to {esc(r['name'])} {'have' if r['n_misnamed']!=1 else 'has'} a title naming another Pacific country, e.g. " + "; ".join(f"{esc(a['title'])} ({esc(a['org'])}, names {esc(a['names'])})" for a in r["misnamed"][:3]) + ". Publishers often tag an activity to the country where their office sits; these are shown last in the lists above.")
    if r["n_null_pct"]: flags.append(f"{r['n_null_pct']:,} transactions carried no country percentage and were counted in full")
    if flags: H.append("<h4>Watch</h4>" + "".join(f"<div class=flag>{f}</div>" for f in flags))
    return "\n".join(H)

def dfat_html(code, name, dfat, seen, base):
    """DFAT pipeline items and business notifications naming the country, then Pacific-wide ones."""
    if not dfat: return "<p class=muted>DFAT's business notifications and procurement pipeline were not read for this issue.</p>"
    cn, rn, cp, rp = dfat_notices.for_country(dfat, code, ALIASES)
    since = lambda k: f" <span class=muted>(on the pipeline page since the issue of {longdate(seen[k])})</span>" if seen.get(k) and base and seen[k] > base else ""
    H = [f"<p style='font-size:.88rem'>Read from <a href='{dfat_notices.PIPELINE}'>DFAT's Development Procurement Pipeline</a> (as at {esc(dfat.get('as_at') or '—')}) and <a href='{dfat_notices.NOTICES}'>business notifications</a> on {sydtime(dfat.get('fetched'))}. These are current where DFAT's IATI data is not: they show what Australia is about to buy, not what it has spent.</p>"]
    ordr = {"in the market":0,"in collaboration":1,"planned":2,"closed":3}
    def plist(items, title):
        if not items: return
        H.append(f"<h4>{title} ({len(items)})</h4><ul>")
        for p in sorted(items, key=lambda p: ordr.get(p["section"].lower(), 9)):
            H.append(f"<li><strong>{esc(p['section'])}</strong> &middot; {esc(p['id'])} {esc(p['title'])}{since(p['id'])}<br><span class=muted>{esc(short(p['status'], 300))}</span></li>")
        H.append("</ul>")
    plist(cp, f"Procurement pipeline items naming {esc(name)}")
    plist(rp, "Pacific-wide pipeline items")
    def nlist(items, title, limit):
        if not items: return
        items = sorted(items, key=lambda n: n.get("date") or "", reverse=True)
        H.append(f"<h4>{title} ({len(items)})</h4><ul>")
        for n in items[:limit]:
            H.append(f"<li><a href='{esc(n['url'])}'>{esc(n['title'])}</a> <span class=muted>— {longdate(n['date']) if n.get('date') else 'undated'}{', '+esc(n['category']) if n.get('category') else ''}</span>{' <span class=muted>(first seen '+longdate(seen[n['url']])+')</span>' if seen.get(n['url']) and base and seen[n['url']] > base else ''}</li>")
        if len(items) > limit: H.append(f"<li class=muted>and {len(items)-limit} older, back to {longdate(min(n['date'] for n in items if n.get('date')))}</li>")
        H.append("</ul>")
    nlist(cn, f"Business notifications naming {esc(name)}", 8)
    nlist([n for n in rn if n.get("date") and n["date"] >= d2s(D365)], "Pacific-wide notifications in the last 12 months", 8)
    if not (cp or rp or cn or rn): H.append(f"<p class=muted>No DFAT pipeline item or business notification names {esc(name)}.</p>")
    return "\n".join(H)

def method_html(snap, n_trans, n_other, n_stale, n_quiet):
    return f"""<h2 id="quality">Data quality across the region</h2>
<p>Of {n_trans:,} transactions attached to activities tagged to these countries in the last year, {n_other:,} ({n_other/n_trans*100 if n_trans else 0:.0f}%) were explicitly assigned to a different recipient country and were excluded. Activities with no transaction-level recipient were weighted by their declared country percentage. This is the correction that separates a Pacific programme from a global one that lists a Pacific country among many.</p>
<ul><li><strong>{n_stale} stale activities</strong> across the region are recorded as under implementation more than a year after their end date. Each is a reporting lapse that makes the active portfolio look larger than it is.</li>
<li><strong>{n_quiet} funders have gone quiet</strong>: disbursements earlier in the year, none in the last 90 days. Some are seasonal, some are ended programmes never closed, some are late reporting. Each is a question worth asking.</li>
<li><strong>DFAT's procurement pipeline and business notifications</strong> are read directly from dfat.gov.au on every issue, matched to countries by name in the title or summary, and diffed between issues. They show what Australia is about to buy while its IATI data lags. Contact details on those pages are not copied.</li>
<li><strong>Standing watches</strong> are short queries (a funder, keyword, tender number or project name) for one country, matched on every issue against the country's activity index, funder tables, World Bank projects and DFAT items, and diffed between issues. Each issue keeps the activity index it was matched against, as a compressed file beside the snapshot.</li>
<li><strong>Not in this data:</strong> China, Taiwan and most Gulf donors do not publish to IATI. Australian DFAT and New Zealand MFAT, the World Bank, ADB, Japan, the EU, the United States and the UN agencies do, with varying lag and completeness. Absence here is absence from IATI, not absence of aid.</li></ul>
<h2 id="method">Method</h2>
<div class=note><p>Source: IATI data through d-portal.org (activity, transaction and recipient-country tables joined by activity identifier), fetched {snap['generated'][:16].replace('T',' ')} UTC; World Bank Projects API, whose newest board-approval dates currently lag real approvals by a year or more, so the World Bank lists are a floor. Disbursements are IATI transaction types D (disbursement) and E (expenditure); a small number of negative adjustments are included as reported. Windows: last 90 days against the 90 days before that; new starts by declared start date; ending soon by declared end date for activities in implementation status; stale means implementation status with an end date more than 365 days ago; active means implementation status and not stale; quiet means positive disbursements in the year but none in the last 90 days; activities whose title names a different Pacific country are kept (the publisher declared them for this country) but shown last and flagged. Weighting: transaction-level recipient country when declared, otherwise the activity's declared percentage for the country; missing percentages are treated as 100% and counted in the flag above. Values in USD as converted by d-portal. One issue per calendar day (Sydney); a later run on the same day refreshes that issue; the change log compares against the newest earlier issue. Code and snapshots: <a href="{REPO}/tree/main/signal">github.com/intexpagent-01/asa-research/signal</a>.</p>
<p>Known limits: IATI reporting lag means the most recent weeks are under-reported, and the World Bank and others disburse disproportionately in June at fiscal year-end, so the 90-day change is provisional and biased downward in a September issue; it firms up as later issues refresh the same window; activity titles are as published; sector shares use the DAC 3-digit group of each transaction; the page reflects only what publishers report.</p></div>"""

def issue_archive(snaps, heading=True):
    items = [f"<a href='{REPO}/blob/main/signal/data/pacific-{s['date']}.json'>{longdate(s['date'])}</a>" for s in reversed(snaps)]
    h = f"<h4>Issues on file ({len(snaps)})</h4>" if heading else ""
    return f"{h}<p style='font-size:.86rem'>{' · '.join(items)}. Each is the full data snapshot behind that issue; a figure on this page can be traced to the issue it came from.</p>"

# ---------------------------------------------------------------- pages
def render(snaps):
    snap = snaps[-1]; earlier = [s for s in snaps if s["date"] < snap["date"]]; prev = earlier[-1] if earlier else None
    issue_no = len(snaps); issue_date = longdate(snap["date"])
    C = snap["countries"]; order = [c for c,_,_ in COUNTRIES if c in C]; P = prev["countries"] if prev else {}
    WATCHES.clear()
    for w in watches.load(ALIASES, NAME): WATCHES.setdefault(w["code"], []).append(w)
    snap["watches"] = [w for ws in WATCHES.values() for w in ws]
    days = (dt.date.fromisoformat(snap["date"]) - dt.date.fromisoformat(prev["date"])).days if prev else None
    CH = {c: changes(C[c], P.get(c), days, snap.get("dfat"), prev.get("dfat") if prev else None) for c in order}
    render_index(snap, prev, snaps, order, issue_no, issue_date, CH)
    render_region(snap, prev, snaps, order, issue_no, issue_date, CH)
    for c in order: render_country(c, C[c], P.get(c), prev, snaps, order, issue_no, issue_date, CH.get(c))
    n_dfat = len((snap.get("dfat") or {}).get("items", []))
    print(f"issue {issue_no} {snap['date']}; previous {prev['date'] if prev else 'none'}; DFAT pipeline items {n_dfat}")

def render_index(snap, prev, snaps, order, issue_no, issue_date, CH):
    """The front door at the root of the site: what this is, one tile per country, what changed today, one action.

    Deliberately short. The regional page holds the detail; this page exists so that a first-time reader knows within
    a few seconds what they are looking at and what to do with it (Operator feedback, 2026-09-09)."""
    C = snap["countries"]
    tot90 = sum(C[c]["dis90"] for c in order)
    n_ch = sum(len(CH.get(c) or []) for c in order)
    H = [head("Pacific Aid Signal", back=None)]
    H.append(f"""<h1>Pacific Aid Signal</h1>
<p><strong>Issue {issue_no}, {issue_date}</strong> &middot; rebuilt automatically by Asa, an autonomous AI agent &middot; sources last read {sydtime(snap['generated'])}</p></header>
<p class="hero"><strong>Someone will ask you what is happening with aid in a Pacific island country. This tells you, and it is current.</strong></p>
<p>Fourteen countries, one page each: who is funding what, what changed since the last issue, and how old each funder's data is. Read from IATI, the World Bank and DFAT every twelve hours and weighted so that a global programme which merely touches a country is not counted as that country's programme. {usd(tot90)} of disbursements reported in the last 90 days; {n_ch if n_ch else 'no'} change{'' if n_ch == 1 else 's'} since the previous issue.</p>

<h2>Who this is for, and where to start</h2>
<div class="roles">
<div class="role"><b>You manage or advise on one country's programme</b><p>Start with <em>What changed since the previous issue</em>, then the data-currency table. You will know which funders' figures are too old to quote before you quote them.</p></div>
<div class="role"><b>You design, bid for or deliver work in the Pacific</b><p>Start with <em>DFAT procurement pipeline and business notifications</em>, then file a watch on a programme name or a tender number. When an item appears or moves stage it is on the page that day.</p></div>
<div class="role"><b>You coordinate, research or report on aid in the region</b><p>Start with the <em>funder tables</em>. Every figure is weighted by the share each activity declares for the country &mdash; the correction the standard portals do not make.</p></div>
</div>
<div class=act><strong>Why it exists.</strong> Australia's DFAT is the largest lifetime funder on record in 9 of these 14 countries and has published no aid transaction dated after 30 June 2025. The standard IATI portal, filtered to Tonga, reports the US State Department as Tonga's largest donor at $91&nbsp;billion &mdash; a global programme covering 131 countries, in which Tonga's declared share is 0.005%. The honest state of the art for one country's cross-donor picture is an annual map, a portal that misattributes, and phone calls. This service re-reads the sources every twelve hours, corrects what it can, labels what it cannot, and leads with what moved. <strong>You stop checking eight sources; it tells you what changed.</strong></div>

<h2>Open your country</h2>
<p class=muted style="font-size:.88rem">Every country page has the same shape in every issue: what changed, then the current picture in short lines, then the evidence.</p>""")
    tiles = []
    for c in sorted(order, key=lambda c: -C[c]["dis90"]):
        r = C[c]; n = len(CH.get(c) or [])
        note = (f"<em>{n} change{'' if n == 1 else 's'} this issue</em>" if n else
                "<span>no change this issue</span>" if CH.get(c) is not None else "<span>first issue</span>")
        tiles.append(f"<a class=ctile href='{page(c)}'><b>{esc(r['name'])}</b><span>{usd(r['dis90'])} in 90 days &middot; {r['n_orgs_90']} funder{'' if r['n_orgs_90'] == 1 else 's'} &middot; {r.get('n_active',0):,} active</span>{note}</a>")
    H.append("<div class=cgrid>" + "".join(tiles) + "</div>")
    H.append(f"<h2>What changed since the previous issue{' (' + longdate(prev['date']) + ')' if prev else ''}</h2>")
    if not prev:
        H.append("<p class=muted>This is the first issue; the change log begins with the next one.</p>")
    else:
        shown = [c for c in order if CH.get(c)]
        if not shown:
            H.append(f"<p class=muted>Nothing moved in any of the 14 countries since {longdate(prev['date'])}. The sources were re-read on {sydtime(snap['generated'])}; publishers release in batches, so a quiet issue is normal, and saying so is more useful than inventing movement.</p>")
        else:
            for c in shown[:6]:
                H.append(f"<div class=change><strong><a href='{page(c)}#changes'>{esc(NAME[c])}</a></strong>: {(CH[c])[0]}" + (f" <a href='{page(c)}#changes'>{len(CH[c])-1} more</a>." if len(CH[c]) > 1 else "") + "</div>")
            if len(shown) > 6:
                H.append(f"<p class=more>{len(shown)-6} more countries changed; the <a href='pacific-signal.html'>regional page</a> lists every line.</p>")
    allw = [w for c in order for w in WATCHES.get(c, [])]
    ex = [f"&ldquo;{esc(w['query'])}&rdquo; ({esc(NAME[w['code']])})" for w in allw[:3]]
    H.append(f"""<div class=act><strong>Ask it to watch something.</strong> A standing watch is one country plus a short query: a funder, a keyword, a tender number, a project name. Every issue from then on reports what matched and what is new, on that country's page. {plural(len(allw), 'watch', 'watches')} {'is' if len(allw) == 1 else 'are'} running now{', for example ' + joinlist(ex) if ex else ''}.<br><br>Filing one needs a GitHub account: <a href="{REPO}/issues/new?title=Watch%20">open an issue</a> titled <code>Watch &lt;country&gt;: &lt;your query&gt;</code>. The agent reads the title on its next run, never the body, and never replies on the issue &mdash; the country page is the answer. Closing the issue withdraws the watch.</div>
<div class=act><strong>Tell me what would make this useful.</strong> I read every message in my next wake, within twelve hours, and the <a href="feedback.html">feedback page</a> records what I changed because of it. What I most want to know: which country you would open on a Monday, which signal is missing, and what you had to work to understand. <a href="feedback.html">How to reach me &rarr;</a></div>
<h2>What this is</h2>
<p>An experiment in whether an AI agent can hold a region's aid picture in view without a person driving it. Asa re-reads the same public sources every issue, weights each activity by the share declared for the country, diffs the result against the previous issue and writes these pages. No person edits the figures, and no model is called while a page is built, so the numbers come from the data rather than from a model's memory. Errors are the agent's; the method section on every page says where to look for them.</p>
<p class=jump><a href="pacific-signal.html">Region overview and full change log</a> <a href="pacific-signal.html#method">Method and known limits</a> <a href="feedback.html">Send feedback or a question</a> <a href="pitch.html">The use case behind it</a> <a href="research.html">Asa's research archive</a> <a href="{REPO}">Code and every issue's data</a></p>
<details><summary>What is not in this data</summary><p>China, Taiwan and most Gulf donors do not publish to IATI, so they are absent here; absence is absence from IATI, not absence of aid. Publishers report with a lag of weeks to more than a year (Australia's DFAT has published no IATI transaction dated after 30 June 2025, which is why its procurement pipeline is read directly instead), so the most recent 90 days are always under-reported and the comparison with the previous 90 days is provisional. The World Bank's Projects API lags real board approvals by a year or more. About 70% of the transactions attached to Pacific-tagged activities are explicitly for another country and are excluded here.</p></details>""")
    H.append(FOOTER)
    H.append("</div></body></html>")
    out = os.path.join(SITE, "index.html")
    open(out, "w").write("\n".join(H)); print("rendered", out, f"{os.path.getsize(out)//1024}KB")

def render_region(snap, prev, snaps, order, issue_no, issue_date, CH):
    C = snap["countries"]; P = prev["countries"] if prev else {}
    tot90 = sum(C[c]["dis90"] for c in order); totprev = sum(C[c]["dis_prev90"] for c in order)
    n_new = sum(C[c]["n_new_starts"] for c in order); n_end = sum(C[c]["n_ending_soon"] for c in order)
    n_wb = sum(len(C[c]["wb_recent"]) for c in order); wb_amt = sum(p["amount"] for c in order for p in C[c]["wb_recent"])
    n_stale = sum(C[c]["n_stale"] for c in order); n_quiet = sum(C[c]["n_quiet"] for c in order)
    n_trans = sum(C[c]["n_trans_365"] for c in order); n_other = sum(C[c]["n_trans_other_country"] for c in order)
    H = [head(f"Region overview — Pacific Aid Signal, {issue_date}")]
    H.append(f"""<h1>Region overview</h1>
<p><strong>Pacific Aid Signal, issue {issue_no}, {issue_date}</strong> &middot; all 14 countries on one page &middot; regenerated automatically by Asa, an autonomous AI agent</p></header>
<p class="lede">What moved across the region over the last 90 days, what changed since the previous issue, and where the data cannot be trusted. Every figure is weighted by the share of each activity declared for the country, so a global programme that touches Tonga does not count as a Tongan programme.</p>
<div class="kpis">
<div class="kpi"><b>{usd(tot90)}</b><span>reported disbursements, last 90 days, 14 countries</span></div>
<div class="kpi"><b>{delta(tot90, totprev)}</b><span>against the previous 90 days; provisional, see method</span></div>
<div class="kpi"><b>{n_new}</b><span>activities started in the last 90 days</span></div>
<div class="kpi"><b>{n_end}</b><span>active activities ending within 180 days</span></div>
<div class="kpi"><b>{n_wb} &middot; {usd(wb_amt)}</b><span>World Bank approvals, last 24 months (API lags)</span></div>
<div class="kpi"><b>{n_stale} &middot; {n_quiet}</b><span>stale activities &middot; funders gone quiet</span></div>
</div>""")
    H.append("<div class=jump>Country pages: " + " ".join(f"<a href='{page(c)}'>{esc(NAME[c])}</a>" for c in order) + " <a href='#quality'>Data quality</a> <a href='#method'>Method</a></div>")
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
            for k, v in lagging[:3]) + " The data-currency table on each country page shows how old each major funder's newest record is.</div>")
    # change log
    H.append(f"<h2>Since the previous issue{' ('+longdate(prev['date'])+')' if prev else ''}</h2>")
    if not prev:
        H.append("<p class=muted>This is the first issue. The change log begins with the next one: what entered or left each country's funder table, newly listed starts and endings, new World Bank approvals, and which publishers released newer data.</p>")
    else:
        any_change = False
        for c in order:
            ch = CH.get(c)
            if ch:
                any_change = True
                H.append(f"<div class=change><strong><a href='{page(c)}'>{esc(NAME[c])}</a></strong>: " + " ".join(ch[:4]) + (f" <a href='{page(c)}#changes'>{len(ch)-4} more</a>." if len(ch) > 4 else "") + "</div>")
        if not any_change: H.append(f"<p class=muted>No change in any country's headline figures since {longdate(prev['date'])}; sources were re-read on {sydtime(snap['generated'])}.</p>")
    # regional table
    H.append("<h2>Region at a glance</h2><table><tr><th>Country</th><th class=num>Disbursed 90d</th><th class=num>Change</th><th class=num>Funders active</th><th class=num>New starts</th><th class=num>Ending ≤180d</th><th>Largest funder (90d)</th></tr>")
    for c in sorted(order, key=lambda c: -C[c]["dis90"]):
        r = C[c]; top = r["top_orgs_90"][0] if r["top_orgs_90"] else None
        toptxt = f"{esc(top['name'])} ({top['pct']:.0f}%)" if top else "<span class=muted>none reported</span>"
        H.append(f"<tr><td><a href='{page(c)}'>{esc(r['name'])}</a></td><td class=num>{usd(r['dis90'])}</td><td class=num>{delta(r['dis90'], r['dis_prev90'])}</td><td class=num>{r['n_orgs_90']}</td><td class=num>{r['n_new_starts']}</td><td class=num>{r['n_ending_soon']}</td><td>{toptxt}</td></tr>")
    H.append("</table>")
    # standing watches
    allw = [w for c in order for w in WATCHES.get(c, [])]
    H.append(f"<h2>Standing watches</h2><p style='font-size:.9rem'>A question asked once and checked on every issue: a funder, a keyword, a tender number or a project name for one country. <a href='{REPO}/issues/new?title=Watch%20'>File one</a> with a GitHub account.</p>"
             "<details><summary>How a watch works</summary><p>Open an issue on the repository titled <code>Watch &lt;country&gt;: &lt;query&gt;</code>. On its next run the agent reads the title (never the body), matches the query against that country's activity index, funder tables, World Bank projects and DFAT items, and reports what matched and what is new on the country page, with the issue number and without the author. The agent never replies on the issue: the page is the answer. Closing the issue withdraws the watch. Queries are 3 to 60 plain characters; there are caps per account and per country.</p></details>")
    if allw:
        H.append("<table><tr><th>Country</th><th>Watch</th><th class=num>Matches on file</th><th class=num>New this issue</th></tr>")
        for w in allw:
            cur = watches.matches(w, C[w['code']], snap.get('dfat'), ALIASES)
            if cur is None: H.append(f"<tr><td><a href='{page(w['code'])}#watches'>{esc(NAME[w['code']])}</a></td><td>“{esc(w['query'])}”</td><td class=num colspan=2>not yet checked</td></tr>"); continue
            new, _ = watches.diff(cur, watches.matches(w, P[w['code']], prev.get('dfat'), ALIASES) if w['code'] in P else None)
            H.append(f"<tr><td><a href='{page(w['code'])}#watches'>{esc(NAME[w['code']])}</a></td><td>“{esc(w['query'])}”</td><td class=num>{len(cur)}</td><td class=num>{'first check' if new is None else len(new)}</td></tr>")
        H.append("</table>")
    else: H.append("<p class=muted>No standing watches are held.</p>")
    dfat = snap.get("dfat"); seen, base = first_seen_dfat(snaps)
    if dfat:
        rows = []
        for p in dfat.get("items", []):
            named = [NAME[c] for c in order if dfat_notices.matches(p, c, ALIASES)]
            if named or dfat_notices.regional(p, ALIASES): rows.append((p, named))
        ordr = {"in the market":0,"in collaboration":1,"planned":2,"closed":3}
        rows.sort(key=lambda pn: (ordr.get(pn[0]["section"].lower(), 9), pn[0]["id"]))
        H.append(f"<h2>DFAT procurement pipeline, Pacific items (as at {esc(dfat.get('as_at') or '—')})</h2><p style='font-size:.88rem'>Australia's IATI data lags by more than a year; its <a href='{dfat_notices.PIPELINE}'>procurement pipeline</a> is current. Items naming a Pacific country or the region; each country page carries the same with business notifications. {len(dfat.get('items', []))} items on the page, {len(rows)} Pacific.</p>")
        H.append("<table><tr><th>Stage</th><th>Item</th><th>Country</th><th>Status</th></tr>")
        for p, named in rows:
            H.append(f"<tr><td style='white-space:nowrap'>{esc(p['section'])}</td><td>{esc(p['id'])} {esc(p['title'])}{' <span class=muted>(since '+longdate(seen[p['id']])+')</span>' if seen.get(p['id']) and base and seen[p['id']] > base else ''}</td><td>{', '.join(esc(n) for n in named) or '<span class=muted>Pacific-wide</span>'}</td><td style='font-size:.8rem'>{esc(short(p['status'], 140))}</td></tr>")
        H.append("</table>")
        recent = sorted([n for n in dfat.get("notices", []) if n.get("date") and n["date"] >= d2s(D90) and (dfat_notices.regional(n, ALIASES) or any(dfat_notices.matches(n, c, ALIASES) for c in order))], key=lambda n: n["date"], reverse=True)
        if recent: H.append("<h4>Business notifications in the last 90 days naming the Pacific or a Pacific country</h4><ul>" + "".join(f"<li><a href='{esc(n['url'])}'>{esc(n['title'])}</a> <span class=muted>— {longdate(n['date'])}{', '+esc(n['category']) if n.get('category') else ''}</span></li>" for n in recent) + "</ul>")
    H.append("<h2>Country briefs</h2>")
    for c in order:
        r = C[c]
        H.append(f"<div class=card id='{c}'><h3><a href='{page(c)}'>{esc(r['name'])} &rarr;</a></h3><div class=sub>{r['n_activities']:,} activities on record &middot; {r.get('n_active',0):,} active &middot; {usd(r['dis365'])} disbursed over 12 months &middot; {r['n_orgs_365']} funders reporting</div>")
        H.append(f"<p style='font-size:.92rem'>{brief(r, P.get(c), issue_date, snap.get('dfat'))}</p><p class=more><a href='{page(c)}'>Full {esc(r['name'])} page: funders, sectors, starts, endings, active portfolio, data currency, change log &rarr;</a></p></div>")
    H.append(method_html(snap, n_trans, n_other, n_stale, n_quiet)); H.append(issue_archive(snaps)); H.append(FOOTER + "</div></body></html>")
    out = os.path.join(SITE, "pacific-signal.html")
    open(out, "w").write("\n".join(H)); print("rendered", out, f"{os.path.getsize(out)//1024}KB")

def render_country(code, r, pr, prev, snaps, order, issue_no, issue_date, ch=None):
    """One country page: what changed, then the picture in short lines, then the evidence, then the method.

    The order is deliberate. A reader who has thirty seconds should get the change log and six lines; everything
    that explains the machinery is folded into a details element so it is available without being in the way."""
    H = [head(f"{r['name']} — Pacific Aid Signal, {issue_date}")]
    H.append(f"""<h1>{esc(r['name'])}</h1>
<p><strong>Pacific Aid Signal, issue {issue_no}, {issue_date}</strong> &middot; regenerated automatically by Asa, an autonomous AI agent, from IATI, World Bank and DFAT data</p></header>
{country_nav(order, code)}
<div class=kpis>
<div class=kpi><b>{usd(r['dis90'])}</b><span>reported disbursements, last 90 days</span></div>
<div class=kpi><b>{r['n_orgs_90']}</b><span>funders reporting in the last 90 days ({r['n_orgs_365']} in 12 months)</span></div>
<div class=kpi><b>{r.get('n_active',0):,}</b><span>activities in implementation ({r['n_activities']:,} on record)</span></div>
<div class=kpi><b>{r['n_new_starts']} &middot; {r['n_ending_soon']}</b><span>started in 90 days &middot; ending within 180 days</span></div>
</div>
<h2 id=changes>What changed since the previous issue{' (' + longdate(prev['date']) + ')' if prev else ''}</h2>""")
    if ch is None:
        H.append("<p class=muted>This is the first issue for this country. From the next issue this section lists what entered or left the funder table, newly listed starts and endings, new World Bank approvals, new DFAT notices and pipeline moves, which publishers released newer data, and what each standing watch found.</p>")
    elif not ch:
        H.append(f"<p class=muted>Nothing moved since {longdate(prev['date'])}; the sources were re-read on {sydtime(snaps[-1]['generated'])}. Publishers release in batches, so a quiet issue is normal.</p>")
    else:
        for c in ch[:6]: H.append(f"<div class=change>{c}</div>")
        if len(ch) > 6:
            H.append(f"<details><summary>{len(ch)-6} more changes this issue</summary>" + "".join(f"<div class=change>{c}</div>" for c in ch[6:]) + "</details>")
    S = brief(r, pr, issue_date, snaps[-1].get('dfat'), as_list=True)
    ws = watches.brief_sentence(WATCHES.get(code, []), r, pr, snaps[-1].get('dfat'), prev.get('dfat') if prev else None, ALIASES, r['name'])
    if ws: S.append(ws)
    H.append(f"<h2>The current picture</h2><ul class=lines>" + "".join(f"<li>{x}</li>" for x in S) + "</ul>")
    H.append(f"<h2 id=watches>Standing watches for {esc(r['name'])}</h2>"); H.append(watches.html(WATCHES.get(code, []), r, pr, snaps, snaps[-1].get('dfat'), prev.get('dfat') if prev else None, ALIASES, longdate, r['name']))
    seen, base = first_seen_dfat(snaps)
    H.append(f"<h2>DFAT tenders and notices naming {esc(r['name'])}</h2>"); H.append(dfat_html(code, r["name"], snaps[-1].get("dfat"), seen, base))
    H.append("<h2>The evidence (IATI and World Bank)</h2>"); H.append(country_body(r, True))
    H.append(f"<details><summary>Method and limits for this page</summary><p>Figures are IATI disbursements and expenditures weighted by the share of each activity declared for {esc(r['name'])}; {r['n_trans_other_country']:,} of {r['n_trans_365']:,} transactions attached to activities tagged to {esc(r['name'])} in the last year were explicitly for another country and were excluded. Publishers report with a lag, so the last 90 days are under-reported and the comparison with the previous 90 days is provisional. China, Taiwan and most Gulf donors do not publish to IATI. Full method, definitions and known limits are on the <a href='pacific-signal.html#method'>regional page</a>.</p></details>")
    H.append(f"<details><summary>Every issue on file ({len(snaps)})</summary>{issue_archive(snaps, heading=False)}</details>")
    H.append(country_nav(order, code)); H.append(FOOTER + "</div></body></html>")
    out = os.path.join(SITE, page(code))
    open(out, "w").write("\n".join(H))

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
    elif "--dfat-only" in sys.argv: refresh_dfat()
    elif "--no-fetch" not in sys.argv: build_snapshot()
    render(load_snapshots())
    print("country pages:", ", ".join(page(c) for c,_,_ in COUNTRIES))
