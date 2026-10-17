# Technical Architecture

How the Pacific Aid Signal collects, processes, and publishes development data.

## System overview

```
Data Sources          Processing Pipeline         Output Layer
─────────────        ───────────────────         ────────────
d-portal (IATI) ──┐
World Bank API ───┤
DFAT Pipeline ────┼── pacific_signal.py ──┬── HTML pages (60+)
DFAT Notices ─────┤   (fetch, weight,    ├── JSON snapshots
NZ GETS ──────────┘    deduplicate,      ├── CSV exports (10)
                       render)            ├── RSS feeds (15)
AusConnect ───────┐                      ├── MCP server (9 tools)
SPC Procurement ──┼── render_radar.py    └── Activity index (.gz)
UNDP Jobs ────────┘
```

## Data sources

| Source | Access method | Refresh | What it provides |
|--------|-------------|---------|-----------------|
| IATI (via d-portal) | HTTP API, 60-day slices | Every wake (12h) | Aid transactions: disbursements, commitments, activities, publishers, sectors |
| World Bank Projects | REST API | Every wake | Project records: approvals, status, board dates, sectors |
| DFAT Procurement Pipeline | HTML scraping | Every wake | Pipeline items: program names, stages, timing, country assignments |
| DFAT Business Notifications | HTML scraping | Every wake | New procurement notices: managing contractor searches, RFTs, REOIs |
| NZ GETS | HTML scraping (3 lists + detail pages) | Every wake | Tenders: open, closed, completed, outcomes (who won, for how much) |
| AusConnect | HTML scraping + detail pages | Every wake | Pacific development vacancies with managing contractor attribution |
| SPC Procurement | HTML scraping (Drupal) | Every wake | Pacific regional organisation tenders |
| UNDP Jobs Portal | HTML parsing | Every wake | UN development positions in the Pacific |

### Data quality corrections applied at fetch time

1. **Recipient-country weighting**: ~71% of IATI transactions tagged to Pacific countries declare the recipient country gets only a fraction of the activity's value. Disbursements are weighted by the declared share. Activities whose title names a different Pacific country are kept but sorted last.
2. **Cross-publisher deduplication**: $388M (4.1%) of $9.36B in active Pacific aid is double-counted across publishers. 88 duplicate clusters identified and collapsed.
3. **Contact stripping**: DFAT contact emails are stripped before storage. NZ GETS contact fields are never read. No personal data enters the snapshot.

## Processing pipeline

### Core pipeline: `pacific_signal.py` (1,000 lines)

Runs once per wake. Stages:

1. **Fetch** — Queries each data source with retry logic. d-portal data fetched in 60-day slices (API caps rows and ignores `orderby`). Failed fetches preserve the previous snapshot block.
2. **Weight** — Each IATI transaction amount multiplied by the activity's declared recipient-country percentage. Activities with zero or missing percentage are included with a flag.
3. **Classify** — Activities categorised as: implementation, pipeline, finalisation, stale (>365 days past end date), implausible (>$500M lifetime with >50% declared to one country).
4. **Aggregate** — Per-country summaries: 90-day and 365-day disbursements, funder counts, sector distributions, data currency per funder.
5. **Diff** — Current snapshot compared to previous issue (different calendar day). Generates change log: new funders, departed funders, new starts, newly ending, DFAT pipeline movements, watch matches.
6. **Render** — HTML pages generated from snapshot data. One front door, 14 country pages, one regional overview.
7. **Index** — Compressed activity index (`pacific-YYYY-MM-DD.index.json.gz`, ~350 KB) containing every activity in pipeline/implementation/finalisation status. Watches match against this index.

### Supporting pipelines

| Pipeline | Source file | Output |
|----------|-----------|--------|
| Consultant Radar | `render_radar.py` + `ausconnect.py`, `spc_procurement.py`, `undp_jobs.py` | `radar.html` — aggregated vacancies from 4 sources |
| AIMS dashboards | `render_aims.py` | 14 country dashboards + index — recipient-side aid management views |
| Field Notes | `render_field_notes.py` | `field-notes.html` — public wake reasoning log |
| 40+ page renderers | `render_*.py` (50 files) | Dashboard, funders, sectors, trends, pipeline, map, search, downloads, etc. |

## Snapshot format

Each run produces `signal/data/pacific-YYYY-MM-DD.json`:

```json
{
  "generated": "2026-10-17T...",
  "date": "2026-10-17",
  "countries": {
    "PG": {
      "code": "PG", "name": "Papua New Guinea",
      "dis90": 64000000, "dis365": 280000000,
      "n_orgs_90": 12, "top_orgs_90": [...],
      "sectors_90": [...], "activities": [...],
      ...
    },
    ...14 countries
  },
  "dfat": {
    "fetched": "...", "as_at": "16 October 2026",
    "notices": [...], "items": [...]
  },
  "nz": {
    "fetched": "...", "tenders": [...]
  }
}
```

Snapshots are committed to the public repository. Every prior issue is preserved.

## Output layer

### Static HTML site (GitHub Pages)

- 60+ HTML pages, all generated by Python renderers
- No JavaScript framework, no build step, no server-side rendering
- CSS defined in `research.html` and shared across all renderers via `site_style()`
- Interactive features (search, comparison, filters) use vanilla JavaScript
- Print stylesheets for country brief output

### CSV exports

10 datasets exported at render time to `site/data/`:
- Country summary, funder disbursements, data currency, sectors, DFAT pipeline, NZ tenders, all activities, World Bank projects, new starts, ending soon

### RSS feeds

15 feeds: one regional (`feed.xml`) + 14 per-country (`feed-<slug>.xml`)

### MCP server

`mcp-server/server.js` — 9 tools for programmatic access:
- `get_country_summary`, `get_country_funders`, `get_country_activities`
- `get_dfat_pipeline`, `get_nz_tenders`, `search_activities`
- `get_data_currency`, `get_regional_overview`, `update_data`

Uses `@modelcontextprotocol/sdk`. 31 tests passing. Self-contained with bundled data snapshots. `setup.sh` auto-configures Claude Desktop.

### Ask box endpoint

Cloudflare Worker (`asa-ask`): receives questions, stores in KV with 90-day TTL. No PII collected. 700-char cap, rate limiting (6/IP/hour), origin allowlist. 20 tests.

## Deployment

```
Agent server (this machine)
├── Runs pacific_signal.py every wake
├── Copies output to ~/asa-research (local clone)
├── git push via deploy key (SSH)
└── GitHub Actions publishes to GitHub Pages

GitHub Pages (pacificaidsignal.org)
├── Static HTML, CSS, JSON, CSV, RSS
├── Custom domain with HTTPS
└── No server-side processing

Cloudflare (Operator's account)
├── Worker: asa-ask (Ask box endpoint)
└── KV: asa-ask (message queue)
```

## Dependencies

### Runtime (Python 3)

No third-party Python packages. All HTTP requests use `urllib.request`. HTML generated as strings. JSON for data serialisation. `gzip` for index compression. `csv` for exports.

### MCP server (Node.js)

- `@modelcontextprotocol/sdk` — MCP protocol implementation
- No other runtime dependencies

### Infrastructure

- GitHub Pages (free) — static hosting
- Cloudflare Workers (free tier) — Ask box endpoint
- No database, no paid cloud services, no API keys for data sources

## Design principles

1. **No model calls at runtime.** All data processing is deterministic Python. No LLM inference in the pipeline. AI is used only for maintenance and development during agent wakes.
2. **Every number is traceable.** Disbursement figures link to IATI activity identifiers. DFAT items link to pipeline source. Methodology page documents every correction.
3. **Graceful degradation.** A failed API returns the previous snapshot's data with a staleness flag. The Ask box falls back to GitHub Issues if the endpoint is down.
4. **Privacy by design.** Contact information stripped at fetch time, not render time (snapshots are public). Ask box collects no identifying information. No analytics, cookies, or tracking.
5. **Platform independence.** Python 3 standard library only. Runs on any machine with Python. Data from public APIs with no registration required (except ReliefWeb, which is blocked on org email).
