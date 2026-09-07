#!/usr/bin/env python3
"""Deep dive into Uganda's Governance sector activities via IATI."""
import csv
import io
import json
import urllib.request
from collections import defaultdict, Counter

BASE = "https://datastore.codeforiati.org/api/1/access"

GOVERNANCE_CODES = {"150", "151", "152", "15110", "15111", "15112", "15113",
                    "15114", "15120", "15130", "15140", "15150", "15151",
                    "15152", "15153", "15160", "15170", "15180", "15190",
                    "15210", "15220", "15230", "15240", "15250", "15261"}

def is_governance(sector_code):
    if not sector_code:
        return False
    code = str(sector_code).strip().split(";")[0].strip()
    return code in GOVERNANCE_CODES or code[:3] in ("150", "151", "152")

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
            print(f"  Error at offset {offset}: {e}")
            break
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch
    return all_rows

def main():
    print("Fetching Uganda activities...", flush=True)
    rows = fetch_activities("UG", 5000)
    print(f"Got {len(rows)} total activities")

    gov_activities = []
    for r in rows:
        if is_governance(r.get("sector-code", "")):
            gov_activities.append(r)

    print(f"Governance activities: {len(gov_activities)}")

    # Get available fields
    if gov_activities:
        print(f"\nAvailable fields: {list(gov_activities[0].keys())}")

    # Group by org
    org_activities = defaultdict(list)
    for a in gov_activities:
        org = a.get("reporting-org", "Unknown")
        org_activities[org].append(a)

    # Analyze subsector codes
    subsector_counts = Counter()
    for a in gov_activities:
        code = str(a.get("sector-code", "")).strip().split(";")[0].strip()
        subsector_counts[code] += 1

    print(f"\n{'='*70}")
    print(f"  GOVERNANCE SUBSECTOR CODES")
    print(f"{'='*70}")
    for code, count in subsector_counts.most_common():
        print(f"  {code:<10} {count:>5} activities")

    # Sample titles from top organizations
    print(f"\n{'='*70}")
    print(f"  ACTIVITY TITLES — sample from top governance organizations")
    print(f"{'='*70}")

    top_orgs = sorted(org_activities.items(), key=lambda x: -len(x[1]))[:15]
    for org, acts in top_orgs:
        print(f"\n  {org} ({len(acts)} governance activities):")
        titles = set()
        for a in acts[:20]:
            title = a.get("title", "").strip()[:120]
            if title and title not in titles:
                titles.add(title)
                print(f"    - {title}")
            if len(titles) >= 8:
                break

    # Look for thematic clusters in titles
    print(f"\n{'='*70}")
    print(f"  KEYWORD FREQUENCY IN GOVERNANCE ACTIVITY TITLES")
    print(f"{'='*70}")

    keywords = Counter()
    theme_words = {
        "democracy", "election", "parliament", "justice", "rights",
        "human rights", "accountability", "transparency", "corruption",
        "civil society", "governance", "decentrali", "local government",
        "public financial", "pfm", "tax", "revenue", "budget",
        "gender", "women", "youth", "disability", "inclusion",
        "peace", "conflict", "security", "refugee",
        "land", "natural resource", "extractive",
        "health system", "education system",
        "capacity", "training", "institutional",
    }

    for a in gov_activities:
        title = (a.get("title", "") + " " + a.get("description", "")).lower()
        for kw in theme_words:
            if kw in title:
                keywords[kw] += 1

    for kw, count in keywords.most_common():
        if count >= 3:
            print(f"  {kw:<25} {count:>5}")

    # Save detailed results
    results = {
        "total_gov_activities": len(gov_activities),
        "total_gov_orgs": len(org_activities),
        "subsector_codes": dict(subsector_counts),
        "org_activity_counts": {o: len(a) for o, a in org_activities.items()},
        "sample_titles": {
            org: [a.get("title", "")[:200] for a in acts[:20]]
            for org, acts in top_orgs
        },
        "theme_keywords": dict(keywords.most_common()),
    }

    with open("research/uganda_governance_detail.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to research/uganda_governance_detail.json")

if __name__ == "__main__":
    main()
