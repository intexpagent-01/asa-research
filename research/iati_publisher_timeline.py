#!/usr/bin/env python3
"""
Analyze IATI publisher growth over time and compare with
fragmentation trends to test the reporting-growth hypothesis.
"""
import json
import urllib.request
from collections import Counter
from datetime import datetime

def fetch_all_publishers():
    url = "https://iatiregistry.org/api/3/action/organization_list?all_fields=true&limit=3000"
    print(f"Fetching publishers from IATI Registry...")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())

    if not data.get("success"):
        raise RuntimeError("IATI Registry API returned failure")

    publishers = data["result"]
    print(f"  Total publishers returned: {len(publishers)}")
    return publishers


def analyze_publisher_timeline(publishers):
    by_year = Counter()
    missing_date = 0
    org_types = Counter()

    for pub in publishers:
        fpd = pub.get("publisher_first_publish_date")
        org_type = pub.get("publisher_organization_type", "unknown")
        org_types[org_type] += 1

        if not fpd:
            missing_date += 1
            continue
        try:
            year = int(fpd[:4])
            if 2005 <= year <= 2026:
                by_year[year] += 1
        except (ValueError, IndexError):
            missing_date += 1

    print(f"\n  Publishers with no first-publish date: {missing_date}")
    print(f"  Publishers with valid date: {len(publishers) - missing_date}")

    print("\n--- IATI Publisher Growth by Year ---")
    cumulative = 0
    yearly_data = {}
    for year in sorted(by_year.keys()):
        cumulative += by_year[year]
        yearly_data[year] = {"new": by_year[year], "cumulative": cumulative}
        print(f"  {year}: +{by_year[year]:4d} new publishers  (cumulative: {cumulative:5d})")

    print("\n--- Publisher Organization Types ---")
    for ot, count in org_types.most_common(15):
        print(f"  {ot}: {count}")

    return yearly_data, org_types


def analyze_publisher_countries(publishers):
    """Which publisher countries are most represented?"""
    countries = Counter()
    east_africa = {"KE": "Kenya", "UG": "Uganda", "RW": "Rwanda",
                   "TZ": "Tanzania", "ET": "Ethiopia"}
    ea_timeline = {code: Counter() for code in east_africa}

    for pub in publishers:
        country = pub.get("publisher_country", "")
        if country:
            countries[country] += 1

        fpd = pub.get("publisher_first_publish_date")
        if country in east_africa and fpd:
            try:
                year = int(fpd[:4])
                if 2005 <= year <= 2026:
                    ea_timeline[country][year] += 1
            except (ValueError, IndexError):
                pass

    print("\n--- Top 20 Publisher Countries ---")
    for c, count in countries.most_common(20):
        label = east_africa.get(c, c)
        marker = " <-- East Africa" if c in east_africa else ""
        print(f"  {c} ({label}): {count}{marker}")

    print("\n--- East African Publisher Growth ---")
    for code, name in sorted(east_africa.items()):
        timeline = ea_timeline[code]
        if timeline:
            cumul = 0
            years_str = []
            for year in sorted(timeline.keys()):
                cumul += timeline[year]
                years_str.append(f"{year}:+{timeline[year]}={cumul}")
            print(f"  {name} ({code}): {', '.join(years_str)}")
        else:
            print(f"  {name} ({code}): no publishers with dates")

    return countries, ea_timeline


def compute_growth_correlation(yearly_data):
    """Compare publisher growth rates with fragmentation growth from temporal analysis."""
    # From temporal_fragmentation.py results (Wake 7):
    # Average +155% growth in reported organizations 2012-2024
    # Growth phase: 2015-2020
    # These are the org counts from the temporal analysis for key pairs
    temporal_org_counts = {
        "UG-Governance": {2012: 30, 2016: 55, 2020: 75, 2024: 80},
        "KE-Governance": {2012: 25, 2016: 45, 2020: 65, 2024: 70},
        "UG-Health": {2012: 20, 2016: 35, 2020: 50, 2024: 55},
        "KE-Health": {2012: 18, 2016: 30, 2020: 45, 2024: 50},
    }

    print("\n--- Publisher Growth vs Fragmentation Growth ---")
    if yearly_data:
        # Growth from 2012 to 2020 (the main growth phase)
        c2012 = sum(v["new"] for y, v in yearly_data.items() if y <= 2012)
        c2015 = sum(v["new"] for y, v in yearly_data.items() if y <= 2015)
        c2020 = sum(v["new"] for y, v in yearly_data.items() if y <= 2020)
        c2024 = sum(v["new"] for y, v in yearly_data.items() if y <= 2024)

        if c2012 > 0:
            growth_12_20 = ((c2020 - c2012) / c2012) * 100
            growth_12_24 = ((c2024 - c2012) / c2012) * 100
            growth_15_20 = ((c2020 - c2015) / c2015) * 100 if c2015 > 0 else 0

            print(f"  IATI publisher growth 2012→2020: +{growth_12_20:.0f}%")
            print(f"  IATI publisher growth 2012→2024: +{growth_12_24:.0f}%")
            print(f"  IATI publisher growth 2015→2020: +{growth_15_20:.0f}%")
            print(f"  Fragmentation growth 2012→2024 (average): +155%")
            print()
            if growth_12_24 > 100:
                print("  FINDING: Publisher base grew substantially over the same period")
                print("  as reported fragmentation. This supports the hypothesis that")
                print("  apparent fragmentation growth is at least partly explained by")
                print("  IATI reporting expansion.")
            else:
                print("  FINDING: Publisher growth is modest compared to fragmentation")
                print("  growth, suggesting some real fragmentation increase.")


def main():
    publishers = fetch_all_publishers()
    yearly_data, org_types = analyze_publisher_timeline(publishers)
    countries, ea_timeline = analyze_publisher_countries(publishers)
    compute_growth_correlation(yearly_data)

    # Save raw data for further analysis
    output = {
        "total_publishers": len(publishers),
        "yearly_data": {str(k): v for k, v in yearly_data.items()},
        "org_types": dict(org_types),
        "top_countries": dict(countries.most_common(30)),
    }
    with open("/home/agent/agent/research/publisher_timeline_data.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nRaw data saved to publisher_timeline_data.json")


if __name__ == "__main__":
    main()
