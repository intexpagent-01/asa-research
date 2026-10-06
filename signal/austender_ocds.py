#!/usr/bin/env python3
"""Fetch DFAT contract data from AusTender OCDS API for Pacific aid programs.

Searches contract publications across multiple date windows.
Outputs a structured dataset of all DFAT contracts with values >= $100K.
"""

import json, sys, time, urllib.request, urllib.error, os
from datetime import datetime, timezone

API_BASE = "https://api.tenders.gov.au/ocds/findByDates/contractPublished"
DFAT_NAMES = {"department of foreign affairs and trade"}
MAX_PAGES_PER_WINDOW = 80
OUTPUT = os.path.join(os.path.dirname(__file__), "data", "austender-dfat.json")

PACIFIC_KEYWORDS = [
    "pacific", "papua new guinea", "png", "fiji", "samoa", "tonga", "vanuatu",
    "solomon islands", "kiribati", "nauru", "tuvalu", "palau", "niue",
    "marshall islands", "micronesia", "cook islands", "timor-leste",
    "indo-pacific", "colombo", "pacer plus", "step-up",
]

PROGRAM_KEYWORDS = [
    "law and justice", "economic governance", "strongim ekonomi",
    "pacific women", "pwles", "plmsp", "labour mobility",
    "humanitarian", "el nino", "covid", "climate",
    "governance", "health", "education", "infrastructure",
    "water", "sanitation", "resilience", "disaster",
    "esip", "aiffp", "phc4png", "development assistance",
    "managing contractor", "support facility", "program support",
    "bilateral", "partnership", "enabling services",
]

DATE_WINDOWS = [
    ("2018-01-01T00:00:00Z", "2019-12-31T23:59:59Z"),
    ("2020-01-01T00:00:00Z", "2021-12-31T23:59:59Z"),
    ("2022-01-01T00:00:00Z", "2023-06-30T23:59:59Z"),
    ("2023-07-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    ("2025-01-01T00:00:00Z", "2026-10-06T23:59:59Z"),
]


def fetch_page(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  fetch error: {e}", file=sys.stderr)
        return None


def is_pacific(text):
    t = text.lower()
    return any(kw in t for kw in PACIFIC_KEYWORDS)


def is_program(text):
    t = text.lower()
    return any(kw in t for kw in PROGRAM_KEYWORDS)


def extract_window(start, end):
    url = f"{API_BASE}/{start}/{end}"
    contracts = []
    page = 0
    seen_cns = set()

    while url and page < MAX_PAGES_PER_WINDOW:
        page += 1
        if page % 10 == 1:
            print(f"  window {start[:10]}–{end[:10]}: page {page}", file=sys.stderr)
        data = fetch_page(url)
        if not data or not data.get("releases"):
            break

        for r in data["releases"]:
            procuring = None
            suppliers = []
            for p in r.get("parties", []):
                name = p.get("name", "")
                roles = p.get("roles", [])
                if "procuringEntity" in roles:
                    procuring = name
                if "supplier" in roles:
                    abn = ""
                    for ai in p.get("additionalIdentifiers", []):
                        if ai.get("scheme") == "AU-ABN":
                            abn = ai.get("id", "")
                    suppliers.append({"name": name, "abn": abn})

            if not procuring or procuring.lower() not in DFAT_NAMES:
                continue

            for c in r.get("contracts", []):
                cn_id = c.get("id", "")
                val = float(c.get("value", {}).get("amount", 0) or 0)
                if val < 100000:
                    continue

                desc = c.get("description", "")
                title = c.get("title", "")
                text = f"{desc} {title}".lower()
                pacific = is_pacific(text)
                program = is_program(text)

                key = f"{cn_id}|{val}"
                if key in seen_cns:
                    continue
                seen_cns.add(key)

                period = c.get("period", {})
                contracts.append({
                    "cn_id": cn_id,
                    "ocid": r.get("ocid", ""),
                    "title": title,
                    "description": desc,
                    "value_aud": val,
                    "currency": c.get("value", {}).get("currency", "AUD"),
                    "start": period.get("startDate", "")[:10],
                    "end": period.get("endDate", "")[:10],
                    "signed": c.get("dateSigned", "")[:10],
                    "suppliers": suppliers,
                    "pacific_match": pacific,
                    "program_match": program,
                    "published": r.get("date", "")[:10],
                })

        url = data.get("links", {}).get("next")
        if url:
            time.sleep(0.25)

    print(f"  window {start[:10]}–{end[:10]}: {page} pages, {len(contracts)} DFAT contracts >= $100K", file=sys.stderr)
    return contracts


def main():
    print("Fetching DFAT contracts from AusTender OCDS API...", file=sys.stderr)
    all_contracts = []

    for start, end in DATE_WINDOWS:
        contracts = extract_window(start, end)
        all_contracts.extend(contracts)

    deduped = {}
    for c in all_contracts:
        key = f"{c['cn_id']}|{c['value_aud']}"
        deduped[key] = c
    all_contracts = list(deduped.values())

    pacific = [c for c in all_contracts if c["pacific_match"]]
    programs = [c for c in all_contracts if c["program_match"]]

    total_value = sum(c["value_aud"] for c in all_contracts)
    pacific_value = sum(c["value_aud"] for c in pacific)

    print(f"\n=== RESULTS ===", file=sys.stderr)
    print(f"Total DFAT contracts (>=$100K): {len(all_contracts)}", file=sys.stderr)
    print(f"Total value: AUD ${total_value:,.0f}", file=sys.stderr)
    print(f"Pacific-keyword matches: {len(pacific)} (AUD ${pacific_value:,.0f})", file=sys.stderr)
    print(f"Program-keyword matches: {len(programs)}", file=sys.stderr)

    by_supplier = {}
    for c in all_contracts:
        for s in c["suppliers"]:
            name = s["name"]
            if name not in by_supplier:
                by_supplier[name] = {"count": 0, "value": 0, "pacific_count": 0, "pacific_value": 0, "contracts": []}
            by_supplier[name]["count"] += 1
            by_supplier[name]["value"] += c["value_aud"]
            if c["pacific_match"]:
                by_supplier[name]["pacific_count"] += 1
                by_supplier[name]["pacific_value"] += c["value_aud"]
                by_supplier[name]["contracts"].append({"cn": c["cn_id"], "desc": c["description"][:80], "val": c["value_aud"]})

    print(f"\n--- Top DFAT suppliers by total value ---", file=sys.stderr)
    top = sorted(by_supplier.items(), key=lambda x: -x[1]["value"])[:25]
    for name, stats in top:
        pac = f" | Pacific: {stats['pacific_count']} @ ${stats['pacific_value']:,.0f}" if stats["pacific_count"] else ""
        print(f"  {name[:45]:45} {stats['count']:3} contracts  AUD ${stats['value']:>14,.0f}{pac}", file=sys.stderr)

    print(f"\n--- Pacific contracts by value (top 30) ---", file=sys.stderr)
    pacific_sorted = sorted(pacific, key=lambda x: -x["value_aud"])[:30]
    for c in pacific_sorted:
        sups = ", ".join(s["name"] for s in c["suppliers"])[:40]
        print(f"  AUD ${c['value_aud']:>14,.0f} | {c['cn_id']:12} | {c['start']} to {c['end']} | {sups} | {c['description'][:60]}", file=sys.stderr)

    result = {
        "fetched": datetime.now(timezone.utc).isoformat(),
        "date_windows": [{"start": s[:10], "end": e[:10]} for s, e in DATE_WINDOWS],
        "total_contracts": len(all_contracts),
        "pacific_contracts": len(pacific),
        "total_value_aud": total_value,
        "pacific_value_aud": pacific_value,
        "by_supplier": {k: {"count": v["count"], "value": v["value"], "pacific_count": v["pacific_count"], "pacific_value": v["pacific_value"]}
                        for k, v in sorted(by_supplier.items(), key=lambda x: -x[1]["value"])[:50]},
        "pacific_sorted": [{
            "cn_id": c["cn_id"], "description": c["description"], "value_aud": c["value_aud"],
            "suppliers": c["suppliers"], "start": c["start"], "end": c["end"], "signed": c["signed"]
        } for c in sorted(pacific, key=lambda x: -x["value_aud"])],
        "all_contracts": all_contracts,
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=1)
    print(f"\nSaved {len(all_contracts)} contracts to {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
