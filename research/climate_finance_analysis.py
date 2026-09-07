#!/usr/bin/env python3
"""
Climate finance measurement analysis: how different definitions produce different numbers.

Three approaches to identifying "climate finance" in IATI:
1. Sector codes — DAC 5-digit codes for environmental/energy sectors
2. Keyword search — "climate" etc. in activity titles/descriptions
3. Policy markers — Rio markers (climate mitigation/adaptation) with significance levels

The central question: do these approaches agree? How much does the measurement
choice shape the "how much climate finance?" answer?
"""
import csv
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter

BASE = "https://datastore.codeforiati.org/api/1/access"
PAGE_SIZE = 500

CLIMATE_SECTORS = {
    "23210": "Energy generation, renewable sources",
    "23220": "Energy generation, non-renewable sources",
    "23230": "Power generation/non-renewable sources",
    "23240": "Solar energy for centralised grids",
    "23250": "Wind energy",
    "23260": "Marine energy",
    "23270": "Energy generation, other",
    "41010": "Environmental policy and admin management",
    "41020": "Biosphere protection",
    "41030": "Bio-diversity",
    "41040": "Site preservation",
    "41081": "Environmental education/training",
    "41082": "Environmental research",
    "14015": "Water resources conservation",
    "23631": "Electric power transmission and distribution (efficiency)",
    "23110": "Energy policy and admin management",
}

STRICTLY_CLIMATE_SECTORS = {
    "23210", "23240", "23250", "23260",
    "41010", "41020", "41030",
}

CLIMATE_KEYWORDS = [
    "climate", "adaptation", "mitigation", "renewable energy",
    "solar", "wind energy", "green climate", "carbon",
    "resilience", "greenhouse", "low.carbon", "clean energy",
    "climate.change", "drought", "flood.risk",
]

def fetch_csv(endpoint, params, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(PAGE_SIZE, limit - offset)
        url = f"{BASE}/{endpoint}.csv?{params}&limit={batch}&offset={offset}"
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
        if len(rows) < batch:
            break
        offset += batch
    return all_rows

def fetch_xml_activities(params, limit=100):
    """Fetch activities as XML to get policy markers."""
    url = f"{BASE}/activity.xml?{params}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  XML fetch error: {e}")
        return []

    activities = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        text_clean = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', text)
        try:
            root = ET.fromstring(text_clean)
        except ET.ParseError as e:
            print(f"  XML parse error: {e}")
            return []

    for act in root.findall('.//iati-activity'):
        iati_id = ""
        id_elem = act.find('iati-identifier')
        if id_elem is not None and id_elem.text:
            iati_id = id_elem.text.strip()

        title = ""
        title_elem = act.find('.//title/narrative')
        if title_elem is not None and title_elem.text:
            title = title_elem.text.strip()

        reporting_org = ""
        ro_elem = act.find('.//reporting-org/narrative')
        if ro_elem is not None and ro_elem.text:
            reporting_org = ro_elem.text.strip()

        markers = {}
        for pm in act.findall('policy-marker'):
            code = pm.get('code', '')
            sig = pm.get('significance', '')
            markers[code] = sig

        sectors = []
        for sec in act.findall('sector'):
            code = sec.get('code', '')
            pct = sec.get('percentage', '100')
            sectors.append((code, pct))

        status = ""
        status_elem = act.find('activity-status')
        if status_elem is not None:
            status = status_elem.get('code', '')

        activities.append({
            "id": iati_id,
            "title": title,
            "reporting_org": reporting_org,
            "policy_markers": markers,
            "sectors": sectors,
            "status": status,
        })

    return activities


def approach1_sector_codes(country_code):
    """Count climate-related activities by DAC sector codes."""
    print(f"\n=== APPROACH 1: Sector Codes ({country_code}) ===")
    results = {}
    total_activities = 0

    for code, label in sorted(CLIMATE_SECTORS.items()):
        rows = fetch_csv("activity", f"recipient-country={country_code}&sector={code}", limit=5000)
        if rows:
            orgs = set(r.get("reporting-org", "") for r in rows)
            commitment = sum(float(r.get("total-Commitment-USD", 0) or 0) for r in rows)
            disbursement = sum(float(r.get("total-Disbursement-USD", 0) or 0) for r in rows)
            results[code] = {
                "label": label,
                "activities": len(rows),
                "orgs": len(orgs),
                "commitment_usd": commitment,
                "disbursement_usd": disbursement,
            }
            total_activities += len(rows)
            print(f"  {code} {label}: {len(rows)} activities, {len(orgs)} orgs, ${commitment/1e6:.1f}M committed, ${disbursement/1e6:.1f}M disbursed")
        else:
            print(f"  {code} {label}: 0 activities")

    print(f"\n  TOTAL: {total_activities} activities across {len(results)} sectors")
    return results


def approach2_keywords(country_code):
    """Count activities with climate keywords in titles."""
    print(f"\n=== APPROACH 2: Keyword Search ({country_code}) ===")
    all_ids = set()
    keyword_hits = {}

    for kw in CLIMATE_KEYWORDS:
        if " " in kw or "." in kw:
            continue
        rows = fetch_csv("activity", f"recipient-country={country_code}&title={kw}", limit=2000)
        if rows:
            ids = set(r.get("iati-identifier", "") for r in rows)
            new_ids = ids - all_ids
            all_ids.update(ids)
            keyword_hits[kw] = {
                "total": len(rows),
                "unique_new": len(new_ids),
            }
            orgs = set(r.get("reporting-org", "") for r in rows)
            commitment = sum(float(r.get("total-Commitment-USD", 0) or 0) for r in rows)
            print(f"  '{kw}': {len(rows)} activities ({len(new_ids)} new), {len(orgs)} orgs, ${commitment/1e6:.1f}M")
        else:
            print(f"  '{kw}': 0 activities")

    print(f"\n  UNIQUE TOTAL: {len(all_ids)} distinct activities")
    return keyword_hits, all_ids


def approach3_policy_markers(country_code):
    """Check policy markers (Rio markers) via XML API."""
    print(f"\n=== APPROACH 3: Policy Markers / Rio Markers ({country_code}) ===")

    # Fetch a sample of activities from climate-relevant sectors via XML
    marker_stats = {
        "6": {"label": "Climate Mitigation", "not_targeted": 0, "significant": 0, "principal": 0, "missing": 0},
        "7": {"label": "Climate Adaptation", "not_targeted": 0, "significant": 0, "principal": 0, "missing": 0},
    }

    total_checked = 0

    for sector_code in ["41010", "23210", "23240"]:
        print(f"\n  Checking sector {sector_code} ({CLIMATE_SECTORS.get(sector_code, '')})...")
        activities = fetch_xml_activities(
            f"recipient-country={country_code}&sector={sector_code}", limit=200
        )
        total_checked += len(activities)
        print(f"    Fetched {len(activities)} activities")

        for act in activities:
            for marker_code in ["6", "7"]:
                if marker_code in act["policy_markers"]:
                    sig = act["policy_markers"][marker_code]
                    if sig == "0":
                        marker_stats[marker_code]["not_targeted"] += 1
                    elif sig == "1":
                        marker_stats[marker_code]["significant"] += 1
                    elif sig == "2":
                        marker_stats[marker_code]["principal"] += 1
                else:
                    marker_stats[marker_code]["missing"] += 1

    print(f"\n  Policy marker results ({total_checked} activities checked):")
    for code, stats in marker_stats.items():
        total_tagged = stats["significant"] + stats["principal"]
        print(f"    Code {code} ({stats['label']}):")
        print(f"      Principal (2): {stats['principal']}")
        print(f"      Significant (1): {stats['significant']}")
        print(f"      Not targeted (0): {stats['not_targeted']}")
        print(f"      Missing: {stats['missing']}")
        print(f"      → Tagged as climate-relevant: {total_tagged}/{total_checked} ({100*total_tagged/max(total_checked,1):.0f}%)")

    return marker_stats, total_checked


def compare_approaches(country_code):
    """Run all three approaches and compare."""
    print(f"\n{'='*60}")
    print(f"CLIMATE FINANCE MEASUREMENT COMPARISON: {country_code}")
    print(f"{'='*60}")

    r1 = approach1_sector_codes(country_code)
    r2_hits, r2_ids = approach2_keywords(country_code)
    r3_stats, r3_total = approach3_policy_markers(country_code)

    print(f"\n{'='*60}")
    print(f"SUMMARY: {country_code}")
    print(f"{'='*60}")

    sector_count = sum(v["activities"] for v in r1.values())
    sector_commitment = sum(v["commitment_usd"] for v in r1.values())

    print(f"  Approach 1 (Sector codes):   {sector_count} activities, ${sector_commitment/1e6:.1f}M committed")
    print(f"  Approach 2 (Keywords):        {len(r2_ids)} unique activities")

    if r3_total > 0:
        mit_tagged = r3_stats["6"]["significant"] + r3_stats["6"]["principal"]
        adp_tagged = r3_stats["7"]["significant"] + r3_stats["7"]["principal"]
        print(f"  Approach 3 (Rio markers):     {mit_tagged} mitigation + {adp_tagged} adaptation tagged (of {r3_total} checked)")
        print(f"    → {100*(mit_tagged+adp_tagged)/max(r3_total,1):.0f}% of climate-sector activities have a climate Rio marker")


def multi_country_comparison(countries):
    """Compare climate finance identification across multiple countries."""
    print(f"\n{'='*60}")
    print(f"MULTI-COUNTRY CLIMATE FINANCE MEASUREMENT")
    print(f"{'='*60}")

    summary = []
    for cc, name in countries:
        print(f"\n--- {name} ({cc}) ---")

        # Sector-code count
        total_sector = 0
        total_commitment = 0
        for code in STRICTLY_CLIMATE_SECTORS:
            rows = fetch_csv("activity", f"recipient-country={cc}&sector={code}", limit=5000)
            total_sector += len(rows)
            total_commitment += sum(float(r.get("total-Commitment-USD", 0) or 0) for r in rows)

        # Keyword count (just 'climate')
        kw_rows = fetch_csv("activity", f"recipient-country={cc}&title=climate", limit=2000)
        kw_count = len(kw_rows)

        # Policy marker sample
        xml_acts = fetch_xml_activities(f"recipient-country={cc}&sector=41010", limit=100)
        mit_tagged = sum(1 for a in xml_acts if a["policy_markers"].get("6", "0") in ("1", "2"))
        adp_tagged = sum(1 for a in xml_acts if a["policy_markers"].get("7", "0") in ("1", "2"))

        summary.append({
            "country": name,
            "code": cc,
            "sector_activities": total_sector,
            "sector_commitment_m": total_commitment / 1e6,
            "keyword_activities": kw_count,
            "xml_checked": len(xml_acts),
            "mitigation_tagged": mit_tagged,
            "adaptation_tagged": adp_tagged,
        })

        print(f"  Sectors: {total_sector} activities, ${total_commitment/1e6:.1f}M")
        print(f"  Keywords ('climate'): {kw_count}")
        print(f"  Rio markers: {mit_tagged} mit + {adp_tagged} adp (of {len(xml_acts)} env-policy checked)")

    print(f"\n{'='*60}")
    print("COMPARISON TABLE")
    print(f"{'='*60}")
    print(f"{'Country':<20} {'Sector':>8} {'$M Commit':>10} {'Keyword':>8} {'Env chk':>8} {'Mit':>4} {'Adp':>4} {'% tagged':>8}")
    for s in summary:
        pct = 100 * (s["mitigation_tagged"] + s["adaptation_tagged"]) / max(s["xml_checked"], 1)
        print(f"{s['country']:<20} {s['sector_activities']:>8} {s['sector_commitment_m']:>10.1f} {s['keyword_activities']:>8} {s['xml_checked']:>8} {s['mitigation_tagged']:>4} {s['adaptation_tagged']:>4} {pct:>7.0f}%")

    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python climate_finance_analysis.py compare KE     # Full comparison for Kenya")
        print("  python climate_finance_analysis.py multi          # Multi-country comparison")
        print("  python climate_finance_analysis.py sectors KE     # Sector codes only")
        print("  python climate_finance_analysis.py keywords KE    # Keyword search only")
        print("  python climate_finance_analysis.py markers KE     # Policy markers only")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "compare":
        cc = sys.argv[2] if len(sys.argv) > 2 else "KE"
        compare_approaches(cc)

    elif cmd == "multi":
        countries = [
            ("KE", "Kenya"),
            ("UG", "Uganda"),
            ("RW", "Rwanda"),
            ("TZ", "Tanzania"),
            ("ET", "Ethiopia"),
        ]
        multi_country_comparison(countries)

    elif cmd == "sectors":
        cc = sys.argv[2] if len(sys.argv) > 2 else "KE"
        approach1_sector_codes(cc)

    elif cmd == "keywords":
        cc = sys.argv[2] if len(sys.argv) > 2 else "KE"
        approach2_keywords(cc)

    elif cmd == "markers":
        cc = sys.argv[2] if len(sys.argv) > 2 else "KE"
        approach3_policy_markers(cc)

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
