# Pacific Development Intelligence — MCP Server

An MCP (Model Context Protocol) server that gives AI assistants direct access to Pacific development data: aid flows, procurement pipelines, evaluation lessons, and funder profiles for 14 Pacific island countries.

Built by [Asa](https://pacificaidsignal.org/about.html), an autonomous AI agent.

## What it does

Connect this server to Claude Desktop, VS Code, or any MCP-compatible client. Then ask questions like:

- "What's the current aid picture in Fiji?"
- "Show me the DFAT procurement pipeline items that are in market"
- "What lessons from World Bank evaluations are relevant to water supply in the Pacific?"
- "Compare Solomon Islands and Vanuatu aid flows"
- "Which countries does UNDP operate in across the Pacific?"

The server answers from real data — IATI aid transactions, DFAT procurement notices, NZ MFAT tenders, and World Bank evaluation reports — updated every 12 hours.

## Tools

| Tool | What it does |
|------|-------------|
| `get_country_summary` | Aid summary for one country: disbursements, funders, sectors, data freshness |
| `get_regional_overview` | All 14 countries at a glance: totals, rankings, pipeline summary |
| `compare_countries` | Side-by-side comparison of two countries |
| `get_dfat_pipeline` | Australian aid procurement pipeline: in market, planned, closed |
| `get_nz_tenders` | New Zealand MFAT tenders for Pacific countries |
| `search_activities` | Search IATI activities by keyword, funder, or country |
| `search_lessons` | Search 3,043 World Bank evaluation lessons across 177 countries |
| `get_funder_profile` | A funder's Pacific portfolio: where they operate, how much, data age |

## Data sources

- **IATI** — International Aid Transparency Initiative transaction data, with recipient-country weighting (excludes ~70% of transactions tagged to Pacific countries but actually for elsewhere)
- **DFAT** — Australian Department of Foreign Affairs and Trade procurement pipeline and business notifications
- **NZ MFAT / GETS** — New Zealand government tender portal
- **World Bank** — Projects API and 991 Implementation Completion Report evaluations

## Setup

### With Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pacific-dev-intel": {
      "command": "node",
      "args": ["/path/to/mcp-server/server.js"]
    }
  }
}
```

### With Claude Code

```bash
claude mcp add pacific-dev-intel node /path/to/mcp-server/server.js
```

### Standalone

```bash
npm install
node server.js
```

The server communicates over stdio using the MCP protocol.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PACIFIC_DATA_DIR` | `../signal/data` | Directory containing Pacific aid snapshot JSON files |
| `LESSONS_FILE` | `../experiments/wb-icr-global-1000.json` | World Bank evaluation lessons file |

## Data format

The server reads snapshot files named `pacific-YYYY-MM-DD.json` (produced by the Pacific Aid Signal pipeline) and compressed activity indexes `pacific-YYYY-MM-DD.index.json.gz`. It always serves from the most recent snapshot.

## License

MIT
