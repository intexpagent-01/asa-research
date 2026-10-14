#!/usr/bin/env python3
"""UNDP Pacific jobs scraper for the Consultant Radar.

UNDP's jobs portal (jobs.undp.org) lists staff positions, personal service
agreements, and internships. The portal renders server-side HTML with country
checkboxes. We fetch the page and extract Pacific-country listings.

Volume is typically low (1-5 Pacific positions at any time) but UNDP is a
major employer in the region.

Privacy: only structured job metadata is collected. No personal data.
"""
import re, html as htmlmod, json, sys, os, datetime as dt, urllib.request

BASE = "https://jobs.undp.org"
LIST_URL = BASE + "/cj_view_jobs.cfm"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) asa-research/0.9 (pacific-consultant-radar)"}

PACIFIC_COUNTRIES = {
    "Papua New Guinea", "Fiji", "Samoa", "Tonga", "Vanuatu",
    "Solomon Islands", "Kiribati", "Tuvalu", "Nauru", "Palau",
    "Marshall Islands", "Micronesia", "Cook Islands", "Niue",
    "Timor-Leste",
}

COUNTRY_RE = re.compile(
    r"\b(Papua New Guinea|Fiji|Samoa|Tonga|Vanuatu|Solomon Islands|Kiribati"
    r"|Tuvalu|Nauru|Palau|Marshall Islands|Micronesia|Cook Islands|Niue"
    r"|Timor.Leste|Suva|Port Moresby|Apia|Honiara|Port Vila|Nuku.alofa)\b", re.I)

CITY_TO_COUNTRY = {
    "suva": "Fiji",
    "port moresby": "Papua New Guinea",
    "apia": "Samoa",
    "honiara": "Solomon Islands",
    "port vila": "Vanuatu",
    "nuku'alofa": "Tonga",
    "nukualofa": "Tonga",
}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def text(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()


def parse_jobs_page(page_html):
    """Parse UNDP jobs portal HTML, returning list of job dicts.

    The portal uses div.vacanciesTable__row elements (not standard HTML tables),
    with each job wrapped in an <a> tag linking to Oracle HCM.
    """
    jobs = []

    entries = re.findall(
        r'<a[^>]*href="([^"]+)"[^>]*class="vacanciesTableLink vacanciesTable__row[^"]*"[^>]*>(.*?)</a>',
        page_html, re.S)

    for job_url, body in entries:
        title_m = re.search(r'<span>(.*?)</span>', body)
        title = text(title_m.group(1)) if title_m else ""

        loc_m = re.search(r'Location.*?<span>(.*?)</span>', body, re.S)
        location = text(loc_m.group(1)) if loc_m else ""

        level_m = re.search(r'Post Level.*?<span>(.*?)</span>', body, re.S)
        level = text(level_m.group(1)) if level_m else ""

        deadline_m = re.search(r'Apply before.*?<span>(.*?)</span>', body, re.S)
        closing_date = text(deadline_m.group(1)) if deadline_m else ""

        agency_m = re.search(r'Agency.*?<span>(.*?)</span>', body, re.S)
        agency = text(agency_m.group(1)) if agency_m else "UNDP"

        is_pacific = False
        countries = []
        combined = title + " " + location
        for m in COUNTRY_RE.finditer(combined):
            name = m.group(1).lower()
            country = CITY_TO_COUNTRY.get(name, m.group(1))
            if country in PACIFIC_COUNTRIES and country not in countries:
                countries.append(country)
                is_pacific = True

        if not is_pacific:
            continue

        closing_iso = ""
        if closing_date:
            for fmt in ["%b-%d-%y", "%d-%b-%y", "%B %d, %Y", "%d %B %Y",
                        "%b-%d-%Y", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    cd = dt.datetime.strptime(closing_date.strip(), fmt)
                    if cd.year < 100:
                        cd = cd.replace(year=cd.year + 2000)
                    closing_iso = cd.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

        job = {
            "title": title,
            "level": level,
            "agency": agency,
            "location": location,
            "closing_date": closing_date,
            "closing_iso": closing_iso,
            "url": job_url,
            "countries": countries,
            "source": "undp",
            "opportunity_type": "position",
            "category": "Services",
            "status": "Advertised",
        }
        jobs.append(job)

    return jobs


def fetch_jobs():
    """Fetch and parse Pacific UNDP jobs."""
    print("Fetching UNDP jobs page...", file=sys.stderr)
    page_html = get(LIST_URL)
    jobs = parse_jobs_page(page_html)
    print(f"  found {len(jobs)} Pacific jobs", file=sys.stderr)
    return jobs


def snapshot(jobs, data_dir=None):
    """Save a snapshot."""
    now = dt.datetime.now(dt.timezone.utc)
    data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)

    snap = {
        "source": "undp",
        "fetched": now.isoformat(),
        "total": len(jobs),
        "jobs": jobs,
    }

    path = os.path.join(data_dir, "undp-latest.json")
    with open(path, "w") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    print(f"  saved {len(jobs)} jobs to {path}", file=sys.stderr)
    return snap


def summary(snap):
    """Print human-readable summary."""
    jobs = snap["jobs"]
    print(f"\nUNDP Pacific jobs: {len(jobs)}")
    for j in jobs:
        countries_str = ", ".join(j.get("countries", []))
        print(f"  {j['title'][:60]:<60} {j.get('closing_date', '?'):<15} {countries_str}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch UNDP Pacific jobs")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--data-dir")
    args = parser.parse_args()

    data_dir = args.data_dir or os.path.join(os.path.dirname(__file__), "data")

    if args.summary_only:
        path = os.path.join(data_dir, "undp-latest.json")
        if os.path.exists(path):
            with open(path) as f:
                snap = json.load(f)
            summary(snap)
        else:
            print(f"No snapshot found at {path}", file=sys.stderr)
            sys.exit(1)
        return

    jobs = fetch_jobs()
    snap = snapshot(jobs, data_dir)
    summary(snap)


if __name__ == "__main__":
    main()
