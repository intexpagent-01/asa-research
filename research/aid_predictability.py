#!/usr/bin/env python3
"""Analyze aid predictability: commitment vs disbursement gaps using d-portal/IATI data."""
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

DPORTAL = "https://d-portal.org/q.json"

COUNTRIES = {
    "KE": "Kenya",
    "UG": "Uganda",
    "RW": "Rwanda",
    "TZ": "Tanzania",
    "ET": "Ethiopia",
}

def epoch_day_to_date(day_num):
    """d-portal stores dates as days since Unix epoch."""
    try:
        return datetime(1970, 1, 1) + timedelta(days=int(day_num))
    except (ValueError, TypeError):
        return None

def fetch_transactions(country_code, tx_code, limit=10000):
    """Fetch transactions. tx_code: C=commitment, D=disbursement, E=expenditure."""
    url = f"{DPORTAL}?from=trans&limit={limit}&country_code={country_code}&trans_code={tx_code}"
    req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.2"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("rows", [])
    except Exception as e:
        print(f"  Error fetching {tx_code} for {country_code}: {e}")
        return []

def fetch_activity_info(aid):
    """Fetch activity-level info for an IATI identifier."""
    url = f"{DPORTAL}?from=act&limit=1&aid={aid}"
    req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.2"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rows = data.get("rows", [])
        return rows[0] if rows else {}
    except Exception:
        return {}

def analyze_country(code, name):
    print(f"\n{'='*60}")
    print(f"  {name} ({code})")
    print(f"{'='*60}")

    print(f"  Fetching commitments...")
    commitments = fetch_transactions(code, "C")
    print(f"  → {len(commitments)} commitment transactions")

    print(f"  Fetching disbursements...")
    disbursements = fetch_transactions(code, "D")
    print(f"  → {len(disbursements)} disbursement transactions")

    print(f"  Fetching expenditures...")
    expenditures = fetch_transactions(code, "E")
    print(f"  → {len(expenditures)} expenditure transactions")

    # By year
    c_by_year = defaultdict(float)
    d_by_year = defaultdict(float)
    e_by_year = defaultdict(float)
    c_by_sector = defaultdict(float)
    d_by_sector = defaultdict(float)

    c_by_aid = defaultdict(float)
    d_by_aid = defaultdict(float)
    c_dates_by_aid = defaultdict(list)
    d_dates_by_aid = defaultdict(list)

    for row in commitments:
        val = row.get("trans_usd") or 0
        dt = epoch_day_to_date(row.get("trans_day"))
        aid = row.get("aid", "")
        sector = row.get("trans_sector_group") or "?"
        if dt and 2010 <= dt.year <= 2025:
            c_by_year[dt.year] += val
        c_by_sector[sector] += val
        c_by_aid[aid] += val
        if dt:
            c_dates_by_aid[aid].append(dt)

    for row in disbursements:
        val = row.get("trans_usd") or 0
        dt = epoch_day_to_date(row.get("trans_day"))
        aid = row.get("aid", "")
        sector = row.get("trans_sector_group") or "?"
        if dt and 2010 <= dt.year <= 2025:
            d_by_year[dt.year] += val
        d_by_sector[sector] += val
        d_by_aid[aid] += val
        if dt:
            d_dates_by_aid[aid].append(dt)

    for row in expenditures:
        val = row.get("trans_usd") or 0
        dt = epoch_day_to_date(row.get("trans_day"))
        if dt and 2010 <= dt.year <= 2025:
            e_by_year[dt.year] += val

    all_years = sorted(set(list(c_by_year.keys()) + list(d_by_year.keys()) + list(e_by_year.keys())))

    print(f"\n  Year-by-year (USD millions):")
    print(f"  {'Year':<6} {'Commit':>12} {'Disburse':>12} {'Expend':>12} {'D/C ratio':>10}")
    year_data = []
    for y in all_years:
        c = c_by_year.get(y, 0)
        d = d_by_year.get(y, 0)
        e = e_by_year.get(y, 0)
        ratio = d / c if c > 0 else None
        ratio_str = f"{ratio:.2f}" if ratio is not None else "n/a"
        print(f"  {y:<6} {c/1e6:>12.1f} {d/1e6:>12.1f} {e/1e6:>12.1f} {ratio_str:>10}")
        year_data.append({
            "year": y,
            "commitments": c,
            "disbursements": d,
            "expenditures": e,
            "d_c_ratio": ratio,
        })

    # Activity-level predictability
    all_aids = set(list(c_by_aid.keys()) + list(d_by_aid.keys()))
    c_only = sum(1 for a in all_aids if a in c_by_aid and a not in d_by_aid)
    d_only = sum(1 for a in all_aids if a not in c_by_aid and a in d_by_aid)
    both = sum(1 for a in all_aids if a in c_by_aid and a in d_by_aid)

    print(f"\n  Activity coverage:")
    print(f"    Total unique activities: {len(all_aids)}")
    print(f"    Commitment only: {c_only} ({c_only/len(all_aids)*100:.1f}%)" if all_aids else "")
    print(f"    Disbursement only: {d_only} ({d_only/len(all_aids)*100:.1f}%)" if all_aids else "")
    print(f"    Both: {both} ({both/len(all_aids)*100:.1f}%)" if all_aids else "")

    # For activities with both: compare C and D values
    ratios = []
    over_committed = 0
    under_committed = 0
    for aid in all_aids:
        if aid in c_by_aid and aid in d_by_aid and c_by_aid[aid] > 0:
            r = d_by_aid[aid] / c_by_aid[aid]
            ratios.append(r)
            if r < 0.5:
                over_committed += 1
            elif r > 1.5:
                under_committed += 1

    if ratios:
        ratios.sort()
        median_r = ratios[len(ratios) // 2]
        mean_r = sum(ratios) / len(ratios)
        p25 = ratios[len(ratios) // 4]
        p75 = ratios[3 * len(ratios) // 4]
        print(f"\n  Disbursement/Commitment ratio (activity-level, n={len(ratios)}):")
        print(f"    Median: {median_r:.2f}")
        print(f"    Mean: {mean_r:.2f}")
        print(f"    P25-P75: {p25:.2f} - {p75:.2f}")
        print(f"    Over-committed (D/C < 0.5): {over_committed} ({over_committed/len(ratios)*100:.1f}%)")
        print(f"    Under-committed (D/C > 1.5): {under_committed} ({under_committed/len(ratios)*100:.1f}%)")

    # Timing: commitment to first disbursement
    delays = []
    shared_aids = set(c_dates_by_aid.keys()) & set(d_dates_by_aid.keys())
    for aid in shared_aids:
        first_c = min(c_dates_by_aid[aid])
        first_d = min(d_dates_by_aid[aid])
        delay = (first_d - first_c).days
        if 0 <= delay <= 3650:
            delays.append(delay)

    timing = {}
    if delays:
        delays.sort()
        timing = {
            "n": len(delays),
            "median_days": delays[len(delays) // 2],
            "mean_days": round(sum(delays) / len(delays), 1),
            "p25_days": delays[len(delays) // 4],
            "p75_days": delays[3 * len(delays) // 4],
        }
        print(f"\n  Commitment-to-first-disbursement delay (n={len(delays)}):")
        print(f"    Median: {timing['median_days']} days ({timing['median_days']/30:.1f} months)")
        print(f"    Mean: {timing['mean_days']} days ({timing['mean_days']/30:.1f} months)")
        print(f"    P25-P75: {timing['p25_days']}-{timing['p75_days']} days")

    # Sector gaps
    all_sectors = sorted(set(list(c_by_sector.keys()) + list(d_by_sector.keys())),
                         key=lambda s: -(c_by_sector.get(s, 0) + d_by_sector.get(s, 0)))
    all_sectors = [s for s in all_sectors if s is not None]
    print(f"\n  Top sectors (USD millions):")
    print(f"  {'Sector':>8} {'Commit':>12} {'Disburse':>12} {'D/C':>8}")
    sector_data = []
    for s in all_sectors[:12]:
        c = c_by_sector.get(s, 0)
        d = d_by_sector.get(s, 0)
        ratio = d / c if c > 0 else None
        ratio_str = f"{ratio:.2f}" if ratio is not None else "n/a"
        print(f"  {s:>8} {c/1e6:>12.1f} {d/1e6:>12.1f} {ratio_str:>8}")
        sector_data.append({"sector_group": s, "commitments": c, "disbursements": d, "ratio": ratio})

    return {
        "country": name,
        "code": code,
        "n_commitments": len(commitments),
        "n_disbursements": len(disbursements),
        "n_expenditures": len(expenditures),
        "by_year": year_data,
        "coverage": {
            "total_activities": len(all_aids),
            "commitment_only": c_only,
            "disbursement_only": d_only,
            "both": both,
        },
        "activity_ratios": {
            "n": len(ratios),
            "median": ratios[len(ratios)//2] if ratios else None,
            "mean": sum(ratios)/len(ratios) if ratios else None,
            "over_committed_pct": over_committed/len(ratios)*100 if ratios else None,
            "under_committed_pct": under_committed/len(ratios)*100 if ratios else None,
        },
        "timing": timing,
        "by_sector": sector_data,
    }


def main():
    results = {}
    for code, name in COUNTRIES.items():
        results[code] = analyze_country(code, name)

    print(f"\n{'='*60}")
    print(f"  CROSS-COUNTRY SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Country':<12} {'C-txns':>8} {'D-txns':>8} {'C-only%':>8} {'D-only%':>8} {'Both%':>8} {'Med D/C':>8} {'Med delay':>10}")
    for code in COUNTRIES:
        r = results[code]
        cov = r["coverage"]
        tot = cov["total_activities"] or 1
        ar = r["activity_ratios"]
        med_r = f"{ar['median']:.2f}" if ar['median'] is not None else "n/a"
        med_d = f"{r['timing']['median_days']}d" if r['timing'].get('median_days') is not None else "n/a"
        print(f"  {r['country']:<12} {r['n_commitments']:>8} {r['n_disbursements']:>8} "
              f"{cov['commitment_only']/tot*100:>7.1f}% {cov['disbursement_only']/tot*100:>7.1f}% "
              f"{cov['both']/tot*100:>7.1f}% {med_r:>8} {med_d:>10}")

    with open("research/aid_predictability.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to research/aid_predictability.json")


if __name__ == "__main__":
    main()
