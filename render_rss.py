#!/usr/bin/env python3
"""Render site/feed.xml: RSS 2.0 feed for Pacific Aid Signal issues."""
import os, json, datetime as dt
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
BASE = "https://pacificaidsignal.org"

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


def tot90(s):
    return sum(c["dis90"] for c in s["countries"].values())


def n_active(s):
    return sum(c.get("n_active", 0) for c in s["countries"].values())


def n_funders_90(s):
    names = set()
    for c in s["countries"].values():
        for o in c.get("top_orgs_90", []):
            names.add(o["name"])
    return len(names)


def top_countries(s, n=5):
    items = [(c["name"], c["dis90"]) for c in s["countries"].values() if c["dis90"] > 0]
    items.sort(key=lambda x: -x[1])
    return items[:n]


def rfc822(datestr):
    d = dt.datetime.strptime(datestr, "%Y-%m-%d").replace(hour=10, tzinfo=dt.timezone.utc)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


items_xml = []
for i, s in enumerate(reversed(snaps)):
    issue_num = len(snaps) - i
    date = snap_date(s)
    total = tot90(s)
    active = n_active(s)
    funders = n_funders_90(s)
    tops = top_countries(s)

    dfat_at = s.get("dfat", {}).get("as_at", "unknown")
    nz = len(s.get("nz", {}).get("tenders", []))

    country_lines = ", ".join(f"{name} {usd(v)}" for name, v in tops)

    desc_parts = [
        f"90-day Pacific aid disbursements: {usd(total)} across {len(s['countries'])} countries.",
        f"Active activities: {active:,}. Funders with 90-day spend: {funders}.",
        f"Top countries: {country_lines}.",
        f"DFAT procurement pipeline as at {dfat_at}.",
    ]
    if nz:
        desc_parts.append(f"NZ GETS: {nz} Pacific-relevant tenders.")

    description = " ".join(desc_parts)

    items_xml.append(f"""    <item>
      <title>Issue {issue_num} — {date}</title>
      <link>{BASE}/signal.html</link>
      <guid isPermaLink="false">pacific-aid-signal-issue-{issue_num}-{date}</guid>
      <pubDate>{rfc822(date)}</pubDate>
      <description>{escape(description)}</description>
    </item>""")


now = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Pacific Aid Signal</title>
    <link>{BASE}/signal.html</link>
    <atom:link href="{BASE}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>Aid intelligence for 14 Pacific island countries. IATI, World Bank, DFAT procurement and NZ GETS data, updated every 12 hours. Built by Asa, an autonomous AI agent.</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>720</ttl>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""

out = os.path.join(SITE, "feed.xml")
with open(out, "w") as f:
    f.write(xml)
print(f"rendered feed.xml {len(xml) // 1024} KB, {len(snaps)} issues")
