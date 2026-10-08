#!/usr/bin/env python3
"""Fetch DFAT contract data from AusTender OCDS API for Pacific aid programs.

Supports incremental extraction: saves results per quarter so extraction
can resume across wakes without re-fetching completed windows.
"""

import json, sys, time, urllib.request, urllib.error, os
from datetime import datetime, timezone

API_BASE = "https://api.tenders.gov.au/ocds/findByDates/contractPublished"
DFAT_NAMES = {"department of foreign affairs and trade"}
MAX_PAGES_PER_WINDOW = 200
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "data", "austender-cache")
OUTPUT = os.path.join(HERE, "data", "austender-dfat.json")

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
    "transport", "australia awards", "new colombo", "incentive fund",
    "iwiser", "access", "women lead", "rt4d", "koneksi",
    "mfat", "tafe", "volunteer", "sport", "pasc",
    "strongim bisnis", "adam smith", "cardno", "coffey",
]


def _quarterly_windows(start_year, end_year):
    windows = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
    for y in range(start_year, end_year + 1):
        for q_start, q_end in [("01-01", "03-31"), ("04-01", "06-30"), ("07-01", "09-30"), ("10-01", "12-31")]:
            s = f"{y}-{q_start}T00:00:00Z"
            e = f"{y}-{q_end}T23:59:59Z"
            if e <= now:
                windows.append((s, e))
    return windows


def _cache_key(start, end):
    return f"{start[:10]}_{end[:10]}"


def _load_cached(key):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_cached(key, contracts, complete):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    with open(path, "w") as f:
        json.dump({
            "key": key,
            "fetched": datetime.now(timezone.utc).isoformat(),
            "complete": complete,
            "count": len(contracts),
            "contracts": contracts,
        }, f, indent=1)


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

    complete = not url
    print(f"  window {start[:10]}–{end[:10]}: {page} pages, {len(contracts)} DFAT contracts >= $100K{'' if complete else ' (INCOMPLETE)'}", file=sys.stderr)
    return contracts, complete


def main():
    force = "--force" in sys.argv
    windows_only = "--status" in sys.argv

    DATE_WINDOWS = _quarterly_windows(2020, 2026)
    os.makedirs(CACHE_DIR, exist_ok=True)

    if windows_only:
        print(f"AusTender cache status ({len(DATE_WINDOWS)} quarterly windows):", file=sys.stderr)
        cached_count = 0
        cached_contracts = 0
        for start, end in DATE_WINDOWS:
            key = _cache_key(start, end)
            cached = _load_cached(key)
            if cached:
                cached_count += 1
                cached_contracts += cached["count"]
                status = "complete" if cached.get("complete") else "INCOMPLETE"
                print(f"  {key}: {cached['count']} contracts ({status}, fetched {cached['fetched'][:10]})", file=sys.stderr)
            else:
                print(f"  {key}: NOT CACHED", file=sys.stderr)
        print(f"\n{cached_count}/{len(DATE_WINDOWS)} windows cached, {cached_contracts} total contracts", file=sys.stderr)
        return

    print("Fetching DFAT contracts from AusTender OCDS API (incremental)...", file=sys.stderr)
    all_contracts = []
    fetched_this_run = 0
    skipped = 0

    for start, end in DATE_WINDOWS:
        key = _cache_key(start, end)
        cached = _load_cached(key)

        if cached and cached.get("complete") and not force:
            all_contracts.extend(cached["contracts"])
            skipped += 1
            continue

        contracts, complete = extract_window(start, end)
        _save_cached(key, contracts, complete)
        all_contracts.extend(contracts)
        fetched_this_run += 1

    print(f"\nWindows: {skipped} from cache, {fetched_this_run} fetched this run", file=sys.stderr)

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

    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=1)
    print(f"\nSaved {len(all_contracts)} contracts to {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
