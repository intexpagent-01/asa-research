#!/usr/bin/env python3
"""Analyze donor concentration and volatility in IATI disbursement data."""
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt

DPORTAL = "https://d-portal.org/q.json"

COUNTRIES = {
    "KE": "Kenya",
    "UG": "Uganda",
    "RW": "Rwanda",
    "TZ": "Tanzania",
    "ET": "Ethiopia",
}

def epoch_day_to_date(day_num):
    try:
        return datetime(1970, 1, 1) + timedelta(days=int(day_num))
    except (ValueError, TypeError):
        return None

def fetch_activities(country_code):
    url = (f"{DPORTAL}?from=act&limit=50000&country_code={country_code}"
           f"&select=reporting,reporting_ref,funder_ref,spend,commitment,day_start,day_end,status_code")
    req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.3"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("rows", [])
    except Exception as e:
        print(f"  Error fetching activities for {country_code}: {e}")
        return []

def herfindahl(shares):
    return sum(s ** 2 for s in shares)

def gini(values):
    n = len(values)
    if n < 2:
        return 1.0
    s = sorted(values)
    total = sum(s)
    if total == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * s[i] for i in range(n)) / (n * total)

def analyze_country(code, name):
    print(f"\n{'='*70}")
    print(f"  {name} ({code})")
    print(f"{'='*70}")

    rows = fetch_activities(code)
    print(f"  {len(rows)} activities total")

    by_org = defaultdict(lambda: {"spend": 0.0, "commitment": 0.0, "count": 0, "name": ""})
    by_org_year = defaultdict(lambda: defaultdict(float))
    by_year = defaultdict(float)
    total_spend = 0.0
    total_commitment = 0.0
    n_with_spend = 0

    for row in rows:
        spend = row.get("spend") or 0
        commit = row.get("commitment") or 0
        ref = row.get("reporting_ref") or "Unknown"
        org_name = row.get("reporting") or ref
        dt = epoch_day_to_date(row.get("day_start"))
        year = dt.year if dt else None

        by_org[ref]["spend"] += spend
        by_org[ref]["commitment"] += commit
        by_org[ref]["count"] += 1
        by_org[ref]["name"] = org_name

        if spend > 0:
            n_with_spend += 1
            total_spend += spend
            if year and 2015 <= year <= 2025:
                by_org_year[year][ref] += spend
                by_year[year] += spend

        total_commitment += commit

    orgs_with_spend = {k: v for k, v in by_org.items() if v["spend"] > 0}
    sorted_orgs = sorted(orgs_with_spend.items(), key=lambda x: -x[1]["spend"])
    n_orgs = len(sorted_orgs)

    print(f"  {n_with_spend} activities with spend > 0, {n_orgs} reporting organizations")
    print(f"  Total spend: ${total_spend/1e6:.1f}M  |  Total commitment: ${total_commitment/1e6:.1f}M")

    if n_orgs == 0:
        return None

    shares = [v["spend"] / total_spend for _, v in sorted_orgs]
    hhi = herfindahl(shares)
    gini_val = gini([v["spend"] for _, v in sorted_orgs])

    cumulative = 0.0
    top_50_count = 0
    top_80_count = 0
    top_90_count = 0
    for _, v in sorted_orgs:
        cumulative += v["spend"] / total_spend
        if top_50_count == 0 and cumulative >= 0.50:
            top_50_count = sorted_orgs.index((_, v)) + 1
        if top_80_count == 0 and cumulative >= 0.80:
            top_80_count = sorted_orgs.index((_, v)) + 1
        if top_90_count == 0 and cumulative >= 0.90:
            top_90_count = sorted_orgs.index((_, v)) + 1

    # Redo properly
    cumulative = 0.0
    top_50_count = top_80_count = top_90_count = 0
    for i, (_, v) in enumerate(sorted_orgs):
        cumulative += v["spend"] / total_spend
        if top_50_count == 0 and cumulative >= 0.50:
            top_50_count = i + 1
        if top_80_count == 0 and cumulative >= 0.80:
            top_80_count = i + 1
        if top_90_count == 0 and cumulative >= 0.90:
            top_90_count = i + 1

    print(f"\n  Concentration metrics:")
    print(f"    HHI:  {hhi:.4f}  (1/{1/hhi:.1f} = effective number of orgs)")
    print(f"    Gini: {gini_val:.3f}")
    print(f"    50% of spend from top {top_50_count} of {n_orgs} orgs ({top_50_count/n_orgs*100:.1f}%)")
    print(f"    80% of spend from top {top_80_count} of {n_orgs} orgs ({top_80_count/n_orgs*100:.1f}%)")
    print(f"    90% of spend from top {top_90_count} of {n_orgs} orgs ({top_90_count/n_orgs*100:.1f}%)")

    print(f"\n  Top 15 donors by spend:")
    top_15 = []
    cum = 0.0
    for i, (ref, v) in enumerate(sorted_orgs[:15]):
        pct = v["spend"] / total_spend * 100
        cum += pct
        name_short = v["name"][:45]
        print(f"    {i+1:2d}. {name_short:45s} ${v['spend']/1e6:9.1f}M  ({pct:5.1f}%)  cum:{cum:5.1f}%  [{v['count']} acts]")
        top_15.append({"ref": ref, "name": v["name"], "spend": v["spend"], "pct": pct, "count": v["count"]})

    # Bottom: how many orgs have tiny spend?
    tiny = sum(1 for _, v in sorted_orgs if v["spend"] / total_spend < 0.001)
    tiny_total = sum(v["spend"] for _, v in sorted_orgs if v["spend"] / total_spend < 0.001)
    print(f"\n  {tiny} orgs ({tiny/n_orgs*100:.0f}%) contribute <0.1% each, totaling ${tiny_total/1e6:.1f}M ({tiny_total/total_spend*100:.1f}%)")

    # Year-by-year
    yearly_data = {}
    for year in sorted(by_org_year.keys()):
        yr_orgs = by_org_year[year]
        yr_total = sum(yr_orgs.values())
        if yr_total == 0:
            continue
        yr_sorted = sorted(yr_orgs.values(), reverse=True)
        yr_shares = [v / yr_total for v in yr_sorted]
        yr_hhi = herfindahl(yr_shares)
        yr_gini = gini(list(yr_orgs.values()))
        n_yr = len(yr_orgs)

        cum = 0.0
        t50 = 0
        for ii, v in enumerate(yr_sorted):
            cum += v / yr_total
            if t50 == 0 and cum >= 0.50:
                t50 = ii + 1

        yearly_data[year] = {
            "hhi": yr_hhi, "gini": yr_gini, "n_orgs": n_yr,
            "total": yr_total, "top50": t50,
        }

    if yearly_data:
        print(f"\n  Year-by-year concentration (2015-2025):")
        print(f"  {'Year':>6} {'HHI':>8} {'Gini':>8} {'Orgs':>6} {'50% in':>7} {'Spend $M':>10}")
        for year in sorted(yearly_data.keys()):
            d = yearly_data[year]
            print(f"  {year:>6} {d['hhi']:>8.4f} {d['gini']:>8.3f} {d['n_orgs']:>6} {d['top50']:>7} {d['total']/1e6:>10.1f}")

    # Volatility
    years = sorted(by_year.keys())
    yoy_changes = {}
    for i in range(1, len(years)):
        if years[i] == years[i-1] + 1 and by_year[years[i-1]] > 0:
            change = (by_year[years[i]] - by_year[years[i-1]]) / by_year[years[i-1]] * 100
            yoy_changes[years[i]] = change

    if yoy_changes:
        changes = list(yoy_changes.values())
        mean_abs = sum(abs(c) for c in changes) / len(changes)
        cv = (sqrt(sum((by_year[y] - sum(by_year.values())/len(by_year))**2 for y in by_year) / len(by_year))
              / (sum(by_year.values())/len(by_year)) * 100) if len(by_year) > 1 else 0
        print(f"\n  Volatility: mean |YoY change| = {mean_abs:.1f}%, CV = {cv:.1f}%")

    return {
        "name": name,
        "code": code,
        "total_spend": total_spend,
        "n_orgs": n_orgs,
        "n_activities": len(rows),
        "n_with_spend": n_with_spend,
        "hhi": hhi,
        "gini": gini_val,
        "top_50": top_50_count,
        "top_80": top_80_count,
        "top_90": top_90_count,
        "top_15": top_15,
        "yearly_data": yearly_data,
        "yoy_changes": yoy_changes,
        "by_year": dict(by_year),
    }


def main():
    print("=" * 70)
    print("  DONOR CONCENTRATION IN IATI DATA — FIVE EAST AFRICAN COUNTRIES")
    print("=" * 70)

    results = {}
    for code, name in COUNTRIES.items():
        result = analyze_country(code, name)
        if result:
            results[code] = result

    print(f"\n\n{'='*70}")
    print("  CROSS-COUNTRY SUMMARY")
    print(f"{'='*70}")
    print(f"\n  {'Country':>12} {'HHI':>8} {'Gini':>8} {'Orgs':>6} {'50%in':>6} {'80%in':>6} {'Spend$M':>10}")
    for code in sorted(results, key=lambda c: -results[c]["hhi"]):
        r = results[code]
        print(f"  {r['name']:>12} {r['hhi']:>8.4f} {r['gini']:>8.3f} {r['n_orgs']:>6} {r['top_50']:>6} {r['top_80']:>6} {r['total_spend']/1e6:>10.1f}")

    # Which donors appear in all 5 countries?
    all_donors = defaultdict(lambda: {"countries": set(), "total": 0.0, "name": ""})
    for code, r in results.items():
        for d in r["top_15"]:
            all_donors[d["ref"]]["countries"].add(code)
            all_donors[d["ref"]]["total"] += d["spend"]
            all_donors[d["ref"]]["name"] = d["name"]

    pan_regional = {k: v for k, v in all_donors.items() if len(v["countries"]) >= 3}
    print(f"\n  Donors in 3+ countries (among each country's top 15):")
    for ref in sorted(pan_regional, key=lambda r: -pan_regional[r]["total"]):
        d = pan_regional[ref]
        codes = sorted(d["countries"])
        print(f"    {d['name'][:45]:45s} ${d['total']/1e6:9.1f}M  ({len(codes)} countries: {', '.join(codes)})")

    # The fragmentation-concentration paradox
    print(f"\n  THE PARADOX:")
    for code in sorted(results, key=lambda c: results[c]["name"]):
        r = results[code]
        print(f"    {r['name']}: {r['n_orgs']} reporting orgs, but {r['top_50']} account for 50% of spend "
              f"({r['top_50']/r['n_orgs']*100:.0f}% of orgs = 50% of money)")


if __name__ == "__main__":
    main()
