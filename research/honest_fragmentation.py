#!/usr/bin/env python3
"""Honest fragmentation analysis — decomposing apparent fragmentation.

Takes a country and sector and produces a multi-perspective analysis
that separates genuine coordination challenges from data artifacts.

Addresses: unit of analysis, subsector disaggregation, org deduplication,
activity status, financial concentration, and coordination signals.
"""
import csv
import io
import json
import re
import sys
import urllib.request
from collections import defaultdict, Counter

BASE = "https://datastore.codeforiati.org/api/1/access"

DAC_SECTORS = {
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
    "510": "Budget Support", "520": "Food Security",
    "600": "Humanitarian", "720": "Emergency",
    "730": "Reconstruction", "740": "Disaster Prevention",
}

GOVERNANCE_THEMES = {
    "Civil society & democracy": {"15150", "15151", "15152", "15153", "151"},
    "Human rights & gender": {"15160", "15164", "15170", "15180", "15261"},
    "Government capacity": {"15110", "15111", "15112", "15113", "15114",
                            "15116", "15117", "15119", "15120", "15123",
                            "15126", "15127", "15129", "15131", "15134",
                            "15142", "15155", "15185", "15196"},
    "Justice": {"15130"},
    "Peace & security": {"15190", "15210", "15220", "15230", "15240", "15250"},
}

STATUS_MAP = {
    "1": "Pipeline", "2": "Active", "3": "Finalising",
    "4": "Closed", "5": "Cancelled", "6": "Suspended",
}

COORD_KEYWORDS = [
    "joint", "pooled", "basket", "multi-donor", "sector-wide",
    "swap", "coordinated", "harmoni", "division of labour",
    "donor coordination", "development partner",
]


def map_sector(code_str):
    if not code_str:
        return "Unspecified"
    code = str(code_str).strip().split(";")[0].strip()
    for length in (3, 2):
        key = code[:length]
        if length == 2:
            key += "0"
        if key in DAC_SECTORS:
            return DAC_SECTORS[key]
    return "Other"


def classify_governance_theme(code_str):
    code = str(code_str).strip().split(";")[0].strip()
    for theme, codes in GOVERNANCE_THEMES.items():
        if code in codes:
            return theme
    return "Other governance"


def normalize_org_name(name):
    """Normalize org names to reduce duplicates."""
    name = name.strip()
    name = re.sub(r'&#0*39;', "'", name)
    name = re.sub(r'&amp;#0*39;', "'", name)
    name = re.sub(r'&#38;', "&", name)
    name = re.sub(r'&amp;', "&", name)

    normalizations = {
        "UK - Foreign, Commonwealth Development Office (FCDO)": "FCDO",
        "UK - Foreign, Commonwealth and Development Office": "FCDO",
        "MERCY CORPS EUROPE": "Mercy Corps Europe",
        "Ministry for Foreign Affairs of Finland": "Finland MFA",
        "Ministry of Foreign Affairs, Finland": "Finland MFA",
    }
    return normalizations.get(name, name)


def fetch_activities(country_code, limit=5000):
    all_rows = []
    offset = 0
    while offset < limit:
        batch = min(500, limit - offset)
        url = f"{BASE}/activity.csv?recipient-country={country_code}&limit={batch}&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "asa-research/0.3"})
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


SECTOR_MISMATCH_KEYWORDS = {
    "Governance": [
        "forestry", "hiv", "aids", "malaria", "vaccination", "immuniz",
        "primary school", "literacy", "water supply", "sanitation",
        "agriculture", "farming", "crop", "livestock", "fisheries",
        "mining", "petroleum", "electricity", "road construction",
        "bridge construction", "railway",
    ],
    "Health": [
        "road construction", "bridge", "railway", "mining", "petroleum",
        "forestry", "timber", "trade policy", "customs", "tariff",
        "election", "parliamentary", "legislature", "judiciary",
        "primary school", "secondary school", "university", "scholarship",
        "curriculum", "textbook",
    ],
    "Education": [
        "hiv", "aids", "malaria", "vaccination", "immuniz", "hospital",
        "clinic", "road construction", "bridge", "railway", "mining",
        "petroleum", "election", "parliamentary", "judiciary",
        "forestry", "timber", "fisheries", "trade policy", "customs",
    ],
}

GENERIC_MISMATCH = [
    "forestry", "hiv", "aids", "malaria", "vaccination", "immuniz",
    "primary school", "literacy", "water supply", "sanitation",
    "agriculture", "farming", "crop", "livestock",
]


def detect_miscoding(activities, sector=None):
    """Flag activities where sector code doesn't match title content."""
    flags = []
    keywords = SECTOR_MISMATCH_KEYWORDS.get(sector, GENERIC_MISMATCH)
    for a in activities:
        title = (a.get("title", "") + " " + a.get("description", "")).lower()
        for kw in keywords:
            if kw in title:
                flags.append({
                    "org": a.get("reporting-org", ""),
                    "title": a.get("title", "")[:100],
                    "keyword": kw,
                    "sector_code": a.get("sector-code", ""),
                })
                break
    return flags


def detect_coordination(activities):
    """Find activities that mention coordination mechanisms."""
    found = []
    for a in activities:
        text = (a.get("title", "") + " " + a.get("description", "")).lower()
        for kw in COORD_KEYWORDS:
            if kw in text:
                found.append({
                    "org": a.get("reporting-org", ""),
                    "title": a.get("title", "")[:100],
                    "keyword": kw,
                })
                break
    return found


def analyze(country_code, target_sector, limit=5000):
    print(f"\n{'='*70}")
    print(f"  HONEST FRAGMENTATION ANALYSIS: {target_sector} in {country_code}")
    print(f"{'='*70}")

    print(f"\nFetching activities...", end=" ", flush=True)
    rows = fetch_activities(country_code, limit)
    print(f"{len(rows)} total activities")

    # Filter to target sector
    sector_rows = [r for r in rows if map_sector(r.get("sector-code", "")) == target_sector]
    print(f"{target_sector} activities: {len(sector_rows)}")

    if not sector_rows:
        print("No activities found for this sector.")
        return

    # === LAYER 1: Raw counts (what naive analysis produces) ===
    raw_orgs = set(r.get("reporting-org", "") for r in sector_rows)
    print(f"\n--- LAYER 1: RAW COUNTS (naive analysis) ---")
    print(f"  Organizations: {len(raw_orgs)}")
    print(f"  Activities: {len(sector_rows)}")

    # === LAYER 2: After deduplication ===
    dedup_orgs = set(normalize_org_name(r.get("reporting-org", "")) for r in sector_rows)
    print(f"\n--- LAYER 2: AFTER ORG NAME DEDUPLICATION ---")
    print(f"  Organizations: {len(dedup_orgs)} (was {len(raw_orgs)})")
    merged = len(raw_orgs) - len(dedup_orgs)
    if merged:
        print(f"  {merged} duplicate org name(s) merged")

    # === LAYER 3: After status filtering (active only) ===
    active_rows = [r for r in sector_rows
                   if r.get("activity-status-code", "") in ("1", "2", "3")]
    active_orgs = set(normalize_org_name(r.get("reporting-org", "")) for r in active_rows)
    closed = len(sector_rows) - len(active_rows)
    print(f"\n--- LAYER 3: ACTIVE ACTIVITIES ONLY ---")
    print(f"  Organizations: {len(active_orgs)} (was {len(dedup_orgs)})")
    print(f"  Activities: {len(active_rows)} (removed {closed} closed/cancelled)")

    # === LAYER 4: Subsector disaggregation (governance only) ===
    if target_sector == "Governance":
        print(f"\n--- LAYER 4: THEMATIC DISAGGREGATION ---")
        theme_orgs = defaultdict(set)
        theme_acts = defaultdict(int)
        theme_usd = defaultdict(float)

        for r in active_rows:
            theme = classify_governance_theme(r.get("sector-code", ""))
            org = normalize_org_name(r.get("reporting-org", ""))
            theme_orgs[theme].add(org)
            theme_acts[theme] += 1
            try:
                theme_usd[theme] += float(r.get("total-Disbursement-USD", 0) or 0)
            except (ValueError, TypeError):
                pass

        print(f"\n  {'Theme':<30} {'Orgs':>5} {'Acts':>6} {'Disbursed USD':>15}")
        print(f"  {'-'*30} {'-'*5} {'-'*6} {'-'*15}")
        for theme in sorted(theme_orgs, key=lambda t: -len(theme_orgs[t])):
            o = len(theme_orgs[theme])
            a = theme_acts[theme]
            u = theme_usd[theme]
            print(f"  {theme:<30} {o:>5} {a:>6} {u:>15,.0f}")

    # === LAYER 5: Miscoding detection ===
    miscoded = detect_miscoding(sector_rows, sector=target_sector)
    if miscoded:
        print(f"\n--- LAYER 5: POTENTIAL MISCODING ---")
        orgs_miscoding = set(m["org"] for m in miscoded)
        print(f"  {len(miscoded)} activities with non-{target_sector.lower()} keywords in titles")
        print(f"  From {len(orgs_miscoding)} organization(s)")
        for org in sorted(orgs_miscoding):
            org_misc = [m for m in miscoded if m["org"] == org]
            print(f"    {org[:55]}: {len(org_misc)} suspect activities")

    # === LAYER 6: Financial perspective ===
    print(f"\n--- LAYER 6: FINANCIAL CONCENTRATION ---")
    org_disb = defaultdict(float)
    org_commit = defaultdict(float)
    for r in sector_rows:
        org = normalize_org_name(r.get("reporting-org", ""))
        try:
            org_disb[org] += float(r.get("total-Disbursement-USD", 0) or 0)
        except (ValueError, TypeError):
            pass
        try:
            org_commit[org] += float(r.get("total-Commitment-USD", 0) or 0)
        except (ValueError, TypeError):
            pass

    total_disb = sum(org_disb.values())
    total_commit = sum(org_commit.values())
    reporting_disb = sum(1 for v in org_disb.values() if v > 0)
    print(f"  Total disbursed: ${total_disb:,.0f}")
    print(f"  Total committed: ${total_commit:,.0f}")
    print(f"  Orgs reporting disbursements: {reporting_disb} of {len(dedup_orgs)}")

    if total_disb > 0:
        top = sorted(org_disb.items(), key=lambda x: -x[1])[:5]
        for org, d in top:
            pct = d / total_disb * 100
            if d > 0:
                print(f"    {org[:50]:<50} ${d:>15,.0f} ({pct:.1f}%)")

    # === LAYER 7: Coordination signals ===
    coord = detect_coordination(sector_rows)
    if coord:
        print(f"\n--- LAYER 7: COORDINATION SIGNALS ---")
        print(f"  {len(coord)} activities mention coordination mechanisms:")
        for c in coord[:10]:
            print(f"    [{c['keyword']}] {c['org'][:35]}: {c['title'][:60]}")

    # === LAYER 8: Implementing org convergence ===
    impl_donors = defaultdict(set)
    for r in sector_rows:
        impl = r.get("participating-org (Implementing)", "").strip()
        donor = normalize_org_name(r.get("reporting-org", ""))
        if impl and impl != donor:
            impl_donors[impl].add(donor)

    multi_donor_impl = {k: v for k, v in impl_donors.items() if len(v) >= 2}
    if multi_donor_impl:
        print(f"\n--- LAYER 8: SHARED IMPLEMENTING PARTNERS ---")
        print(f"  {len(multi_donor_impl)} implementing orgs receive from 2+ donors:")
        for impl, donors in sorted(multi_donor_impl.items(), key=lambda x: -len(x[1]))[:8]:
            print(f"    {impl[:50]:<50} ← {len(donors)} donors")

    # === SUMMARY ===
    print(f"\n{'='*70}")
    print(f"  SUMMARY: Fragmentation in {target_sector}, {country_code}")
    print(f"{'='*70}")
    print(f"""
  Naive count:         {len(raw_orgs)} organizations, {len(sector_rows)} activities
  After dedup:         {len(dedup_orgs)} organizations
  Active only:         {len(active_orgs)} organizations, {len(active_rows)} activities
  Reporting finances:  {reporting_disb} organizations report disbursements
  Coordination found:  {len(coord)} activities mention coordination mechanisms
  Potential miscoding: {len(miscoded)} activities with mismatched titles

  The gap between {len(raw_orgs)} (naive) and {len(active_orgs)} (active, deduped) represents
  measurement artifact, not coordination burden.
""")

    return {
        "country": country_code,
        "sector": target_sector,
        "raw_orgs": len(raw_orgs),
        "dedup_orgs": len(dedup_orgs),
        "active_orgs": len(active_orgs),
        "total_activities": len(sector_rows),
        "active_activities": len(active_rows),
        "miscoded": len(miscoded),
        "coordination_signals": len(coord),
        "total_disbursed_usd": total_disb,
        "orgs_reporting_financials": reporting_disb,
    }


def main():
    country = sys.argv[1] if len(sys.argv) > 1 else "UG"
    sector = sys.argv[2] if len(sys.argv) > 2 else "Governance"
    result = analyze(country, sector)
    if result:
        outfile = f"research/honest_fragmentation_{country}_{sector.lower().replace(' ', '_')}.json"
        with open(outfile, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results saved to {outfile}")


if __name__ == "__main__":
    main()
