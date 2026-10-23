#!/usr/bin/env python3
"""Generate sitemap.xml for pacificaidsignal.org."""
import os, glob, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
BASE = "https://pacificaidsignal.org"
TODAY = dt.date.today().isoformat()

HIGH = {
    "index.html": 1.0,
    "compliance-checker.html": 0.9,
    "multi-donor-checklist.html": 0.8,
    "donor-standards.html": 0.7,
    "us-pacific-aid.html": 0.8,
    "signal.html": 0.8,
    "evidence.html": 0.7,
    "lessons-engine.html": 0.7,
    "quality-intelligence.html": 0.7,
    "radar.html": 0.7,
    "dashboard.html": 0.6,
    "methodology.html": 0.6,
    "about.html": 0.6,
    "mcp.html": 0.6,
    "map.html": 0.6,
    "pacific-signal.html": 0.6,
    "funders.html": 0.5,
    "pipeline.html": 0.5,
    "sectors.html": 0.5,
    "download.html": 0.5,
    "compare.html": 0.5,
    "explorer.html": 0.5,
}

SKIP = {"dev.html", "situation-2026-slides.html", "privacy.html", "pitch.html"}

def main():
    pages = []
    for f in sorted(glob.glob(os.path.join(SITE, "*.html"))):
        name = os.path.basename(f)
        if name in SKIP:
            continue
        with open(f) as fh:
            if "noindex" in fh.read(2000):
                continue
        prio = HIGH.get(name, 0.3)
        freq = "daily" if prio >= 0.8 else "weekly" if prio >= 0.5 else "monthly"
        pages.append((name, prio, freq))

    pages.sort(key=lambda x: -x[1])

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for name, prio, freq in pages:
        loc = f"{BASE}/{name}" if name != "index.html" else BASE + "/"
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{TODAY}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{prio:.1f}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    out = os.path.join(SITE, "sitemap.xml")
    with open(out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"sitemap.xml: {len(pages)} URLs written to {out}")

if __name__ == "__main__":
    main()
