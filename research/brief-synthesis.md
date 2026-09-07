# The Measurement Layer: What Five Analyses of IATI Data Reveal

**Asa · September 2026**

## The pattern

How fragmented is aid in Uganda? Is fragmentation growing? Are donors coordinating? How much goes to climate? Each question seems answerable with IATI data: query the datastore, count the results, get a number.

Across five analyses of IATI data covering East African aid flows, we found that each of these questions has a measurement layer — a set of methodological choices that shapes the answer as much as the underlying reality does. The number you get depends less on what is happening than on how you define, count, and filter.

This is not a criticism of IATI. The data is genuinely valuable for transparency — it lets anyone see who reports doing what, where, with what money. But transparency data and analytical data serve different purposes, and the gap between them is larger and more systematic than is commonly acknowledged.

## Five demonstrations

### 1. Counting organizations is not measuring fragmentation

Ask IATI how many organizations work on governance in Uganda and you get 85. Decompose that number and roughly one-fifth disappears: duplicate organization names, completed or cancelled activities still in the database, and activities miscoded to the wrong sector. The remaining organizations span at least three distinct domains — civil society support, human rights, and government capacity building — that don't create coordination costs for each other.

Across 12 country-sector pairs, the average artifact rate was 21%. The range (12–35%) is remarkably consistent — the inflation is structural, not anomalous.

### 2. Counting organizations over time is not measuring trends

Every one of ten country-sector pairs shows apparent fragmentation growth from 2010 to 2024 — an average of +155%, with no pair showing a sustained decline. But IATI's publisher base grew 2,051% over the same period, 14 times faster than fragmentation. The data cannot tell us whether fragmentation is actually increasing or just becoming more visible as more organizations start reporting.

### 3. Structured coordination fields cannot measure coordination

IATI has fields designed to capture coordination: multi-funder activity types, participating organization roles, collaboration types. Across 4,756 activities, the multi-funder field was used zero times. The "accountable organization" role was filled for 28% of activities. Meanwhile, 16% of detectable coordination evidence — basket funds, SWAps, joint programs — was visible only through free-text keyword search, invisible to any structured query.

### 4. Half of apparent fragmentation growth is reporting expansion

Cross-referencing fragmentation entrants with IATI publisher registry dates showed that roughly 50% of organizations entering each country-sector pair after 2015 had never published IATI data before. They didn't start working in the sector — they started reporting. IATI publisher growth and apparent fragmentation growth share the same timeline, the same acceleration phase (2016–2019), and the same post-2020 plateau.

### 5. The measurement method determines which donors count

Three standard approaches to identifying climate finance in IATI data — sector codes, keyword searches, and Rio markers — identify almost entirely different pools of activities. In Kenya, only 7% of the combined set was found by all three methods. USAID, the largest environmental donor by activity count (~300 per country), has 0% Rio marker fill. The Green Climate Fund and Germany achieve 100%. An assessment using Rio markers will systematically count European contributions and miss American ones. Including "significant" alongside "principal" as a marker threshold triples adaptation counts.

## The common structure

In each case, a choice invisible to the end user — which organizations to include, which time period to compare, which field to query, which tag to filter on — shapes the answer as much as the underlying development reality.

And in each case, the measurement layer is invisible to someone who trusts the output number.

The five findings are not independent problems but expressions of a single structural feature: IATI was designed for transparency (who did what, where) rather than for the analytical questions commonly posed of it (how fragmented, how coordinated, how much climate finance). When transparency data is used for analytical purposes without decomposition, the measurement layer fills the gap between what the data captures and what the question requires — silently, systematically, and in ways that create real policy risk.

## What would help

These are not intractable problems. Five concrete improvements would substantially narrow the measurement gap:

1. **Organizational identifiers.** Replacing free-text organization names with persistent identifiers would eliminate the deduplication problem at source.
2. **Mandatory activity status maintenance.** Requiring publishers to update activity status (or auto-closing after an inactivity threshold) would prevent historical records from inflating current counts.
3. **Structured coordination fields.** Making coordination mechanism fields mandatory — or at least making "not coordinated" an explicit choice — would make coordination visible to structured queries.
4. **Consistent marker completion.** Requiring Rio markers (or any policy marker) on all activities, with "not targeted" as an explicit option, would close the gap between "not tagged" and "does not apply."
5. **Cross-method validation.** Any quantitative claim derived from IATI data should be tested against at least one alternative measurement approach. If two methods produce substantially different numbers, the right response is not to pick one but to report the disagreement.

## A note on scope

This analysis covers five East African countries, three sectors, and one additional domain (climate finance). Whether the patterns hold elsewhere is an empirical question. But the structural features that produce them — free-text organization names, archived activities alongside current ones, optional coordination fields, inconsistent marker completion — are inherent to IATI's data model, not specific to East Africa. The measurement layer is present everywhere IATI data is used for analytical purposes. The question is not whether it exists but how large it is.
