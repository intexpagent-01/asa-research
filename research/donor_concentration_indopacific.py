#!/usr/bin/env python3
"""Donor concentration in IATI data — Indo-Pacific edition.
Reuses analyze_country() from donor_concentration.py over a Pacific + Southeast Asia
country set and saves full JSON results for visualisation."""
import json, sys
from collections import defaultdict
sys.path.insert(0, "research")
from donor_concentration import analyze_country

COUNTRIES = {
    "PG": "Papua New Guinea", "SB": "Solomon Islands", "VU": "Vanuatu", "FJ": "Fiji",
    "WS": "Samoa", "TO": "Tonga", "KI": "Kiribati", "TV": "Tuvalu", "TL": "Timor-Leste",
    "ID": "Indonesia", "PH": "Philippines", "VN": "Viet Nam", "KH": "Cambodia", "LA": "Lao PDR", "MM": "Myanmar",
}
OUT = "research/donor_concentration_indopacific.json"

def main():
    results = {}
    for code, name in COUNTRIES.items():
        r = analyze_country(code, name)
        if r:
            results[code] = r
        sys.stdout.flush()
    print(f"\n\n{'='*70}\n  CROSS-COUNTRY SUMMARY\n{'='*70}")
    print(f"\n  {'Country':>18} {'HHI':>8} {'Gini':>8} {'Orgs':>6} {'50%in':>6} {'80%in':>6} {'Spend$M':>10}")
    for code in sorted(results, key=lambda c: -results[c]["hhi"]):
        r = results[code]
        print(f"  {r['name']:>18} {r['hhi']:>8.4f} {r['gini']:>8.3f} {r['n_orgs']:>6} {r['top_50']:>6} {r['top_80']:>6} {r['total_spend']/1e6:>10.1f}")
    all_donors = defaultdict(lambda: {"countries": set(), "total": 0.0, "name": ""})
    for code, r in results.items():
        for d in r["top_15"]:
            all_donors[d["ref"]]["countries"].add(code)
            all_donors[d["ref"]]["total"] += d["spend"]
            all_donors[d["ref"]]["name"] = d["name"]
    print(f"\n  Donors in 3+ countries (among each country's top 15):")
    for ref in sorted(all_donors, key=lambda r: -all_donors[r]["total"]):
        d = all_donors[ref]
        if len(d["countries"]) >= 3:
            print(f"    {d['name'][:45]:45s} ${d['total']/1e6:9.1f}M  ({len(d['countries'])}: {', '.join(sorted(d['countries']))})")
    for r in results.values():
        r["yearly_data"] = {str(k): v for k, v in r["yearly_data"].items()}
        r["yoy_changes"] = {str(k): v for k, v in r["yoy_changes"].items()}
        r["by_year"] = {str(k): v for k, v in r["by_year"].items()}
    json.dump(results, open(OUT, "w"), indent=1)
    print(f"\nSaved {OUT}")

if __name__ == "__main__":
    main()
