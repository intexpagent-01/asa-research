#!/usr/bin/env python3
"""Cross-reference DFAT pipeline items against AusTender and IATI data.

Given a pipeline item (by ID or title keywords), finds:
- AusTender predecessor contracts (values, suppliers, dates)
- IATI activities in the relevant country/program
- Competitor DFAT portfolios from AusTender

Usage:
  python3 signal/pipeline_xref.py DFAT-1100
  python3 signal/pipeline_xref.py "strongim ekonomi"
  python3 signal/pipeline_xref.py --all          # cross-reference every pipeline item
"""

import json, sys, os, re, gzip
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

COUNTRY_MAP = {
    "papua new guinea": "PG", "png": "PG",
    "fiji": "FJ",
    "solomon islands": "SB", "solomons": "SB",
    "vanuatu": "VU",
    "samoa": "WS",
    "tonga": "TO",
    "kiribati": "KI",
    "tuvalu": "TV",
    "micronesia": "FM", "fsm": "FM",
    "marshall islands": "MH",
    "palau": "PW",
    "nauru": "NR",
    "niue": "NU",
    "cook islands": "CK",
    "timor-leste": "TL", "timor leste": "TL",
    "laos": "LA",
    "indonesia": "ID",
    "philippines": "PH",
    "pacific": "PACIFIC",
}


def _latest_snapshot():
    files = sorted(f for f in os.listdir(DATA) if f.startswith("pacific-") and f.endswith(".json") and not f.endswith(".index.json.gz"))
    if not files:
        return None
    path = os.path.join(DATA, files[-1])
    with open(path) as f:
        return json.load(f)


def _load_austender():
    path = os.path.join(DATA, "austender-dfat.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _load_index(snapshot_date=None):
    if snapshot_date:
        path = os.path.join(DATA, f"pacific-{snapshot_date}.index.json.gz")
    else:
        files = sorted(f for f in os.listdir(DATA) if f.endswith(".index.json.gz"))
        if not files:
            return None
        path = os.path.join(DATA, files[-1])
    if not os.path.exists(path):
        return None
    with gzip.open(path, "rt") as f:
        return json.load(f)


def _extract_keywords(title):
    stop = {"the", "of", "for", "and", "in", "a", "an", "to", "phase",
            "program", "programme", "project", "facility", "support",
            "partnership", "services", "review", "mid-term", "design",
            "new", "investment", "ii", "iii", "iv", "v", "national",
            "enhanced", "advice", "bilateral", "improving", "development",
            "harnessing", "strengthening"}
    words = re.findall(r"[a-z]+", title.lower())
    keywords = [w for w in words if w not in stop and len(w) > 2]
    # Also extract multi-word phrases that are more specific
    phrases = []
    t = title.lower()
    for phrase_len in [3, 2]:
        for i in range(len(words) - phrase_len + 1):
            phrase = " ".join(words[i:i + phrase_len])
            if all(w not in stop for w in words[i:i + phrase_len]):
                phrases.append(phrase)
    return keywords, phrases


def _detect_country(title):
    t = title.lower()
    for name, code in COUNTRY_MAP.items():
        if name in t:
            return code
    return None


def _match_score(text, keywords):
    t = text.lower()
    return sum(1 for kw in keywords if kw in t)


def find_pipeline_item(snapshot, query):
    items = snapshot.get("dfat", {}).get("items", [])
    q = query.lower().strip()

    for it in items:
        if it.get("id", "").lower() == q:
            return it

    best = None
    best_score = 0
    keywords = q.split()
    for it in items:
        text = f"{it.get('id','')} {it.get('title','')} {it.get('status','')}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best = it
    if best_score >= max(1, len(keywords) // 2):
        return best
    return None


def find_austender_contracts(austender, item_title, country_code=None):
    if not austender:
        return []

    keywords, phrases = _extract_keywords(item_title)
    contracts = austender.get("all_contracts", [])
    matches = []

    for c in contracts:
        text = f"{c.get('description','')} {c.get('title','')}".lower()
        sup_text = " ".join(s["name"].lower() for s in c.get("suppliers", []))
        full = f"{text} {sup_text}"

        score = _match_score(full, keywords)
        phrase_bonus = sum(2 for p in phrases if p in full)
        total = score + phrase_bonus

        if total >= 2 or (total >= 1 and country_code and
                          any(name in text for name, code in COUNTRY_MAP.items() if code == country_code)):
            matches.append((total, c))

    matches.sort(key=lambda x: (-x[0], -x[1].get("value_aud", 0)))
    return [c for _, c in matches[:20]]


def find_iati_activities(index, item_title, country_code=None):
    if not index:
        return []

    keywords, phrases = _extract_keywords(item_title)
    results = []

    countries_to_search = [country_code] if country_code and country_code in index else list(index.keys())

    for cc in countries_to_search:
        country_data = index.get(cc, {})
        cols = country_data.get("cols", [])
        rows = country_data.get("rows", [])

        for row in rows:
            rec = dict(zip(cols, row))
            text = f"{rec.get('title','')} {rec.get('org','')} {rec.get('aid','')}".lower()
            score = _match_score(text, keywords)
            phrase_bonus = sum(3 for p in phrases if p in text)
            total = score + phrase_bonus

            if total >= 3 or (total >= 2 and "australia" in rec.get("org", "").lower()):
                rec["_country"] = cc
                rec["_score"] = total
                results.append(rec)

    results.sort(key=lambda x: (-x["_score"], -(x.get("spend") or 0)))
    return results[:30]


def get_competitor_portfolios(austender):
    if not austender:
        return {}

    by_supplier = austender.get("by_supplier", {})
    portfolios = {}
    for name, stats in sorted(by_supplier.items(), key=lambda x: -x[1].get("value", 0))[:15]:
        portfolios[name] = {
            "total_contracts": stats.get("count", 0),
            "total_value_aud": stats.get("value", 0),
            "pacific_contracts": stats.get("pacific_count", 0),
            "pacific_value_aud": stats.get("pacific_value", 0),
        }
    return portfolios


def cross_reference(query):
    snapshot = _latest_snapshot()
    if not snapshot:
        print("No snapshot found.", file=sys.stderr)
        return None

    austender = _load_austender()
    index = _load_index()

    item = find_pipeline_item(snapshot, query)
    if not item:
        print(f"No pipeline item matching '{query}'", file=sys.stderr)
        return None

    title = item.get("title", "")
    item_id = item.get("id", "")
    country = _detect_country(title)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Pipeline item: {item_id} — {title}", file=sys.stderr)
    print(f"Section: {item.get('section', '?')}", file=sys.stderr)
    print(f"Country: {country or 'Pacific/Regional'}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    at_contracts = find_austender_contracts(austender, title, country)
    iati_acts = find_iati_activities(index, title, country)
    competitors = get_competitor_portfolios(austender)

    if at_contracts:
        print(f"\n--- AusTender contracts ({len(at_contracts)}) ---", file=sys.stderr)
        for c in at_contracts[:10]:
            sups = ", ".join(s["name"] for s in c.get("suppliers", []))[:50]
            print(f"  AUD ${c.get('value_aud',0):>14,.0f} | {c.get('start','')[:10]}–{c.get('end','')[:10]} | {sups}", file=sys.stderr)
            print(f"    {c.get('description','')[:80]}", file=sys.stderr)
    else:
        print("\n--- No AusTender matches ---", file=sys.stderr)

    if iati_acts:
        print(f"\n--- IATI activities ({len(iati_acts)}) ---", file=sys.stderr)
        for a in iati_acts[:10]:
            spend = a.get("spend", 0) or 0
            print(f"  ${spend:>12,.0f} | {a.get('org','')[:40]} | {a.get('title','')[:60]}", file=sys.stderr)
    else:
        print("\n--- No IATI matches ---", file=sys.stderr)

    result = {
        "item": item,
        "country": country,
        "austender_contracts": at_contracts,
        "iati_activities": [{k: v for k, v in a.items() if not k.startswith("_")} for a in iati_acts],
        "competitor_portfolios": competitors,
        "austender_total": sum(c.get("value_aud", 0) for c in at_contracts),
        "iati_total_spend": sum((a.get("spend") or 0) for a in iati_acts),
    }

    return result


def cross_reference_all():
    snapshot = _latest_snapshot()
    if not snapshot:
        print("No snapshot found.", file=sys.stderr)
        return

    items = snapshot.get("dfat", {}).get("items", [])
    print(f"Cross-referencing {len(items)} pipeline items...\n", file=sys.stderr)

    results = {}
    for item in items:
        item_id = item.get("id", "")
        title = item.get("title", "")
        r = cross_reference(item_id or title)
        if r:
            key = item_id or title[:30]
            results[key] = {
                "title": title,
                "section": item.get("section", ""),
                "country": r.get("country"),
                "austender_matches": len(r.get("austender_contracts", [])),
                "austender_value": r.get("austender_total", 0),
                "iati_matches": len(r.get("iati_activities", [])),
                "iati_spend": r.get("iati_total_spend", 0),
            }

    print(f"\n{'='*80}", file=sys.stderr)
    print(f"PIPELINE CROSS-REFERENCE SUMMARY", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"{'Item':<40} {'AT#':>4} {'AT Value':>14} {'IATI#':>5} {'IATI Spend':>14}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)
    for key, r in sorted(results.items(), key=lambda x: -x[1]["austender_value"]):
        print(f"{r['title'][:39]:<40} {r['austender_matches']:>4} ${r['austender_value']:>13,.0f} {r['iati_matches']:>5} ${r['iati_spend']:>13,.0f}", file=sys.stderr)

    out = os.path.join(DATA, "pipeline-xref.json")
    with open(out, "w") as f:
        json.dump({
            "generated": datetime.now(timezone.utc).isoformat(),
            "items": results,
        }, f, indent=1)
    print(f"\nSaved to {out}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pipeline_xref.py <DFAT-ID or keywords or --all>", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--all":
        cross_reference_all()
    else:
        query = " ".join(sys.argv[1:])
        result = cross_reference(query)
        if result:
            print(json.dumps(result, indent=2, default=str))
