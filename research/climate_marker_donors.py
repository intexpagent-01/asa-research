#!/usr/bin/env python3
"""Analyze which donors use climate Rio markers and which don't."""
import csv
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter

BASE = "https://datastore.codeforiati.org/api/1/access"

def fetch_xml_activities(params, limit=500):
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
        except ET.ParseError:
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
        ro_ref = ""
        ro_tag = act.find('reporting-org')
        if ro_tag is not None:
            ro_ref = ro_tag.get('ref', '')

        markers = {}
        for pm in act.findall('policy-marker'):
            code = pm.get('code', '')
            sig = pm.get('significance', '')
            markers[code] = sig

        activities.append({
            "id": iati_id,
            "title": title,
            "reporting_org": reporting_org,
            "reporting_org_ref": ro_ref,
            "policy_markers": markers,
        })

    return activities


def analyze_donor_markers(country_code):
    """For a given country, check which donors use climate markers."""
    print(f"\n=== Donor Rio Marker Usage: {country_code} ===")
    print(f"(Checking environmental-sector activities)\n")

    # Fetch a larger sample from environmental sectors
    all_activities = []
    for sector in ["41010", "41020", "41030", "23210", "23240"]:
        acts = fetch_xml_activities(
            f"recipient-country={country_code}&sector={sector}", limit=500
        )
        all_activities.extend(acts)
        print(f"  Sector {sector}: {len(acts)} activities")

    # Deduplicate by ID
    seen = set()
    unique = []
    for a in all_activities:
        if a["id"] not in seen:
            seen.add(a["id"])
            unique.append(a)
    print(f"\n  Total unique activities: {len(unique)}")

    # Analyze by donor
    donor_stats = defaultdict(lambda: {
        "total": 0,
        "has_any_marker": 0,
        "climate_mit": 0,
        "climate_adp": 0,
        "marker_present_but_zero": 0,
    })

    for act in unique:
        org = act["reporting_org"] or act["reporting_org_ref"]
        donor_stats[org]["total"] += 1

        has_any = len(act["policy_markers"]) > 0
        if has_any:
            donor_stats[org]["has_any_marker"] += 1

        mit_sig = act["policy_markers"].get("6", None)
        adp_sig = act["policy_markers"].get("7", None)

        if mit_sig in ("1", "2"):
            donor_stats[org]["climate_mit"] += 1
        if adp_sig in ("1", "2"):
            donor_stats[org]["climate_adp"] += 1
        if mit_sig == "0" or adp_sig == "0":
            donor_stats[org]["marker_present_but_zero"] += 1

    # Sort by total activities
    sorted_donors = sorted(donor_stats.items(), key=lambda x: -x[1]["total"])

    print(f"\n{'Donor':<45} {'Total':>5} {'Has M':>5} {'Mit':>4} {'Adp':>4} {'Zero':>4} {'%filled':>7}")
    print("-" * 80)

    marker_users = 0
    marker_non_users = 0

    for org, stats in sorted_donors:
        if stats["total"] < 3:
            continue
        pct = 100 * stats["has_any_marker"] / stats["total"]
        print(f"{org[:44]:<45} {stats['total']:>5} {stats['has_any_marker']:>5} {stats['climate_mit']:>4} {stats['climate_adp']:>4} {stats['marker_present_but_zero']:>4} {pct:>6.0f}%")
        if pct > 50:
            marker_users += stats["total"]
        else:
            marker_non_users += stats["total"]

    print(f"\n  Activities from marker-using donors (>50% fill): {marker_users}")
    print(f"  Activities from non-marker donors (≤50% fill): {marker_non_users}")
    print(f"  → {100*marker_non_users/max(marker_users+marker_non_users,1):.0f}% of activities can't be counted by Rio markers")

    return dict(donor_stats)


def cross_country_donor_comparison():
    """Compare donor marker usage across countries."""
    print("\n" + "="*60)
    print("CROSS-COUNTRY DONOR MARKER COMPARISON")
    print("="*60)

    countries = [("KE", "Kenya"), ("UG", "Uganda"), ("ET", "Ethiopia")]

    all_donor_data = {}
    for cc, name in countries:
        print(f"\n--- {name} ---")
        stats = analyze_donor_markers(cc)
        all_donor_data[cc] = stats

    # Find donors active in multiple countries
    all_donors = set()
    for cc, stats in all_donor_data.items():
        all_donors.update(stats.keys())

    print("\n\n=== DONORS ACTIVE IN MULTIPLE COUNTRIES ===")
    print(f"{'Donor':<45}", end="")
    for cc, _ in countries:
        print(f" {cc:>10}", end="")
    print(f" {'Marker?':>8}")

    multi_country = []
    for donor in all_donors:
        presence = []
        for cc, _ in countries:
            if donor in all_donor_data[cc]:
                presence.append(cc)
        if len(presence) >= 2:
            multi_country.append((donor, presence))

    for donor, presence in sorted(multi_country, key=lambda x: -len(x[1])):
        line = f"{donor[:44]:<45}"
        uses_markers = []
        for cc, _ in countries:
            if cc in presence:
                stats = all_donor_data[cc][donor]
                pct = 100 * stats["has_any_marker"] / max(stats["total"], 1)
                line += f" {stats['total']:>4}({pct:.0f}%)"
                uses_markers.append(pct > 50)
            else:
                line += f" {'—':>10}"
        consistent = "Yes" if all(uses_markers) else ("No" if not any(uses_markers) else "Mixed")
        line += f" {consistent:>8}"
        print(line)


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python climate_marker_donors.py KE          # Single country analysis")
        print("  python climate_marker_donors.py cross       # Cross-country comparison")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "cross":
        cross_country_donor_comparison()
    else:
        analyze_donor_markers(cmd)


if __name__ == "__main__":
    main()
