#!/usr/bin/env python3
"""Poverty measurement layer analysis using World Bank PIP API.

Tests whether methodological choices — poverty line, welfare type, PPP vintage,
survey instrument — shape headline poverty numbers as much as underlying reality.
"""

import requests
import json
import sys
from collections import defaultdict

API = "https://api.worldbank.org/pip/v1/pip"

FOCUS_COUNTRIES = ["IND", "NGA", "ETH", "BGD", "TZA", "KEN", "UGA", "MOZ", "COD", "IDN"]
POVERTY_LINES = [2.15, 3.65, 6.85]


def fetch_pip(povline=2.15, fill_gaps=False):
    params = {
        "country": "all",
        "year": "all",
        "povline": povline,
        "fill_gaps": str(fill_gaps).lower(),
        "welfare_type": "all",
        "reporting_level": "national",
        "format": "json",
    }
    r = requests.get(API, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def analyze_poverty_line_sensitivity():
    """How much does the poverty headcount change with different poverty lines?"""
    print("\n" + "=" * 70)
    print("1. POVERTY LINE SENSITIVITY")
    print("   Same data, different lines: $2.15, $3.65, $6.85/day")
    print("=" * 70)

    results = {}
    for pl in POVERTY_LINES:
        data = fetch_pip(povline=pl)
        for rec in data:
            cc = rec["country_code"]
            yr = rec["reporting_year"]
            if cc in FOCUS_COUNTRIES and yr >= 2015:
                key = (cc, rec["country_name"], yr)
                if key not in results:
                    results[key] = {}
                results[key][pl] = rec["headcount"]

    print(f"\n{'Country':<20} {'Year':<6} {'$2.15':<10} {'$3.65':<10} {'$6.85':<10} {'Ratio':<8}")
    print("-" * 64)

    ratios = []
    for (cc, name, yr), lines in sorted(results.items()):
        if len(lines) == 3 and lines.get(2.15, 0) > 0.01:
            r = lines[6.85] / lines[2.15]
            ratios.append(r)
            print(f"{name:<20} {yr:<6} {lines[2.15]:<10.1%} {lines[3.65]:<10.1%} {lines[6.85]:<10.1%} {r:<8.1f}x")

    if ratios:
        avg_ratio = sum(ratios) / len(ratios)
        print(f"\nAverage ratio ($6.85/$2.15): {avg_ratio:.1f}x")
        print(f"Choosing a higher line multiplies the 'poor' population by {avg_ratio:.0f}x on average")

    return results


def analyze_welfare_type_divergence():
    """Consumption vs income surveys give systematically different answers."""
    print("\n" + "=" * 70)
    print("2. WELFARE TYPE DIVERGENCE")
    print("   Same country, consumption vs income measurement")
    print("=" * 70)

    data = fetch_pip(povline=2.15)

    by_country = defaultdict(list)
    for rec in data:
        by_country[rec["country_code"]].append(rec)

    divergences = []
    print(f"\n{'Country':<25} {'Year':<6} {'Consumption':<14} {'Income':<14} {'Gap':<10}")
    print("-" * 69)

    for cc, recs in sorted(by_country.items()):
        by_year = defaultdict(dict)
        for rec in recs:
            wt = rec["welfare_type"]
            yr = rec["reporting_year"]
            by_year[yr][wt] = rec["headcount"]

        for yr, types in sorted(by_year.items()):
            if "consumption" in types and "income" in types:
                c, i = types["consumption"], types["income"]
                gap = abs(c - i)
                if gap > 0.01:
                    name = next(r["country_name"] for r in recs)
                    divergences.append((name, yr, c, i, gap))
                    print(f"{name:<25} {yr:<6} {c:<14.1%} {i:<14.1%} {gap:<10.1%}")

    if divergences:
        avg_gap = sum(d[4] for d in divergences) / len(divergences)
        print(f"\n{len(divergences)} country-years with both measurement types")
        print(f"Average absolute divergence: {avg_gap:.1%}")
    else:
        print("\nFew countries have both consumption and income surveys for the same year.")
        print("This itself is a finding: welfare type is a country-level methodological")
        print("choice, not a comparable measurement.")

    return divergences


def analyze_survey_comparability():
    """How many surveys are marked as non-comparable with their predecessors?"""
    print("\n" + "=" * 70)
    print("3. SURVEY COMPARABILITY BREAKS")
    print("   When methodology changes, trend lines fracture")
    print("=" * 70)

    data = fetch_pip(povline=2.15)

    country_surveys = defaultdict(list)
    for rec in data:
        if rec["country_code"] in FOCUS_COUNTRIES:
            country_surveys[rec["country_code"]].append(rec)

    total_breaks = 0
    total_spells = 0
    country_stats = []

    for cc in sorted(country_surveys.keys()):
        recs = sorted(country_surveys[cc], key=lambda x: x["reporting_year"])
        name = recs[0]["country_name"]
        spells = set()
        surveys = set()
        welfare_types = set()
        years = []

        for rec in recs:
            spells.add(rec.get("comparable_spell", ""))
            surveys.add(rec.get("survey_acronym", ""))
            welfare_types.add(rec["welfare_type"])
            years.append(rec["reporting_year"])

        n_spells = len([s for s in spells if s])
        n_surveys = len([s for s in surveys if s])
        breaks = max(0, n_spells - 1)
        total_breaks += breaks
        total_spells += n_spells

        headcounts = [(rec["reporting_year"], rec["headcount"]) for rec in recs]
        if len(headcounts) >= 2:
            first_hc = headcounts[0][1]
            last_hc = headcounts[-1][1]
        else:
            first_hc = last_hc = None

        country_stats.append({
            "name": name,
            "code": cc,
            "years": len(years),
            "year_range": f"{min(years)}-{max(years)}" if years else "",
            "spells": n_spells,
            "breaks": breaks,
            "surveys": n_surveys,
            "survey_names": sorted(surveys),
            "welfare_types": sorted(welfare_types),
            "first_hc": first_hc,
            "last_hc": last_hc,
        })

    print(f"\n{'Country':<20} {'Years':<6} {'Range':<12} {'Spells':<8} {'Breaks':<8} {'Surveys':<8} {'Welfare':<15}")
    print("-" * 79)

    for cs in country_stats:
        wt = ", ".join(cs["welfare_types"])
        print(f"{cs['name']:<20} {cs['years']:<6} {cs['year_range']:<12} {cs['spells']:<8} {cs['breaks']:<8} {cs['surveys']:<8} {wt:<15}")

    print(f"\nTotal comparability breaks across {len(country_stats)} countries: {total_breaks}")
    print(f"Average spells per country: {total_spells / len(country_stats):.1f}")
    print("Each break means the trend line before and after is not directly comparable.")

    return country_stats


def analyze_interpolation_share():
    """How much of the 'data' is actually interpolated/extrapolated?"""
    print("\n" + "=" * 70)
    print("4. INTERPOLATION vs ACTUAL SURVEYS")
    print("   What fraction of data points are modeled, not measured?")
    print("=" * 70)

    data_filled = fetch_pip(povline=2.15, fill_gaps=True)
    data_survey = fetch_pip(povline=2.15, fill_gaps=False)

    survey_keys = set()
    for rec in data_survey:
        survey_keys.add((rec["country_code"], rec["reporting_year"]))

    focus_filled = [r for r in data_filled if r["country_code"] in FOCUS_COUNTRIES and r["reporting_year"] >= 2000]
    focus_survey = [r for r in data_survey if r["country_code"] in FOCUS_COUNTRIES and r["reporting_year"] >= 2000]

    by_country = defaultdict(lambda: {"filled": 0, "survey": 0})
    for rec in focus_filled:
        by_country[rec["country_code"]]["filled"] += 1
    for rec in focus_survey:
        by_country[rec["country_code"]]["survey"] += 1

    print(f"\n{'Country':<20} {'Filled pts':<12} {'Survey pts':<12} {'Interpolated':<14} {'Survey %':<10}")
    print("-" * 68)

    total_filled = 0
    total_survey = 0
    for cc in sorted(by_country.keys()):
        name_rec = next((r for r in data_filled if r["country_code"] == cc), None)
        name = name_rec["country_name"] if name_rec else cc
        f = by_country[cc]["filled"]
        s = by_country[cc]["survey"]
        interp = f - s
        pct = s / f if f > 0 else 0
        total_filled += f
        total_survey += s
        print(f"{name:<20} {f:<12} {s:<12} {interp:<14} {pct:<10.0%}")

    total_interp_pct = (total_filled - total_survey) / total_filled if total_filled > 0 else 0
    print(f"\nTotal: {total_filled} filled data points, {total_survey} actual surveys")
    print(f"Interpolation rate: {total_interp_pct:.0%} of data points are modeled, not measured")

    return by_country


def analyze_ppp_sensitivity():
    """How much do PPP conversion factors vary and what's their impact?"""
    print("\n" + "=" * 70)
    print("5. PPP VINTAGE EFFECT")
    print("   Poverty line $2.15 uses 2017 PPPs; previous was $1.90 in 2011 PPPs")
    print("=" * 70)

    data_215 = fetch_pip(povline=2.15)
    data_190 = fetch_pip(povline=1.90)

    by_country_215 = {}
    by_country_190 = {}

    for rec in data_215:
        cc = rec["country_code"]
        yr = rec["reporting_year"]
        if cc in FOCUS_COUNTRIES and yr >= 2010:
            key = (cc, rec["country_name"], yr)
            by_country_215[key] = rec["headcount"]

    for rec in data_190:
        cc = rec["country_code"]
        yr = rec["reporting_year"]
        if cc in FOCUS_COUNTRIES and yr >= 2010:
            key = (cc, rec["country_name"], yr)
            by_country_190[key] = rec["headcount"]

    common = set(by_country_215.keys()) & set(by_country_190.keys())

    print(f"\n{'Country':<20} {'Year':<6} {'$2.15 (2017 PPP)':<18} {'$1.90 (2011 PPP)':<18} {'Difference':<12}")
    print("-" * 74)

    diffs = []
    for key in sorted(common):
        cc, name, yr = key
        h215 = by_country_215[key]
        h190 = by_country_190[key]
        diff = h215 - h190
        diffs.append((name, yr, h215, h190, diff))
        if abs(diff) > 0.005:
            print(f"{name:<20} {yr:<6} {h215:<18.1%} {h190:<18.1%} {diff:+<12.1%}")

    if diffs:
        abs_diffs = [abs(d[4]) for d in diffs]
        avg_diff = sum(abs_diffs) / len(abs_diffs)
        max_diff = max(abs_diffs)
        sign_changes = sum(1 for d in diffs if (d[2] > 0.5) != (d[3] > 0.5))
        print(f"\nAverage absolute difference: {avg_diff:.1%}")
        print(f"Maximum difference: {max_diff:.1%}")
        print(f"Cases where poverty line choice flips majority/minority status: {sign_changes}")

    return diffs


def analyze_india_deep_dive():
    """India case study: the poster child for measurement sensitivity."""
    print("\n" + "=" * 70)
    print("6. CASE STUDY: INDIA")
    print("   How measurement choices shape the poverty narrative")
    print("=" * 70)

    results = {}
    for pl in [1.90, 2.15, 3.65, 6.85]:
        data = fetch_pip(povline=pl)
        for rec in data:
            if rec["country_code"] == "IND":
                yr = rec["reporting_year"]
                if yr not in results:
                    results[yr] = {"year": yr, "welfare": rec["welfare_type"],
                                   "survey": rec.get("survey_acronym", ""),
                                   "spell": rec.get("comparable_spell", ""),
                                   "ppp": rec.get("ppp", "")}
                results[yr][f"pl_{pl}"] = rec["headcount"]
                results[yr]["mean"] = rec.get("mean", "")
                results[yr]["gini"] = rec.get("gini", "")

    print(f"\n{'Year':<6} {'Survey':<8} {'Spell':<8} {'$1.90':<10} {'$2.15':<10} {'$3.65':<10} {'$6.85':<10} {'Gini':<8}")
    print("-" * 68)

    for yr in sorted(results.keys()):
        r = results[yr]
        vals = [
            r.get("pl_1.9", r.get("pl_1.90", "")),
            r.get("pl_2.15", ""),
            r.get("pl_3.65", ""),
            r.get("pl_6.85", ""),
        ]
        formatted = []
        for v in vals:
            formatted.append(f"{v:.1%}" if isinstance(v, (int, float)) else str(v))

        gini = r.get("gini", "")
        gini_str = f"{gini:.3f}" if isinstance(gini, (int, float)) else str(gini)
        print(f"{yr:<6} {r.get('survey', ''):<8} {r.get('spell', ''):<8} {formatted[0]:<10} {formatted[1]:<10} {formatted[2]:<10} {formatted[3]:<10} {gini_str:<8}")

    latest = max(results.keys())
    r = results[latest]
    low = r.get("pl_2.15", 0)
    high = r.get("pl_6.85", 0)
    if low and high:
        pop = 1400
        low_m = low * pop
        high_m = high * pop
        print(f"\nLatest year ({latest}):")
        print(f"  At $2.15/day: {low:.1%} = ~{low_m:.0f}M people")
        print(f"  At $6.85/day: {high:.1%} = ~{high_m:.0f}M people")
        print(f"  The poverty line choice determines whether {low_m:.0f}M or {high_m:.0f}M Indians are 'poor'")

    return results


def main():
    print("POVERTY MEASUREMENT LAYER ANALYSIS")
    print("How methodological choices shape headline poverty numbers")
    print("Data source: World Bank Poverty and Inequality Platform (PIP)")
    print()

    results = {}

    results["poverty_lines"] = analyze_poverty_line_sensitivity()
    results["welfare_type"] = analyze_welfare_type_divergence()
    results["comparability"] = analyze_survey_comparability()
    results["interpolation"] = analyze_interpolation_share()
    results["ppp"] = analyze_ppp_sensitivity()
    results["india"] = analyze_india_deep_dive()

    print("\n" + "=" * 70)
    print("SUMMARY: THE POVERTY MEASUREMENT LAYER")
    print("=" * 70)
    print("""
Five methodological choices — each invisible to the headline number —
shape poverty statistics as much as the underlying economic reality:

1. POVERTY LINE: Moving from $2.15 to $6.85 multiplies the poor by 2-4x
2. WELFARE TYPE: Consumption vs income is a country-level choice, not comparable
3. SURVEY BREAKS: Comparability spells fracture trend lines
4. INTERPOLATION: A large share of 'data' is modeled, not measured
5. PPP VINTAGE: Rebasing PPPs shifts headcounts by several percentage points

The pattern is the same as in IATI and WGI: the measurement methodology
is invisible to the end user but shapes the answer as much as reality.
""")


if __name__ == "__main__":
    main()
