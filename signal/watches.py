"""Standing watches for the Pacific Aid Signal.

A watch is one country plus a short query: a funder, a keyword, a tender number, a project name. On every issue
it is matched against the country's current activity index, funder tables, World Bank projects and the DFAT
items naming the country, and the change log reports what matched since the previous issue. No model call at
runtime; the question outlives the session that filed it.

Sources: `watches.json` beside this file (filed by the Operator or Asa), and optionally open GitHub Issues on the
public repository titled "Watch <country>: <query>" (public route approved by the Operator 2026-09-08, C3; set
SIGNAL_WATCH_ISSUES=0 to switch it off). Issue bodies are never read or rendered; the query is reduced to a short safe
character set before use; the author is not shown; the agent never replies on an issue. Limits on the public route:
a private blocklist (`watch-blocklist.txt` beside this file, not published), at most MAX_PER_AUTHOR watches per GitHub
account and MAX_PER_COUNTRY issue-filed watches per country (earliest issues win), duplicates of an existing watch
skipped, and only links back to the repository's own issues are rendered.
"""
import datetime as dt, json, os, re, sys, urllib.request
from dfat_notices import for_country
import mfat_tenders

LOCAL = os.environ.get("SIGNAL_WATCHES") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "watches.json")
ISSUES_API = "https://api.github.com/repos/intexpagent-01/asa-research/issues?state=open&per_page=100&sort=created&direction=asc"
ISSUE_URL = "https://github.com/intexpagent-01/asa-research/issues/"
NEW_ISSUE = "https://github.com/intexpagent-01/asa-research/issues/new?title="
BLOCKLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watch-blocklist.txt")
MAX_PER_AUTHOR, MAX_PER_COUNTRY = 5, 10
SAFE = re.compile(r"[^A-Za-z0-9 .,'&()/-]")
STATUS = {1: "pipeline", 2: "implementation", 3: "finalisation"}
KIND = {"activity": "IATI activity", "funder": "funder", "wb": "World Bank project", "dfat-item": "DFAT pipeline item", "notice": "DFAT notice",
        "nz-tender": "New Zealand MFAT tender"}

def usd(v):
    v = v or 0
    return f"${v/1e9:.1f}B" if abs(v) >= 9.995e8 else f"${v/1e6:.1f}M" if abs(v) >= 9.995e5 else f"${v/1e3:.0f}K" if abs(v) >= 999.5 else f"${v:.0f}"
def esc(s): return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def clean_query(q):
    q = SAFE.sub(" ", q or ""); q = re.sub(r"\s+", " ", q).strip()[:60]
    return q if len(q) >= 3 else None

def blocked(q):
    """True when the query contains a whole word from the private blocklist (one lower-case term per line). A missing
    file blocks nothing."""
    try: terms = [t.strip().lower() for t in open(BLOCKLIST) if t.strip() and not t.startswith("#")]
    except FileNotFoundError: return False
    words = set(re.findall(r"[a-z0-9]+", q.lower()))
    return any(t in words for t in terms)

def file_url(name):
    """Link that opens a new issue with the title pre-filled for one country."""
    from urllib.parse import quote
    return NEW_ISSUE + quote(f"Watch {name}: ")

def load(aliases, names):
    """Watches as {id, code, query, since, source, note[, url]}; local file first, GitHub Issues only if enabled."""
    W = []
    try:
        for i, w in enumerate(json.load(open(LOCAL)), 1):
            q = clean_query(w.get("query")); code = w.get("country")
            if q and code in aliases:
                W.append({"id": w.get("id") or f"W{i}", "code": code, "query": q, "since": w.get("since"), "source": "local", "note": w.get("note") or ""})
    except FileNotFoundError:
        pass
    if os.environ.get("SIGNAL_WATCH_ISSUES", "1") != "0":
        try: W += from_issues(aliases, names, W)
        except Exception as e: print(f"!! GitHub issues read failed ({e}); local watches only", file=sys.stderr)
    return W

def from_issues(aliases, names, existing=()):
    """Watches from open issues titled 'Watch <country>: <query>'. Only the title, number, creation date and author id
    are used; the author id only to cap filings per account, and it is not kept."""
    req = urllib.request.Request(ISSUES_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "pacific-aid-signal"})
    rows = json.load(urllib.request.urlopen(req, timeout=15)); out = []
    seen = {(w["code"], w["query"].lower()) for w in existing}; per_author = {}; per_country = {}; skipped = []
    for it in sorted(rows, key=lambda i: i.get("number") or 0):
        if "pull_request" in it: continue
        m = re.match(r"\s*watch\s+(.+?)\s*:\s*(.+)$", it.get("title") or "", re.I)
        if not m: continue
        want = m.group(1).strip().lower()
        code = next((c for c, al in aliases.items() if want in [a.lower() for a in al] + [c.lower(), names[c].lower()]), None)
        q = clean_query(m.group(2)); n = it.get("number"); author = (it.get("user") or {}).get("id")
        url = it.get("html_url") or ""
        if not (code and q): skipped.append((n, "unparsed")); continue
        if blocked(q): skipped.append((n, "blocklist")); continue
        if (code, q.lower()) in seen: skipped.append((n, "duplicate")); continue
        if per_author.get(author, 0) >= MAX_PER_AUTHOR: skipped.append((n, "author cap")); continue
        if per_country.get(code, 0) >= MAX_PER_COUNTRY: skipped.append((n, "country cap")); continue
        if not url.startswith(ISSUE_URL): url = f"{ISSUE_URL}{n}"
        seen.add((code, q.lower())); per_author[author] = per_author.get(author, 0) + 1; per_country[code] = per_country.get(code, 0) + 1
        out.append({"id": f"#{n}", "code": code, "query": q, "since": (it.get("created_at") or "")[:10], "source": "issue", "note": "", "url": url})
    print(f"   watches from issues: {len(out)} accepted" + (f", skipped {skipped}" if skipped else ""), file=sys.stderr)
    return out

# ---------------------------------------------------------------- matching
def _pat(q): return r"(?<![A-Za-z0-9])" + re.escape(q) + r"(?![A-Za-z0-9])"
def hit(q, *texts):
    flags = re.I if len(q) > 3 else 0
    return any(t and re.search(_pat(q), str(t), flags) for t in texts)

def matches(w, r, dfat, aliases, nz=None):
    """Hits for one watch in one country's snapshot record: {kind, key, label, detail, sort}. Returns None when the
    record has no activity index (issues before the watches feature), so a diff against it is not attempted."""
    idx = r.get("acts_index")
    if not idx: return None
    q = w["query"]; H = []
    cols = idx["cols"]
    for row in idx["rows"]:
        a = dict(zip(cols, row))
        if hit(q, a["title"], a["org"], a["aid"]):
            st = STATUS.get(a["st"], str(a["st"])) + (", stale" if a.get("stale") else "")
            det = f"{a['org']}; {st}; {a['start'] or '?'} to {a['end'] or '?'}; {usd(a['spend'])} spent"
            if a.get("pct") is not None and a["pct"] < 99.5: det += f"; {'under 1' if a['pct'] < 1 else f'{a['pct']:.0f}'}% declared for this country"
            if a.get("names"): det += f"; title names {a['names']}"
            rank = 3 if a.get("stale") else {2: 0, 1: 1, 3: 2}.get(a["st"], 3)
            H.append({"kind": "activity", "key": a["aid"], "label": a["title"], "detail": det, "sort": (rank, -(a["spend"] or 0)),
                      "ref": a["ref"], "org": a["org"]})
    F = {}
    for o in r.get("orgs_90", []):
        if hit(q, o["name"], o["ref"]): F.setdefault(o["ref"], {"name": o["name"], "bits": []})["bits"].append(f"disbursed {usd(o['usd'])} in the last 90 days")
    for f in r.get("currency", []):
        if hit(q, f["name"], f["ref"]): F.setdefault(f["ref"], {"name": f["name"], "bits": []})["bits"].append(f"newest transaction {f['latest'] or 'none'}; {usd(f['lifetime_usd'])} lifetime")
    for ref, name, last in r.get("quiet_orgs", []):
        if hit(q, name, ref): F.setdefault(ref, {"name": name, "bits": []})["bits"].append(f"quiet since {last}")
    for f in r.get("active_by_funder", []):
        if hit(q, f["name"], f["ref"]): F.setdefault(f["ref"], {"name": f["name"], "bits": []})["bits"].append(f"{f['n']} active activities")
    for ref, v in F.items(): H.append({"kind": "funder", "key": ref, "label": v["name"], "detail": "; ".join(v["bits"]), "sort": (0, 0)})
    for p in r.get("wb_recent", []):
        if hit(q, p["name"], p["id"]): H.append({"kind": "wb", "key": p["id"], "label": p["name"], "detail": f"approved {p['approved']}; {usd(p['amount'])}", "sort": (0, -(p["amount"] or 0))})
    for p in r.get("wb_pipeline", []):
        if hit(q, p["name"], p["id"]): H.append({"kind": "wb", "key": p["id"], "label": p["name"], "detail": "pipeline" + (f"; {usd(p['amount'])}" if p.get("amount") else ""), "sort": (1, 0)})
    cn, rn, cp, rp = for_country(dfat, r["code"], aliases)
    for p in cp + rp:
        if hit(q, p["title"], p["id"], p.get("status")): H.append({"kind": "dfat-item", "key": p["id"], "label": f"{p['id']} {p['title']}", "detail": f"{p['section']}; {p.get('status') or ''}".rstrip("; "), "sort": (0, 0)})
    cutoff = (dt.date.today() - dt.timedelta(days=365)).isoformat()      # older notices are history, not a live match
    for n in cn + rn:
        if (n.get("date") or "") >= cutoff and hit(q, n["title"], n.get("summary")):
            H.append({"kind": "notice", "key": n["url"], "label": n["title"], "detail": f"{n.get('date') or ''} {n.get('category') or ''}".strip(), "sort": (0, -int((n.get("date") or "0000").replace("-", "") or 0)), "url": n["url"]})
    zc, zr = mfat_tenders.for_country(nz, r["code"], aliases)
    for t in zc + zr:
        if hit(q, t["title"], t.get("overview"), t.get("ref"), t.get("dept")):
            det = mfat_tenders.STATUS_WORD.get(t["status"], t["status"])
            o = t.get("outcome") or {}
            if o.get("supplier"): det += f"; awarded to {o['supplier']}"
            elif o.get("state"): det += f"; {o['state']}"
            H.append({"kind": "nz-tender", "key": t["id"], "label": t["title"], "detail": det,
                      "sort": (0 if t["status"] == "open" else 1, 0), "url": t.get("url")})
    H.sort(key=lambda h: (["dfat-item", "nz-tender", "notice", "funder", "activity", "wb"].index(h["kind"]), h["sort"], h["label"]))
    return H

def _tail(h):
    """An activity identifier with its publisher's own prefix removed. IATI identifiers are conventionally
    <org ref>-<publisher's own reference>, so the tail survives a change of organisation identifier."""
    k, ref = h.get("key") or "", h.get("ref") or ""
    return k[len(ref):].lstrip("-") if ref and k.startswith(ref) else k

def _reidentified(new, gone):
    """A publisher that re-registers under a new IATI organisation identifier makes every one of its activities look
    like one hit leaving and an identical one arriving. Pair those up so the change log can say what really happened.

    Deliberately strict: same kind and title, a different organisation identifier, and the same identifier tail. Two
    unrelated activities that merely share a title are left as a separate arrival and departure, which is honest.
    Found on 2026-09-10, when IM-CR-017899B ("Manx Times") became IM-CR-024714B ("openmindedly")."""
    pool = list(gone); moved = []; arrivals = []
    for h in new:
        m = next((g for g in pool if g["kind"] == "activity" == h["kind"]
                  and (g["label"] or "").strip().lower() == (h["label"] or "").strip().lower()
                  and (g.get("ref") or "") != (h.get("ref") or "") and _tail(g) == _tail(h)), None)
        if m: pool.remove(m); moved.append((m, h))
        else: arrivals.append(h)
    return arrivals, pool, moved

def diff(cur, prev, moved=False):
    """(new, gone[, reidentified]) by (kind, key); prev None means the watch was not checked against the previous issue.

    Hits whose publisher merely changed its organisation identifier are held out of both lists; pass moved=True to
    receive them as (old, new) pairs."""
    if prev is None: return (None, None, None) if moved else (None, None)
    pk = {(h["kind"], h["key"]) for h in prev}; ck = {(h["kind"], h["key"]) for h in cur}
    n = [h for h in cur if (h["kind"], h["key"]) not in pk]; g = [h for h in prev if (h["kind"], h["key"]) not in ck]
    n, g, mv = _reidentified(n, g)
    return (n, g, mv) if moved else (n, g)

def first_seen(w, snaps, aliases):
    """Issue date on which each hit first matched, across issues that carry an activity index."""
    seen = {}
    for s in snaps:
        r = s["countries"].get(w["code"])
        if not r or not r.get("acts_index"): continue
        for h in matches(w, r, s.get("dfat"), aliases, s.get("nz")) or []: seen.setdefault((h["kind"], h["key"]), s["date"])
    return seen

# ---------------------------------------------------------------- rendering
def file_para(name):
    return (f"Anyone with a GitHub account can file one: <a href='{esc(file_url(name))}'>open an issue</a> on the repository titled "
            f"<code>Watch {esc(name)}: your query</code> (3 to 60 plain characters). The agent reads the title on its next run, never the body, "
            f"shows the query and the issue number here without the author, and does not reply on the issue: this page is the answer. "
            f"Closing the issue withdraws the watch. Watches filed by the Operator of this experiment or by the agent are marked as such.")
def line(h):
    lab = f"<a href='{esc(h['url'])}'>{esc(h['label'])}</a>" if h.get("url") else esc(h["label"])
    return f"{lab} <span class=muted>({KIND[h['kind']]}; {esc(h['detail'])})</span>"

def change_lines(watches, r, pr, dfat, pdfat, aliases, nz=None, pnz=None):
    """Change-log entries for a country's watches: new and lost matches, three per watch."""
    out = []
    for w in watches:
        cur = matches(w, r, dfat, aliases, nz)
        if cur is None: continue
        new, gone, moved = diff(cur, matches(w, pr, pdfat, aliases, pnz) if pr else None, moved=True)
        if new is None:
            out.append(f"Watch “{esc(w['query'])}” first checked in this issue: {len(cur)} match{'es' if len(cur) != 1 else ''} on file."); continue
        for h in new[:3]: out.append(f"Watch “{esc(w['query'])}”: new match, {line(h)}.")
        for o, h in moved[:2]:
            out.append(f"Watch “{esc(w['query'])}”: same activity, new publisher identity — {esc(h['label'])} is now published by "
                       f"{esc(h.get('org'))} ({esc(h.get('ref'))}), previously {esc(o.get('org'))} ({esc(o.get('ref'))}). The publisher re-registered; "
                       f"the activity did not change.")
        if len(moved) > 2: out[-1] += f" {len(moved)-2} more of its activities moved with it."
        if len(new) > 3: out[-1] += f" And {len(new)-3} more new matches for this watch."
        if gone: out.append(f"Watch “{esc(w['query'])}”: no longer matching " + ", ".join(esc(h["label"]) for h in gone[:3]) + (f" and {len(gone)-3} more" if len(gone) > 3 else "") + " (left the record, or the match moved outside the window).")
    return out

def brief_sentence(watches, r, pr, dfat, pdfat, aliases, name, nz=None, pnz=None):
    if not watches: return ""
    n_new = 0; checked = 0; first = 0; on_file = 0
    for w in watches:
        cur = matches(w, r, dfat, aliases, nz)
        if cur is None: continue
        checked += 1; on_file += len(cur); new, _ = diff(cur, matches(w, pr, pdfat, aliases, pnz) if pr else None)
        if new is None: first += 1
        else: n_new += len(new)
    if not checked: return ""
    k = len(watches); head = f"{k} standing watch{'es are' if k != 1 else ' is'} held for {name}; "
    if first == checked: return head + f"first checked in this issue, {on_file} match{'es' if on_file != 1 else ''} on file."
    return head + (f"{n_new} new match{'es' if n_new != 1 else ''} this issue." if n_new else "no new matches this issue.")

def html(watches, r, pr, snaps, dfat, pdfat, aliases, longdate, name, limit=8, nz=None, pnz=None):
    """Section body for one country page."""
    if not watches:
        return f"<p class=muted>No standing watch is held for {esc(name)}. A watch is a funder, keyword, tender number or project name that the agent checks on every issue and reports on in the change log above. {file_para(name)}</p>"
    H = [f"<details><summary>What a standing watch is, and how to file one</summary><p>A watch is a question asked once and checked on every issue: the agent matches it against {esc(name)}'s current activities, funders, World Bank projects, DFAT items and New Zealand MFAT tenders and reports what changed. {file_para(name)}</p></details>"]
    for w in watches:
        src = f"filed {longdate(w['since'])}" if w.get("since") else "filed date unknown"
        if w.get("url"): src += f", <a href='{esc(w['url'])}'>issue {esc(w['id'])}</a>"
        elif w.get("note"): src += f"; {esc(w['note'])}"
        H.append(f"<h4>“{esc(w['query'])}” <span class=muted style='font-weight:normal'>({src})</span></h4>")
        cur = matches(w, r, dfat, aliases, nz)
        if cur is None: H.append("<p class=muted>Not yet checked: this issue carries no activity index. From the next issue the watch is matched on every run.</p>"); continue
        new, gone, moved = diff(cur, matches(w, pr, pdfat, aliases, pnz) if pr else None, moved=True)
        if new is None: status = f"First checked in this issue: {len(cur)} match{'es' if len(cur) != 1 else ''} on file."
        elif new or gone or moved: status = f"Since the previous issue: {len(new)} new match{'es' if len(new) != 1 else ''}" + (f", {len(gone)} no longer matching" if gone else "") + (f", {len(moved)} republished under a new publisher identifier" if moved else "") + f"; {len(cur)} on file."
        else: status = f"Since the previous issue: no change; {len(cur)} match{'es' if len(cur) != 1 else ''} on file."
        H.append(f"<p style='font-size:.9rem'><strong>{status}</strong></p>")
        if cur:
            seen = first_seen(w, snaps, aliases); base = min(seen.values()) if seen else None
            newk = {(h["kind"], h["key"]) for h in (new or [])}
            H.append("<ul>")
            for h in cur[:limit]:
                fs = seen.get((h["kind"], h["key"]))
                mark = " <span class=up>new</span>" if (h["kind"], h["key"]) in newk else (f" <span class=muted>first matched {longdate(fs)}</span>" if fs and base and fs > base else "")
                H.append(f"<li>{line(h)}{mark}</li>")
            if len(cur) > limit: H.append(f"<li class=muted>and {len(cur)-limit} more</li>")
            H.append("</ul>")
        else: H.append("<p class=muted>Nothing on record matches this watch.</p>")
    return "\n".join(H)
