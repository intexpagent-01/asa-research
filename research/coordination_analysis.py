#!/usr/bin/env python3
"""Coordination visibility analysis — what IATI data can and can't show
about aid coordination mechanisms.

Examines structured fields (collaboration-type, aid-type, participating orgs)
alongside unstructured signals (title/description keywords) to measure
the gap between coordination that exists and coordination that's visible.
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

COLLABORATION_TYPES = {
    "1": "Bilateral",
    "2": "Multilateral (inflows)",
    "3": "Bilateral, core to NGOs/multilaterals",
    "4": "Multilateral outflows",
    "6": "Private sector outflows",
    "7": "Bilateral, ex-post NGO/multilateral",
    "8": "Bilateral, triangular co-operation",
}

AID_TYPES = {
    "A01": "General budget support",
    "A02": "Sector budget support",
    "B01": "Core support to NGOs/institutions",
    "B02": "Core to specific programmes",
    "B03": "Contributions to managed funds",
    "B04": "Basket funds / pooled funding",
    "C01": "Project-type interventions",
    "D01": "Donor country personnel",
    "D02": "Other technical assistance",
    "E01": "Scholarships in donor country",
    "E02": "Imputed student costs",
    "F01": "Debt relief",
    "G01": "Administrative costs",
    "H01": "Development awareness",
    "H02": "Refugees in donor country",
}

COORD_KEYWORDS = {
    "pooled_funding": ["pooled fund", "basket fund", "multi-donor trust", "mdtf",
                       "common fund", "sector budget support"],
    "joint_programming": ["joint programme", "joint program", "joint project",
                          "joint initiative", "joint assessment", "joint review",
                          "united nations joint", "un joint"],
    "sector_coordination": ["swap", "sector-wide", "sectorwide", "sector wide",
                            "sector plan", "sector strategy"],
    "donor_coordination": ["donor coordination", "development partner",
                           "division of labour", "aid coordination",
                           "donor harmoni", "paris declaration", "accra agenda",
                           "busan"],
    "harmonization": ["harmoni", "aligned", "alignment", "coordinated approach",
                      "common framework", "mutual accountability"],
}

ORG_TYPE_CODES = {
    "10": "Government",
    "15": "Other public sector",
    "21": "International NGO",
    "22": "National NGO",
    "23": "Regional NGO",
    "30": "Public-private partnership",
    "40": "Multilateral",
    "60": "Foundation",
    "70": "Private sector",
    "80": "Academic/research",
}


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


def normalize_org_name(name):
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
        url = (f"{BASE}/activity.csv?recipient-country={country_code}"
               f"&limit={batch}&offset={offset}")
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


def analyze_coordination(country_code, target_sector, limit=5000):
    print(f"\n{'='*70}")
    print(f"  COORDINATION VISIBILITY: {target_sector} in {country_code}")
    print(f"{'='*70}")

    print(f"\nFetching activities...", end=" ", flush=True)
    rows = fetch_activities(country_code, limit)
    print(f"{len(rows)} total activities")

    sector_rows = [r for r in rows if map_sector(r.get("sector-code", "")) == target_sector]
    print(f"{target_sector} activities: {len(sector_rows)}")
    if not sector_rows:
        return None

    active_rows = [r for r in sector_rows
                   if r.get("activity-status-code", "") in ("1", "2", "3")]
    print(f"Active activities: {len(active_rows)}")

    results = {
        "country": country_code,
        "sector": target_sector,
        "total_activities": len(sector_rows),
        "active_activities": len(active_rows),
    }

    # === 1. STRUCTURED FIELD COMPLETENESS ===
    print(f"\n--- STRUCTURED COORDINATION FIELDS ---")

    collab_codes = Counter()
    collab_empty = 0
    aid_type_codes = Counter()
    aid_type_empty = 0

    for r in active_rows:
        cc = r.get("collaboration-type-code", "").strip()
        if cc:
            collab_codes[cc] += 1
        else:
            collab_empty += 1

        at = r.get("default-aid-type-code", "").strip()
        if at:
            aid_type_codes[at] += 1
        else:
            aid_type_empty += 1

    collab_total = len(active_rows)
    collab_filled = collab_total - collab_empty
    print(f"\n  Collaboration type code:")
    print(f"    Filled: {collab_filled}/{collab_total} ({100*collab_filled/collab_total:.0f}%)")
    if collab_codes:
        for code, count in collab_codes.most_common():
            label = COLLABORATION_TYPES.get(code, f"Unknown ({code})")
            print(f"      {label}: {count}")
    else:
        print(f"    (all empty)")

    aid_filled = collab_total - aid_type_empty
    print(f"\n  Aid type code:")
    print(f"    Filled: {aid_filled}/{collab_total} ({100*aid_filled/collab_total:.0f}%)")
    basket_count = aid_type_codes.get("B04", 0) + aid_type_codes.get("B03", 0)
    if aid_type_codes:
        for code, count in aid_type_codes.most_common():
            label = AID_TYPES.get(code, f"Unknown ({code})")
            marker = " ← COORDINATION" if code in ("B03", "B04", "A02") else ""
            print(f"      {label}: {count}{marker}")

    results["collaboration_type_filled_pct"] = round(100 * collab_filled / collab_total) if collab_total else 0
    results["aid_type_filled_pct"] = round(100 * aid_filled / collab_total) if collab_total else 0
    results["basket_fund_activities"] = basket_count

    # === 2. PARTICIPATING ORG ROLE COMPLETENESS ===
    print(f"\n  Participating org roles:")
    roles = ["Funding", "Implementing", "Extending", "Accountable"]
    role_stats = {}
    for role in roles:
        field = f"participating-org ({role})"
        filled = sum(1 for r in active_rows if r.get(field, "").strip())
        pct = 100 * filled / len(active_rows) if active_rows else 0
        print(f"    {role}: {filled}/{len(active_rows)} ({pct:.0f}%)")
        role_stats[role] = {"filled": filled, "pct": round(pct)}

    results["participating_org_completeness"] = role_stats

    # Multi-funder activities (same activity, multiple funding orgs listed)
    multi_funder = 0
    for r in active_rows:
        funders = r.get("participating-org (Funding)", "").strip()
        if ";" in funders:
            multi_funder += 1
    print(f"\n    Activities listing multiple funders: {multi_funder}")
    results["multi_funder_activities"] = multi_funder

    # === 3. KEYWORD-BASED COORDINATION SIGNALS ===
    print(f"\n--- KEYWORD COORDINATION SIGNALS ---")
    keyword_hits = defaultdict(list)
    any_coord = set()

    for r in active_rows:
        text = (r.get("title", "") + " " + r.get("description", "") + " "
                + r.get("description_general", "") + " "
                + r.get("description_objectives", "")).lower()
        org = normalize_org_name(r.get("reporting-org", ""))
        iati_id = r.get("iati-identifier", "")

        for category, keywords in COORD_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    keyword_hits[category].append({
                        "org": org,
                        "title": r.get("title", "")[:100],
                        "keyword": kw,
                        "iati_id": iati_id,
                        "aid_type": r.get("default-aid-type-code", ""),
                        "collab_type": r.get("collaboration-type-code", ""),
                    })
                    any_coord.add(iati_id)
                    break

    total_coord = len(any_coord)
    print(f"\n  Activities with any coordination keyword: {total_coord}/{len(active_rows)} "
          f"({100*total_coord/len(active_rows):.1f}%)")

    results["keyword_coordination"] = {}
    for cat in ["pooled_funding", "joint_programming", "sector_coordination",
                "donor_coordination", "harmonization"]:
        hits = keyword_hits[cat]
        orgs = set(h["org"] for h in hits)
        print(f"\n  {cat.replace('_', ' ').title()}: {len(hits)} activities from {len(orgs)} org(s)")
        for h in hits[:3]:
            print(f"    {h['org'][:30]}: {h['title'][:55]}")
        if len(hits) > 3:
            print(f"    ... and {len(hits)-3} more")

        # Check if structured fields capture these
        structured = sum(1 for h in hits if h["aid_type"] in ("B03", "B04", "A02")
                         or h["collab_type"] in ("2", "4", "8"))
        if hits:
            print(f"    Also captured in structured fields: {structured}/{len(hits)} "
                  f"({100*structured/len(hits):.0f}%)")

        results["keyword_coordination"][cat] = {
            "activities": len(hits),
            "orgs": len(orgs),
            "also_in_structured": structured,
        }

    results["total_keyword_coord_activities"] = total_coord

    # === 4. SHARED IMPLEMENTING PARTNERS ===
    print(f"\n--- SHARED IMPLEMENTING PARTNERS ---")
    impl_donors = defaultdict(set)
    impl_activities = defaultdict(int)
    impl_usd = defaultdict(float)

    for r in active_rows:
        impl = r.get("participating-org (Implementing)", "").strip()
        donor = normalize_org_name(r.get("reporting-org", ""))
        if impl:
            for imp in impl.split(";"):
                imp = imp.strip()
                if imp and imp != donor:
                    impl_donors[imp].add(donor)
                    impl_activities[imp] += 1
                    try:
                        impl_usd[imp] += float(r.get("total-Disbursement-USD", 0) or 0)
                    except (ValueError, TypeError):
                        pass

    multi = {k: v for k, v in impl_donors.items() if len(v) >= 2}
    print(f"  Implementing orgs receiving from 2+ reporting orgs: {len(multi)}")
    top_shared = sorted(multi.items(), key=lambda x: -len(x[1]))[:10]
    for impl, donors in top_shared:
        usd = impl_usd.get(impl, 0)
        acts = impl_activities.get(impl, 0)
        print(f"    {impl[:45]:<45} ← {len(donors)} donors, {acts} activities"
              + (f", ${usd:,.0f}" if usd > 0 else ""))

    results["shared_implementers"] = len(multi)
    results["shared_implementer_details"] = [
        {"name": impl[:60], "donors": len(donors), "activities": impl_activities[impl]}
        for impl, donors in top_shared[:5]
    ]

    # === 5. COORDINATION GAP ANALYSIS ===
    print(f"\n--- COORDINATION GAP SUMMARY ---")

    # Activities with keyword signals but no structured coordination fields
    keyword_ids = any_coord
    structured_coord_ids = set()
    for r in active_rows:
        iati_id = r.get("iati-identifier", "")
        at = r.get("default-aid-type-code", "").strip()
        ct = r.get("collaboration-type-code", "").strip()
        if at in ("B03", "B04", "A02") or ct in ("2", "4", "8"):
            structured_coord_ids.add(iati_id)

    only_keyword = keyword_ids - structured_coord_ids
    only_structured = structured_coord_ids - keyword_ids
    both = keyword_ids & structured_coord_ids
    neither = len(active_rows) - len(keyword_ids | structured_coord_ids)

    print(f"\n  Coordination detection comparison:")
    print(f"    Keyword signals only:    {len(only_keyword):>4} activities")
    print(f"    Structured fields only:  {len(only_structured):>4} activities")
    print(f"    Both methods detect:     {len(both):>4} activities")
    print(f"    Neither method:          {neither:>4} activities")

    total_any = len(keyword_ids | structured_coord_ids)
    if total_any:
        keyword_only_pct = 100 * len(only_keyword) / total_any
        print(f"\n  {keyword_only_pct:.0f}% of coordination signals come from keywords ONLY")
        print(f"  (invisible in structured queries)")

    results["gap_analysis"] = {
        "keyword_only": len(only_keyword),
        "structured_only": len(only_structured),
        "both": len(both),
        "neither": neither,
        "keyword_only_pct": round(100 * len(only_keyword) / total_any) if total_any else 0,
    }

    # === 6. ORG TYPE DIVERSITY ===
    print(f"\n--- ORGANIZATION TYPE DIVERSITY ---")
    org_types = Counter()
    for r in active_rows:
        ot = r.get("reporting-org-type-code", "").strip()
        org = normalize_org_name(r.get("reporting-org", ""))
        if ot:
            org_types[ot] += 1

    for code, count in org_types.most_common():
        label = ORG_TYPE_CODES.get(code, f"Unknown ({code})")
        print(f"    {label}: {count} activities")

    results["org_type_distribution"] = {
        ORG_TYPE_CODES.get(k, k): v for k, v in org_types.most_common()
    }

    # === SUMMARY ===
    print(f"\n{'='*70}")
    print(f"  COORDINATION VISIBILITY SUMMARY: {target_sector} in {country_code}")
    print(f"{'='*70}")
    print(f"""
  Active activities:              {len(active_rows)}
  Collaboration type filled:      {collab_filled}/{collab_total} ({results['collaboration_type_filled_pct']}%)
  Aid type filled:                {aid_filled}/{collab_total} ({results['aid_type_filled_pct']}%)
  Basket/pooled fund activities:  {basket_count}
  Keyword coordination signals:   {total_coord} ({100*total_coord/len(active_rows):.1f}%)
  Shared implementing partners:   {len(multi)} (receiving from 2+ donors)
  Coordination visible only via keywords: {len(only_keyword)} activities
""")

    return results


def run_comparative(countries, sectors, limit=5000):
    all_results = []
    for country in countries:
        for sector in sectors:
            result = analyze_coordination(country, sector, limit)
            if result:
                all_results.append(result)

    if all_results:
        print(f"\n\n{'='*70}")
        print(f"  COMPARATIVE COORDINATION VISIBILITY")
        print(f"{'='*70}")
        print(f"\n  {'Pair':<20} {'Collab%':>8} {'Aid%':>6} {'B04':>5} {'KW Coord':>9} "
              f"{'KW-Only%':>9} {'Shared':>7}")
        print(f"  {'-'*20} {'-'*8} {'-'*6} {'-'*5} {'-'*9} {'-'*9} {'-'*7}")
        for r in all_results:
            pair = f"{r['country']} {r['sector'][:8]}"
            kw_pct = (100 * r['total_keyword_coord_activities'] / r['active_activities']
                      if r['active_activities'] else 0)
            gap = r['gap_analysis']
            print(f"  {pair:<20} {r['collaboration_type_filled_pct']:>7}% "
                  f"{r['aid_type_filled_pct']:>5}% {r['basket_fund_activities']:>5} "
                  f"{r['total_keyword_coord_activities']:>5} ({kw_pct:>3.0f}%) "
                  f"{gap['keyword_only_pct']:>7}%  {r['shared_implementers']:>5}")

    return all_results


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        countries = ["UG", "KE", "RW", "TZ", "ET"]
        sectors = ["Governance", "Health"]
        results = run_comparative(countries, sectors)
        with open("research/coordination_analysis.json", "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to research/coordination_analysis.json")
    else:
        country = sys.argv[1] if len(sys.argv) > 1 else "UG"
        sector = sys.argv[2] if len(sys.argv) > 2 else "Governance"
        result = analyze_coordination(country, sector)
        if result:
            outfile = f"research/coordination_{country}_{sector.lower()}.json"
            with open(outfile, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Results saved to {outfile}")


if __name__ == "__main__":
    main()
