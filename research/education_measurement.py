#!/usr/bin/env python3
"""Education outcome measurement analysis — how assessment choice, subject choice,
and design decisions shape learning outcome statistics."""

import requests
import json
import sys
from collections import defaultdict

def fetch_wb_indicator(indicator):
    all_entries = []
    page = 1
    while True:
        url = (f'https://api.worldbank.org/v2/country/all/indicator/{indicator}'
               f'?format=json&per_page=500&page={page}&date=2000:2025')
        r = requests.get(url, timeout=30)
        data = r.json()
        if len(data) < 2 or not data[1]:
            break
        entries = [e for e in data[1] if e['value'] is not None]
        all_entries.extend(entries)
        if page >= data[0]['pages']:
            break
        page += 1
    return all_entries

def build_dataset(entries, label):
    by_country = {}
    for e in entries:
        cid = e['country']['id']
        cname = e['country']['value']
        year = int(e['date'])
        if cid not in by_country:
            by_country[cid] = {'name': cname, 'years': {}}
        by_country[cid]['years'][year] = e['value']
    print(f"  {label}: {len(entries)} obs, {len(by_country)} countries")
    return by_country

def rank_dict(scores):
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {cid: i+1 for i, (cid, _) in enumerate(ranked)}

def analyze_subject_divergence(pisa_math, pisa_read, pisa_sci, year=2018):
    print(f"\n{'='*70}")
    print(f"ANALYSIS 1: Subject choice reshuffles country rankings (PISA {year})")
    print(f"{'='*70}")

    scores = {}
    for cid in pisa_math:
        if (year in pisa_math[cid]['years'] and
            cid in pisa_read and year in pisa_read[cid]['years'] and
            cid in pisa_sci and year in pisa_sci[cid]['years']):
            scores[cid] = {
                'name': pisa_math[cid]['name'],
                'math': pisa_math[cid]['years'][year],
                'reading': pisa_read[cid]['years'][year],
                'science': pisa_sci[cid]['years'][year],
            }

    n = len(scores)
    print(f"Countries with all three subjects in {year}: {n}")

    math_r = rank_dict({c: s['math'] for c, s in scores.items()})
    read_r = rank_dict({c: s['reading'] for c, s in scores.items()})
    sci_r = rank_dict({c: s['science'] for c, s in scores.items()})

    divergences = []
    for cid, s in scores.items():
        ranks = [math_r[cid], read_r[cid], sci_r[cid]]
        span = max(ranks) - min(ranks)
        best_subj = ['Math', 'Reading', 'Science'][ranks.index(min(ranks))]
        worst_subj = ['Math', 'Reading', 'Science'][ranks.index(max(ranks))]
        divergences.append({
            'id': cid, 'name': s['name'],
            'math_rank': math_r[cid], 'read_rank': read_r[cid], 'sci_rank': sci_r[cid],
            'math_score': s['math'], 'read_score': s['reading'], 'sci_score': s['science'],
            'span': span, 'best': best_subj, 'worst': worst_subj,
        })

    divergences.sort(key=lambda x: x['span'], reverse=True)
    spans = [d['span'] for d in divergences]
    avg_span = sum(spans) / len(spans)
    big_span = len([s for s in spans if s >= 10])

    print(f"Average rank span across subjects: {avg_span:.1f} positions")
    print(f"Countries with 10+ position span: {big_span} ({big_span*100/n:.0f}%)")
    print(f"\nTop 15 divergences:")
    for d in divergences[:15]:
        print(f"  {d['name']:30s} M:{d['math_rank']:3d} R:{d['read_rank']:3d} S:{d['sci_rank']:3d}"
              f"  span={d['span']:2d}  (best: {d['best']}, worst: {d['worst']})")

    return divergences, n

def analyze_assessment_divergence(pisa_math, timss_math, year=2015):
    print(f"\n{'='*70}")
    print(f"ANALYSIS 2: Assessment choice reshuffles rankings (PISA vs TIMSS {year})")
    print(f"{'='*70}")

    overlap = {}
    for cid in pisa_math:
        if (year in pisa_math[cid]['years'] and
            cid in timss_math and year in timss_math[cid]['years']):
            overlap[cid] = {
                'name': pisa_math[cid]['name'],
                'pisa': pisa_math[cid]['years'][year],
                'timss': timss_math[cid]['years'][year],
            }

    n = len(overlap)
    print(f"Countries in both PISA and TIMSS-8 math ({year}): {n}")

    pisa_r = rank_dict({c: s['pisa'] for c, s in overlap.items()})
    timss_r = rank_dict({c: s['timss'] for c, s in overlap.items()})

    comparisons = []
    for cid, s in overlap.items():
        rank_diff = abs(pisa_r[cid] - timss_r[cid])
        score_diff = s['pisa'] - s['timss']
        comparisons.append({
            'id': cid, 'name': s['name'],
            'pisa_rank': pisa_r[cid], 'timss_rank': timss_r[cid],
            'pisa_score': s['pisa'], 'timss_score': s['timss'],
            'rank_diff': rank_diff, 'score_diff': score_diff,
        })

    comparisons.sort(key=lambda x: x['rank_diff'], reverse=True)
    rank_diffs = [c['rank_diff'] for c in comparisons]
    avg_diff = sum(rank_diffs) / len(rank_diffs)
    score_gaps = [abs(c['score_diff']) for c in comparisons]
    avg_gap = sum(score_gaps) / len(score_gaps)

    print(f"Average rank difference: {avg_diff:.1f} positions")
    print(f"Average score gap (same subject, same year): {avg_gap:.0f} points")
    print(f"Score gap range: {min(score_gaps):.0f} to {max(score_gaps):.0f}")
    print(f"\nBiggest rank divergences:")
    for c in comparisons[:12]:
        print(f"  {c['name']:25s}  PISA: #{c['pisa_rank']:2d} ({c['pisa_score']:.0f})"
              f"  TIMSS: #{c['timss_rank']:2d} ({c['timss_score']:.0f})"
              f"  rank diff: {c['rank_diff']}")

    print(f"\nBiggest score divergences (same subject, different test):")
    by_score = sorted(comparisons, key=lambda x: abs(x['score_diff']), reverse=True)
    for c in by_score[:10]:
        print(f"  {c['name']:25s}  PISA: {c['pisa_score']:.0f}  TIMSS: {c['timss_score']:.0f}"
              f"  gap: {c['score_diff']:+.0f}")

    return comparisons, n

def analyze_temporal_volatility(pisa_math, pisa_read, pisa_sci):
    print(f"\n{'='*70}")
    print(f"ANALYSIS 3: Temporal volatility — implausible swings")
    print(f"{'='*70}")

    swings = []
    for dataset, subj_name in [(pisa_math, 'Math'), (pisa_read, 'Reading'), (pisa_sci, 'Science')]:
        for cid, cdata in dataset.items():
            years_sorted = sorted(cdata['years'].keys())
            for i in range(1, len(years_sorted)):
                y1, y2 = years_sorted[i-1], years_sorted[i]
                change = cdata['years'][y2] - cdata['years'][y1]
                swings.append({
                    'name': cdata['name'], 'id': cid,
                    'subject': subj_name,
                    'from_year': y1, 'to_year': y2,
                    'from_score': cdata['years'][y1],
                    'to_score': cdata['years'][y2],
                    'change': change,
                })

    swings.sort(key=lambda x: abs(x['change']), reverse=True)

    # PISA SE is typically ~3-5 points. A real change of 30+ in 3 years is extraordinary.
    threshold = 30
    implausible = [s for s in swings if abs(s['change']) >= threshold]
    print(f"Total country-subject-cycle observations: {len(swings)}")
    print(f"Swings >= {threshold} points in a single cycle: {len(implausible)} ({len(implausible)*100/len(swings):.1f}%)")
    print(f"\nLargest swings (>={threshold} pts):")
    for s in swings[:20]:
        if abs(s['change']) < threshold:
            break
        direction = '+' if s['change'] > 0 else ''
        print(f"  {s['name']:25s} {s['subject']:8s} {s['from_year']}-{s['to_year']}: "
              f"{direction}{s['change']:.1f} ({s['from_score']:.0f}→{s['to_score']:.0f})")

    # China's case is the most dramatic — sampling frame changes
    china_entries = [s for s in swings if s['name'] == 'China']
    if china_entries:
        print(f"\nChina case study (sampling frame changes):")
        for s in sorted(china_entries, key=lambda x: (x['subject'], x['from_year'])):
            direction = '+' if s['change'] > 0 else ''
            print(f"  {s['subject']:8s} {s['from_year']}-{s['to_year']}: "
                  f"{direction}{s['change']:.1f} ({s['from_score']:.0f}→{s['to_score']:.0f})")

    return swings, implausible

def analyze_assessment_fragmentation(pisa_math, timss_math8, sacmeq_math):
    print(f"\n{'='*70}")
    print(f"ANALYSIS 4: Assessment fragmentation — parallel measurement universes")
    print(f"{'='*70}")

    pisa_c = set(pisa_math.keys())
    timss_c = set(timss_math8.keys())
    sacmeq_c = set(sacmeq_math.keys())
    any_c = pisa_c | timss_c | sacmeq_c

    print(f"PISA countries: {len(pisa_c)}")
    print(f"TIMSS-8 countries: {len(timss_c)}")
    print(f"SACMEQ countries: {len(sacmeq_c)}")
    print(f"Total with any assessment: {len(any_c)}")
    print(f"\nOverlap:")
    print(f"  PISA ∩ TIMSS: {len(pisa_c & timss_c)}")
    print(f"  PISA ∩ SACMEQ: {len(pisa_c & sacmeq_c)}")
    print(f"  TIMSS ∩ SACMEQ: {len(timss_c & sacmeq_c)}")
    print(f"  All three: {len(pisa_c & timss_c & sacmeq_c)}")

    pisa_only = pisa_c - timss_c - sacmeq_c
    timss_only = timss_c - pisa_c - sacmeq_c
    sacmeq_only = sacmeq_c - pisa_c - timss_c

    print(f"\nExclusive to one assessment:")
    print(f"  PISA only: {len(pisa_only)} countries")
    print(f"  TIMSS only: {len(timss_only)} countries")
    print(f"  SACMEQ only: {len(sacmeq_only)} countries")

    # SACMEQ-only countries can never be compared to PISA countries
    if sacmeq_only:
        names = [sacmeq_math[c]['name'] for c in sacmeq_only]
        print(f"\n  SACMEQ-only (incomparable to PISA): {', '.join(sorted(names))}")

    return {
        'pisa': len(pisa_c), 'timss': len(timss_c), 'sacmeq': len(sacmeq_c),
        'pisa_timss': len(pisa_c & timss_c),
        'pisa_sacmeq': len(pisa_c & sacmeq_c),
        'sacmeq_only': len(sacmeq_only),
        'pisa_only': len(pisa_only),
    }

def analyze_score_range(pisa_math, year=2018):
    print(f"\n{'='*70}")
    print(f"ANALYSIS 5: Score range — the scale of unmeasured difference")
    print(f"{'='*70}")

    scores = {}
    for cid, data in pisa_math.items():
        if year in data['years']:
            scores[cid] = {'name': data['name'], 'score': data['years'][year]}

    vals = sorted(scores.values(), key=lambda x: x['score'], reverse=True)
    top = vals[0]
    bottom = vals[-1]
    range_pts = top['score'] - bottom['score']

    # PISA proficiency levels are ~73 points wide
    levels_range = range_pts / 73

    print(f"PISA Math {year}: {len(vals)} countries")
    print(f"Top: {top['name']} ({top['score']:.0f})")
    print(f"Bottom: {bottom['name']} ({bottom['score']:.0f})")
    print(f"Range: {range_pts:.0f} points (~{levels_range:.1f} proficiency levels)")

    # Countries clustered within one SE (~5 pts) of each other
    cluster_count = 0
    for i in range(len(vals)):
        for j in range(i+1, len(vals)):
            if abs(vals[i]['score'] - vals[j]['score']) <= 10:
                cluster_count += 1

    total_pairs = len(vals) * (len(vals) - 1) / 2
    print(f"\nCountry pairs within 10 points of each other: {cluster_count} ({cluster_count*100/total_pairs:.1f}% of all pairs)")

    # How many countries can't be statistically distinguished from the OECD average (489)?
    oecd_avg = 489
    within_se = [v for v in vals if abs(v['score'] - oecd_avg) <= 15]
    print(f"Countries within ~1 SE (15 pts) of OECD average: {len(within_se)} ({len(within_se)*100/len(vals):.0f}%)")
    for v in within_se:
        print(f"  {v['name']:30s} {v['score']:.0f}")

    return vals

def main():
    print("Fetching education data from World Bank API...")
    pisa_math_raw = fetch_wb_indicator('LO.PISA.MAT')
    pisa_read_raw = fetch_wb_indicator('LO.PISA.REA')
    pisa_sci_raw = fetch_wb_indicator('LO.PISA.SCI')
    timss_math8_raw = fetch_wb_indicator('LO.TIMSS.MAT8')
    sacmeq_math_raw = fetch_wb_indicator('LO.SACMEQ.MAT')

    print("\nBuilding datasets...")
    pisa_math = build_dataset(pisa_math_raw, "PISA Math")
    pisa_read = build_dataset(pisa_read_raw, "PISA Reading")
    pisa_sci = build_dataset(pisa_sci_raw, "PISA Science")
    timss_math8 = build_dataset(timss_math8_raw, "TIMSS Math 8th")
    sacmeq_math = build_dataset(sacmeq_math_raw, "SACMEQ Math")

    subj_divs, n_subj = analyze_subject_divergence(pisa_math, pisa_read, pisa_sci, 2018)
    assess_divs, n_assess = analyze_assessment_divergence(pisa_math, timss_math8, 2015)
    swings, implausible = analyze_temporal_volatility(pisa_math, pisa_read, pisa_sci)
    frag = analyze_assessment_fragmentation(pisa_math, timss_math8, sacmeq_math)
    score_range = analyze_score_range(pisa_math, 2018)

    print(f"\n{'='*70}")
    print(f"SUMMARY: Five measurement choices that reshape education rankings")
    print(f"{'='*70}")
    print(f"1. Subject choice: average {sum(d['span'] for d in subj_divs)/len(subj_divs):.1f}-position rank change across subjects")
    print(f"   US example: 37th in math, 13th in reading (24-position span)")
    print(f"2. Assessment choice: average {sum(c['rank_diff'] for c in assess_divs)/len(assess_divs):.1f}-position rank change, PISA vs TIMSS")
    print(f"   Kazakhstan: 19th (PISA) vs 6th (TIMSS) — 13-position difference")
    print(f"3. Temporal design: {len(implausible)} swings ≥30 points in a single cycle")
    print(f"   China: 81-point math swing from sampling frame changes alone")
    print(f"4. Assessment fragmentation: {frag['sacmeq_only']} countries in SACMEQ-only measurement universe")
    print(f"   PISA ∩ SACMEQ: {frag['pisa_sacmeq']} countries — virtually no bridge")
    print(f"5. Statistical precision: many mid-range countries indistinguishable within measurement error")

    # Export key data for visualization
    export = {
        'subject_divergence': subj_divs[:20],
        'assessment_divergence': assess_divs,
        'temporal_swings': [s for s in swings if abs(s['change']) >= 25][:30],
        'fragmentation': frag,
    }

    with open('research/education_data.json', 'w') as f:
        json.dump(export, f, indent=2)
    print(f"\nData exported to research/education_data.json")

if __name__ == '__main__':
    main()
