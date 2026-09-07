#!/usr/bin/env python3
"""Analyze aid fragmentation across countries using IATI data.

Fragmentation = many small donors in the same sector/country, rather than
coordinated larger programs. High fragmentation increases transaction costs
for recipient governments and can reduce aid effectiveness.

Metrics:
- Herfindahl-Hirschman Index (HHI) per sector: concentration of funding
- Donor count per sector
- Average project size
- Cross-country comparison of sector allocation patterns
"""
import csv
import io
import json
import sys
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field

BASE = "https://datastore.codeforiati.org/api/1/access"
PAGE_SIZE = 500

SECTOR_MAP = {
    "111": "Education",
    "112": "Education",
    "113": "Education",
    "114": "Education",
    "121": "Health",
    "122": "Health",
    "123": "Health",
    "130": "Population/Reproductive",
    "131": "Population/Reproductive",
    "132": "Population/Reproductive",
    "140": "Water & Sanitation",
    "141": "Water & Sanitation",
    "142": "Water & Sanitation",
    "143": "Water & Sanitation",
    "150": "Government & Civil Society",
    "151": "Government & Civil Society",
    "152": "Government & Civil Society",
    "160": "Social Infrastructure",
    "161": "Social Infrastructure",
    "162": "Social Infrastructure",
    "163": "Social Infrastructure",
    "210": "Transport",
    "211": "Transport",
    "212": "Transport",
    "213": "Transport",
    "214": "Transport",
    "220": "Communications",
    "221": "Communications",
    "222": "Communications",
    "223": "Communications",
    "230": "Energy",
    "231": "Energy",
    "232": "Energy",
    "233": "Energy",
    "234": "Energy",
    "235": "Energy",
    "236": "Energy",
    "240": "Finance",
    "241": "Finance",
    "242": "Finance",
    "243": "Finance",
    "244": "Finance",
    "245": "Finance",
    "250": "Business",
    "251": "Business",
    "252": "Business",
    "253": "Business",
    "310": "Agriculture",
    "311": "Agriculture",
    "312": "Agriculture",
    "313": "Agriculture",
    "314": "Agriculture",
    "315": "Agriculture",
    "320": "Industry",
    "321": "Industry",
    "322": "Industry",
    "323": "Industry",
    "330": "Trade",
    "331": "Trade",
    "332": "Trade",
    "410": "Environment",
    "411": "Environment",
    "412": "Environment",
    "413": "Environment",
    "414": "Environment",
    "430": "Multisector",
    "431": "Multisector",
    "432": "Multisector",
    "433": "Multisector",
    "434": "Multisector",
    "510": "Budget Support",
    "520": "Food Aid",
    "530": "Debt",
    "600": "Humanitarian",
    "720": "Emergency",
    "730": "Reconstruction",
    "740": "Disaster Prevention",
    "910": "Admin Costs",
    "920": "Refugees",
    "930": "Refugees",
    "998": "Unallocated",
}


def sector_group(code_str):
    if not code_str:
        return "Unknown"
    code = code_str.strip().split(";")[0].strip()
    for prefix_len in (3,):
        key = code[:prefix_len]
        if key in SECTOR_MAP:
            return SECTOR_MAP[key]
    if code[:2].isdigit():
        key = code[:2] + "0"
        if key in SECTOR_MAP:
            return SECTOR_MAP[key]
    if code[:1].isdigit():
        key = code[:1] + "00"
        if key in SECTOR_MAP:
            return SECTOR_MAP[key]
    return code_str[:40] if len(code_str) > 40 else code_str


def fetch_transactions(country_code, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(PAGE_SIZE, limit - offset)
        url = (
            f"{BASE}/transaction.csv?"
            f"recipient-country={country_code}&limit={batch}&offset={offset}"
        )
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


def parse_disbursements(rows):
    return [r for r in rows if r.get("transaction-type") in ("3", "4")]


def compute_hhi(shares):
    return sum(s * s for s in shares)


def analyze_country(country_code, limit=5000):
    print(f"\n{'='*60}")
    print(f"  {country_code} — fetching up to {limit} transactions")
    print(f"{'='*60}")

    rows = fetch_transactions(country_code, limit)
    disb = parse_disbursements(rows)
    print(f"  Total transactions: {len(rows)}, disbursements/expenditures: {len(disb)}")

    sector_donors = defaultdict(lambda: defaultdict(float))
    sector_totals = defaultdict(float)
    donor_totals = defaultdict(float)
    year_totals = defaultdict(float)

    for r in disb:
        sector_code = r.get("sector-code") or r.get("sector") or ""
        sector = sector_group(sector_code)
        donor = r.get("reporting-org") or "Unknown"
        try:
            val = float(r.get("transaction-value-USD") or r.get("transaction-value") or 0)
        except ValueError:
            val = 0

        sector_donors[sector][donor] += val
        sector_totals[sector] += val
        donor_totals[donor] += val

        date = r.get("transaction-date") or ""
        year = date[:4] if len(date) >= 4 else "Unknown"
        year_totals[year] += val

    results = {
        "country": country_code,
        "total_transactions": len(rows),
        "disbursements": len(disb),
        "sectors": {},
        "donors": {},
        "years": dict(sorted(year_totals.items())),
    }

    total_all = sum(sector_totals.values())

    print(f"\n  {'Sector':<28} {'Volume':>12} {'Donors':>7} {'HHI':>8}  Concentration")
    print(f"  {'-'*28} {'-'*12} {'-'*7} {'-'*8}  {'-'*15}")

    for sector in sorted(sector_totals, key=lambda s: -abs(sector_totals[s])):
        donors_in_sector = sector_donors[sector]
        vol = sector_totals[sector]
        n_donors = len(donors_in_sector)

        if vol == 0:
            continue

        shares = [abs(v) / abs(vol) for v in donors_in_sector.values() if vol != 0]
        hhi = compute_hhi(shares)

        if hhi > 0.5:
            conc = "Highly concentrated"
        elif hhi > 0.25:
            conc = "Concentrated"
        elif hhi > 0.15:
            conc = "Moderate"
        else:
            conc = "Fragmented"

        results["sectors"][sector] = {
            "volume_usd": vol,
            "donor_count": n_donors,
            "hhi": round(hhi, 4),
            "concentration": conc,
            "top_donors": sorted(
                donors_in_sector.items(), key=lambda x: -abs(x[1])
            )[:5],
        }

        print(f"  {sector:<28} {fmt_usd(vol):>12} {n_donors:>7} {hhi:>8.4f}  {conc}")

    for donor in sorted(donor_totals, key=lambda d: -abs(donor_totals[d]))[:15]:
        results["donors"][donor] = donor_totals[donor]

    print(f"\n  Top donors:")
    for donor, vol in sorted(donor_totals.items(), key=lambda x: -abs(x[1]))[:10]:
        share = abs(vol) / abs(total_all) * 100 if total_all else 0
        print(f"    {fmt_usd(vol):>12} ({share:4.1f}%)  {donor[:50]}")

    return results


def fmt_usd(val):
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    if abs(val) >= 1e3:
        return f"${val/1e3:.0f}K"
    return f"${val:.0f}"


def cross_country_summary(all_results):
    print(f"\n{'='*60}")
    print(f"  CROSS-COUNTRY COMPARISON")
    print(f"{'='*60}")

    all_sectors = set()
    for r in all_results:
        all_sectors.update(r["sectors"].keys())

    major_sectors = set()
    for s in all_sectors:
        for r in all_results:
            if s in r["sectors"] and abs(r["sectors"][s]["volume_usd"]) > 1e6:
                major_sectors.add(s)
                break

    print(f"\n  Average HHI by sector (lower = more fragmented):")
    print(f"  {'Sector':<28}", end="")
    for r in all_results:
        print(f" {r['country']:>8}", end="")
    print()

    for sector in sorted(major_sectors):
        print(f"  {sector:<28}", end="")
        for r in all_results:
            if sector in r["sectors"]:
                hhi = r["sectors"][sector]["hhi"]
                print(f" {hhi:>8.3f}", end="")
            else:
                print(f" {'---':>8}", end="")
        print()

    print(f"\n  Donor count by sector:")
    print(f"  {'Sector':<28}", end="")
    for r in all_results:
        print(f" {r['country']:>8}", end="")
    print()

    for sector in sorted(major_sectors):
        print(f"  {sector:<28}", end="")
        for r in all_results:
            if sector in r["sectors"]:
                dc = r["sectors"][sector]["donor_count"]
                print(f" {dc:>8}", end="")
            else:
                print(f" {'---':>8}", end="")
        print()

    # Fragmentation summary
    print(f"\n  Fragmentation summary (sectors with HHI < 0.15):")
    for r in all_results:
        fragmented = [
            s for s, d in r["sectors"].items()
            if d["hhi"] < 0.15 and abs(d["volume_usd"]) > 1e6
        ]
        print(f"    {r['country']}: {len(fragmented)} fragmented sectors — {', '.join(fragmented[:5])}")


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else ["KE", "RW", "TZ", "UG", "ET"]
    limit = 3000

    all_results = []
    for cc in countries:
        result = analyze_country(cc, limit)
        all_results.append(result)

    if len(all_results) > 1:
        cross_country_summary(all_results)

    with open("research/fragmentation_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to research/fragmentation_results.json")


if __name__ == "__main__":
    main()
