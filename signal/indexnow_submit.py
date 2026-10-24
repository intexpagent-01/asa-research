#!/usr/bin/env python3
"""Submit URLs to IndexNow (Bing, Yandex, Seznam, Naver) for faster indexing."""
import json, sys, urllib.request, urllib.error, xml.etree.ElementTree as ET, os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
KEY = "1d086706cf37412f829f9970fd41ffbe"
HOST = "pacificaidsignal.org"
ENDPOINT = "https://api.indexnow.org/indexnow"

def urls_from_sitemap():
    path = os.path.join(SITE, "sitemap.xml")
    tree = ET.parse(path)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [loc.text for loc in tree.findall(".//s:loc", ns)]

def submit(urls, max_urls=100):
    priority = [u for u in urls if any(k in u for k in (
        "compliance-checker", "donor-standards", "multi-donor-checklist",
        "/", "signal.html", "us-pacific-aid", "evidence", "lessons-engine"
    ))]
    rest = [u for u in urls if u not in priority]
    ordered = priority + rest

    batch = ordered[:max_urls]
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": batch,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        print(f"IndexNow: submitted {len(batch)} URLs — HTTP {resp.status}")
        return resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"IndexNow: HTTP {e.code} — {body}")
        return e.code
    except Exception as e:
        print(f"IndexNow: error — {e}")
        return None

def main():
    urls = urls_from_sitemap()
    print(f"Sitemap: {len(urls)} URLs")
    if not urls:
        print("No URLs to submit.")
        return
    status = submit(urls)
    if status == 200:
        print("Success: URLs submitted for indexing by Bing, Yandex, Seznam, Naver.")
    elif status == 202:
        print("Accepted: URLs queued for processing.")
    elif status == 422:
        print("Key file not yet accessible — deploy site first, then retry.")
    else:
        print(f"Unexpected status. Will retry next wake if needed.")

if __name__ == "__main__":
    main()
