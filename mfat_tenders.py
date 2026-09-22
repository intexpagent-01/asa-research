#!/usr/bin/env python3
"""New Zealand MFAT tenders, read from GETS, as a second bilateral procurement source for the Pacific Aid Signal.

New Zealand is the second bilateral funder of the Pacific after Australia, and like Australia its IATI
publication lags. Its live procurement is on GETS (the Government Electronic Tenders Service), which is
public, free and searchable but has no per-country view: the Pacific items sit among several hundred
open tenders from every New Zealand agency, council and university. The service adds the country filter,
the first-seen date, and the diff between issues — including the outcome, which GETS publishes and which
is the part a desk officer cannot get from IATI at all.

Three lists are read: open tenders, closed tenders (bidding shut, outcome not yet published) and completed
tenders (outcome published, including "not awarded"). Rows are kept when the buying agency is MFAT or when
the title names a Pacific country or the region; only kept rows have their detail page fetched.

Named contacts, e-mail addresses and telephone numbers appear on GETS detail pages. They are personal
information about people doing their jobs and are stripped before anything is stored: the contact fields are
never read, and overview text is cut at the point where it turns into contact instructions.
"""
import re, html, sys, time, urllib.request, datetime as dt

BASE = "https://www.gets.govt.nz"
LISTS = [("open", "ExternalIndex.htm"), ("closed", "ExternalClosedTenderList.htm"), ("completed", "ExternalAwardedTenderList.htm")]
SEARCH = BASE + "/ExternalIndex.htm"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) asa-research/0.8 (pacific-aid-signal)"}
AGENCY = "Ministry of Foreign Affairs and Trade"

# Coarse keep-filter applied while scanning the lists, so that only plausible rows cost a detail fetch.
# Country matching proper is done at render time by dfat_notices.matches, against the same alias table.
HINT = re.compile(r"(?<![A-Za-z])(Pacific|Fiji|Samoa|Tonga|Vanuatu|Solomon Islands|Kiribati|Tuvalu|Nauru|Niue"
                  r"|Tokelau|Cook Islands|Papua New Guinea|PNG|Marshall Islands|Micronesia|Palau|Polynesia|Melanesia)"
                  r"(?![A-Za-z])", re.I)

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def text(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()

def para(fragment):
    """Flatten a detail-page paragraph, keeping its line breaks as sentence boundaries."""
    f = re.sub(r"<br\s*/?>", "\n", fragment or "")
    f = re.sub(r"</(p|li|div|tr)>", "\n", f)
    t = re.sub(r"<[^>]+>", " ", f)
    t = html.unescape(t)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()

# ---------------------------------------------------------------- personal information
# GETS detail pages carry the buying agency's named contact, and award notices carry the supplier's name and
# postal address — which, when the supplier is one person, is their home address. None of that is stored.
# Contact fields are never read; overview text is cut where it turns into contact instructions; and the
# published outcome is never kept as text at all, only as the classified fields below.
CONTACT_CUE = re.compile(r"(for (all )?(correspondence|queries|enquiries|further information)[^\n]*?contact"
                         r"|please contact\b|point of contact\b|contact details\b|contact person\b)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?\d[\d\s()-]{7,}\d)")
ADDRESS = re.compile(r"\s*[\u2013-]\s*[^.]{0,60}?,[^.]{0,60}?,[^.]{0,90}?\b(NEW ZEALAND|AUSTRALIA)\b", re.I)

def strip_contacts(t):
    """Cut a block of text where it turns into contact instructions, then remove any address, number or link left."""
    if not t: return ""
    m = CONTACT_CUE.search(t)
    if m: t = t[:m.start()]
    t = ADDRESS.sub("", t)
    keep = [ln for ln in t.split("\n") if not EMAIL.search(ln) and not PHONE.search(ln)]
    t = "\n".join(keep)
    t = re.sub(r"https?://(?!www\.gets\.govt\.nz)\S+", "", t)       # third-party links (job boards, agency portals)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n+", " ", t)).strip(" \u2013-,;:")

# ---------------------------------------------------------------- the published outcome, as fields rather than text
# GETS publishes what happened, which is the part IATI never carries. It is kept as a small set of fields instead
# of as free text: a person's name is not a procurement fact worth republishing, the postal address certainly is
# not, and a record with no free text cannot carry an instruction onto a page either.
ENTITY = re.compile(r"\b(Limited|Ltd|LLC|Inc|Incorporated|Pty|PLC|Trust|Group|Services|Consulting|Consultants"
                    r"|Partners|Partnership|Company|Corporation|Foundation|University|Institute|Association"
                    r"|Council|Holdings|Solutions|Contractors|Construction|Engineering|Associates)\b", re.I)
TITLE = re.compile(r"\b(Sir|Dame|Dr|Mr|Mrs|Ms|Prof|Professor|Hon)\b\.?", re.I)
# Two award layouts appear: GETS's own award box ("This tender has been awarded. <supplier> Value $ ..."), and
# free text written by the buyer ("...has been awarded on 4 September 2026 to <supplier>").
AWARD_BOX = re.compile(r"award(?:ed)?\s*[.:]\s*([^.,;]{2,70}?)(?=\s+Value\b|\s+Further\b|\s*$)", re.I)
AWARDED_TO = re.compile(r"award(?:ed)?\s+(?:to|on[^,.]{0,30}?\bto)\s*:?\s*([^.,;]{2,70})", re.I)
VALUE = re.compile(r"(?:value(?:\s+of)?|contract value(?:\s+of)?)\s*[:~]?\s*\$\s*([\d,]+(?:\.\d+)?)", re.I)
DATED = re.compile(r"(?:Award Date|Date RFx was completed/updated)\s*:?\s*(?:\w+day,?\s*)?(\d{1,2})\s+(\w+)\s+(\d{4})", re.I)
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}

def _looks_organisation(n):
    """Positive evidence that a name is an entity: a company-style word, or an all-capitals initialism."""
    if ENTITY.search(n): return True
    return any(w.isupper() and len(w) > 1 and w.isalpha() for w in n.split())

def _organisation(name):
    """The awardee as an organisation, or None when the notice names a person.

    A person is not republished here: their name is on the GETS page, one click away, and the fact that the
    contract was awarded — which is what a country desk needs — survives without it. The test is deliberately
    conservative: a name counts as an organisation only on positive evidence, so an unrecognised name is
    treated as a person and withheld.
    """
    n = " ".join((name or "").split()).strip(" -\u2013:")
    n = re.split(r"\s+as of\b|\s+with effect\b|\s+for the\b", n, flags=re.I)[0].strip()
    if not n: return None
    # "<person> of <entity>": the contracting party is the entity, so keep that half and drop the person.
    if " of " in n:
        head, tail = n.split(" of ", 1)
        if not _looks_organisation(head) and _looks_organisation(tail) and not TITLE.search(tail):
            return tail.strip()
    if TITLE.search(n): return None
    return n if _looks_organisation(n) else None

def classify_outcome(t):
    """The published outcome as fields: state, supplier (organisations only), value, date, superseded-by."""
    if not t: return None
    t = ADDRESS.sub("", t)          # before anything is read out of it, so no address can reach a field
    o = {}
    low = t.lower()
    sup = re.search(r"superseded by GETS listing (\d+)", t, re.I)
    if sup: o["superseded_by"] = sup.group(1)
    if re.search(r"not been (successfully )?awarded|no bids|cancelled|withdrawn", low): o["state"] = "not awarded"
    elif sup and "no winner" in low: o["state"] = "superseded"
    elif re.search(r"has been awarded|contract (has been |was )?awarded|awarded to", low): o["state"] = "awarded"
    elif "no winner" in low: o["state"] = "not awarded"
    else: o["state"] = "completed"
    if o["state"] == "awarded":
        org = None
        for pat in (AWARD_BOX, AWARDED_TO):
            for cand in pat.findall(t):
                org = _organisation(cand)
                if org: break
            if org: break
        if org: o["supplier"] = org[:80]
        else: o["supplier_withheld"] = True
    v = VALUE.search(t)
    if v:
        try: o["value_nzd"] = float(v.group(1).replace(",", ""))
        except ValueError: pass
    d = DATED.search(t)
    if d and d.group(2).lower() in MONTHS:
        try: o["date"] = dt.date(int(d.group(3)), MONTHS[d.group(2).lower()], int(d.group(1))).isoformat()
        except ValueError: pass
    # The buyer's own note is free text and can name anyone in it. It is kept only where it carries something the
    # fields above cannot — why a tender ended without an award, or what superseded it — and never for an award,
    # where supplier, value and date already say everything and the sentence is usually "awarded to <a person>".
    note = re.search(r"Further (?:information|Award Information)\s*:?\s*([^\n]{4,200})", t, re.I)
    if note and o["state"] != "awarded":
        n = strip_contacts(note.group(1))
        n = re.sub(r"\s*Date RFx was completed.*$", "", n, flags=re.I)
        if any(c and not _organisation(c) for c in AWARDED_TO.findall(n)): n = ""   # names a person
        if n and n.strip().lower() not in ("completed by system",): o["note"] = n[:180]
    return o

# ---------------------------------------------------------------- list pages
ROW = re.compile(r'<tr id="tender-(\d+)"[^>]*>(.*?)</tr>', re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
DETAIL = re.compile(r'href="([^"]*ExternalTenderDetails\.htm\?id=\d+)"')

def scan_list(path, status, max_pages, pause):
    """One GETS list, newest first: the rows worth keeping, with the list-level fields."""
    out, seen = [], set()
    for p in range(1, max_pages + 1):
        s = get(f"{BASE}/{path}?page={p}&orderBy=date")
        rows = ROW.findall(s)
        if not rows: break
        fresh = 0
        for tid, body in rows:
            if tid in seen: continue
            seen.add(tid); fresh += 1
            c = [text(x) for x in CELL.findall(body)]
            if len(c) < 6: continue
            org, title = c[5], c[2]
            if AGENCY.lower() not in org.lower() and not HINT.search(title): continue
            m = DETAIL.search(body)
            out.append({"id": tid, "ref": c[1] if c[1] != "[None]" else None, "title": title, "type": c[3],
                        "date_label": c[4], "org": org, "status": status,
                        "url": (BASE + "/" + m.group(1)) if m else None})
        if not fresh: break
        time.sleep(pause)
    return out

# ---------------------------------------------------------------- detail pages
FIELD = re.compile(r'<td class="label-cell">(.*?)</td>\s*<td[^>]*>(.*?)</td>', re.S)
SECTION = re.compile(r'<div class="detail-divider">\s*<span class="legend">(.*?)</span>\s*</div>\s*(.*?)(?=<div class="detail-divider">|</div>\s*</div>|$)', re.S)
KEEP_FIELDS = {"Department/Business Unit": "dept", "Tender Type": "type_full", "Tender Coverage": "coverage",
               "Categories": "categories", "Regions": "regions", "Open Date": "opened", "Close Date": "closes",
               "Reference #": "ref"}

def fetch_detail(t):
    """Add the description, the published outcome and the structured fields. Contact fields are never read."""
    s = get(t["url"])
    i = s.find('class="tender-details-info-tbl"')
    body = s[i:] if i > 0 else s
    for label, value in FIELD.findall(body):
        key = KEEP_FIELDS.get(text(label).rstrip(" :").strip())
        if key:
            v = text(value).replace("[?]", "").strip()
            if v: t[key] = v[:300]
    for name, content in SECTION.findall(body):
        n = text(name).lower()
        if n == "overview": t["overview"] = strip_contacts(para(content))[:700]
        elif "outcome" in n: t["outcome"] = classify_outcome(para(content))
    t["summary"] = t.get("overview", "")      # the key dfat_notices.matches reads
    return t

# MFAT's aid budget sits in these business units; a tender in one of them is development spending even when its
# title names no country ("Relief Supplies Logistics"). Anything else is kept only if it names the Pacific.
AID_DEPT = {"crown funding", "partner government tenders"}

def pacific_relevant(t):
    if (t.get("dept") or "").strip().lower() in AID_DEPT: return True
    return bool(HINT.search(" ".join(filter(None, [t.get("title"), t.get("overview"), t.get("regions")]))))

def fetch_all(max_pages=18, pause=0.4, detail_pause=0.3):
    t0 = time.time(); found, seen = [], set()
    for status, path in LISTS:
        for t in scan_list(path, status, max_pages, pause):
            if t["id"] in seen: continue          # a tender can appear on two lists; the first (most open) state wins
            seen.add(t["id"]); found.append(t)
    ok = 0
    for t in found:
        if not t["url"]: continue
        try:
            fetch_detail(t); ok += 1
        except Exception as e:
            print(f"!! GETS detail {t['id']} failed ({e})", file=sys.stderr)
        time.sleep(detail_pause)
    kept = [t for t in found if pacific_relevant(t)]
    d = {"fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
         "tenders": kept}
    n_mfat = sum(1 for t in kept if AGENCY.lower() in t["org"].lower())
    print(f"GETS: {len(kept)} Pacific-relevant tenders of {len(found)} scanned ({n_mfat} MFAT), "
          f"{ok} detail pages [{time.time()-t0:.0f}s]", file=sys.stderr, flush=True)
    return d

# ---------------------------------------------------------------- matching (at render time, like DFAT)
def for_country(nz, code, aliases):
    """(tenders naming the country, Pacific-wide tenders) from a snapshot's GETS block."""
    import dfat_notices
    if not nz: return [], []
    T = nz.get("tenders", [])
    cn = [t for t in T if dfat_notices.matches(t, code, aliases)]
    rn = [t for t in T if dfat_notices.regional(t, aliases) and not dfat_notices.matches(t, code, aliases)]
    return cn, rn

STATUS_WORD = {"open": "open for bids", "closed": "closed, outcome not yet published", "completed": "completed"}

if __name__ == "__main__":
    import json
    json.dump(fetch_all(), sys.stdout, indent=1)
