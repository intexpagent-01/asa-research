#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync, readdirSync, existsSync, writeFileSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { gunzipSync } from "zlib";

const __dirname = dirname(fileURLToPath(import.meta.url));

function findDataDir() {
  if (process.env.PACIFIC_DATA_DIR) return process.env.PACIFIC_DATA_DIR;
  const bundled = join(__dirname, "data");
  if (existsSync(bundled)) {
    const snaps = readdirSync(bundled).filter(f => /^pacific-\d{4}-\d{2}-\d{2}\.json$/.test(f));
    if (snaps.length) return bundled;
  }
  return join(__dirname, "..", "signal", "data");
}
let DATA_DIR = findDataDir();
const LESSONS_FILE = process.env.LESSONS_FILE ||
  (existsSync(join(__dirname, "data", "wb-icr-global-1000.json"))
    ? join(__dirname, "data", "wb-icr-global-1000.json")
    : join(__dirname, "..", "experiments", "wb-icr-global-1000.json"));

const COUNTRIES = {
  PG: "Papua New Guinea", FJ: "Fiji", SB: "Solomon Islands",
  VU: "Vanuatu", WS: "Samoa", TO: "Tonga", KI: "Kiribati",
  TV: "Tuvalu", FM: "Micronesia", MH: "Marshall Islands",
  PW: "Palau", NR: "Nauru", NU: "Niue", CK: "Cook Islands"
};

function latestSnapshot() {
  const files = readdirSync(DATA_DIR)
    .filter(f => /^pacific-\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .sort();
  if (!files.length) throw new Error("No snapshot files found in " + DATA_DIR);
  const path = join(DATA_DIR, files[files.length - 1]);
  return JSON.parse(readFileSync(path, "utf8"));
}

function loadIndex(date) {
  const path = join(DATA_DIR, `pacific-${date}.index.json.gz`);
  if (!existsSync(path)) return null;
  return JSON.parse(gunzipSync(readFileSync(path)).toString());
}

let _lessons = null;
function loadLessons() {
  if (_lessons) return _lessons;
  if (!existsSync(LESSONS_FILE)) return { projects: [] };
  _lessons = JSON.parse(readFileSync(LESSONS_FILE, "utf8"));
  return _lessons;
}

function fmt(usd) {
  if (usd == null) return "N/A";
  if (Math.abs(usd) >= 1e9) return `$${(usd / 1e9).toFixed(1)}B`;
  if (Math.abs(usd) >= 1e6) return `$${(usd / 1e6).toFixed(1)}M`;
  if (Math.abs(usd) >= 1e3) return `$${(usd / 1e3).toFixed(0)}K`;
  return `$${usd.toFixed(0)}`;
}

const FUNDER_ALIASES = {
  undp: "united nations development programme",
  unicef: "unicef",
  who: "world health organization",
  fao: "food and agriculture organization",
  adb: "asian development bank",
  wb: "world bank",
  dfat: "australia",
  nzmfat: "new zealand ministry",
  eu: "european commission",
  afd: "afd",
  ilo: "international labour organization",
  usaid: "united states agency",
  jica: "japan international cooperation",
  unfpa: "united nations population fund",
  unido: "united nations industrial development",
  unaids: "joint programme on hiv",
  gef: "global environment facility",
};

function matchFunder(query) {
  const q = query.toLowerCase().trim();
  return FUNDER_ALIASES[q] || q;
}

const COUNTRY_ALIASES = {
  png: "PG", fiji: "FJ", solomons: "SB", "solomon islands": "SB",
  vanuatu: "VU", samoa: "WS", tonga: "TO", kiribati: "KI",
  tuvalu: "TV", micronesia: "FM", "marshall islands": "MH", "fsm": "FM",
  palau: "PW", nauru: "NR", niue: "NU", "cook islands": "CK", rmi: "MH",
};

function matchCountry(query) {
  const q = query.toUpperCase().trim();
  if (COUNTRIES[q]) return q;
  const lower = query.toLowerCase().trim();
  if (COUNTRY_ALIASES[lower]) return COUNTRY_ALIASES[lower];
  for (const [code, name] of Object.entries(COUNTRIES)) {
    if (name.toLowerCase() === lower) return code;
  }
  for (const [code, name] of Object.entries(COUNTRIES)) {
    if (name.toLowerCase().includes(lower)) return code;
  }
  return null;
}

function countryMatchesFilter(text, countryCode) {
  if (!text || !countryCode) return false;
  const name = COUNTRIES[countryCode].toLowerCase();
  const lower = text.toLowerCase();
  if (lower.includes(name)) return true;
  for (const [alias, code] of Object.entries(COUNTRY_ALIASES)) {
    if (code === countryCode && lower.includes(alias)) return true;
  }
  if (countryCode === "PG" && lower.includes("png")) return true;
  if (lower.includes("pacific") || lower.includes("regional")) return true;
  return false;
}

function decodeIndex(countryData) {
  if (!countryData) return [];
  if (Array.isArray(countryData)) return countryData;
  const { cols, rows } = countryData;
  if (!cols || !rows) return [];
  return rows.map(row => {
    const obj = {};
    cols.forEach((col, i) => { obj[col] = row[i]; });
    return obj;
  });
}

const STATUS_MAP = { 1: "Pipeline", 2: "Implementation", 3: "Finalisation", 4: "Closed", 5: "Suspended" };

// --- Server setup ---

const server = new McpServer({
  name: "pacific-dev-intel",
  version: "0.1.0",
}, {
  capabilities: {
    tools: {},
  },
  instructions: "Pacific Development Intelligence server. Provides real-time aid flow data, procurement pipeline, and evaluation lessons for 14 Pacific island countries. Data from IATI, DFAT, NZ MFAT, and World Bank."
});

// Tool 1: Get country aid summary
server.tool(
  "get_country_summary",
  "Get an aid summary for a Pacific island country: disbursements, top funders, active activities, data freshness, and recent changes.",
  {
    country: z.string().describe("Country name or ISO code (e.g. 'Fiji', 'FJ', 'Papua New Guinea', 'PG')")
  },
  async ({ country }) => {
    const snap = latestSnapshot();
    const code = matchCountry(country);
    if (!code || !snap.countries[code]) {
      return { content: [{ type: "text", text: `Country not found: "${country}". Available: ${Object.entries(COUNTRIES).map(([c,n]) => `${n} (${c})`).join(", ")}` }] };
    }
    const c = snap.countries[code];
    const lines = [
      `# ${c.name} — Aid Summary`,
      `Data as of: ${snap.date}`,
      "",
      `## Key Figures (90-day window)`,
      `- Reported spending (90 days): ${fmt(c.dis90)} (IATI disbursements + expenditures, weighted by recipient-country share)`,
      `- Reported spending (previous 90 days): ${fmt(c.dis_prev90)}`,
      `- Reported spending (365 days): ${fmt(c.dis365)}`,
      `- Commitments (365 days): ${fmt(c.com365)}`,
      `- Active funders (90 days): ${c.n_orgs_90}`,
      `- Active funders (365 days): ${c.n_orgs_365}`,
      `- Active activities (90 days): ${c.n_acts_90}`,
      `- Total activities: ${c.n_activities}`,
      `- Active (implementation): ${c.n_active}`,
      `- Stale (>365 days past end): ${c.n_stale}`,
      `- New starts: ${c.n_new_starts}`,
      `- Ending soon: ${c.n_ending_soon}`,
      "",
      `## Top Funders (90-day disbursements)`,
    ];
    for (const org of (c.top_orgs_90 || []).slice(0, 10)) {
      lines.push(`- ${org.name}: ${fmt(org.usd)} (${org.pct.toFixed(1)}%)`);
    }
    if (c.quiet_orgs && c.quiet_orgs.length) {
      lines.push("", `## Quiet Funders (active in 365 days, silent in 90)`);
      for (const org of c.quiet_orgs.slice(0, 5)) {
        const name = typeof org === "string" ? org.split(",").slice(1).join(",").trim() : (org.name || org);
        lines.push(`- ${name}`);
      }
      if (c.n_quiet > 5) lines.push(`  ... and ${c.n_quiet - 5} more`);
    }
    lines.push("", `## Sectors (90 days)`);
    for (const s of (c.sectors_90 || []).slice(0, 8)) {
      lines.push(`- ${s.name}: ${fmt(s.usd)} (${s.pct.toFixed(1)}%)`);
    }
    if (c.currency && c.currency.length) {
      lines.push("", `## Data Freshness (top funders)`);
      for (const f of c.currency.slice(0, 10)) {
        lines.push(`- ${f.name}: last data ${f.age_days} days ago (${f.latest || "unknown"}), lifetime ${fmt(f.lifetime_usd)}`);
      }
    }
    if (c.wb_recent && c.wb_recent.length) {
      lines.push("", `## World Bank Projects (recent)`);
      for (const p of c.wb_recent) {
        lines.push(`- ${p.name}: ${fmt(p.amount)} (${p.id})`);
      }
    }
    if (c.wb_pipeline && c.wb_pipeline.length) {
      lines.push("", `## World Bank Pipeline`);
      for (const p of c.wb_pipeline) {
        lines.push(`- ${p.name}: ${fmt(p.amount)} (${p.id})`);
      }
    }
    lines.push("", `## Data Quality`,
      `- Transactions in 365 days: ${c.n_trans_365.toLocaleString()}`,
      `- Excluded (tagged to other country): ${c.n_trans_other_country.toLocaleString()} (${c.n_trans_365 ? ((c.n_trans_other_country / c.n_trans_365) * 100).toFixed(0) : 0}%)`,
      `- Implausible values: ${c.n_stale > 0 ? (c.implausible || []).length : 0}`
    );
    const staleOrgs = (c.currency || []).filter(f => f.age_days > 365);
    if (staleOrgs.length) {
      lines.push("", `## Coverage Warnings`);
      for (const f of staleOrgs.slice(0, 5)) {
        lines.push(`- ${f.name}: no transactions reported for ${f.age_days} days. Reported spending figures may understate actual activity from this funder.`);
      }
      if (staleOrgs.length > 5) lines.push(`  ... and ${staleOrgs.length - 5} more funders with stale data`);
    }
    lines.push("", "---", `Note: Spending figures combine IATI disbursement and expenditure transactions, weighted by declared recipient-country percentage. Reporting organisations are publishers, not necessarily original donors. Where no recent transactions are reported, this reflects missing published data — not necessarily zero activity. Snapshot: ${snap.date}.`);
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 2: DFAT procurement pipeline
server.tool(
  "get_dfat_pipeline",
  "Get the current DFAT (Australian aid) procurement pipeline: items in market, planned, and recently closed. Includes program names, countries, and timing.",
  {
    status: z.enum(["all", "in_market", "planned", "closed"]).default("all").describe("Filter by pipeline status"),
    country: z.string().optional().describe("Filter by country name (optional)")
  },
  async ({ status, country }) => {
    const snap = latestSnapshot();
    const dfat = snap.dfat;
    if (!dfat || !dfat.items) {
      return { content: [{ type: "text", text: "DFAT pipeline data not available in the current snapshot." }] };
    }
    let items = dfat.items;
    const countryCode = country ? matchCountry(country) : null;
    if (status !== "all") {
      const statusMap = { in_market: "in the market", planned: "planned", closed: "closed" };
      const target = statusMap[status] || status;
      items = items.filter(i => (i.section || "").toLowerCase().includes(target));
    }
    if (country) {
      items = items.filter(i =>
        countryMatchesFilter(i.country, countryCode) ||
        countryMatchesFilter(i.title, countryCode) ||
        (countryCode && (i.country || "").toLowerCase().includes(country.toLowerCase())) ||
        (i.title || "").toLowerCase().includes(country.toLowerCase())
      );
    }
    const lines = [
      `# DFAT Procurement Pipeline`,
      `As at: ${dfat.as_at || "unknown"}`,
      `Fetched: ${dfat.fetched || "unknown"}`,
      `Total items: ${dfat.items.length} (showing ${items.length}${status !== "all" ? `, filtered to ${status}` : ""}${country ? `, filtered to ${country}` : ""})`,
      ""
    ];
    for (const item of items) {
      lines.push(`## ${item.id || "?"} — ${item.title || "Untitled"}`);
      if (item.country) lines.push(`Country: ${item.country}`);
      if (item.section) lines.push(`Stage: ${item.section}`);
      if (item.status) lines.push(`Status: ${item.status}`);
      if (item.approach) lines.push(`Approach: ${item.approach}`);
      if (item.timing) lines.push(`Timing: ${item.timing}`);
      if (item.value) lines.push(`Value: ${item.value}`);
      lines.push("");
    }
    if (dfat.notices && dfat.notices.length) {
      let notices = dfat.notices;
      if (country) {
        notices = notices.filter(n =>
          countryMatchesFilter(n.title, countryCode) ||
          (n.title || "").toLowerCase().includes(country.toLowerCase())
        );
      }
      if (notices.length) {
        const recent = notices.slice(0, 10);
        lines.push(`## Recent Business Notifications${country ? ` mentioning ${country}` : ""} (latest ${Math.min(10, notices.length)})`);
        for (const n of recent) {
          lines.push(`- [${n.date || "?"}] ${n.title || "Untitled"}`);
          if (n.url) lines.push(`  ${n.url}`);
        }
      }
    }
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 3: NZ MFAT tenders
server.tool(
  "get_nz_tenders",
  "Get New Zealand tenders for Pacific island countries from the GETS portal, including open and completed.",
  {
    country: z.string().optional().describe("Filter by country name (optional)"),
    status: z.enum(["all", "open", "completed"]).default("all").describe("Filter by tender status")
  },
  async ({ country, status }) => {
    const snap = latestSnapshot();
    const nz = snap.nz;
    if (!nz || !nz.tenders) {
      return { content: [{ type: "text", text: "NZ tender data not available in the current snapshot." }] };
    }
    let tenders = nz.tenders;
    if (country) {
      const lower = country.toLowerCase();
      tenders = tenders.filter(t =>
        (t.title || "").toLowerCase().includes(lower) ||
        (t.countries || []).some(c => c.toLowerCase().includes(lower))
      );
    }
    if (status !== "all") {
      tenders = tenders.filter(t => (t.status || "").toLowerCase() === status);
    }
    const openCount = nz.tenders.filter(t => (t.status || "").toLowerCase() === "open").length;
    const completedCount = nz.tenders.filter(t => (t.status || "").toLowerCase() === "completed").length;
    const lines = [
      `# NZ Pacific Tenders (GETS)`,
      `Fetched: ${nz.fetched || "unknown"}`,
      `Total: ${nz.tenders.length} (${openCount} open, ${completedCount} completed)`,
      `Showing: ${tenders.length}${status !== "all" ? ` (${status} only)` : ""}${country ? ` matching ${country}` : ""}`,
      "",
      "Note: These tenders were identified by Pacific-related terms in the listing. Agency, geographic scope, and delivery location vary — check individual tenders for details.",
      ""
    ];
    for (const t of tenders) {
      lines.push(`## ${t.title || "Untitled"}`);
      if (t.ref) lines.push(`Reference: ${t.ref}`);
      if (t.status) lines.push(`Status: ${t.status}`);
      if (t.agency) lines.push(`Agency: ${t.agency}`);
      if (t.closes) lines.push(`Closes: ${t.closes}`);
      if (t.countries && t.countries.length) lines.push(`Countries: ${t.countries.join(", ")}`);
      if (t.value) lines.push(`Value: ${t.value}`);
      if (t.url) lines.push(`URL: ${t.url}`);
      lines.push("");
    }
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 4: Search aid activities
server.tool(
  "search_activities",
  "Search aid activities across all 14 Pacific island countries by keyword, funder, or country. Returns matching IATI activities with their details.",
  {
    query: z.string().describe("Search term: keyword, funder name, project title, or IATI identifier"),
    country: z.string().optional().describe("Restrict to a specific country (name or code)"),
    limit: z.number().default(20).describe("Maximum results to return (max 100)")
  },
  async ({ query, country, limit }) => {
    limit = Math.max(1, Math.min(limit || 20, 100));
    const snap = latestSnapshot();
    const date = snap.date;
    const index = loadIndex(date);
    if (!index) {
      return { content: [{ type: "text", text: `Activity index not available for ${date}. Try get_country_summary instead.` }] };
    }
    const q = query.toLowerCase();
    let targetCountries = Object.keys(COUNTRIES);
    if (country) {
      const code = matchCountry(country);
      if (code) {
        targetCountries = [code];
      } else {
        return { content: [{ type: "text", text: `Country not recognised: "${country}". Available: ${Object.entries(COUNTRIES).map(([c,n]) => `${n} (${c})`).join(", ")}` }] };
      }
    }
    const results = [];
    let totalMatches = 0;
    for (const code of targetCountries) {
      const acts = decodeIndex(index[code]);
      if (!acts.length) continue;
      for (const a of acts) {
        const text = [a.title, a.org, a.aid, a.ref].filter(Boolean).join(" ").toLowerCase();
        if (text.includes(q)) {
          totalMatches++;
          if (results.length < limit) {
            results.push({ ...a, country: COUNTRIES[code], countryCode: code });
          }
        }
      }
    }
    if (!results.length) {
      return { content: [{ type: "text", text: `No activities found matching "${query}"${country ? ` in ${country}` : ""}.` }] };
    }
    const lines = [`# Activities matching "${query}"`, `Showing: ${results.length} of ${totalMatches} matches`, `Source: IATI activity index, snapshot ${date}`, ""];
    for (const r of results) {
      lines.push(`## ${r.title || "Untitled"}`);
      const status = STATUS_MAP[r.st] || r.st || "?";
      lines.push(`Country: ${r.country} | Funder: ${r.org || "?"} | ID: ${r.aid || "?"}`);
      if (r.start || r.end) lines.push(`Period: ${r.start || "?"} to ${r.end || "?"}`);
      if (r.spend != null) lines.push(`Reported spending: ${fmt(r.spend)}${r.pct != null && r.pct < 100 ? ` (${r.pct}% country share)` : ""}`);
      lines.push(`Status: ${status}${r.stale ? " (stale — past declared end date by >365 days)" : ""}`);
      lines.push("");
    }
    lines.push("---", "Note: Spending figures combine IATI disbursement and expenditure transactions, weighted by declared recipient-country percentage. Figures reflect what reporting organisations have published, not necessarily what was provided as the original donor.");
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 5: Search World Bank evaluation lessons
server.tool(
  "search_lessons",
  "Search 3,043 lessons from 991 World Bank project evaluations across 177 countries. Find what worked, what failed, and why in development projects by topic, country, sector, or outcome rating.",
  {
    query: z.string().describe("Search term: topic, sector, country, or keyword (e.g. 'water supply', 'community engagement', 'gender')"),
    country: z.string().optional().describe("Filter by country name"),
    outcome: z.enum(["any", "satisfactory", "unsatisfactory"]).default("any").describe("Filter by project outcome rating"),
    limit: z.number().default(10).describe("Maximum results to return (max 50)")
  },
  async ({ query, country, outcome, limit }) => {
    limit = Math.max(1, Math.min(limit || 10, 50));
    const data = loadLessons();
    const projects = data.projects || [];
    if (!projects.length) {
      return { content: [{ type: "text", text: "Evaluation lesson corpus is not available. The lessons dataset may not be installed. Check that wb-icr-global-1000.json exists in the data directory." }] };
    }
    const q = query.toLowerCase();
    const results = [];
    for (const p of projects) {
      if (country) {
        const c = country.toLowerCase();
        if (!(p.country || "").toLowerCase().includes(c)) continue;
      }
      if (outcome !== "any") {
        const rating = (p.outcome_rating || "").toLowerCase();
        if (outcome === "satisfactory" && !rating.includes("satisfactory")) continue;
        if (outcome === "unsatisfactory" && !rating.includes("unsatisfactory")) continue;
        if (outcome === "satisfactory" && rating.includes("unsatisfactory")) continue;
      }
      const lessons = p.lessons || [];
      for (const lesson of lessons) {
        const text = [lesson, p.title, p.country, ...(p.sectors || []), ...(p.themes || [])].filter(Boolean).join(" ").toLowerCase();
        if (text.includes(q)) {
          results.push({
            lesson,
            project: p.title,
            country: p.country,
            region: p.region,
            outcome_rating: p.outcome_rating,
            sectors: p.sectors,
            project_id: p.project_id
          });
          if (results.length >= limit) break;
        }
      }
      if (results.length >= limit) break;
    }
    if (!results.length) {
      return { content: [{ type: "text", text: `No lessons found matching "${query}"${country ? ` in ${country}` : ""}. The search uses substring matching on lesson text, project title, country, sectors, and themes.` }] };
    }
    const lines = [
      `# Evaluation Lessons: "${query}"`,
      `Found: ${results.length} lessons from World Bank ICR (Implementation Completion Report) reviews`,
      `Corpus: ${projects.length} projects, searched by substring match (not semantic or relevance-ranked)`,
      ""
    ];
    for (const r of results) {
      lines.push(`## ${r.project || "Untitled Project"}`);
      lines.push(`Country: ${r.country || "?"} | Region: ${r.region || "?"} | Outcome: ${r.outcome_rating || "?"}`);
      if (r.project_id) lines.push(`Project ID: ${r.project_id}`);
      if (r.sectors && r.sectors.length) lines.push(`Sectors: ${r.sectors.join(", ")}`);
      lines.push("");
      lines.push(r.lesson.length > 800 ? r.lesson.substring(0, 800) + "..." : r.lesson);
      lines.push("");
    }
    lines.push("---", "Note: Lessons are extracted from World Bank ICR reviews. A project's outcome rating does not prove each individual lesson caused success or failure. Global findings may not transfer directly to Pacific or other specific contexts. These are evidence inputs, not conclusions.");
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 6: Compare countries
server.tool(
  "compare_countries",
  "Compare two Pacific island countries side by side: aid volumes, funders, sectors, data quality.",
  {
    country_a: z.string().describe("First country (name or code)"),
    country_b: z.string().describe("Second country (name or code)")
  },
  async ({ country_a, country_b }) => {
    const snap = latestSnapshot();
    const codeA = matchCountry(country_a);
    const codeB = matchCountry(country_b);
    if (!codeA || !snap.countries[codeA]) {
      return { content: [{ type: "text", text: `Country not found: "${country_a}"` }] };
    }
    if (!codeB || !snap.countries[codeB]) {
      return { content: [{ type: "text", text: `Country not found: "${country_b}"` }] };
    }
    const a = snap.countries[codeA];
    const b = snap.countries[codeB];
    const lines = [
      `# ${a.name} vs ${b.name}`,
      `Data as of: ${snap.date}`,
      "",
      `| Metric | ${a.name} | ${b.name} |`,
      `|--------|${"-".repeat(a.name.length + 2)}|${"-".repeat(b.name.length + 2)}|`,
      `| 90-day disbursements | ${fmt(a.dis90)} | ${fmt(b.dis90)} |`,
      `| 365-day disbursements | ${fmt(a.dis365)} | ${fmt(b.dis365)} |`,
      `| Active funders (90d) | ${a.n_orgs_90} | ${b.n_orgs_90} |`,
      `| Active funders (365d) | ${a.n_orgs_365} | ${b.n_orgs_365} |`,
      `| Active activities (90d) | ${a.n_acts_90} | ${b.n_acts_90} |`,
      `| Total activities | ${a.n_activities} | ${b.n_activities} |`,
      `| Active (implementation) | ${a.n_active} | ${b.n_active} |`,
      `| Stale | ${a.n_stale} | ${b.n_stale} |`,
      `| New starts | ${a.n_new_starts} | ${b.n_new_starts} |`,
      `| Ending soon | ${a.n_ending_soon} | ${b.n_ending_soon} |`,
      "",
      `## Top Funders`,
      `### ${a.name}`,
    ];
    for (const org of (a.top_orgs_90 || []).slice(0, 5)) {
      lines.push(`- ${org.name}: ${fmt(org.usd)}`);
    }
    lines.push(`### ${b.name}`);
    for (const org of (b.top_orgs_90 || []).slice(0, 5)) {
      lines.push(`- ${org.name}: ${fmt(org.usd)}`);
    }
    lines.push("", `## Data Freshness Warnings`);
    for (const [label, c] of [[a.name, a], [b.name, b]]) {
      const staleOrgs = (c.currency || []).filter(f => f.age_days > 365);
      if (staleOrgs.length) {
        lines.push(`### ${label}`);
        for (const f of staleOrgs.slice(0, 5)) {
          lines.push(`- ${f.name}: no transactions reported for ${f.age_days} days (latest: ${f.latest || "unknown"}). Figures may understate actual activity.`);
        }
        if (staleOrgs.length > 5) lines.push(`  ... and ${staleOrgs.length - 5} more with stale data`);
      }
    }
    lines.push("", "---", "Note: Spending figures combine IATI disbursement and expenditure transactions. Reporting organisations are publishers, not necessarily original donors. Where a funder's data is stale, $0 reflects missing reports, not zero activity.");
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 7: Regional overview
server.tool(
  "get_regional_overview",
  "Get a high-level overview of aid flows across all 14 Pacific island countries: total disbursements, top recipients, top funders, data freshness issues.",
  {},
  async () => {
    const snap = latestSnapshot();
    const countries = snap.countries;
    let totalDis90 = 0, totalDis365 = 0, totalActs = 0, totalStale = 0;
    const countryRows = [];
    const allFunders = {};

    for (const [code, c] of Object.entries(countries)) {
      totalDis90 += c.dis90 || 0;
      totalDis365 += c.dis365 || 0;
      totalActs += c.n_active || 0;
      totalStale += c.n_stale || 0;
      countryRows.push({ name: c.name, code, dis90: c.dis90, dis365: c.dis365, orgs90: c.n_orgs_90, active: c.n_active });
      for (const org of (c.orgs_90 || [])) {
        allFunders[org.name] = (allFunders[org.name] || 0) + (org.usd || 0);
      }
    }
    countryRows.sort((a, b) => (b.dis90 || 0) - (a.dis90 || 0));
    const topFunders = Object.entries(allFunders).sort((a, b) => b[1] - a[1]).slice(0, 15);

    const lines = [
      `# Pacific Aid — Regional Overview`,
      `Data as of: ${snap.date}`,
      "",
      `## Totals (IATI-reported spending: disbursements + expenditures, weighted by recipient-country share)`,
      `- 90-day reported spending: ${fmt(totalDis90)}`,
      `- 365-day reported spending: ${fmt(totalDis365)}`,
      `- Active activities: ${totalActs.toLocaleString()}`,
      `- Stale activities: ${totalStale.toLocaleString()}`,
      `- Countries: ${Object.keys(countries).length}`,
      "",
      `## By Country (90-day disbursements)`,
    ];
    for (const row of countryRows) {
      lines.push(`- ${row.name} (${row.code}): ${fmt(row.dis90)} | ${row.orgs90} funders | ${row.active} active`);
    }
    lines.push("", `## Top Funders (90-day, region-wide)`);
    for (const [name, usd] of topFunders) {
      lines.push(`- ${name}: ${fmt(usd)}`);
    }

    const dfat = snap.dfat;
    if (dfat) {
      const items = dfat.items || [];
      const inMarket = items.filter(i => (i.section || "").toLowerCase() === "in the market").length;
      const planned = items.filter(i => (i.section || "").toLowerCase() === "planned").length;
      const inCollab = items.filter(i => (i.section || "").toLowerCase() === "in collaboration").length;
      const closed = items.filter(i => (i.section || "").toLowerCase() === "closed").length;
      lines.push("", `## DFAT Pipeline Summary`,
        `- As at: ${dfat.as_at}`,
        `- Total items: ${items.length}`,
        `- In the market: ${inMarket}`,
        `- Planned: ${planned}`,
        `- In collaboration: ${inCollab}`,
        `- Closed: ${closed}`
      );
    }
    const nz = snap.nz;
    if (nz) {
      const tenders = nz.tenders || [];
      const openCount = tenders.filter(t => (t.status || "").toLowerCase() === "open").length;
      const completedCount = tenders.filter(t => (t.status || "").toLowerCase() === "completed").length;
      lines.push("", `## NZ Pacific Tenders (GETS): ${tenders.length} total (${openCount} open, ${completedCount} completed)`);
    }
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 8: Funder profile
server.tool(
  "get_funder_profile",
  "Get a profile of a specific development funder across all Pacific island countries: where they operate, how much they disburse, and how fresh their data is.",
  {
    funder: z.string().describe("Funder name or partial name (e.g. 'Australia', 'UNDP', 'World Bank', 'EU')")
  },
  async ({ funder }) => {
    const snap = latestSnapshot();
    const q = matchFunder(funder);
    const presence = [];

    for (const [code, c] of Object.entries(snap.countries)) {
      for (const org of (c.orgs_90 || [])) {
        if (org.name.toLowerCase().includes(q)) {
          presence.push({ country: c.name, code, usd: org.usd, name: org.name });
        }
      }
      for (const f of (c.currency || [])) {
        if (f.name.toLowerCase().includes(q) && !presence.find(p => p.code === code)) {
          presence.push({ country: c.name, code, usd: 0, name: f.name, age_days: f.age_days, latest: f.latest, lifetime: f.lifetime_usd });
        }
      }
    }
    if (!presence.length) {
      return { content: [{ type: "text", text: `No funder matching "${funder}" found in Pacific aid data.` }] };
    }
    const canonName = presence[0].name;
    const totalUsd = presence.reduce((s, p) => s + (p.usd || 0), 0);
    presence.sort((a, b) => (b.usd || 0) - (a.usd || 0));

    const lines = [
      `# Funder Profile: ${canonName}`,
      `Data as of: ${snap.date}`,
      "",
      `Total 90-day disbursements (Pacific): ${fmt(totalUsd)}`,
      `Present in: ${presence.length} of ${Object.keys(snap.countries).length} countries`,
      "",
      `## Country Presence`,
    ];
    for (const p of presence) {
      let line = `- ${p.country}: ${fmt(p.usd)}`;
      if (p.age_days != null) line += ` (data ${p.age_days} days old)`;
      if (p.lifetime != null) line += ` | lifetime: ${fmt(p.lifetime)}`;
      lines.push(line);
    }
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Tool 9: Update data from public repo
server.tool(
  "update_data",
  "Fetch the latest Pacific aid data from the public repository. The data updates every 12 hours; use this to get the most recent snapshot without manually updating files.",
  {},
  async () => {
    try {
      const resp = await fetch(
        "https://api.github.com/repos/intexpagent-01/asa-research/contents/signal/data",
        { headers: { "User-Agent": "pacific-dev-intel-mcp/0.1" } }
      );
      if (!resp.ok) throw new Error(`GitHub API: ${resp.status}`);
      const files = await resp.json();
      const snapshots = files
        .filter(f => /^pacific-\d{4}-\d{2}-\d{2}\.json$/.test(f.name))
        .sort((a, b) => a.name.localeCompare(b.name));
      if (!snapshots.length) throw new Error("No snapshots found in repository");

      const latest = snapshots[snapshots.length - 1];
      const latestDate = latest.name.replace(/^pacific-|\.json$/g, "");

      const currentFiles = readdirSync(DATA_DIR)
        .filter(f => /^pacific-\d{4}-\d{2}-\d{2}\.json$/.test(f))
        .sort();
      const currentLatest = currentFiles.length ? currentFiles[currentFiles.length - 1] : null;
      const currentDate = currentLatest ? currentLatest.replace(/^pacific-|\.json$/g, "") : null;

      const targetDir = join(__dirname, "data");
      if (!existsSync(targetDir)) mkdirSync(targetDir, { recursive: true });

      if (currentDate === latestDate) {
        const currentSize = existsSync(join(DATA_DIR, currentLatest))
          ? readFileSync(join(DATA_DIR, currentLatest)).length : 0;
        if (currentSize > 0 && latest.size && Math.abs(currentSize - latest.size) < 100) {
          return { content: [{ type: "text", text: `Data is already current: ${latestDate} (${(currentSize / 1024).toFixed(0)} KB).` }] };
        }
      }

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);
      let dataResp;
      try {
        dataResp = await fetch(latest.download_url, { signal: controller.signal });
      } finally {
        clearTimeout(timeout);
      }
      if (!dataResp.ok) throw new Error(`Failed to fetch snapshot: ${dataResp.status}`);
      const data = await dataResp.text();
      if (data.length > 50 * 1024 * 1024) throw new Error(`Snapshot too large: ${(data.length / 1024 / 1024).toFixed(1)} MB`);

      let parsed;
      try {
        parsed = JSON.parse(data);
        if (!parsed.date || !parsed.countries) throw new Error("Invalid snapshot structure");
      } catch (e) {
        throw new Error(`Downloaded snapshot failed validation: ${e.message}`);
      }
      writeFileSync(join(targetDir, latest.name), data);

      const indexName = latest.name.replace(".json", ".index.json.gz");
      const indexFile = files.find(f => f.name === indexName);
      let indexUpdated = false;
      if (indexFile) {
        const idxController = new AbortController();
        const idxTimeout = setTimeout(() => idxController.abort(), 60000);
        try {
          const idxResp = await fetch(indexFile.download_url, { signal: idxController.signal });
          if (idxResp.ok) {
            const idxBuf = Buffer.from(await idxResp.arrayBuffer());
            if (idxBuf.length > 20 * 1024 * 1024) throw new Error("Index too large");
            writeFileSync(join(targetDir, indexName), idxBuf);
            indexUpdated = true;
          }
        } finally {
          clearTimeout(idxTimeout);
        }
      }

      DATA_DIR = targetDir;

      return { content: [{ type: "text", text: `Updated from ${currentDate || "none"} to ${latestDate}.${indexUpdated ? " Activity search index also updated." : ""}` }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Update failed: ${e.message}. Using existing data.` }] };
    }
  }
);

// --- Start ---
const transport = new StdioServerTransport();
await server.connect(transport);
