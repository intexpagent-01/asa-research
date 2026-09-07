#!/usr/bin/env python3
"""SDG indicator coverage analysis — how universal are the universal goals?

Strategy: For each indicator, fetch page 1 with pageSize=1 to get totalElements,
then query specific countries to check coverage. Much faster than downloading
full datasets.
"""

import json
import urllib.request
import urllib.parse
import time
import sys
from collections import defaultdict

BASE = "https://unstats.un.org/sdgs/UNSDGAPIV5/v1/sdg"

def api_get(path, params=None, retries=2):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return None

# Key countries for analysis
COUNTRIES = {
    # LDCs (15 — diverse geography)
    "4": ("Afghanistan", "LDC"), "108": ("Burundi", "LDC"), "140": ("Central African Republic", "LDC"),
    "148": ("Chad", "LDC"), "180": ("DR Congo", "LDC"),
    "231": ("Ethiopia", "LDC"), "332": ("Haiti", "LDC"),
    "454": ("Malawi", "LDC"), "466": ("Mali", "LDC"),
    "524": ("Nepal", "LDC"), "562": ("Niger", "LDC"),
    "706": ("Somalia", "LDC"), "728": ("South Sudan", "LDC"),
    "800": ("Uganda", "LDC"), "834": ("Tanzania", "LDC"),
    # Middle-income (5)
    "356": ("India", "MIC"), "404": ("Kenya", "MIC"), "566": ("Nigeria", "MIC"),
    "76": ("Brazil", "MIC"), "710": ("South Africa", "MIC"),
    # High-income OECD (5)
    "276": ("Germany", "HIC"), "392": ("Japan", "HIC"),
    "578": ("Norway", "HIC"), "826": ("United Kingdom", "HIC"), "840": ("United States", "HIC"),
}

SAMPLE_INDICATORS = [
    "1.1.1",  "1.2.1",  "2.1.1",  "2.2.1",  "3.1.1",  "3.2.1",  "3.8.1",
    "4.1.1",  "4.2.2",  "5.5.1",  "5.5.2",  "6.1.1",  "6.2.1",  "7.1.1",
    "7.2.1",  "8.1.1",  "8.5.2",  "9.2.1",  "9.c.1",  "10.1.1", "10.4.1",
    "11.1.1", "11.6.2", "12.2.2", "13.1.1", "14.5.1", "15.1.1", "15.1.2",
    "16.1.1", "16.3.2", "17.1.1", "17.8.1", "17.19.2",
]

INDICATOR_NAMES = {
    "1.1.1": "Population below intl poverty line",
    "1.2.1": "Population below national poverty line",
    "2.1.1": "Prevalence of undernourishment",
    "2.2.1": "Stunting prevalence (under 5)",
    "3.1.1": "Maternal mortality ratio",
    "3.2.1": "Under-5 mortality rate",
    "3.8.1": "UHC service coverage index",
    "4.1.1": "Min proficiency in reading/math",
    "4.2.2": "Pre-primary participation rate",
    "5.5.1": "Women in national parliaments",
    "5.5.2": "Women in managerial positions",
    "6.1.1": "Safely managed drinking water",
    "6.2.1": "Safely managed sanitation",
    "7.1.1": "Access to electricity",
    "7.2.1": "Renewable energy share",
    "8.1.1": "Real GDP per capita growth",
    "8.5.2": "Unemployment rate",
    "9.2.1": "Manufacturing value added % GDP",
    "9.c.1": "Mobile network coverage",
    "10.1.1": "Bottom 40% income growth",
    "10.4.1": "Labour share of GDP",
    "11.1.1": "Urban slum population",
    "11.6.2": "Urban PM2.5 levels",
    "12.2.2": "Domestic material consumption",
    "13.1.1": "Disaster deaths & missing",
    "14.5.1": "Marine protected areas",
    "15.1.1": "Forest area proportion",
    "15.1.2": "KBA protection coverage",
    "16.1.1": "Intentional homicides per 100k",
    "16.3.2": "Unsentenced detainees",
    "17.1.1": "Tax revenue as % of GDP",
    "17.8.1": "Internet users (%)",
    "17.19.2": "Census & vital registration",
}

def check_indicator_for_country(indicator, country_code):
    """Check if a specific country has data for an indicator. Returns (has_data, nature, year_count)."""
    data = api_get("/Indicator/Data", {
        "indicator": indicator,
        "areaCode": country_code,
        "pageSize": 5,
    })
    if not data or "data" not in data or not data["data"]:
        return False, None, 0

    natures = set()
    years = set()
    for rec in data["data"]:
        nat = rec.get("attributes", {}).get("Nature", "?")
        natures.add(nat)
        yr = rec.get("timePeriodStart")
        if yr:
            years.add(yr)

    primary_nature = "C" if "C" in natures else ("CA" if "CA" in natures else
                     ("G" if "G" in natures else ("E" if "E" in natures else
                     ("M" if "M" in natures else "?"))))
    return True, primary_nature, len(years)

def get_indicator_total(indicator):
    """Get total record count for an indicator."""
    data = api_get("/Indicator/Data", {
        "indicator": indicator,
        "pageSize": 1,
    })
    if data:
        return data.get("totalElements", 0)
    return 0

def main():
    print("=" * 70)
    print("SDG INDICATOR COVERAGE ANALYSIS")
    print("How Universal Are the Universal Goals?")
    print("=" * 70)

    n_indicators = len(SAMPLE_INDICATORS)
    n_countries = len(COUNTRIES)
    total_queries = n_indicators * n_countries
    print(f"\nAnalyzing {n_indicators} indicators x {n_countries} countries = {total_queries} queries")
    print("(~2 queries/second, estimated time: ~15 minutes)\n")

    # Matrix: indicator -> country -> (has_data, nature, years)
    coverage = {}
    query_count = 0

    for i, ind in enumerate(SAMPLE_INDICATORS):
        coverage[ind] = {}
        for code in COUNTRIES:
            query_count += 1
            if query_count % 20 == 0:
                sys.stdout.write(f"\r  Progress: {query_count}/{total_queries} ({query_count/total_queries*100:.0f}%)")
                sys.stdout.flush()

            has_data, nature, year_count = check_indicator_for_country(ind, code)
            coverage[ind][code] = {"has_data": has_data, "nature": nature, "years": year_count}
            time.sleep(0.15)

    print(f"\r  Progress: {total_queries}/{total_queries} (100%)         ")

    # Analyze results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    # A. Coverage by indicator
    print("\n--- A. INDICATOR COVERAGE (countries with any data out of {}) ---\n".format(n_countries))
    ind_stats = []
    for ind in SAMPLE_INDICATORS:
        has = sum(1 for c in COUNTRIES if coverage[ind][c]["has_data"])
        ldc_has = sum(1 for c, (name, group) in COUNTRIES.items() if group == "LDC" and coverage[ind][c]["has_data"])
        hic_has = sum(1 for c, (name, group) in COUNTRIES.items() if group == "HIC" and coverage[ind][c]["has_data"])
        ldc_total = sum(1 for c, (name, group) in COUNTRIES.items() if group == "LDC")
        hic_total = sum(1 for c, (name, group) in COUNTRIES.items() if group == "HIC")
        ind_stats.append({
            "code": ind, "total": has, "ldc": ldc_has, "hic": hic_has,
            "ldc_pct": ldc_has / ldc_total * 100, "hic_pct": hic_has / hic_total * 100,
        })

    ind_stats.sort(key=lambda x: x["total"], reverse=True)
    for s in ind_stats:
        name = INDICATOR_NAMES.get(s["code"], "")[:40]
        gap = s["hic_pct"] - s["ldc_pct"]
        gap_marker = f"+{gap:.0f}pp" if gap > 0 else f"{gap:.0f}pp"
        print(f"  {s['code']:8s} | {s['total']:2d}/{n_countries} | LDC:{s['ldc_pct']:5.0f}% HIC:{s['hic_pct']:5.0f}% gap:{gap_marker:>6s} | {name}")

    # B. Coverage by country
    print("\n--- B. COUNTRY COVERAGE (indicators with data out of {}) ---\n".format(n_indicators))
    country_stats = []
    for code, (name, group) in COUNTRIES.items():
        has = sum(1 for ind in SAMPLE_INDICATORS if coverage[ind][code]["has_data"])
        natures = defaultdict(int)
        for ind in SAMPLE_INDICATORS:
            if coverage[ind][code]["has_data"]:
                nat = coverage[ind][code]["nature"]
                if nat:
                    natures[nat] += 1
        country_produced = natures.get("C", 0) + natures.get("CA", 0)
        country_stats.append({
            "code": code, "name": name, "group": group, "indicators": has,
            "pct": has / n_indicators * 100, "country_produced": country_produced,
            "country_pct": country_produced / has * 100 if has > 0 else 0,
            "natures": dict(natures),
        })

    # Sort by group then coverage
    for group_name in ["LDC", "MIC", "HIC"]:
        group_countries = [c for c in country_stats if c["group"] == group_name]
        group_countries.sort(key=lambda x: x["indicators"])
        avg = sum(c["indicators"] for c in group_countries) / len(group_countries) if group_countries else 0
        avg_cp = sum(c["country_pct"] for c in group_countries) / len(group_countries) if group_countries else 0
        print(f"  {group_name} (avg: {avg:.1f}/{n_indicators} indicators, {avg_cp:.0f}% country-produced)")
        for c in group_countries:
            bar = "#" * c["indicators"] + "." * (n_indicators - c["indicators"])
            print(f"    {c['name']:25s} | {c['indicators']:2d}/{n_indicators} | {bar} | own:{c['country_pct']:.0f}%")
        print()

    # C. Coverage gap summary
    print("--- C. COVERAGE GAP SUMMARY ---\n")
    ldc_countries = [c for c in country_stats if c["group"] == "LDC"]
    mic_countries = [c for c in country_stats if c["group"] == "MIC"]
    hic_countries = [c for c in country_stats if c["group"] == "HIC"]

    ldc_avg = sum(c["indicators"] for c in ldc_countries) / len(ldc_countries) if ldc_countries else 0
    mic_avg = sum(c["indicators"] for c in mic_countries) / len(mic_countries) if mic_countries else 0
    hic_avg = sum(c["indicators"] for c in hic_countries) / len(hic_countries) if hic_countries else 0

    ldc_cp = sum(c["country_pct"] for c in ldc_countries) / len(ldc_countries) if ldc_countries else 0
    mic_cp = sum(c["country_pct"] for c in mic_countries) / len(mic_countries) if mic_countries else 0
    hic_cp = sum(c["country_pct"] for c in hic_countries) / len(hic_countries) if hic_countries else 0

    print(f"  LDCs:             {ldc_avg:.1f}/{n_indicators} indicators ({ldc_avg/n_indicators*100:.0f}%), {ldc_cp:.0f}% country-produced")
    print(f"  Middle-income:    {mic_avg:.1f}/{n_indicators} indicators ({mic_avg/n_indicators*100:.0f}%), {mic_cp:.0f}% country-produced")
    print(f"  High-income OECD: {hic_avg:.1f}/{n_indicators} indicators ({hic_avg/n_indicators*100:.0f}%), {hic_cp:.0f}% country-produced")
    print(f"\n  Gap: HICs have {hic_avg - ldc_avg:.1f} more indicators than LDCs on average")
    if ldc_avg > 0:
        print(f"  Ratio: {hic_avg/ldc_avg:.2f}x")

    # D. Data nature breakdown
    print("\n--- D. DATA NATURE: WHO PRODUCES THE NUMBERS? ---\n")
    nature_labels = {"C": "Country", "CA": "Adjusted", "G": "Global", "E": "Estimated", "M": "Modeled"}
    for group_name, group_list in [("LDC", ldc_countries), ("MIC", mic_countries), ("HIC", hic_countries)]:
        totals = defaultdict(int)
        for c in group_list:
            for nat, count in c["natures"].items():
                totals[nat] += count
        total = sum(totals.values()) or 1
        parts = [f"{nature_labels.get(n, n)}: {totals[n]/total*100:.0f}%" for n in ["C", "CA", "G", "E", "M"] if n in totals]
        print(f"  {group_name:4s}: {' | '.join(parts)}")

    # E. Per-goal coverage
    print("\n--- E. COVERAGE BY SDG GOAL ---\n")
    goal_stats = defaultdict(lambda: {"ldc_pcts": [], "hic_pcts": [], "indicators": []})
    for s in ind_stats:
        goal = s["code"].split(".")[0]
        goal_stats[goal]["ldc_pcts"].append(s["ldc_pct"])
        goal_stats[goal]["hic_pcts"].append(s["hic_pct"])
        goal_stats[goal]["indicators"].append(s["code"])

    for goal in sorted(goal_stats.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        gs = goal_stats[goal]
        ldc_avg_g = sum(gs["ldc_pcts"]) / len(gs["ldc_pcts"])
        hic_avg_g = sum(gs["hic_pcts"]) / len(gs["hic_pcts"])
        gap = hic_avg_g - ldc_avg_g
        print(f"  Goal {goal:2s}: LDC {ldc_avg_g:5.0f}% | HIC {hic_avg_g:5.0f}% | gap {gap:+.0f}pp | ({', '.join(gs['indicators'])})")

    # Save JSON for visualization
    output = {
        "metadata": {"n_indicators": n_indicators, "n_countries": n_countries,
                      "n_ldc": len(ldc_countries), "n_mic": len(mic_countries), "n_hic": len(hic_countries)},
        "indicator_stats": [
            {"code": s["code"], "name": INDICATOR_NAMES.get(s["code"], ""),
             "total": s["total"], "ldc": s["ldc"], "hic": s["hic"],
             "ldc_pct": round(s["ldc_pct"], 1), "hic_pct": round(s["hic_pct"], 1)}
            for s in ind_stats
        ],
        "country_stats": [
            {"name": c["name"], "group": c["group"], "indicators": c["indicators"],
             "pct": round(c["pct"], 1), "country_pct": round(c["country_pct"], 1),
             "natures": c["natures"]}
            for c in sorted(country_stats, key=lambda x: ({"LDC": 0, "MIC": 1, "HIC": 2}[x["group"]], x["indicators"]))
        ],
        "summary": {
            "ldc_avg": round(ldc_avg, 1), "mic_avg": round(mic_avg, 1), "hic_avg": round(hic_avg, 1),
            "ldc_cp": round(ldc_cp, 1), "mic_cp": round(mic_cp, 1), "hic_cp": round(hic_cp, 1),
            "gap": round(hic_avg - ldc_avg, 1),
        },
        "goal_stats": {
            goal: {"ldc_avg": round(sum(gs["ldc_pcts"])/len(gs["ldc_pcts"]), 1),
                   "hic_avg": round(sum(gs["hic_pcts"])/len(gs["hic_pcts"]), 1),
                   "indicators": gs["indicators"]}
            for goal, gs in sorted(goal_stats.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 99)
        },
    }

    with open("research/sdg_coverage_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to research/sdg_coverage_results.json")

if __name__ == "__main__":
    main()
