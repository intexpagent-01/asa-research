#!/usr/bin/env python3
"""Temporal fragmentation analysis — how has the number of active
organizations in a country-sector changed over time?

Uses IATI activity start/end dates to reconstruct which organizations
were active in each year, then tracks entry, exit, and net change.
"""
import csv
import io
import json
import re
import sys
import urllib.request
from collections import defaultdict

BASE = "https://datastore.codeforiati.org/api/1/access"

DAC_SECTORS = {
    "111": "Education", "112": "Education", "113": "Education", "114": "Education",
    "121": "Health", "122": "Health", "123": "Health",
    "150": "Governance", "151": "Governance", "152": "Governance",
}


def map_sector(code_str):
    if not code_str:
        return None
    code = str(code_str).strip().split(";")[0].strip()
    for length in (3, 2):
        key = code[:length]
        if length == 2:
            key += "0"
        if key in DAC_SECTORS:
            return DAC_SECTORS[key]
    return None


def normalize_org(name):
    name = name.strip()
    name = re.sub(r'&#0*39;', "'", name)
    name = re.sub(r'&amp;', "&", name)
    norms = {
        "UK - Foreign, Commonwealth Development Office (FCDO)": "FCDO",
        "UK - Foreign, Commonwealth and Development Office": "FCDO",
        "Ministry for Foreign Affairs of Finland": "Finland MFA",
        "Ministry of Foreign Affairs, Finland": "Finland MFA",
    }
    return norms.get(name, name)


def extract_year(date_str):
    if not date_str or len(date_str) < 4:
        return None
    try:
        return int(date_str[:4])
    except ValueError:
        return None


def fetch_activities(country_code, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(500, limit - offset)
        url = f"{BASE}/activity.csv?recipient-country={country_code}&limit={batch}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.4"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8")
        except Exception as e:
            print(f"  Error at offset {offset}: {e}", file=sys.stderr)
            break
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch
    return all_rows


def analyze_temporal(country_code, target_sector, limit=5000, year_range=(2010, 2026)):
    print(f"\nFetching activities for {country_code}...", flush=True)
    rows = fetch_activities(country_code, limit)
    print(f"  Total: {len(rows)} activities")

    sector_rows = [r for r in rows if map_sector(r.get("sector-code", "")) == target_sector]
    print(f"  {target_sector}: {len(sector_rows)} activities")

    if not sector_rows:
        return None

    org_active_years = defaultdict(set)

    for r in sector_rows:
        org = normalize_org(r.get("reporting-org", ""))
        start = extract_year(r.get("start-actual", "") or r.get("start-planned", ""))
        end = extract_year(r.get("end-actual", "") or r.get("end-planned", ""))
        status = r.get("activity-status-code", "")

        if not start:
            continue

        if not end:
            if status in ("4", "5", "6"):
                end = start
            else:
                end = year_range[1]

        end = min(end, year_range[1])
        start = max(start, year_range[0])

        for y in range(start, end + 1):
            if year_range[0] <= y <= year_range[1]:
                org_active_years[org].add(y)

    yearly = {}
    for y in range(year_range[0], year_range[1] + 1):
        orgs_this_year = {org for org, years in org_active_years.items() if y in years}
        yearly[y] = orgs_this_year

    timeline = []
    prev_orgs = set()
    for y in range(year_range[0], year_range[1] + 1):
        current = yearly.get(y, set())
        entered = current - prev_orgs
        exited = prev_orgs - current
        timeline.append({
            "year": y,
            "count": len(current),
            "entered": len(entered),
            "exited": len(exited),
            "net": len(entered) - len(exited),
            "entered_names": sorted(entered)[:5],
            "exited_names": sorted(exited)[:5],
        })
        prev_orgs = current

    return {
        "country": country_code,
        "sector": target_sector,
        "timeline": timeline,
        "total_ever": len(org_active_years),
    }


def main():
    countries = ["UG", "KE", "RW", "TZ", "ET"]
    sectors = ["Governance", "Health"]

    results = {}

    for country in countries:
        for sector in sectors:
            print(f"\n{'='*60}")
            print(f"  {sector} in {country}")
            print(f"{'='*60}")
            result = analyze_temporal(country, sector)
            if result:
                key = f"{country}_{sector}"
                results[key] = result
                print(f"\n  Year   Orgs  Entered  Exited   Net")
                print(f"  ----   ----  -------  ------   ---")
                for t in result["timeline"]:
                    print(f"  {t['year']}   {t['count']:>4}   {t['entered']:>5}   {t['exited']:>5}   {t['net']:>+4}")

    if results:
        print(f"\n\n{'='*60}")
        print(f"  COMPARATIVE TEMPORAL SUMMARY")
        print(f"{'='*60}")

        print(f"\n  {'Pair':<20} {'2012':>5} {'2016':>5} {'2020':>5} {'2024':>5} {'Change':>8}")
        print(f"  {'-'*20} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*8}")
        for key, r in sorted(results.items()):
            tl = {t["year"]: t["count"] for t in r["timeline"]}
            c12 = tl.get(2012, 0)
            c16 = tl.get(2016, 0)
            c20 = tl.get(2020, 0)
            c24 = tl.get(2024, 0)
            change = c24 - c12 if c12 else 0
            pct = f"{change/c12*100:+.0f}%" if c12 else "n/a"
            print(f"  {key:<20} {c12:>5} {c16:>5} {c20:>5} {c24:>5} {pct:>8}")

    outfile = "research/temporal_fragmentation.json"
    with open(outfile, "w") as f:
        json.dump(results, f, indent=2, default=list)
    print(f"\nSaved to {outfile}")


if __name__ == "__main__":
    main()
