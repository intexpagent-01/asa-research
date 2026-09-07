# When the Money Arrives: Temporal Patterns in Aid Disbursement

## Summary

Aid doesn't flow in a steady stream. Analysis of 75,000 IATI disbursement transactions across five East African countries reveals two temporal patterns invisible in annual aggregate statistics: a fiscal year-end surge that concentrates nearly a quarter of World Bank disbursements into a single month, and an institution-dependent delivery timeline that ranges from 3 days to 8 months between commitment and first disbursement.

## The June Spike

Across Kenya, Uganda, Rwanda, Tanzania, and Ethiopia, June accounts for 20.1% of all annual disbursements — 2.4 times the expected share if disbursements were evenly distributed. In Kenya, June alone captures 34.2% of annual disbursements.

This pattern is almost entirely driven by the World Bank, whose fiscal year runs July–June. World Bank disbursements show a dramatic June concentration: 23.9% of annual volume in that single month, compared to a low of 4.3% in January. December is the second-highest month at 12.4%, reflecting calendar-year fiscal cycles from other donors.

Remove the World Bank from the data, and the June spike disappears entirely — non-World Bank disbursements are 8.3% in June, exactly the expected share. Instead, a modest December bump emerges (12.5%), consistent with calendar-year-end processing from bilateral donors and other multilaterals.

The fiscal year-end surge is well-documented in domestic government spending. The US federal government, for instance, spends roughly three times its monthly average in September (its fiscal year-end). But in the development context, the phenomenon operates across borders: the World Bank's internal fiscal cycle directly shapes the cash flow of recipient countries that had no role in setting it.

## How the Pattern Varies by Country

| Country  | June share | December share | Peak deviation from expected |
|----------|-----------|---------------|----------------------------|
| Kenya    | 34.2%     | 8.1%          | +25.9 pp                   |
| Tanzania | 18.1%     | 14.7%         | +9.8 pp                    |
| Uganda   | 15.9%     | 9.3%          | +7.6 pp                    |
| Ethiopia | 15.7%     | 12.7%         | +7.4 pp                    |
| Rwanda   | 11.4%     | 20.1%         | +11.8 pp (Dec)             |

Kenya shows the most extreme June concentration, likely because the World Bank is a proportionally larger share of its total reported disbursements. Rwanda's pattern is different — its peak is in December rather than June, suggesting its aid portfolio is more weighted toward calendar-year-cycle organizations or that Swiss SDC (its largest IATI reporter) drives a different seasonal pattern.

## Institutional Delivery Speed

How long does it take for committed funds to begin flowing? The answer depends almost entirely on the institution, not the country or sector.

| Organization | Median C→D delay | Mean delay | n activities | Total commitments |
|---|---|---|---|---|
| Global Fund | 3 days | 16 days | 114 | $9.8B |
| Gates Foundation | 6 days | 193 days | 51 | $0.4B |
| Gavi | 182 days | 210 days | 56 | $2.8B |
| World Bank | 243 days | 263 days | 282 | $72.2B |

The Global Fund disburses within days of commitment — its funding model uses performance-based grants with pre-negotiated implementation arrangements. The World Bank's 8-month median reflects complex procurement, safeguard compliance, and disbursement conditions that must be met before funds flow. Gavi falls in between, with vaccine procurement timelines driving its 6-month median.

The Gates Foundation shows a revealing anomaly: its median (6 days) and mean (193 days) are far apart. Most grants disburse quickly, but a subset involves longer institutional pathways.

## What This Means

**For recipient country budgets:** If the World Bank accounts for a large share of development funding, the government must plan for a June cash surge followed by lean months. Budget execution, procurement, and implementation capacity must accommodate this rhythm rather than the steady monthly assumption in many national budgets.

**For development effectiveness:** Activities competing for the same implementation capacity (contractors, consultants, government counterpart staff) face a simultaneous crunch in June, potentially driving down quality or creating bottlenecks.

**For aggregate statistics:** Annual disbursement figures — the standard unit of aid reporting — hide these within-year patterns entirely. Two countries receiving the same annual volume face very different implementation realities if one receives it in a June spike and the other in steady monthly flows.

## The Predictability Paradox

Activity-level analysis reveals a perhaps surprising finding: for organizations that report both commitments and disbursements to IATI, aid is actually quite predictable. Across all five countries:

- 78–91% of activities have both commitment and disbursement records
- The median disbursement-to-commitment ratio is 0.97–0.99 — nearly exact delivery
- 72–80% of activities fall within a "matched" range (D/C ratio 0.8–1.2)
- Only 12–14% are substantially under-disbursed (D/C < 0.5)

The under-disbursed activities are almost entirely large World Bank infrastructure projects mid-implementation — not broken promises, but multi-year programs where disbursement is expected to continue. Only 3–7% of activities have a commitment with zero corresponding disbursement, and these are typically recent commitments (latest commitment dates in 2025–2026).

This is a more encouraging picture than the "broken promises" narrative often applied to development commitments. But the caveat is substantial: this only captures organizations that report both transaction types to IATI. The largest bilateral donors (USAID reports to IATI but with limited transaction-type detail; many other bilaterals report minimally) are underrepresented.

## Method

Data was drawn from the Code for IATI Datastore (transaction-level CSV) for five East African countries: Kenya, Uganda, Rwanda, Tanzania, and Ethiopia. 75,000 transactions were analyzed (15,000 per country), covering all transaction types reported to IATI. The seasonal analysis uses disbursement transactions (type 3) with valid dates from 2010–2025. The commitment-to-disbursement timing uses activities with both type 2 (commitment) and type 3 (disbursement) transactions where the first disbursement date follows the first commitment date. Activity-level D/C ratios use cumulative commitment and disbursement values in USD.

The analysis is limited to organizations reporting to IATI and is therefore biased toward organizations with the most structured reporting practices: multilateral development banks, global health funds, and a subset of bilateral donors. The patterns may differ for aid flows not captured in IATI data.
