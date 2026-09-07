#!/usr/bin/env python3
"""
Worldwide Governance Indicators — Measurement Layer Analysis

Explores how much of the apparent precision in governance rankings
is supported by the underlying data vs. shaped by methodology.

Uses World Bank API (source 3 = WGI).
"""

import json
import urllib.request
import time
import sys

BASE = "https://api.worldbank.org/v2"

DIMENSIONS = {
    "CC": "Control of Corruption",
    "GE": "Government Effectiveness",
    "PV": "Political Stability",
    "RL": "Rule of Law",
    "RQ": "Regulatory Quality",
    "VA": "Voice and Accountability",
}

FOCUS_COUNTRIES = {
    "UGA": "Uganda",
    "KEN": "Kenya",
    "RWA": "Rwanda",
    "TZA": "Tanzania",
    "ETH": "Ethiopia",
    "GHA": "Ghana",
    "NGA": "Nigeria",
    "ZAF": "South Africa",
    "IND": "India",
    "BGD": "Bangladesh",
    "KHM": "Cambodia",
    "VNM": "Vietnam",
    "GTM": "Guatemala",
    "COL": "Colombia",
    "SEN": "Senegal",
}

def fetch_indicator(indicator_id, year="2023", countries=None):
    """Fetch a single WGI indicator for given countries and year."""
    if countries:
        country_str = ";".join(countries)
    else:
        country_str = "all"

    url = f"{BASE}/country/{country_str}/indicator/{indicator_id}?format=json&date={year}&per_page=300&source=3"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
            if len(data) > 1 and data[1]:
                return data[1]
    except Exception as e:
        print(f"  Error fetching {indicator_id}: {e}", file=sys.stderr)
    return []


def fetch_dimension(dim_code, year="2023", countries=None):
    """Fetch all indicators for a WGI dimension."""
    suffixes = {
        "EST": "estimate",
        "SC": "score",
        "SC_LB": "score_lb",
        "SC_UB": "score_ub",
        "SE": "std_error",
        "SR": "num_sources",
    }

    results = {}
    for suffix, field in suffixes.items():
        indicator_id = f"GOV_WGI_{dim_code}.{suffix}"
        records = fetch_indicator(indicator_id, year, countries)
        for rec in records:
            iso3 = rec["countryiso3code"]
            if iso3 not in results:
                results[iso3] = {"country": rec["country"]["value"], "iso3": iso3}
            val = rec["value"]
            if val is not None:
                results[iso3][field] = float(val)
        time.sleep(0.3)

    return results


def analyze_confidence_intervals(data, dim_name):
    """Analyze how much confidence intervals overlap in rankings."""
    scored = []
    for iso3, rec in data.items():
        if "score" in rec and "score_lb" in rec and "score_ub" in rec:
            scored.append({
                "iso3": iso3,
                "country": rec["country"],
                "score": rec["score"],
                "lb": rec["score_lb"],
                "ub": rec["score_ub"],
                "width": rec["score_ub"] - rec["score_lb"],
                "std_error": rec.get("std_error", None),
                "num_sources": rec.get("num_sources", None),
            })

    scored.sort(key=lambda x: x["score"], reverse=True)

    overlap_count = 0
    total_pairs = 0
    for i in range(len(scored)):
        for j in range(i + 1, len(scored)):
            total_pairs += 1
            if scored[i]["lb"] < scored[j]["ub"]:
                overlap_count += 1

    return scored, overlap_count, total_pairs


def analyze_source_coverage(data, dim_name):
    """Analyze how source count varies and affects precision."""
    records = []
    for iso3, rec in data.items():
        if "num_sources" in rec and "score" in rec:
            records.append({
                "iso3": iso3,
                "country": rec["country"],
                "score": rec["score"],
                "num_sources": rec.get("num_sources", 0),
                "std_error": rec.get("std_error", 0),
                "ci_width": rec.get("score_ub", 0) - rec.get("score_lb", 0),
            })
    return records


def main():
    year = "2023"
    countries = list(FOCUS_COUNTRIES.keys())
    all_results = {}

    print(f"=== WGI Measurement Layer Analysis — {year} ===\n")
    print(f"Focus: {len(countries)} countries across Sub-Saharan Africa, South Asia, Southeast Asia, Latin America\n")

    for dim_code, dim_name in DIMENSIONS.items():
        print(f"\n--- {dim_name} ({dim_code}) ---")
        data = fetch_dimension(dim_code, year, countries)
        all_results[dim_code] = data

        if not data:
            print("  No data returned")
            continue

        scored, overlaps, total = analyze_confidence_intervals(data, dim_name)
        coverage = analyze_source_coverage(data, dim_name)

        print(f"  Countries with data: {len(scored)}")
        if total > 0:
            print(f"  Pairwise CI overlaps: {overlaps}/{total} ({100*overlaps/total:.0f}%)")

        if scored:
            widths = [s["width"] for s in scored]
            print(f"  CI width — min: {min(widths):.1f}, max: {max(widths):.1f}, mean: {sum(widths)/len(widths):.1f}")

        print(f"\n  {'Rank':<5} {'Country':<15} {'Score':>6} {'90% CI':>15} {'Width':>6} {'Sources':>8}")
        print(f"  {'─'*5} {'─'*15} {'─'*6} {'─'*15} {'─'*6} {'─'*8}")
        for rank, s in enumerate(scored, 1):
            ci = f"[{s['lb']:.1f}–{s['ub']:.1f}]"
            sources = f"{s['num_sources']:.0f}" if s['num_sources'] else "—"
            print(f"  {rank:<5} {s['country']:<15} {s['score']:>6.1f} {ci:>15} {s['width']:>6.1f} {sources:>8}")

    # Global analysis: fetch ALL countries for one dimension to see full ranking instability
    print(f"\n\n=== Global Ranking Instability — Government Effectiveness ===")
    print("Fetching all countries...")
    global_data = fetch_dimension("GE", year)
    global_scored, g_overlaps, g_total = analyze_confidence_intervals(global_data, "GE")

    if g_total > 0:
        print(f"Countries with data: {len(global_scored)}")
        print(f"Pairwise CI overlaps: {g_overlaps}/{g_total} ({100*g_overlaps/g_total:.0f}%)")

        widths = [s["width"] for s in global_scored]
        sources_list = [s["num_sources"] for s in global_scored if s["num_sources"]]
        print(f"CI width — min: {min(widths):.1f}, max: {max(widths):.1f}, mean: {sum(widths)/len(widths):.1f}")
        if sources_list:
            print(f"Sources — min: {min(sources_list):.0f}, max: {max(sources_list):.0f}, mean: {sum(sources_list)/len(sources_list):.1f}")

        # Find countries where rank could change by 10+ positions within CI
        rank_instability = []
        for i, country in enumerate(global_scored):
            could_be_higher = sum(1 for j in range(i) if global_scored[j]["lb"] < country["ub"])
            could_be_lower = sum(1 for j in range(i+1, len(global_scored)) if global_scored[j]["ub"] > country["lb"])
            rank_range = could_be_higher + could_be_lower + 1
            rank_instability.append({
                **country,
                "nominal_rank": i + 1,
                "could_be_higher": could_be_higher,
                "could_be_lower": could_be_lower,
                "rank_range": rank_range,
            })

        rank_instability.sort(key=lambda x: x["rank_range"], reverse=True)

        print(f"\n  Most unstable rankings (countries whose rank could shift most within 90% CI):")
        print(f"  {'Rank':<5} {'Country':<25} {'Score':>6} {'CI Width':>8} {'Could shift':>12} {'Sources':>8}")
        print(f"  {'─'*5} {'─'*25} {'─'*6} {'─'*8} {'─'*12} {'─'*8}")
        for r in rank_instability[:20]:
            sources = f"{r['num_sources']:.0f}" if r['num_sources'] else "—"
            shift = f"±{r['rank_range']//2}"
            print(f"  {r['nominal_rank']:<5} {r['country']:<25} {r['score']:>6.1f} {r['width']:>8.1f} {shift:>12} {sources:>8}")

        # Correlation between source count and CI width
        paired = [(s["num_sources"], s["width"]) for s in global_scored if s["num_sources"]]
        if paired:
            n = len(paired)
            sx = sum(p[0] for p in paired)
            sy = sum(p[1] for p in paired)
            sxx = sum(p[0]**2 for p in paired)
            syy = sum(p[1]**2 for p in paired)
            sxy = sum(p[0]*p[1] for p in paired)
            denom = ((n*sxx - sx*sx) * (n*syy - sy*sy))**0.5
            if denom > 0:
                r = (n*sxy - sx*sy) / denom
                print(f"\n  Correlation (sources vs CI width): r = {r:.3f}")
                print(f"  {'→ More sources = narrower CI' if r < 0 else '→ More sources = wider CI (unexpected)'}")

        # Focus countries ranking
        focus_in_global = [r for r in rank_instability if r["iso3"] in FOCUS_COUNTRIES]
        if focus_in_global:
            focus_in_global.sort(key=lambda x: x["nominal_rank"])
            print(f"\n  Focus countries in global ranking:")
            print(f"  {'Rank':<5} {'Country':<15} {'Score':>6} {'90% CI':>15} {'Possible ranks':>15} {'Sources':>8}")
            print(f"  {'─'*5} {'─'*15} {'─'*6} {'─'*15} {'─'*15} {'─'*8}")
            for r in focus_in_global:
                ci = f"[{r['lb']:.1f}–{r['ub']:.1f}]"
                sources = f"{r['num_sources']:.0f}" if r['num_sources'] else "—"
                low_rank = r["nominal_rank"] + r["could_be_lower"]
                high_rank = r["nominal_rank"] - r["could_be_higher"]
                rank_range = f"{high_rank}–{low_rank}"
                print(f"  {r['nominal_rank']:<5} {r['country']:<15} {r['score']:>6.1f} {ci:>15} {rank_range:>15} {sources:>8}")

    # Save full results
    output = {
        "year": year,
        "focus_countries": all_results,
        "global_ge": {
            "scored": global_scored if global_scored else [],
            "overlaps": g_overlaps if g_total else 0,
            "total_pairs": g_total if g_total else 0,
        }
    }

    with open("research/wgi_analysis.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to research/wgi_analysis.json")


if __name__ == "__main__":
    main()
