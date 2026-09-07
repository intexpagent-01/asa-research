#!/usr/bin/env python3
"""Fetch and analyze IATI aid data for a given country."""
import csv
import io
import sys
import json
import urllib.request
from collections import defaultdict

BASE = "https://datastore.codeforiati.org/api/1/access"

PAGE_SIZE = 500

def fetch_transactions(country_code, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(PAGE_SIZE, limit - offset)
        url = f"{BASE}/transaction.csv?recipient-country={country_code}&limit={batch}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        all_rows.extend(rows)
        print(f"  fetched {len(rows)} rows (offset {offset})")
        if len(rows) < batch:
            break
        offset += batch
    return all_rows

def analyze_sectors(rows):
    sector_totals = defaultdict(float)
    sector_counts = defaultdict(int)
    for row in rows:
        sector = row.get("sector") or row.get("sector-code") or "Unknown"
        try:
            val = float(row.get("transaction-value-USD") or row.get("transaction-value") or 0)
        except ValueError:
            val = 0
        sector_totals[sector] += val
        sector_counts[sector] += 1
    return sorted(sector_totals.items(), key=lambda x: -abs(x[1]))

def analyze_funders(rows):
    funder_totals = defaultdict(float)
    for row in rows:
        funder = row.get("reporting-org") or "Unknown"
        try:
            val = float(row.get("transaction-value-USD") or row.get("transaction-value") or 0)
        except ValueError:
            val = 0
        funder_totals[funder] += val
    return sorted(funder_totals.items(), key=lambda x: -abs(x[1]))

def analyze_years(rows):
    year_totals = defaultdict(float)
    for row in rows:
        date = row.get("transaction-date") or ""
        year = date[:4] if len(date) >= 4 else "Unknown"
        try:
            val = float(row.get("transaction-value-USD") or row.get("transaction-value") or 0)
        except ValueError:
            val = 0
        year_totals[year] += val
    return sorted(year_totals.items())

def fmt_usd(val):
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    if abs(val) >= 1e3:
        return f"${val/1e3:.0f}K"
    return f"${val:.0f}"

def main():
    country = sys.argv[1] if len(sys.argv) > 1 else "KE"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    print(f"Fetching up to {limit} transactions for {country}...")
    rows = fetch_transactions(country, limit)
    print(f"Got {len(rows)} transactions.\n")

    disbursements = [r for r in rows if r.get("transaction-type") in ("3", "4")]
    print(f"Disbursements/expenditures: {len(disbursements)}\n")

    print("=== Top Sectors (by USD volume) ===")
    for sector, total in analyze_sectors(disbursements)[:15]:
        print(f"  {fmt_usd(total):>10}  {sector}")

    print("\n=== Top Funders (by USD volume) ===")
    for funder, total in analyze_funders(disbursements)[:15]:
        print(f"  {fmt_usd(total):>10}  {funder}")

    print("\n=== Year Trend ===")
    for year, total in analyze_years(disbursements):
        bar = "█" * max(1, int(abs(total) / 1e7))
        print(f"  {year}: {fmt_usd(total):>10}  {bar}")

    if "--json" in sys.argv:
        output = {
            "country": country,
            "transaction_count": len(rows),
            "disbursement_count": len(disbursements),
            "top_sectors": [{"sector": s, "usd": t} for s, t in analyze_sectors(disbursements)[:15]],
            "top_funders": [{"funder": f, "usd": t} for f, t in analyze_funders(disbursements)[:15]],
        }
        with open(f"iati_{country.lower()}.json", "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to iati_{country.lower()}.json")

if __name__ == "__main__":
    main()
