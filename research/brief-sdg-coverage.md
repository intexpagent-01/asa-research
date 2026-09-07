# How Universal Are the Universal Goals? SDG Indicator Coverage Across Income Groups

*The Sustainable Development Goals promise universal monitoring. The data tells a more complicated story.*

## The finding

The Sustainable Development Goals are called "universal" — they apply to every country. We checked whether the data does too.

We queried the UN SDG Global Database for 33 key indicators across 25 countries: 15 Least Developed Countries, 5 middle-income countries, and 5 high-income OECD members. For each indicator-country pair, we checked whether any data exists and who produced it — the country itself, or the global statistical system.

The headline: coverage is surprisingly high everywhere. LDCs average 28.0 out of 33 indicators (85%). Middle-income and high-income countries both average 31.6 out of 33 (96%). The gap is only 3.6 indicators. Tanzania, an LDC, has complete coverage — 33 out of 33.

| Income group | Indicators (of 33) | Coverage | Country-produced |
|---|---|---|---|
| LDCs (15 countries) | 28.0 | 85% | 56% |
| Middle-income (5) | 31.6 | 96% | 60% |
| High-income OECD (5) | 31.6 | 96% | 55% |

But this headline conceals three important patterns.

## Pattern 1: The places where gaps exist reveal what's hardest to measure

Coverage gaps are concentrated in specific domains, not spread evenly:

| Domain | LDC coverage | HIC coverage | Gap |
|---|---|---|---|
| Goal 14 — Life Below Water | 20% | 100% | 80pp |
| Goal 4 — Quality Education | 60% | 100% | 40pp |
| Goal 10 — Reduced Inequalities | 43% | 80% | 37pp |
| Goal 16 — Peace, Justice, Institutions | 63% | 90% | 27pp |

Marine protected areas (14.5.1): only 3 of 15 LDCs have data, compared to all 5 HICs. Education quality (4.1.1, minimum proficiency in reading and math): only 47% of LDCs have data. Inequality (10.1.1, bottom 40% income growth): 53% of LDCs. Census and vital registration (17.19.2): 47% of LDCs.

These are the indicators that require the most sophisticated statistical infrastructure — household surveys with consumption modules, learning assessments, population registers. The gap is not random; it maps onto institutional capacity.

## Pattern 2: Some goals are better measured where they matter most

A few indicators show the reverse pattern — LDCs have better coverage than HICs:

- **National poverty line (1.2.1):** LDC 100%, HIC 60%. All 15 LDCs report; only 3 of 5 HICs bother.
- **Stunting prevalence (2.2.1):** LDC 100%, HIC 80%. All LDCs report; stunting is not tracked in all HICs.
- **Disaster deaths (13.1.1):** LDC 87%, HIC 80%. Comparable coverage.

The SDG framework was designed around developing-country concerns. Indicators that measure poverty, hunger, and basic survival have near-universal coverage in LDCs because that is where they were designed to apply. HICs, where stunting and extreme poverty are statistically negligible, sometimes don't report at all. The "universality" of the goals runs in both directions — some goals are more universal in practice than others.

## Pattern 3: Who actually produces the numbers?

This is the most significant finding. Across all income groups, only about half of SDG data is produced by the countries themselves:

| Data source | LDCs | MICs | HICs |
|---|---|---|---|
| Country-produced (C) | 45% | 51% | 47% |
| Country-adjusted (CA) | 11% | 9% | 8% |
| Estimated (E) | 25% | 24% | 28% |
| Modeled (M) | 10% | 11% | 8% |
| Global monitoring (G) | 9% | 5% | 9% |

The numbers are remarkably similar across income groups. High-income countries are not producing dramatically more of their own SDG data than least developed countries. Germany and Japan have lower country-produced rates (53%) than Nepal (60%) or Burundi (59%).

This challenges the standard narrative. The coverage gap story is usually told as "poor countries lack data." The data nature story is different: the global SDG monitoring system — UN agencies, the World Bank, WHO, UNESCO — produces a large share of everyone's numbers. The system appears to have roughly 85-96% coverage not because countries are measuring themselves, but because a global statistical apparatus fills the gaps through estimation, modeling, and global monitoring programs.

## What this means

The SDG monitoring framework achieves near-universal coverage through a specific institutional arrangement: a network of international agencies that estimate, model, and monitor indicators that many countries cannot or do not measure themselves. This works — the dashboard is populated, the reports are published, the trends are tracked.

But it raises a question about what "monitoring" means. When a modeled estimate fills a cell in the SDG database, the indicator exists as a number. But it does not exist as a measurement that the country's own statistical office produced, verified, and can act on. The coverage rate measures the completeness of the global database; it does not measure the capacity of national statistical systems.

The places where the gaps remain — education quality, inequality, justice systems, marine environments — are precisely the domains where estimation is hardest and country data is most needed. These are not random gaps; they are the frontier of what the global statistical system can fill without the country itself.

## Connection to the measurement layer

This finding extends the measurement layer thesis to the SDG framework itself. The previous analyses showed that methodology shapes the answer within a single data system (IATI, WGI, poverty lines, education tests). The SDG coverage analysis shows a layer above that: the institutional architecture of who produces the data shapes what appears to be measured at all.

A country with 85% SDG coverage and a country with 96% coverage are not 11 percentage points apart in their ability to track progress. They may be much further apart in whether the numbers on their dashboard come from their own observations or from someone else's estimates.

## Method

Data from the UN SDG Global Database API (UNSDGAPIV5). For each of 33 indicators across 25 countries, we checked for the presence of any data and recorded the "Nature" attribute: C (country data), CA (country adjusted), G (global monitoring), E (estimated), M (modeled). Countries were selected to span LDCs (15, diverse geography), middle-income (5), and high-income OECD (5). Indicators were selected to span all 17 goals with emphasis on headline indicators. This is a sample, not a census — the full SDG framework has 231 unique indicators. Coverage rates for the full set would likely be lower, particularly for Tier II and Tier III indicators.
