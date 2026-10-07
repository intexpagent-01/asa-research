#!/usr/bin/env python3
"""Targeted AusTender OCDS lookup for specific DFAT programs.

Queries the API for specific quarterly windows and filters for DFAT contracts
matching given keywords. Much faster than a full extraction — queries only
the windows and pages needed for a specific program.
"""

import json, sys, time, urllib.request, urllib.error, os
from datetime import datetime, timezone

API_BASE = "https://api.tenders.gov.au/ocds/findByDates/contractPublished"
DFAT_NAMES = {"department of foreign affairs and trade"}
MAX_PAGES = 200
OUTDIR = os.path.join(os.path.dirname(__file__), "data")


def fetch_page(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  fetch error: {e}", file=sys.stderr)
        return None


def search_window(start, end, keywords, max_pages=MAX_PAGES):
    """Search a single date window for DFAT contracts matching any keyword."""
    url = f"{API_BASE}/{start}/{end}"
    matches = []
    page = 0
    seen = set()

    kw_lower = [k.lower() for k in keywords]

    while url and page < max_pages:
        page += 1
        if page % 20 == 1:
            print(f"  {start[:10]}–{end[:10]}: page {page}", file=sys.stderr)

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
                desc = c.get("description", "")
                title = c.get("title", "")
                text = f"{desc} {title}".lower()
                sup_text = " ".join(s["name"].lower() for s in suppliers)
                full_text = f"{text} {sup_text}"

                if not any(kw in full_text for kw in kw_lower):
                    continue

                key = f"{cn_id}|{val}"
                if key in seen:
                    continue
                seen.add(key)

                period = c.get("period", {})
                matches.append({
                    "cn_id": cn_id,
                    "ocid": r.get("ocid", ""),
                    "title": title,
                    "description": desc,
                    "value_aud": val,
                    "start": period.get("startDate", "")[:10],
                    "end": period.get("endDate", "")[:10],
                    "signed": c.get("dateSigned", "")[:10],
                    "suppliers": suppliers,
                    "published": r.get("date", "")[:10],
                    "keywords_matched": [kw for kw in kw_lower if kw in full_text],
                })

        url = data.get("links", {}).get("next")
        if url:
            time.sleep(0.2)

    print(f"  {start[:10]}–{end[:10]}: {page} pages, {len(matches)} matches", file=sys.stderr)
    return matches


def quarterly_windows(start_year, end_year):
    windows = []
    for y in range(start_year, end_year + 1):
        for q_start, q_end in [("01-01", "03-31"), ("04-01", "06-30"),
                                ("07-01", "09-30"), ("10-01", "12-31")]:
            s = f"{y}-{q_start}T00:00:00Z"
            e = f"{y}-{q_end}T23:59:59Z"
            if s <= "2026-10-07T23:59:59Z":
                windows.append((s, e))
    return windows


def lookup(keywords, years=(2020, 2026), max_pages=MAX_PAGES, save_as=None):
    """Run a targeted lookup across quarterly windows."""
    print(f"Searching AusTender for: {keywords}", file=sys.stderr)
    windows = quarterly_windows(*years)
    all_matches = []

    for s, e in windows:
        matches = search_window(s, e, keywords, max_pages)
        all_matches.extend(matches)

    # Deduplicate
    deduped = {}
    for m in all_matches:
        key = f"{m['cn_id']}|{m['value_aud']}"
        deduped[key] = m
    all_matches = sorted(deduped.values(), key=lambda x: -x["value_aud"])

    total = sum(m["value_aud"] for m in all_matches)
    print(f"\n=== {len(all_matches)} DFAT contracts matching {keywords} ===", file=sys.stderr)
    print(f"Total value: AUD ${total:,.0f}", file=sys.stderr)

    for m in all_matches[:20]:
        sups = ", ".join(s["name"] for s in m["suppliers"])[:50]
        print(f"  ${m['value_aud']:>14,.0f} | {m['cn_id']} | {m['start']}–{m['end']} | {sups} | {m['description'][:60]}", file=sys.stderr)

    if save_as:
        path = os.path.join(OUTDIR, save_as)
        os.makedirs(OUTDIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "fetched": datetime.now(timezone.utc).isoformat(),
                "keywords": keywords,
                "total_contracts": len(all_matches),
                "total_value_aud": total,
                "contracts": all_matches,
            }, f, indent=1)
        print(f"Saved to {path}", file=sys.stderr)

    return all_matches


# Predefined lookups for active briefs
BRIEF_LOOKUPS = {
    "strongim-ekonomi": {
        "keywords": ["strongim", "solomon islands", "economic governance",
                      "adam smith", "bisnis", "bilateral"],
        "save_as": "austender-strongim-ekonomi.json",
    },
    "pasc": {
        "keywords": ["sport", "pasc", "pacific aus", "team up",
                      "community sport", "pacific sport"],
        "save_as": "austender-pasc.json",
    },
    "pwles": {
        "keywords": ["pacific women", "pwles", "gender equality",
                      "women lead", "cardno"],
        "save_as": "austender-pwles.json",
    },
    "plmsp": {
        "keywords": ["labour mobility", "plmsp", "seasonal worker",
                      "pacific labour", "palm scheme"],
        "save_as": "austender-plmsp.json",
    },
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 austender_lookup.py <brief-name|keyword1,keyword2,...>", file=sys.stderr)
        print(f"  Brief names: {', '.join(BRIEF_LOOKUPS.keys())}", file=sys.stderr)
        print("  Or: python3 austender_lookup.py solomon,strongim,dt global", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    if arg in BRIEF_LOOKUPS:
        cfg = BRIEF_LOOKUPS[arg]
        lookup(cfg["keywords"], save_as=cfg["save_as"])
    else:
        keywords = [k.strip() for k in arg.split(",")]
        lookup(keywords, save_as=f"austender-custom-{keywords[0]}.json")
