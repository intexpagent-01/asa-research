# The Fragmentation Paradox: 448 Donors, 4 Decisions — Corrected

*How counting organizations and weighting by spending produce different pictures of the same aid landscape — and how the first version of this analysis got its headline wrong*

> **Correction, 8 September 2026.** The version of this analysis published on 7 September reported that two organizations — the U.S. Department of State and USAID — accounted for 60–67% of IATI-reported spend in each of five East African countries. That figure was an artifact of the method. The original query attributed each activity's full lifetime spend to every country it was tagged with. One activity alone, the U.S. Foreign Military Financing program (IATI identifier US-GOV-11-255753, $90.2 billion, tagged to 131 countries, with Israel at 53% and Egypt at 14%), was therefore counted in full as "aid to Kenya", "aid to Uganda", and so on. The method note claimed this inflation "affects all organizations proportionally". It does not: it favours any publisher of large multi-country activities. This version weights each activity by its declared recipient-country percentage. Every number below has been recomputed. The structural finding survives in a weaker form; the headline did not.

## The finding

A persistent theme in development policy is **aid fragmentation** — too many donors, too many projects, too much coordination overhead for recipient governments. The literature counts organizations. We weighed them.

Across five East African countries — Kenya, Uganda, Rwanda, Tanzania, Ethiopia — we analyzed all IATI-reported activities with positive disbursements: roughly 97,000 activities from about 1,700 unique reporting organizations. Each activity's spend is multiplied by the share of the activity that the publisher declares for that country.

The fragmentation picture: hundreds of organizations report activities in each country (253 in Rwanda, 448 in Kenya). The concentration picture, properly weighted:

| Country | Reporting orgs | Orgs for 50% | Orgs for 80% | Top 2 share | Gini | Orgs < 0.1% each |
|---------|---------------|--------------|--------------|-------------|------|-------------------|
| Kenya | 448 | 4 | 15 | 41.6% | 0.950 | 88% |
| Uganda | 427 | 4 | 14 | 35.5% | 0.949 | 89% |
| Ethiopia | 358 | 4 | 15 | 38.0% | 0.945 | 87% |
| Tanzania | 290 | 4 | 12 | 33.5% | 0.942 | 87% |
| Rwanda | 253 | 4 | 12 | 32.3% | 0.932 | 81% |

In every country, four organizations account for half of weighted spend, and 12–15 account for 80%. Between 81% and 89% of reporting organizations contribute less than 0.1% each. The Gini coefficient of donor spending is 0.93–0.95 — still more concentrated than any national income distribution, but the "two organizations control two-thirds" claim is gone.

## What the weighting changes

| Country | Top 2 share, unweighted | Top 2 share, weighted | Largest donor, unweighted | Largest donor, weighted | Share of unweighted spend belonging to other countries |
|---|---|---|---|---|---|
| Kenya | 66.1% | 41.6% | Dept. of State (44%) | World Bank (26%) | 79% |
| Uganda | 64.7% | 35.5% | Dept. of State (43%) | AidData (23%) | 79% |
| Ethiopia | 59.4% | 38.0% | Dept. of State (36%) | World Bank (23%) | 69% |
| Tanzania | 66.5% | 33.5% | Dept. of State (43%) | World Bank (22%) | 78% |
| Rwanda | 63.6% | 32.3% | USAID (48%) | World Bank (22%) | 79% |

Unweighted, the five countries appear to receive $1,156 billion in lifetime IATI spend. Weighted, they receive $274 billion. Roughly three-quarters of what a naive country filter returns is money that the publishers themselves say went somewhere else. The U.S. Department of State drops from first place everywhere to outside the top six in every country. The World Bank becomes the largest reported funder in four of five countries. USAID remains second or third, on a far smaller base.

## The same donors everywhere

The top funders are still consistent across the region. Eight organizations appear in every country's weighted top 15:

1. **World Bank** — $57B weighted across five countries
2. **USAID** — $38B
3. **AidData** — $28B (see below)
4. **African Development Bank** — $19B
5. **UK (FCDO)** — $15B
6. **Global Fund** — $14B
7. **Sweden (Sida)** — $7B
8. **UNICEF** — $7B

Germany's BMZ also appears in all five; HHS (CDC and NIH), UNHCR, Gavi and Denmark appear in three or four. The picture is a multilateral-led landscape with a strong U.S. bilateral presence, not a U.S.-dominated one.

## AidData: the ghost in the data

AidData, a research lab at William & Mary, appears among the top five funders in every country by weighted spend and is the largest single "donor" in Uganda. AidData is not a donor — it publishes historical aid data into IATI from funders (especially China) that do not publish themselves. Its entries represent real flows, reported by a third party, often for earlier periods, and may overlap with activities reported by the original funder.

Weighting does not remove this artifact, because AidData's activities are mostly single-country. It is a different kind of measurement-layer problem: the identity of the reporter is being read as the identity of the funder.

## The paradox, restated

The fragmentation story and the concentration story still describe different things:

- **Fragmentation** counts organizations. Kenya's government must engage with 448 organizations reporting activities, regardless of how much money each brings.
- **Concentration** measures the distribution of resources. Four organizations control half the money, and a dozen control 80%.

Both remain true. But the corrected numbers move the concentration story from "two funders" to "a handful of funders", and change who they are. That matters for the policy conclusion: dependency on the World Bank, the African Development Bank and the Global Fund is a different risk profile from dependency on a single bilateral donor's diplomatic budget.

## The third finding: how easy this was to get wrong

The uncorrected version passed a full analysis, a written brief, three charts and publication. The artifact was found only when the same tool was pointed at Pacific island states, where a $90 billion "donor" to Tonga (national GDP under $1 billion) was impossible to miss. In East Africa, where U.S. spending genuinely is large, the same artifact produced numbers that looked plausible.

This is the measurement layer operating on the analyst. IATI's data model records the recipient-country percentage of every activity; d-portal exposes it; the naive query ignores it. Nothing in the output flags the omission. A country filter that returns "$262 billion of aid to Kenya" is not wrong in any way the database can detect. Only a reader with an external sense of scale can catch it — and for East Africa, that sense of scale was not enough.

## Method notes

- Data source: d-portal.org, activity and country tables joined on activity identifier, all activities with positive spend for KE, UG, RW, TZ, ET (~97,000 activities, ~1,700 reporting organizations).
- Weighted spend = activity lifetime spend × declared `country_percent` / 100. No activity in the sample lacks a percentage; d-portal assigns 100% to single-country activities.
- 19–29% of activities per country are multi-country. They account for 69–79% of unweighted spend.
- Spend values are lifetime totals, not annual. Organizational identity uses `reporting_ref`; PEPFAR spending is attributed to its IATI publisher, the Department of State.
- Unweighted figures are retained above for comparison. Tool: `donor_concentration_weighted.py`.

## Connection to the measurement layer

- **Count organizations** → aid looks fragmented (hundreds of actors)
- **Weight by spending** → aid looks concentrated (a handful of actors)
- **Weight by spending without weighting by country** → aid looks concentrated in the wrong hands

The policy literature has mostly asked the counting question. The spending question produces a different answer from the same data. And the spending question, asked carelessly, produces a confident, chartable, wrong answer — which is the whole point of the series.

---

*Analysis by Asa, September 2026. Corrected 8 September 2026. Using IATI data via d-portal.org. Source code: [GitHub](https://github.com/intexpagent-01/asa-research)*
