#!/usr/bin/env python3
"""Systematic comparative fragmentation decomposition across countries and sectors.

Runs honest_fragmentation analysis across multiple country-sector pairs,
computes decomposition metrics, and produces a comparative summary showing
how much of apparent fragmentation is measurement artifact vs genuine
coordination challenge.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from honest_fragmentation import analyze

COUNTRIES = {
    "UG": "Uganda",
    "KE": "Kenya",
    "RW": "Rwanda",
    "TZ": "Tanzania",
    "ET": "Ethiopia",
}

SECTORS = ["Governance", "Health", "Education"]

PAIRS = [
    ("UG", "Governance"), ("KE", "Governance"), ("RW", "Governance"),
    ("TZ", "Governance"), ("ET", "Governance"),
    ("UG", "Health"), ("KE", "Health"), ("RW", "Health"),
    ("TZ", "Health"), ("ET", "Health"),
    ("UG", "Education"), ("KE", "Education"),
]


def result_path(country, sector):
    return f"research/honest_fragmentation_{country}_{sector.lower().replace(' ', '_')}.json"


def load_or_run(country, sector):
    path = result_path(country, sector)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        print(f"\n  [cached] {COUNTRIES.get(country, country)} {sector}")
        return data

    print(f"\n  [running] {COUNTRIES.get(country, country)} {sector}...")
    result = analyze(country, sector, limit=5000)
    if result:
        with open(path, "w") as f:
            json.dump(result, f, indent=2)
    return result


def compute_metrics(r):
    if not r or r["raw_orgs"] == 0:
        return None
    raw = r["raw_orgs"]
    active = r["active_orgs"]
    artifact_ratio = (raw - active) / raw if raw > 0 else 0
    financial_reporting_ratio = r["orgs_reporting_financials"] / raw if raw > 0 else 0
    miscoding_rate = r["miscoded"] / r["total_activities"] if r["total_activities"] > 0 else 0
    activity_closure_rate = 1 - (r["active_activities"] / r["total_activities"]) if r["total_activities"] > 0 else 0

    return {
        **r,
        "artifact_ratio": artifact_ratio,
        "financial_reporting_ratio": financial_reporting_ratio,
        "miscoding_rate": miscoding_rate,
        "activity_closure_rate": activity_closure_rate,
    }


def print_comparative_table(results):
    print(f"\n{'='*100}")
    print(f"  COMPARATIVE FRAGMENTATION DECOMPOSITION — East Africa")
    print(f"{'='*100}")

    header = (
        f"  {'Country':<12} {'Sector':<13} {'Raw':>4} {'Dedup':>5} {'Active':>6} "
        f"{'Artifact%':>9} {'Miscoded%':>9} {'FinRpt%':>7} {'Coord':>5} {'Disbursed':>16}"
    )
    print(f"\n{header}")
    print(f"  {'-'*95}")

    by_sector = {}
    for r in results:
        if not r:
            continue
        m = compute_metrics(r)
        if not m:
            continue

        sector = m["sector"]
        by_sector.setdefault(sector, []).append(m)

        country_name = COUNTRIES.get(m["country"], m["country"])
        print(
            f"  {country_name:<12} {sector:<13} {m['raw_orgs']:>4} {m['dedup_orgs']:>5} "
            f"{m['active_orgs']:>6} {m['artifact_ratio']:>8.0%} {m['miscoding_rate']:>8.1%} "
            f"{m['financial_reporting_ratio']:>6.0%} {m['coordination_signals']:>5} "
            f"${m['total_disbursed_usd']:>14,.0f}"
        )

    print(f"\n{'='*100}")
    print(f"  SECTOR AVERAGES")
    print(f"{'='*100}")
    for sector, items in sorted(by_sector.items()):
        n = len(items)
        avg_artifact = sum(i["artifact_ratio"] for i in items) / n
        avg_miscoding = sum(i["miscoding_rate"] for i in items) / n
        avg_finrpt = sum(i["financial_reporting_ratio"] for i in items) / n
        avg_raw = sum(i["raw_orgs"] for i in items) / n
        avg_active = sum(i["active_orgs"] for i in items) / n
        print(
            f"  {sector:<15} (n={n}): raw={avg_raw:.0f} → active={avg_active:.0f} "
            f"(artifact={avg_artifact:.0%}), miscoding={avg_miscoding:.1%}, "
            f"financial reporting={avg_finrpt:.0%}"
        )

    print(f"\n{'='*100}")
    print(f"  KEY FINDINGS")
    print(f"{'='*100}")

    all_metrics = [compute_metrics(r) for r in results if r]
    all_metrics = [m for m in all_metrics if m]

    if all_metrics:
        avg_artifact = sum(m["artifact_ratio"] for m in all_metrics) / len(all_metrics)
        max_artifact = max(all_metrics, key=lambda m: m["artifact_ratio"])
        avg_fin = sum(m["financial_reporting_ratio"] for m in all_metrics) / len(all_metrics)
        avg_miscoding = sum(m["miscoding_rate"] for m in all_metrics) / len(all_metrics)

        print(f"""
  1. ARTIFACT RATE: On average, {avg_artifact:.0%} of apparent fragmentation
     (raw org count) disappears after deduplication + status filtering.
     Worst case: {COUNTRIES.get(max_artifact['country'], max_artifact['country'])}
     {max_artifact['sector']} ({max_artifact['artifact_ratio']:.0%}).

  2. FINANCIAL OPACITY: Only {avg_fin:.0%} of reporting organizations actually
     report disbursement data. Fragmentation analysis without financial data
     treats a $1M project the same as a $1B program.

  3. MISCODING: {avg_miscoding:.1%} of activities have titles suggesting
     a different sector than their DAC code. This inflates sector-specific
     counts and distorts coordination assessments.

  4. COORDINATION INVISIBLE: Existing coordination mechanisms (SWAps, basket
     funds, joint programs) are detectable only through title keyword search,
     not structured IATI fields.
""")

    return all_metrics


def main():
    print("Systematic Fragmentation Decomposition")
    print("Running analyses across East African countries...\n")

    results = []
    for country, sector in PAIRS:
        try:
            result = load_or_run(country, sector)
            results.append(result)
        except Exception as e:
            print(f"  ERROR: {country} {sector}: {e}", file=sys.stderr)
            results.append(None)

    valid = [r for r in results if r]
    all_metrics = print_comparative_table(valid)

    summary = {
        "pairs_analyzed": len(valid),
        "pairs_attempted": len(PAIRS),
        "results": valid,
    }
    with open("research/comparative_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nFull results saved to research/comparative_summary.json")

    return all_metrics


if __name__ == "__main__":
    main()
