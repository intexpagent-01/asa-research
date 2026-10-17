# Standards and Interoperability

How the Pacific Aid Signal uses and aligns with open data standards.

## IATI Standard

The Signal's primary data source is the International Aid Transparency Initiative (IATI) data standard, accessed via the d-portal API.

**What we use:**
- IATI activity identifiers for traceability
- DAC 5-digit sector codes for sector classification
- Transaction types (disbursements, commitments) per IATI vocabulary
- Participating organisation references and roles
- Recipient-country codes (ISO 3166-1 alpha-2)
- Activity status vocabulary (pipeline, implementation, finalisation)
- Activity date types (start, end, planned, actual)

**How we extend it:**
- Recipient-country percentage weighting — IATI allows publishers to declare what share of an activity goes to each recipient country, but most tools ignore this field and count the full amount for every tagged country. We weight by the declared share.
- Cross-publisher deduplication — IATI has no native deduplication mechanism. We identify duplicate clusters using publisher, title, and identifier patterns.
- Data currency tracking — we compute per-funder data freshness from the most recent transaction date, which IATI does not expose as a first-class concept.

## OCDS (Open Contracting Data Standard)

AusTender publishes contract data using OCDS. The Signal reads this via the AusTender OCDS API for procurement intelligence (managing contractor identification, contract values, program cross-referencing).

## Output formats

| Format | Standard | Use |
|--------|----------|-----|
| HTML | HTML5, valid markup | Human-readable pages |
| JSON | RFC 8259 | Snapshot data, activity indices |
| CSV | RFC 4180 | 10 downloadable datasets |
| RSS | RSS 2.0 (XML) | 15 syndication feeds |
| MCP | Model Context Protocol | AI assistant integration (9 tools) |

## Accessibility

- Semantic HTML with heading hierarchy
- Color contrast meets WCAG AA for body text
- All data tables have header rows
- Print stylesheets for offline use
- No JavaScript required for core data viewing
- Mobile-responsive layout

## Licensing

MIT License — permissive, compatible with institutional adoption and downstream use.

## Data provenance

Every page traces its numbers to source:
- IATI activities link to d-portal activity pages
- DFAT pipeline items reference the procurement pipeline source page
- NZ GETS tenders reference the GETS listing
- World Bank projects reference the Projects API
- Methodology page documents every data correction and its rationale
