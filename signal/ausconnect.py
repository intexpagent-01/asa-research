#!/usr/bin/env python3
"""AusConnect opportunity scraper for the Consultant Radar.

AusConnect (ausconnect.dfat.gov.au) is DFAT's shared portal where managing contractors
and smaller delivery partners post expressions of interest, short-term adviser panels,
design/review/MEL/GEDSI consultancies, and other subcontracting opportunities. These are
the roles independent Pacific development consultants actually compete for — below the
managing-contract level tracked by the DFAT pipeline and AusTender.

The site is a Drupal instance with paginated HTML at /opportunities?page=N (10 per page).
No API, no login required.

Privacy: AusConnect detail pages may name contacts. The scraper collects only structured
metadata from the list pages (title, URL, close date, posted date, regions, sectors,
summary). Detail pages are fetched only for link validation; contact fields are stripped.
"""
import re, html as htmlmod, json, sys, time, os, datetime as dt, urllib.request

BASE = "https://ausconnect.dfat.gov.au"
LIST_URL = BASE + "/opportunities"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) asa-research/0.9 (pacific-consultant-radar)"}

PACIFIC_HINT = re.compile(
    r"(?<![A-Za-z])(Pacific|Fiji|Samoa|Tonga|Vanuatu|Solomon Islands|Kiribati|Tuvalu|Nauru|Niue"
    r"|Tokelau|Cook Islands|Papua New Guinea|PNG|Marshall Islands|Micronesia|Palau|Polynesia|Melanesia"
    r"|Timor.Leste|Bougainville)"
    r"(?![A-Za-z])", re.I)

SE_ASIA_HINT = re.compile(
    r"(?<![A-Za-z])(Indonesia|Cambodia|Vietnam|Laos|Myanmar|Philippines|Thailand|Mongolia"
    r"|South.East Asia|Southeast Asia|ASEAN)"
    r"(?![A-Za-z])", re.I)

MC_NAMES = [
    "DT Global", "Abt", "Palladium", "Tetra Tech", "Cowater", "Cardno",
    "GHD", "SMEC", "Coffey", "Adam Smith International", "DAI",
    "Mott MacDonald", "Scope Global", "AECOM", "Kpmg", "Deloitte", "PwC", "EY",
]
MC_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in MC_NAMES) + r")\b", re.I)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s()-]{7,}\d)")


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def text(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()


def strip_contacts(t):
    if not t:
        return ""
    lines = [ln for ln in t.split("\n") if not EMAIL_RE.search(ln) and not PHONE_RE.search(ln)]
    return re.sub(r"\s+", " ", "\n".join(lines)).strip()


def parse_list_page(page_html):
    """Parse a single list page, returning a list of opportunity dicts."""
    opps = []
    parts = re.split(r'<article[^>]*class="node node--type-opportunity[^>]*>', page_html)

    for part in parts[1:]:
        block = part.split("</article>")[0] if "</article>" in part else part[:5000]
        opp = {}

        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        if h2:
            opp["title"] = htmlmod.unescape(re.sub(r"<[^>]+>", "", h2.group(1)).strip())

        url_m = re.search(r'href="(/opportunities/[^"]+)"', block)
        if url_m:
            opp["url"] = url_m.group(1)

        close_m = re.search(
            r'field-close-date.*?<time[^>]*datetime="([^"]+)"[^>]*>([^<]+)</time>',
            block, re.S)
        if close_m:
            opp["close_iso"] = close_m.group(1)
            opp["close_display"] = close_m.group(2).strip()

        posted_m = re.search(
            r'field-posted-date.*?<time[^>]*datetime="([^"]+)"',
            block, re.S)
        if posted_m:
            opp["posted_iso"] = posted_m.group(1)

        region_block = re.search(
            r'field-regions(.*?)(?=<div class="(?:text-content|field field--|clearfix))',
            block, re.S)
        if region_block:
            regions = re.findall(r'field__item">\s*(.*?)\s*<', region_block.group(1))
            opp["regions"] = [r.strip() for r in regions if r.strip()]

        sector_block = re.search(
            r'field-sector(.*?)(?=<div class="(?:text-content|field field--|clearfix))',
            block, re.S)
        if sector_block:
            sectors = re.findall(r'field__item">\s*(.*?)\s*<', sector_block.group(1))
            opp["sectors"] = [htmlmod.unescape(s.strip()) for s in sectors if s.strip()]

        summary_m = re.search(r'field-summary.*?<p>(.*?)</p>', block, re.S)
        if summary_m:
            opp["summary"] = strip_contacts(
                htmlmod.unescape(re.sub(r"<[^>]+>", "", summary_m.group(1)).strip()))

        if opp.get("title"):
            opps.append(opp)

    return opps


def classify_opportunity(opp):
    """Tag an opportunity with region classification and detected MC."""
    combined = " ".join([
        opp.get("title", ""),
        " ".join(opp.get("regions", [])),
        " ".join(opp.get("sectors", [])),
        opp.get("summary", ""),
    ])

    opp["is_pacific"] = bool(PACIFIC_HINT.search(combined))
    opp["is_se_asia"] = bool(SE_ASIA_HINT.search(combined))

    mc_m = MC_RE.search(combined)
    if mc_m:
        opp["managing_contractor"] = mc_m.group(1)

    opp_type = "unknown"
    title_lower = opp.get("title", "").lower()
    if any(k in title_lower for k in ["rfp", "rft", "request for"]):
        opp_type = "rfp"
    elif any(k in title_lower for k in ["eoi", "expression of interest"]):
        opp_type = "eoi"
    elif any(k in title_lower for k in [
        "adviser", "advisor", "specialist", "coordinator", "manager",
        "lead", "officer", "director", "consultant", "team leader",
    ]):
        opp_type = "position"
    opp["opportunity_type"] = opp_type

    return opp


def fetch_all_opportunities(max_pages=20, delay=1.5):
    """Fetch all current AusConnect opportunities across paginated pages."""
    all_opps = []
    for page in range(max_pages):
        url = f"{LIST_URL}?page={page}" if page > 0 else LIST_URL
        try:
            page_html = get(url)
        except Exception as e:
            print(f"  page {page}: fetch error: {e}", file=sys.stderr)
            break

        opps = parse_list_page(page_html)
        if not opps:
            break

        for o in opps:
            classify_opportunity(o)
        all_opps.extend(opps)
        print(f"  page {page}: {len(opps)} opportunities", file=sys.stderr)

        if page < max_pages - 1:
            time.sleep(delay)

    return all_opps


def snapshot(opps, data_dir=None):
    """Build and save a snapshot dict."""
    now = dt.datetime.now(dt.timezone.utc)
    data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)

    pacific = [o for o in opps if o.get("is_pacific")]
    se_asia = [o for o in opps if o.get("is_se_asia")]

    open_opps = []
    for o in opps:
        close = o.get("close_iso", "")
        if close:
            try:
                close_dt = dt.datetime.fromisoformat(close.replace("Z", "+00:00"))
                if close_dt >= now:
                    open_opps.append(o)
            except ValueError:
                open_opps.append(o)
        else:
            open_opps.append(o)

    snap = {
        "source": "ausconnect",
        "fetched": now.isoformat(),
        "total": len(opps),
        "pacific": len(pacific),
        "se_asia": len(se_asia),
        "open": len(open_opps),
        "opportunities": opps,
    }

    path = os.path.join(data_dir, "ausconnect-latest.json")
    with open(path, "w") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    print(f"  saved {len(opps)} opportunities to {path}", file=sys.stderr)

    return snap


def summary(snap):
    """Print a human-readable summary of the snapshot."""
    opps = snap["opportunities"]
    pacific = [o for o in opps if o.get("is_pacific")]
    open_pacific = []
    now = dt.datetime.now(dt.timezone.utc)
    for o in pacific:
        close = o.get("close_iso", "")
        if close:
            try:
                close_dt = dt.datetime.fromisoformat(close.replace("Z", "+00:00"))
                if close_dt >= now:
                    open_pacific.append(o)
            except ValueError:
                open_pacific.append(o)
        else:
            open_pacific.append(o)

    print(f"\nAusConnect snapshot: {snap['total']} total, {snap['pacific']} Pacific, {snap['open']} still open")
    print(f"Pacific opportunities still open: {len(open_pacific)}")

    if open_pacific:
        print("\n  Open Pacific opportunities:")
        for o in sorted(open_pacific, key=lambda x: x.get("close_iso", "9999")):
            close = o.get("close_display", o.get("close_iso", "?")[:10])
            mc = o.get("managing_contractor", "")
            mc_str = f" [{mc}]" if mc else ""
            sectors = ", ".join(o.get("sectors", []))[:40]
            print(f"    {close}  {o['title'][:65]}{mc_str}")
            if sectors:
                print(f"             {sectors}")

    by_mc = {}
    for o in pacific:
        mc = o.get("managing_contractor", "Unknown")
        by_mc.setdefault(mc, []).append(o)
    if by_mc:
        print("\n  Pacific opportunities by managing contractor:")
        for mc, items in sorted(by_mc.items(), key=lambda x: -len(x[1])):
            print(f"    {mc}: {len(items)}")

    by_type = {}
    for o in pacific:
        by_type.setdefault(o.get("opportunity_type", "unknown"), []).append(o)
    if by_type:
        print("\n  Pacific opportunities by type:")
        for t, items in sorted(by_type.items(), key=lambda x: -len(x[1])):
            print(f"    {t}: {len(items)}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch AusConnect opportunities")
    parser.add_argument("--summary-only", action="store_true",
                        help="Read existing snapshot and print summary")
    parser.add_argument("--data-dir",
                        help="Override data directory")
    args = parser.parse_args()

    data_dir = args.data_dir or os.path.join(os.path.dirname(__file__), "data")

    if args.summary_only:
        path = os.path.join(data_dir, "ausconnect-latest.json")
        if os.path.exists(path):
            with open(path) as f:
                snap = json.load(f)
            summary(snap)
        else:
            print(f"No snapshot found at {path}", file=sys.stderr)
            sys.exit(1)
        return

    print("Fetching AusConnect opportunities...", file=sys.stderr)
    opps = fetch_all_opportunities()
    snap = snapshot(opps, data_dir)
    summary(snap)


if __name__ == "__main__":
    main()
