#!/usr/bin/env python3
"""Donor concentration in IATI data, with and without recipient-country weighting.

d-portal's act table gives each activity's TOTAL spend. Joining the country table
gives the activity's declared percentage for the country. The unweighted method
(used in the Wake 18 analysis) attributes an activity's full spend to every
country it is tagged with; the weighted method multiplies by country_percent/100.

Usage: python3 donor_concentration_weighted.py OUTFILE CODE=Name [CODE=Name ...]
"""
import json, sys, urllib.request
from collections import defaultdict

DPORTAL = "https://d-portal.org/q.json"

def fetch(country_code):
    url = (f"{DPORTAL}?from=act,country&limit=50000&country_code={country_code}"
           f"&select=aid,reporting,reporting_ref,spend,commitment,status_code,country_percent")
    req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.4"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8")).get("rows", [])

def hhi(vals):
    t = sum(vals); return sum((v / t) ** 2 for v in vals) if t else 0

def gini(values):
    n = len(values)
    if n < 2: return 1.0
    s = sorted(values); total = sum(s)
    if total == 0: return 0.0
    return sum((2 * (i + 1) - n - 1) * s[i] for i in range(n)) / (n * total)

def summarize(by_org):
    orgs = {k: v for k, v in by_org.items() if v["spend"] > 0}
    total = sum(v["spend"] for v in orgs.values())
    ranked = sorted(orgs.items(), key=lambda kv: -kv[1]["spend"])
    cum = 0; t50 = t80 = 0
    for i, (_, v) in enumerate(ranked):
        cum += v["spend"] / total if total else 0
        if not t50 and cum >= 0.5: t50 = i + 1
        if not t80 and cum >= 0.8: t80 = i + 1
    tiny = sum(1 for _, v in ranked if total and v["spend"] / total < 0.001)
    return {"total_spend": total, "n_orgs": len(orgs), "hhi": hhi([v["spend"] for v in orgs.values()]),
            "gini": gini([v["spend"] for v in orgs.values()]), "top_50": t50, "top_80": t80,
            "tiny_orgs": tiny,
            "top_15": [{"ref": k, "name": v["name"], "spend": v["spend"], "pct": v["spend"] / total * 100 if total else 0,
                        "count": v["count"]} for k, v in ranked[:15]]}

def analyze(code, name):
    rows = fetch(code)
    raw = defaultdict(lambda: {"spend": 0.0, "count": 0, "name": ""})
    wtd = defaultdict(lambda: {"spend": 0.0, "count": 0, "name": ""})
    n_multi = 0; spend_from_elsewhere = 0.0; n_null = 0
    for r in rows:
        s = r.get("spend") or 0
        p = r.get("country_percent")
        if p is None: p = 100.0; n_null += 1
        ref = r.get("reporting_ref") or "Unknown"; org = r.get("reporting") or ref
        for d in (raw[ref], wtd[ref]): d["name"] = org; d["count"] += 1
        raw[ref]["spend"] += s
        wtd[ref]["spend"] += s * p / 100
        if p < 100: n_multi += 1; spend_from_elsewhere += s * (1 - p / 100)
    R, W = summarize(raw), summarize(wtd)
    out = {"code": code, "name": name, "n_activities": len(rows), "n_multi_country": n_multi,
           "n_null_percent": n_null, "raw": R, "weighted": W,
           "share_attributed_from_elsewhere": spend_from_elsewhere / R["total_spend"] if R["total_spend"] else 0}
    print(f"\n== {name} ({code}): {len(rows)} acts, {n_multi} multi-country ({n_multi/len(rows)*100:.0f}%), null pct {n_null}")
    print(f"   raw total ${R['total_spend']/1e6:,.0f}M -> weighted ${W['total_spend']/1e6:,.0f}M "
          f"({out['share_attributed_from_elsewhere']*100:.1f}% of raw spend belongs to other countries)")
    for label, S in (("RAW", R), ("WEIGHTED", W)):
        print(f"   {label:8s} orgs {S['n_orgs']:4d} HHI {S['hhi']:.3f} Gini {S['gini']:.3f} 50%in {S['top_50']} 80%in {S['top_80']} tiny {S['tiny_orgs']}")
        for i, d in enumerate(S["top_15"][:6]):
            print(f"      {i+1}. {d['name'][:42]:42s} ${d['spend']/1e6:9.1f}M {d['pct']:5.1f}%")
    return out

def main():
    outfile = sys.argv[1]
    countries = [a.split("=", 1) for a in sys.argv[2:]]
    results = {}
    for code, name in countries:
        try:
            results[code] = analyze(code, name)
        except Exception as e:
            print(f"!! {code} failed: {e}")
        sys.stdout.flush()
        json.dump(results, open(outfile, "w"), indent=1)
    print(f"\nSaved {outfile}")

if __name__ == "__main__":
    main()
