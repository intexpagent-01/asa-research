#!/usr/bin/env python3
"""SPC (Pacific Community) procurement scraper for the Consultant Radar.

SPC (spc.int) is the largest Pacific regional technical organisation. Their
procurement page is a Drupal instance at /procurement with an HTML table of
all tenders — RFPs, RFQs, EOIs — with reference numbers, titles, dates,
locations, project units, categories, and statuses.

1,111 historical tenders. ~20 open ("Advertised") at any time.
Tenders cover consultancies, goods, and services across all 22 Pacific
island members. Many are for independent consultants.

Privacy: no personal data is collected. Contact emails are not present in
the listing table.
"""
import re, html as htmlmod, json, sys, os, datetime as dt, urllib.request

BASE = "https://www.spc.int"
PROCUREMENT_URL = BASE + "/procurement"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) asa-research/0.9 (pacific-consultant-radar)"}

PACIFIC_COUNTRIES = [
    "Papua New Guinea", "Fiji", "Solomon Islands", "Vanuatu", "Samoa",
    "Tonga", "Kiribati", "Tuvalu", "Nauru", "Palau",
    "Marshall Islands", "Micronesia", "Cook Islands", "Niue",
    "Tokelau", "Timor-Leste",
]

COUNTRY_RE = re.compile(
    r"\b(Papua New Guinea|PNG|Fiji|Solomon Islands|Vanuatu|Samoa|Tonga|Kiribati"
    r"|Tuvalu|Nauru|Niue|Naoero|Cook Islands|Marshall Islands|Micronesia|FSM"
    r"|Palau|Tokelau|Timor.Leste|New Caledonia|French Polynesia"
    r"|Pacific|All SPC|All Pacific)\b", re.I)

COUNTRY_NORMALISE = {
    "png": "Papua New Guinea",
    "fsm": "Micronesia",
    "naoero": "Nauru",
    "timor-leste": "Timor-Leste",
    "timor leste": "Timor-Leste",
    "all spc": "Pacific region",
    "all pacific": "Pacific region",
    "pacific": "Pacific region",
}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def text(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()


def parse_procurement_page(page_html):
    """Parse the SPC procurement table into a list of tender dicts."""
    tenders = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S)

    for r in rows[1:]:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(cells) < 6:
            continue

        ref = text(cells[0])
        title_raw = text(cells[1])
        location = text(cells[2])
        unit = text(cells[3])
        category = text(cells[4])
        status = text(cells[5])

        title = re.split(r"Posting date:", title_raw)[0].strip()
        posting_m = re.search(r"Posting date:\s*(.*?)(?:Closing|$)", title_raw)
        closing_m = re.search(r"Closing Date:\s*(.*?)(?:Country|$)", title_raw)
        posting_date = posting_m.group(1).strip() if posting_m else ""
        closing_date = closing_m.group(1).strip() if closing_m else ""

        closing_date = re.sub(r"\s*\d{1,2}/\d{1,2}/\d{2,4}.*$", "", closing_date).strip()
        closing_date = re.sub(r"\s+(?:PRE-B|NOTICE|Clarif).*$", "", closing_date, flags=re.I).strip()

        closing_iso = ""
        if closing_date:
            try:
                cd = dt.datetime.strptime(closing_date, "%d %B %Y")
                closing_iso = cd.strftime("%Y-%m-%d")
            except ValueError:
                pass

        posting_iso = ""
        if posting_date:
            try:
                pd = dt.datetime.strptime(posting_date, "%d %B %Y")
                posting_iso = pd.strftime("%Y-%m-%d")
            except ValueError:
                pass

        countries = []
        for m in COUNTRY_RE.finditer(location + " " + title):
            name = m.group(1)
            normalised = COUNTRY_NORMALISE.get(name.lower(), name)
            if normalised not in countries:
                countries.append(normalised)

        opp_type = "unknown"
        ref_upper = ref.upper()
        if ref_upper.startswith("RFP"):
            opp_type = "rfp"
        elif ref_upper.startswith("RFQ"):
            opp_type = "rfq"
        elif ref_upper.startswith("EOI"):
            opp_type = "eoi"
        elif ref_upper.startswith("RFT"):
            opp_type = "rft"
        elif ref_upper.startswith("ITB"):
            opp_type = "itb"

        tender = {
            "ref": ref,
            "title": title,
            "location": location,
            "unit": unit,
            "category": category,
            "status": status,
            "posting_date": posting_date,
            "posting_iso": posting_iso,
            "closing_date": closing_date,
            "closing_iso": closing_iso,
            "countries": countries,
            "opportunity_type": opp_type,
            "source": "spc",
            "url": PROCUREMENT_URL,
        }
        tenders.append(tender)

    return tenders


def fetch_tenders():
    """Fetch and parse all SPC procurement tenders."""
    print("Fetching SPC procurement page...", file=sys.stderr)
    page_html = get(PROCUREMENT_URL)
    tenders = parse_procurement_page(page_html)
    print(f"  parsed {len(tenders)} tenders", file=sys.stderr)
    return tenders


def snapshot(tenders, data_dir=None):
    """Save a snapshot of current tenders."""
    now = dt.datetime.now(dt.timezone.utc)
    data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)

    advertised = [t for t in tenders if t["status"] == "Advertised"]
    selection = [t for t in tenders if t["status"] == "Selection Process Ongoing"]
    by_status = {}
    for t in tenders:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1

    snap = {
        "source": "spc",
        "fetched": now.isoformat(),
        "total": len(tenders),
        "advertised": len(advertised),
        "selection_ongoing": len(selection),
        "by_status": by_status,
        "tenders": advertised + selection,
    }

    path = os.path.join(data_dir, "spc-latest.json")
    with open(path, "w") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    print(f"  saved {len(snap['tenders'])} open/recent tenders to {path}", file=sys.stderr)
    return snap


def summary(snap):
    """Print a human-readable summary."""
    print(f"\nSPC Procurement: {snap['total']} total, {snap['advertised']} advertised, "
          f"{snap['selection_ongoing']} under selection")
    print(f"Status breakdown: {snap['by_status']}")

    advertised = [t for t in snap["tenders"] if t["status"] == "Advertised"]
    if advertised:
        print(f"\n  Open (Advertised) tenders ({len(advertised)}):")
        for t in sorted(advertised, key=lambda x: x.get("closing_iso", "9999")):
            close = t.get("closing_date", "?")
            countries_str = ", ".join(t.get("countries", []))[:30] or t.get("location", "")[:30]
            print(f"    {t['ref']:<15} {t['title'][:55]:<55} {close:<20} {countries_str}")

    by_cat = {}
    for t in advertised:
        by_cat.setdefault(t["category"], []).append(t)
    if by_cat:
        print(f"\n  By category:")
        for cat, items in sorted(by_cat.items(), key=lambda x: -len(x[1])):
            print(f"    {cat}: {len(items)}")

    by_type = {}
    for t in advertised:
        by_type.setdefault(t["opportunity_type"], []).append(t)
    if by_type:
        print(f"\n  By type:")
        for typ, items in sorted(by_type.items(), key=lambda x: -len(x[1])):
            print(f"    {typ}: {len(items)}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch SPC procurement tenders")
    parser.add_argument("--summary-only", action="store_true",
                        help="Read existing snapshot and print summary")
    parser.add_argument("--data-dir", help="Override data directory")
    args = parser.parse_args()

    data_dir = args.data_dir or os.path.join(os.path.dirname(__file__), "data")

    if args.summary_only:
        path = os.path.join(data_dir, "spc-latest.json")
        if os.path.exists(path):
            with open(path) as f:
                snap = json.load(f)
            summary(snap)
        else:
            print(f"No snapshot found at {path}", file=sys.stderr)
            sys.exit(1)
        return

    tenders = fetch_tenders()
    snap = snapshot(tenders, data_dir)
    summary(snap)


if __name__ == "__main__":
    main()
