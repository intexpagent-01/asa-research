#!/usr/bin/env python3
"""Explore climate finance data in IATI: Rio markers, sector codes, and reporting patterns."""
import csv
import io
import json
import sys
import urllib.request
from collections import defaultdict, Counter

BASE = "https://datastore.codeforiati.org/api/1/access"
PAGE_SIZE = 500

def fetch_activities(params, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(PAGE_SIZE, limit - offset)
        url = f"{BASE}/activity.csv?{params}&limit={batch}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8")
        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            break
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        all_rows.extend(rows)
        print(f"  fetched {len(rows)} rows (offset {offset})")
        if len(rows) < batch:
            break
        offset += batch
    return all_rows

def fetch_transactions(params, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(PAGE_SIZE, limit - offset)
        url = f"{BASE}/transaction.csv?{params}&limit={batch}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8")
        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            break
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        all_rows.extend(rows)
        print(f"  fetched {len(rows)} rows (offset {offset})")
        if len(rows) < batch:
            break
        offset += batch
    return all_rows

def explore_climate_sectors():
    """Fetch activities with climate-related DAC sector codes."""
    # DAC 5-digit codes related to climate:
    # 41010 - Environmental policy and admin management
    # 41020 - Biosphere protection
    # 41030 - Bio-diversity
    # 41040 - Site preservation
    # 41081 - Environmental education/training
    # 41082 - Environmental research
    # 23210 - Energy generation, renewable sources
    # 23220 - Energy generation, non-renewable sources
    # 23230 - Power generation/non-renewable sources (multiple)
    # 23240 - Solar energy
    # 23250 - Wind energy
    # 23260 - Marine energy
    # 23270 - Energy generation, other
    # 31310 - Fishing policy & admin management (adaptation)
    # 14015 - Water resources conservation
    # 14081 - Education and training in water supply and sanitation

    climate_sectors = [
        "41010", "41020", "41030", "41040", "41081", "41082",
        "23210", "23220", "23230", "23240", "23250", "23260", "23270",
        "14015"
    ]

    print("\n=== Climate-related activities by sector code ===")
    for code in ["41010", "23210", "23240"]:
        print(f"\nSector {code}:")
        rows = fetch_activities(f"sector={code}", limit=1000)
        if rows:
            print(f"  Total activities: {len(rows)}")
            orgs = Counter(r.get("reporting-org", "Unknown") for r in rows)
            print(f"  Reporting orgs: {len(orgs)}")
            for org, count in orgs.most_common(10):
                print(f"    {org}: {count}")

def explore_policy_markers():
    """Check what columns are available for policy markers (Rio markers)."""
    print("\n=== Checking available columns in activity data ===")
    rows = fetch_activities("sector=41010", limit=10)
    if rows:
        print(f"\nAvailable columns ({len(rows[0])} total):")
        for col in sorted(rows[0].keys()):
            sample = rows[0].get(col, "")
            if sample:
                print(f"  {col}: {sample[:80]}")
            else:
                print(f"  {col}: (empty)")

def explore_climate_keywords():
    """Search for activities mentioning climate in titles/descriptions."""
    print("\n=== Climate keyword search in activity titles ===")

    # Try fetching activities with keyword search
    keywords = ["climate", "adaptation", "mitigation", "renewable energy", "green climate"]

    for kw in keywords:
        print(f"\nKeyword '{kw}':")
        # The Code for IATI datastore supports title search
        rows = fetch_activities(f"title={kw}", limit=500)
        if rows:
            print(f"  Activities found: {len(rows)}")
            orgs = Counter(r.get("reporting-org", "Unknown") for r in rows)
            print(f"  Reporting orgs: {len(orgs)}")

            # Check date range
            years = []
            for r in rows:
                start = r.get("start-actual", "") or r.get("start-planned", "")
                if start and len(start) >= 4:
                    years.append(start[:4])
            if years:
                year_counts = Counter(years)
                print(f"  Year range: {min(years)} - {max(years)}")
                for y in sorted(year_counts.keys())[-5:]:
                    print(f"    {y}: {year_counts[y]} activities")

            # Sample titles
            print("  Sample titles:")
            for r in rows[:5]:
                title = r.get("title", "No title")
                org = r.get("reporting-org", "Unknown")
                print(f"    [{org}] {title[:100]}")
        else:
            print("  No results")

def explore_green_climate_fund():
    """Look at Green Climate Fund activities specifically."""
    print("\n=== Green Climate Fund activities ===")
    rows = fetch_activities("reporting-org=Green Climate Fund", limit=1000)
    if not rows:
        # Try by ref
        rows = fetch_activities("reporting-org.ref=47134", limit=1000)
    if not rows:
        rows = fetch_activities("title=Green Climate Fund", limit=500)

    if rows:
        print(f"  Total activities: {len(rows)}")
        # Check sectors
        sectors = Counter()
        for r in rows:
            s = r.get("sector", "") or r.get("sector-code", "")
            sectors[s] += 1
        print(f"  Sectors:")
        for s, c in sectors.most_common(15):
            print(f"    {s}: {c}")

        # Check countries
        countries = Counter()
        for r in rows:
            c = r.get("recipient-country", "") or r.get("recipient-country-code", "")
            countries[c] += 1
        print(f"  Recipient countries: {len(countries)}")
        for c, cnt in countries.most_common(10):
            print(f"    {c}: {cnt}")
    else:
        print("  No GCF activities found through these queries")

def explore_transaction_columns():
    """Check transaction-level data for climate markers."""
    print("\n=== Transaction columns for climate-sector activities ===")
    rows = fetch_transactions("sector=23210", limit=10)
    if rows:
        print(f"\nAvailable columns ({len(rows[0])} total):")
        for col in sorted(rows[0].keys()):
            sample = rows[0].get(col, "")
            if sample:
                print(f"  {col}: {sample[:100]}")

def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "sectors":
            explore_climate_sectors()
        elif cmd == "markers":
            explore_policy_markers()
        elif cmd == "keywords":
            explore_climate_keywords()
        elif cmd == "gcf":
            explore_green_climate_fund()
        elif cmd == "txn-cols":
            explore_transaction_columns()
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("Climate Finance Explorer")
        print("Commands: sectors, markers, keywords, gcf, txn-cols")
        print("\nRunning full exploration...\n")
        explore_policy_markers()
        explore_climate_keywords()
        explore_climate_sectors()

if __name__ == "__main__":
    main()
