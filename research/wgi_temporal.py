#!/usr/bin/env python3
"""
WGI Temporal Analysis — Are governance changes real or measurement noise?

For each focus country, fetches WGI scores over time and checks whether
year-to-year and decade-to-decade changes exceed the confidence intervals.
"""

import json
import urllib.request
import time
import sys

BASE = "https://api.worldbank.org/v2"

DIMENSIONS = {
    "CC": "Control of Corruption",
    "GE": "Government Effectiveness",
    "RL": "Rule of Law",
    "VA": "Voice and Accountability",
}

FOCUS_COUNTRIES = ["UGA", "KEN", "RWA", "ETH", "GHA", "NGA", "IND", "BGD", "VNM", "COL"]

COUNTRY_NAMES = {
    "UGA": "Uganda", "KEN": "Kenya", "RWA": "Rwanda", "ETH": "Ethiopia",
    "GHA": "Ghana", "NGA": "Nigeria", "IND": "India", "BGD": "Bangladesh",
    "VNM": "Vietnam", "COL": "Colombia",
}

YEARS = list(range(2006, 2024))


def fetch_timeseries(dim_code, suffix, countries):
    """Fetch a full time series for an indicator."""
    country_str = ";".join(countries)
    year_range = f"{min(YEARS)}:{max(YEARS)}"
    indicator = f"GOV_WGI_{dim_code}.{suffix}"
    url = f"{BASE}/country/{country_str}/indicator/{indicator}?format=json&date={year_range}&per_page=500&source=3"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
            if len(data) > 1 and data[1]:
                return data[1]
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
    return []


def build_timeseries(dim_code, countries):
    """Build country → year → {score, lb, ub, se} lookup."""
    result = {}

    for suffix, field in [("SC", "score"), ("SC_LB", "lb"), ("SC_UB", "ub"), ("SE", "se")]:
        records = fetch_timeseries(dim_code, suffix, countries)
        for rec in records:
            iso3 = rec["countryiso3code"]
            year = int(rec["date"])
            val = rec["value"]
            if val is None:
                continue
            if iso3 not in result:
                result[iso3] = {}
            if year not in result[iso3]:
                result[iso3][year] = {}
            result[iso3][year][field] = float(val)
        time.sleep(0.3)

    return result


def analyze_changes(timeseries, dim_name):
    """For each country, check if changes exceed CIs."""
    print(f"\n=== {dim_name} — Temporal Change Analysis ===\n")

    all_changes = []
    significant_changes = []

    for iso3 in FOCUS_COUNTRIES:
        if iso3 not in timeseries:
            continue
        data = timeseries[iso3]
        years_available = sorted(y for y in data if "score" in data[y] and "lb" in data[y])

        if len(years_available) < 2:
            continue

        first_year = years_available[0]
        last_year = years_available[-1]

        if "score" not in data[first_year] or "score" not in data[last_year]:
            continue

        first_score = data[first_year]["score"]
        last_score = data[last_year]["score"]
        change = last_score - first_score

        first_lb = data[first_year].get("lb", first_score)
        first_ub = data[first_year].get("ub", first_score)
        last_lb = data[last_year].get("lb", last_score)
        last_ub = data[last_year].get("ub", last_score)

        # Do the CIs overlap? If yes, change is not statistically distinguishable
        ci_overlap = last_lb < first_ub and first_lb < last_ub
        significant = not ci_overlap

        all_changes.append({
            "iso3": iso3,
            "country": COUNTRY_NAMES.get(iso3, iso3),
            "first_year": first_year,
            "last_year": last_year,
            "first_score": first_score,
            "last_score": last_score,
            "change": change,
            "first_ci": f"[{first_lb:.1f}–{first_ub:.1f}]",
            "last_ci": f"[{last_lb:.1f}–{last_ub:.1f}]",
            "ci_overlap": ci_overlap,
            "significant": significant,
        })

        if significant:
            significant_changes.append(all_changes[-1])

    # Print results
    print(f"  {'Country':<12} {'Period':>12} {'Change':>8} {'First CI':>15} {'Last CI':>15} {'Detectable?':>12}")
    print(f"  {'─'*12} {'─'*12} {'─'*8} {'─'*15} {'─'*15} {'─'*12}")
    for c in sorted(all_changes, key=lambda x: abs(x["change"]), reverse=True):
        det = "YES" if c["significant"] else "no"
        period = f"{c['first_year']}→{c['last_year']}"
        sign = "+" if c["change"] >= 0 else ""
        print(f"  {c['country']:<12} {period:>12} {sign}{c['change']:>7.1f} {c['first_ci']:>15} {c['last_ci']:>15} {det:>12}")

    sig_count = len(significant_changes)
    total = len(all_changes)
    print(f"\n  Statistically detectable changes: {sig_count}/{total} ({100*sig_count/total:.0f}%)")

    # Year-to-year volatility
    print(f"\n  Year-to-year volatility (consecutive changes):")
    yoy_total = 0
    yoy_exceeds_ci = 0
    volatility_data = []

    for iso3 in FOCUS_COUNTRIES:
        if iso3 not in timeseries:
            continue
        data = timeseries[iso3]
        years_available = sorted(y for y in data if "score" in data[y])
        changes = []
        for i in range(1, len(years_available)):
            y0, y1 = years_available[i-1], years_available[i]
            if "score" in data[y0] and "score" in data[y1]:
                ch = data[y1]["score"] - data[y0]["score"]
                changes.append(abs(ch))
                yoy_total += 1
                ci0 = data[y0].get("ub", 0) - data[y0].get("lb", 0)
                if abs(ch) > ci0 / 2:
                    yoy_exceeds_ci += 1
        if changes:
            avg = sum(changes) / len(changes)
            max_ch = max(changes)
            volatility_data.append({
                "country": COUNTRY_NAMES.get(iso3, iso3),
                "avg": avg,
                "max": max_ch,
                "n": len(changes),
            })

    if volatility_data:
        print(f"  {'Country':<12} {'Avg |change|':>12} {'Max |change|':>12} {'Periods':>8}")
        print(f"  {'─'*12} {'─'*12} {'─'*12} {'─'*8}")
        for v in sorted(volatility_data, key=lambda x: x["avg"], reverse=True):
            print(f"  {v['country']:<12} {v['avg']:>12.1f} {v['max']:>12.1f} {v['n']:>8}")

    return all_changes


def cross_dimension_analysis(all_data):
    """Compare how countries rank differently across dimensions."""
    print(f"\n\n=== Cross-Dimension Ranking Divergence (2023) ===\n")

    country_ranks = {}
    for dim_code, dim_name in DIMENSIONS.items():
        ts = all_data[dim_code]
        scores_2023 = []
        for iso3 in FOCUS_COUNTRIES:
            if iso3 in ts and 2023 in ts[iso3] and "score" in ts[iso3][2023]:
                scores_2023.append((iso3, ts[iso3][2023]["score"]))
        scores_2023.sort(key=lambda x: x[1], reverse=True)
        for rank, (iso3, score) in enumerate(scores_2023, 1):
            if iso3 not in country_ranks:
                country_ranks[iso3] = {}
            country_ranks[iso3][dim_code] = rank

    print(f"  {'Country':<12}", end="")
    for dim_code in DIMENSIONS:
        print(f" {dim_code:>4}", end="")
    print(f" {'Range':>6}")
    print(f"  {'─'*12}", end="")
    for _ in DIMENSIONS:
        print(f" {'─'*4}", end="")
    print(f" {'─'*6}")

    for iso3 in FOCUS_COUNTRIES:
        if iso3 not in country_ranks:
            continue
        ranks = country_ranks[iso3]
        if len(ranks) < len(DIMENSIONS):
            continue
        vals = list(ranks.values())
        rng = max(vals) - min(vals)
        print(f"  {COUNTRY_NAMES.get(iso3, iso3):<12}", end="")
        for dim_code in DIMENSIONS:
            print(f" {ranks.get(dim_code, '—'):>4}", end="")
        print(f" {rng:>6}")


def main():
    all_data = {}

    for dim_code, dim_name in DIMENSIONS.items():
        print(f"Fetching {dim_name}...")
        ts = build_timeseries(dim_code, FOCUS_COUNTRIES)
        all_data[dim_code] = ts
        analyze_changes(ts, dim_name)

    cross_dimension_analysis(all_data)

    # Save
    output = {
        "analysis": "WGI temporal measurement layer",
        "countries": FOCUS_COUNTRIES,
        "years": YEARS,
        "dimensions": {k: v for k, v in DIMENSIONS.items()},
    }
    with open("research/wgi_temporal.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to research/wgi_temporal.json")


if __name__ == "__main__":
    main()
