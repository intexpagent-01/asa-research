#!/usr/bin/env python3
"""Activity-level aid fragmentation analysis across East African countries.

Uses IATI activity data to analyze:
1. How many organizations operate in each sector per country
2. Which donors appear across multiple countries (overlap)
3. Sector specialization vs. generalism among donors
4. Coordination density — how crowded sectors are
"""
import csv
import io
import json
import sys
import urllib.request
from collections import defaultdict

BASE = "https://datastore.codeforiati.org/api/1/access"

SECTOR_GROUP = {
    "111": "Education", "112": "Education", "113": "Education", "114": "Education",
    "121": "Health", "122": "Health", "123": "Health",
    "130": "Population/Reproductive", "131": "Population/Reproductive",
    "140": "Water & Sanitation", "141": "Water & Sanitation",
    "150": "Governance", "151": "Governance", "152": "Governance",
    "160": "Social Protection", "161": "Social Protection",
    "210": "Transport", "220": "Communications",
    "230": "Energy", "231": "Energy", "232": "Energy",
    "240": "Finance", "241": "Finance",
    "250": "Business", "251": "Business",
    "310": "Agriculture", "311": "Agriculture", "312": "Agriculture",
    "313": "Agriculture", "314": "Agriculture",
    "320": "Industry", "321": "Industry",
    "330": "Trade", "331": "Trade",
    "410": "Environment", "411": "Environment", "412": "Environment",
    "430": "Multisector", "431": "Multisector",
    "510": "Budget Support",
    "520": "Food Security",
    "600": "Humanitarian", "720": "Emergency", "730": "Reconstruction",
    "740": "Disaster Prevention",
}


def map_sector(code_str):
    if not code_str:
        return "Unspecified"
    code = str(code_str).strip().split(";")[0].strip()
    for length in (3, 2):
        key = code[:length]
        if length == 2:
            key += "0"
        if key in SECTOR_GROUP:
            return SECTOR_GROUP[key]
    return "Other"


def fetch_activities(country_code, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(500, limit - offset)
        url = f"{BASE}/activity.csv?recipient-country={country_code}&limit={batch}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.2"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8")
        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            break
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch
    return all_rows


def analyze_country(country_code, limit=5000):
    print(f"\nFetching {country_code}...", end=" ", flush=True)
    rows = fetch_activities(country_code, limit)
    print(f"{len(rows)} activities")

    sector_orgs = defaultdict(set)
    org_sectors = defaultdict(set)
    org_activity_count = defaultdict(int)
    sector_activity_count = defaultdict(int)
    org_types = {}

    for r in rows:
        org = r.get("reporting-org", "Unknown")
        org_type = r.get("reporting-org-type", "Unknown")
        sector_code = r.get("sector-code", "")
        sector = map_sector(sector_code)

        sector_orgs[sector].add(org)
        org_sectors[org].add(sector)
        org_activity_count[org] += 1
        sector_activity_count[sector] += 1
        org_types[org] = org_type

    return {
        "country": country_code,
        "total_activities": len(rows),
        "total_orgs": len(org_activity_count),
        "sector_orgs": {s: sorted(orgs) for s, orgs in sector_orgs.items()},
        "sector_org_count": {s: len(orgs) for s, orgs in sector_orgs.items()},
        "sector_activity_count": dict(sector_activity_count),
        "org_sectors": {o: sorted(secs) for o, secs in org_sectors.items()},
        "org_activity_count": dict(org_activity_count),
        "org_types": org_types,
    }


def print_sector_crowding(results):
    print(f"\n{'='*70}")
    print(f"  SECTOR CROWDING — organizations per sector")
    print(f"{'='*70}")

    all_sectors = set()
    for r in results:
        for s, c in r["sector_org_count"].items():
            if c >= 3:
                all_sectors.add(s)

    print(f"\n  {'Sector':<22}", end="")
    for r in results:
        print(f" {r['country']:>6}", end="")
    print()
    print(f"  {'-'*22}", end="")
    for _ in results:
        print(f" {'-'*6}", end="")
    print()

    for sector in sorted(all_sectors):
        print(f"  {sector:<22}", end="")
        for r in results:
            count = r["sector_org_count"].get(sector, 0)
            print(f" {count:>6}", end="")
        print()


def print_donor_overlap(results):
    print(f"\n{'='*70}")
    print(f"  DONOR OVERLAP — organizations active in multiple countries")
    print(f"{'='*70}")

    org_countries = defaultdict(set)
    for r in results:
        for org in r["org_activity_count"]:
            org_countries[org].add(r["country"])

    multi_country = {
        org: countries
        for org, countries in org_countries.items()
        if len(countries) >= 3
    }

    by_count = sorted(multi_country.items(), key=lambda x: (-len(x[1]), x[0]))

    print(f"\n  Organizations in 3+ countries ({len(by_count)} total):\n")
    print(f"  {'Organization':<55} {'Countries':>10}  Present in")
    print(f"  {'-'*55} {'-'*10}  {'-'*20}")

    for org, countries in by_count[:30]:
        ccs = ", ".join(sorted(countries))
        print(f"  {org[:55]:<55} {len(countries):>10}  {ccs}")

    return multi_country


def print_specialization(results):
    print(f"\n{'='*70}")
    print(f"  DONOR SPECIALIZATION vs. GENERALISM")
    print(f"{'='*70}")

    all_org_sectors = defaultdict(set)
    all_org_activities = defaultdict(int)
    all_org_types = {}

    for r in results:
        for org, secs in r["org_sectors"].items():
            all_org_sectors[org].update(secs)
            all_org_activities[org] += r["org_activity_count"][org]
            all_org_types[org] = r["org_types"].get(org, "?")

    specialists = []
    generalists = []

    for org, sectors in all_org_sectors.items():
        if all_org_activities[org] < 10:
            continue
        if len(sectors) <= 2:
            specialists.append((org, sectors, all_org_activities[org]))
        elif len(sectors) >= 5:
            generalists.append((org, sectors, all_org_activities[org]))

    print(f"\n  Specialists (1-2 sectors, 10+ activities):")
    for org, secs, count in sorted(specialists, key=lambda x: -x[2])[:15]:
        print(f"    {count:>5} activities  {org[:45]:<45}  → {', '.join(sorted(secs))}")

    print(f"\n  Generalists (5+ sectors, 10+ activities):")
    for org, secs, count in sorted(generalists, key=lambda x: -x[2])[:15]:
        print(f"    {count:>5} activities  {org[:45]:<45}  → {len(secs)} sectors")


def print_coordination_density(results):
    print(f"\n{'='*70}")
    print(f"  COORDINATION DENSITY — activities per org per sector")
    print(f"{'='*70}")

    print(f"\n  High-density sectors (many orgs, many activities = coordination challenge):\n")
    print(f"  {'Country':<6} {'Sector':<22} {'Orgs':>5} {'Activities':>10} {'Act/Org':>8}")
    print(f"  {'-'*6} {'-'*22} {'-'*5} {'-'*10} {'-'*8}")

    for r in results:
        sectors = []
        for sector, org_count in r["sector_org_count"].items():
            act_count = r["sector_activity_count"].get(sector, 0)
            if org_count >= 5 and act_count >= 20:
                sectors.append((sector, org_count, act_count))

        for sector, orgs, acts in sorted(sectors, key=lambda x: -x[1]):
            ratio = acts / orgs if orgs > 0 else 0
            print(f"  {r['country']:<6} {sector:<22} {orgs:>5} {acts:>10} {ratio:>8.1f}")


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else ["KE", "RW", "TZ", "UG", "ET"]

    results = []
    for cc in countries:
        results.append(analyze_country(cc, 5000))

    print_sector_crowding(results)
    print_donor_overlap(results)
    print_specialization(results)
    print_coordination_density(results)

    with open("research/activity_fragmentation.json", "w") as f:
        json.dump(results, f, indent=2, default=list)
    print(f"\nResults saved to research/activity_fragmentation.json")


if __name__ == "__main__":
    main()
