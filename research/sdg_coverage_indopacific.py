#!/usr/bin/env python3
"""SDG indicator coverage — Indo-Pacific edition.

Reuses the indicator sample and API client from sdg_coverage.py, but with a
region-specific country set and generic group handling.
Groups: PIC = Pacific Island countries (incl. Timor-Leste), ASIA = Southeast and
South Asian developing countries, HIC = high-income regional comparators.
"""
import json, sys, time
from collections import defaultdict
sys.path.insert(0, "research")
from sdg_coverage import check_indicator_for_country, SAMPLE_INDICATORS, INDICATOR_NAMES

COUNTRIES = {
    "598": ("Papua New Guinea", "PIC"), "90": ("Solomon Islands", "PIC"), "548": ("Vanuatu", "PIC"),
    "242": ("Fiji", "PIC"), "882": ("Samoa", "PIC"), "776": ("Tonga", "PIC"), "296": ("Kiribati", "PIC"),
    "798": ("Tuvalu", "PIC"), "583": ("Micronesia (FSM)", "PIC"), "584": ("Marshall Islands", "PIC"),
    "520": ("Nauru", "PIC"), "585": ("Palau", "PIC"), "626": ("Timor-Leste", "PIC"),
    "360": ("Indonesia", "ASIA"), "608": ("Philippines", "ASIA"), "704": ("Viet Nam", "ASIA"),
    "116": ("Cambodia", "ASIA"), "418": ("Lao PDR", "ASIA"), "104": ("Myanmar", "ASIA"),
    "50": ("Bangladesh", "ASIA"), "144": ("Sri Lanka", "ASIA"),
    "36": ("Australia", "HIC"), "554": ("New Zealand", "HIC"), "392": ("Japan", "HIC"), "702": ("Singapore", "HIC"),
}
GROUPS = ["PIC", "ASIA", "HIC"]
OUT = "research/sdg_coverage_indopacific.json"

def main():
    n_ind, n_c = len(SAMPLE_INDICATORS), len(COUNTRIES)
    print(f"Indo-Pacific SDG coverage: {n_ind} indicators x {n_c} countries = {n_ind*n_c} queries", flush=True)
    from concurrent.futures import ThreadPoolExecutor
    coverage = {ind: {} for ind in SAMPLE_INDICATORS}
    jobs = [(ind, code) for ind in SAMPLE_INDICATORS for code in COUNTRIES]
    def run(job):
        ind, code = job
        has, nat, yrs = check_indicator_for_country(ind, code)
        return ind, code, {"has_data": has, "nature": nat, "years": yrs}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, (ind, code, res) in enumerate(ex.map(run, jobs), 1):
            coverage[ind][code] = res
            if i % 50 == 0: print(f"  {i}/{len(jobs)}", flush=True)

    ind_stats = []
    for ind in SAMPLE_INDICATORS:
        row = {"code": ind, "name": INDICATOR_NAMES.get(ind, ""), "total": sum(1 for c in COUNTRIES if coverage[ind][c]["has_data"])}
        for g in GROUPS:
            members = [c for c, (_, gg) in COUNTRIES.items() if gg == g]
            has = sum(1 for c in members if coverage[ind][c]["has_data"])
            row[g] = has; row[g + "_pct"] = round(has / len(members) * 100, 1)
        ind_stats.append(row)

    country_stats = []
    for code, (name, g) in COUNTRIES.items():
        has = sum(1 for ind in SAMPLE_INDICATORS if coverage[ind][code]["has_data"])
        natures = defaultdict(int)
        for ind in SAMPLE_INDICATORS:
            if coverage[ind][code]["has_data"] and coverage[ind][code]["nature"]:
                natures[coverage[ind][code]["nature"]] += 1
        cp = natures.get("C", 0) + natures.get("CA", 0)
        country_stats.append({"code": code, "name": name, "group": g, "indicators": has,
                              "pct": round(has / n_ind * 100, 1), "country_produced": cp,
                              "country_pct": round(cp / has * 100, 1) if has else 0, "natures": dict(natures),
                              "missing": [ind for ind in SAMPLE_INDICATORS if not coverage[ind][code]["has_data"]]})

    summary = {}
    nature_mix = {}
    for g in GROUPS:
        members = [c for c in country_stats if c["group"] == g]
        summary[g] = {"n": len(members),
                      "avg_indicators": round(sum(c["indicators"] for c in members) / len(members), 1),
                      "avg_pct": round(sum(c["pct"] for c in members) / len(members), 1),
                      "avg_country_pct": round(sum(c["country_pct"] for c in members) / len(members), 1)}
        tot = defaultdict(int)
        for c in members:
            for k, v in c["natures"].items(): tot[k] += v
        T = sum(tot.values()) or 1
        nature_mix[g] = {k: round(v / T * 100, 1) for k, v in tot.items()}

    goal_stats = {}
    for ind in ind_stats:
        goal = ind["code"].split(".")[0]
        gs = goal_stats.setdefault(goal, {"indicators": [], **{g + "_pcts": [] for g in GROUPS}})
        gs["indicators"].append(ind["code"])
        for g in GROUPS: gs[g + "_pcts"].append(ind[g + "_pct"])
    goal_out = {}
    for goal, gs in goal_stats.items():
        goal_out[goal] = {"indicators": gs["indicators"], **{g + "_avg": round(sum(gs[g + "_pcts"]) / len(gs[g + "_pcts"]), 1) for g in GROUPS}}

    out = {"metadata": {"n_indicators": n_ind, "n_countries": n_c, "groups": {g: summary[g]["n"] for g in GROUPS}},
           "indicator_stats": sorted(ind_stats, key=lambda x: x["total"], reverse=True),
           "country_stats": sorted(country_stats, key=lambda x: (GROUPS.index(x["group"]), x["indicators"])),
           "summary": summary, "nature_mix": nature_mix, "goal_stats": goal_out}
    json.dump(out, open(OUT, "w"), indent=2)

    print("\n=== SUMMARY ===")
    for g in GROUPS:
        print(f"  {g}: {summary[g]} natures={nature_mix[g]}")
    print("\n=== COUNTRIES ===")
    for c in out["country_stats"]:
        print(f"  {c['group']:4s} {c['name']:20s} {c['indicators']:2d}/{n_ind} own:{c['country_pct']:5.1f}% missing={','.join(c['missing'])}")
    print("\n=== INDICATORS (by group %) ===")
    for r in out["indicator_stats"]:
        print(f"  {r['code']:8s} " + " ".join(f"{g}:{r[g+'_pct']:5.1f}" for g in GROUPS) + f"  {r['name']}")
    print("\n=== GOALS ===")
    for goal, gs in sorted(goal_out.items(), key=lambda x: int(x[0])):
        print(f"  Goal {goal:2s} " + " ".join(f"{g}:{gs[g+'_avg']:5.1f}" for g in GROUPS))
    print(f"\nSaved {OUT}")

if __name__ == "__main__":
    main()
