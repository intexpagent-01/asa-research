#!/usr/bin/env python3
"""Render per-country RSS feeds: site/feed-<slug>.xml for each of the 14 countries."""
import os, json, datetime as dt
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
BASE = "https://pacificaidsignal.org"

COUNTRIES = [
    ("PG","Papua New Guinea","papua-new-guinea"),("FJ","Fiji","fiji"),
    ("SB","Solomon Islands","solomon-islands"),("VU","Vanuatu","vanuatu"),
    ("WS","Samoa","samoa"),("TO","Tonga","tonga"),("KI","Kiribati","kiribati"),
    ("TV","Tuvalu","tuvalu"),("FM","Micronesia (Fed. States)","micronesia"),
    ("MH","Marshall Islands","marshall-islands"),("PW","Palau","palau"),
    ("NR","Nauru","nauru"),("NU","Niue","niue"),("CK","Cook Islands","cook-islands"),
]

snap_files = sorted(
    f for f in os.listdir(os.path.join(HERE, "data"))
    if f.startswith("pacific-") and f.endswith(".json") and "index" not in f
)

snaps = []
for f in snap_files:
    with open(os.path.join(HERE, "data", f)) as fh:
        snaps.append(json.load(fh))


def usd(v):
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def snap_date(s):
    return s.get("date", s.get("generated", "")[:10])


def rfc822(datestr):
    d = dt.datetime.strptime(datestr, "%Y-%m-%d").replace(hour=10, tzinfo=dt.timezone.utc)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


def country_item(code, name, slug, s, prev_s, issue_num):
    """Build one RSS <item> for a country in a given issue."""
    date = snap_date(s)
    c = s["countries"].get(code)
    if not c:
        return None

    dis90 = c["dis90"]
    prev_dis90 = c.get("dis_prev90", 0)
    n_funders = c.get("n_orgs_90", 0)
    n_active = c.get("n_active", 0)
    n_stale = c.get("n_stale", 0)
    n_ending = c.get("n_ending_soon", 0)
    n_new = c.get("n_new_starts", 0)

    # Compute delta from previous snapshot
    delta_line = ""
    if prev_s and code in prev_s["countries"]:
        prev_val = prev_s["countries"][code]["dis90"]
        if prev_val > 0:
            pct = (dis90 - prev_val) / prev_val * 100
            direction = "up" if pct > 0 else "down"
            delta_line = f" ({direction} {abs(pct):.0f}% from previous issue)."
        elif dis90 > 0:
            delta_line = " (new spending this issue)."

    # Top funders
    top_funders = c.get("top_orgs_90", [])[:3]
    funder_line = ""
    if top_funders:
        parts = [f"{escape(f['name'])} ({f['pct']:.0f}%)" for f in top_funders]
        funder_line = f" Top funders: {', '.join(parts)}."

    # DFAT items for this country
    dfat = s.get("dfat", {})
    dfat_items = [it for it in dfat.get("items", []) if code in it.get("countries", [])]
    dfat_line = ""
    if dfat_items:
        in_market = sum(1 for it in dfat_items if it.get("stage", "").lower() in ("in market", "rfq", "rft"))
        if in_market:
            dfat_line = f" DFAT pipeline: {in_market} in market."

    # NZ tenders
    nz = s.get("nz", {})
    nz_tenders = [t for t in nz.get("tenders", []) if code in t.get("countries", [])]
    nz_line = ""
    if nz_tenders:
        nz_line = f" NZ tenders: {len(nz_tenders)}."

    desc = (
        f"{name}: {usd(dis90)} in 90-day IATI-reported disbursements{delta_line}"
        f" {n_funders} funders reporting, {n_active:,} active activities, "
        f"{n_stale} stale, {n_ending} ending within 180 days, {n_new} new starts."
        f"{funder_line}{dfat_line}{nz_line}"
    )

    page_url = f"{BASE}/pacific-signal-{slug}.html"

    return f"""    <item>
      <title>{escape(name)} — Issue {issue_num}, {date}</title>
      <link>{page_url}</link>
      <guid isPermaLink="false">pacific-aid-signal-{slug}-issue-{issue_num}-{date}</guid>
      <pubDate>{rfc822(date)}</pubDate>
      <description>{escape(desc)}</description>
    </item>"""


now = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
count = 0

for code, name, slug in COUNTRIES:
    items_xml = []
    for i, s in enumerate(reversed(snaps)):
        issue_num = len(snaps) - i
        prev_s = snaps[len(snaps) - i - 2] if (len(snaps) - i - 2) >= 0 else None
        item = country_item(code, name, slug, s, prev_s, issue_num)
        if item:
            items_xml.append(item)

    feed_file = f"feed-{slug}.xml"
    page_url = f"{BASE}/pacific-signal-{slug}.html"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Pacific Aid Signal — {escape(name)}</title>
    <link>{page_url}</link>
    <atom:link href="{BASE}/{feed_file}" rel="self" type="application/rss+xml"/>
    <description>Aid intelligence for {escape(name)}. IATI disbursements, funder activity, DFAT procurement and NZ GETS data, updated every 12 hours. Built by Asa, an autonomous AI agent.</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>720</ttl>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""

    out = os.path.join(SITE, feed_file)
    with open(out, "w") as f:
        f.write(xml)
    count += 1

print(f"rendered {count} country RSS feeds, {len(snaps)} issues each")
