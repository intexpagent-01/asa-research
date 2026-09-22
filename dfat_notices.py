#!/usr/bin/env python3
"""DFAT business notifications and Development Procurement Pipeline as a source for the Pacific Aid Signal.

DFAT's IATI publication lags by more than a year, but its business-notifications page (calls for proposals,
market approaches, consultations) and its procurement pipeline page (tenders in the market, in collaboration,
planned, closed) are current and public. A desk officer reads them anyway; the service adds the per-country
filter, the first-seen date, and the diff between issues.

Contact e-mail addresses on the pipeline page are personal and are stripped before anything is stored.
"""
import re, html, sys, time, urllib.request, datetime as dt

BASE = "https://www.dfat.gov.au"
NOTICES = BASE + "/about-us/business-opportunities/business-notifications"
PIPELINE = BASE + "/about-us/business-opportunities/development-procurement-pipeline"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) asa-research/0.7 (pacific-aid-signal)"}

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def text(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()

def strip_contacts(fragment):
    """Remove mailto links, bare e-mail addresses and the empty parentheses they leave behind."""
    f = re.sub(r"\(\s*<a href=\"mailto:[^\"]*\"[^>]*>.*?</a>\s*\)", "", fragment, flags=re.S)
    f = re.sub(r"<a href=\"mailto:[^\"]*\"[^>]*>.*?</a>", "", f, flags=re.S)
    f = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "", f)
    f = re.sub(r"\(\s*\)", "", f)
    f = re.sub(r"The shortlisted organisations and their points of contact for this procurement are \(in alphabetical order\):", "Shortlisted:", f)
    return re.sub(r"\s+([,.;])", r"\1", f)

def fetch_notices(max_pages=12, pause=0.5):
    """All business notifications, newest first: title, url, date (ISO), category, summary."""
    out, seen = [], set()
    for p in range(max_pages):
        s = get(NOTICES + (f"?page={p}" if p else ""))
        rows = re.findall(r'<li class="views-row">(.*?)</li>\s*(?=<li class="views-row">|</ul>)', s, re.S)
        if not rows: break
        for row in rows:
            m = re.search(r'<h3 class="teaser__title">.*?<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
            if not m: continue
            url = m.group(1) if m.group(1).startswith("http") else BASE + m.group(1)
            if url in seen: continue
            seen.add(url)
            d = re.search(r'<time datetime="(\d{4}-\d\d-\d\d)', row)
            cat = re.search(r'field--name-field-category.*?<div class="field__item">(.*?)</div>', row, re.S)
            summ = re.search(r'teaser__summary[^>]*>(.*?)</div>\s*</div>', row, re.S)
            out.append({"title": text(m.group(2)), "url": url, "date": d.group(1) if d else None,
                        "category": text(cat.group(1)) if cat else None, "summary": text(summ.group(1))[:400] if summ else ""})
        time.sleep(pause)
    return out

def fetch_pipeline():
    """Pipeline items: id, title, section (In the market / In collaboration / Closed / Planned), status text."""
    s = get(PIPELINE)
    i = s.rfind("The following list of proposed projects"); body = s[i:]
    j = body.find("</main"); body = body[:j] if j > 0 else body
    as_at = re.search(r"As at ([^<]+)</strong>", body)
    items, section = [], None
    for kind, content in re.findall(r"<(h2|h3|p)[^>]*>(.*?)</\1>", body, re.S):
        if kind == "h2": section = text(content)
        elif kind == "h3" and section:
            m = re.match(r"\s*(DFAT-\d+)\s*:\s*(.*)", text(content))
            items.append({"id": m.group(1) if m else text(content)[:20], "title": m.group(2).strip() if m else text(content),
                          "section": section, "status": ""})
        elif kind == "p" and items and section:
            t = text(strip_contacts(content))
            if t and items[-1]["section"] == section: items[-1]["status"] = (items[-1]["status"] + " " + t).strip()[:600]
    return {"as_at": text(as_at.group(1)) if as_at else None, "items": items}

def fetch_all():
    t0 = time.time()
    d = {"fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
         "notices": fetch_notices()}
    d.update(fetch_pipeline())
    print(f"DFAT: {len(d['notices'])} notices, {len(d['items'])} pipeline items (as at {d['as_at']}) [{time.time()-t0:.0f}s]", file=sys.stderr, flush=True)
    return d

# ---------------------------------------------------------------- matching (done at render time so alias changes apply to old issues)
def _pat(a): return r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])"
def matches(item, code, aliases):
    """True if the item's title or text names the country. Regional ("Pacific") items are matched separately."""
    t = item["title"] + " " + (item.get("summary") or item.get("status") or "")
    return any(re.search(_pat(a), t, re.I if len(a) > 3 else 0) for a in aliases[code])
def regional(item, aliases):
    """Names the Pacific (or Indo-Pacific) in the title and no specific country in the title."""
    if not re.search(r"(?<![A-Za-z])Pacific(?![A-Za-z])", item["title"]): return False
    return not any(re.search(_pat(a), item["title"], re.I if len(a) > 3 else 0) for al in aliases.values() for a in al)

def for_country(dfat, code, aliases):
    """Split a snapshot's DFAT block into (country notices, regional notices, country pipeline, regional pipeline)."""
    if not dfat: return [], [], [], []
    N = dfat.get("notices", []); P = dfat.get("items", [])
    cn = [n for n in N if matches(n, code, aliases)]; rn = [n for n in N if regional(n, aliases) and not matches(n, code, aliases)]
    cp = [p for p in P if matches(p, code, aliases)]; rp = [p for p in P if regional(p, aliases) and not matches(p, code, aliases)]
    return cn, rn, cp, rp

if __name__ == "__main__":
    import json
    d = fetch_all()
    json.dump(d, sys.stdout, indent=1)
