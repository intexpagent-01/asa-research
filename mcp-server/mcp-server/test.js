#!/usr/bin/env node

import { spawn } from "child_process";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
let passed = 0, failed = 0;

function startServer() {
  const proc = spawn("node", [join(__dirname, "server.js")], {
    stdio: ["pipe", "pipe", "pipe"]
  });
  let buf = "";
  const pending = new Map();
  proc.stdout.on("data", chunk => {
    buf += chunk.toString();
    const lines = buf.split("\n");
    buf = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        const resolve = pending.get(msg.id);
        if (resolve) { pending.delete(msg.id); resolve(msg); }
      } catch {}
    }
  });
  let nextId = 1;
  function send(method, params = {}) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      pending.set(id, resolve);
      proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
      setTimeout(() => { pending.delete(id); reject(new Error(`Timeout: ${method}`)); }, 10000);
    });
  }
  return { proc, send };
}

async function run() {
  const { proc, send } = startServer();

  try {
    // Initialize
    const init = await send("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "test", version: "1.0" }
    });
    assert(init.result.serverInfo.name === "pacific-dev-intel", "server name");

    // List tools
    const tools = await send("tools/list");
    const names = tools.result.tools.map(t => t.name);
    assert(names.includes("get_country_summary"), "has get_country_summary");
    assert(names.includes("get_dfat_pipeline"), "has get_dfat_pipeline");
    assert(names.includes("search_lessons"), "has search_lessons");
    assert(names.includes("get_regional_overview"), "has get_regional_overview");
    assert(names.includes("search_activities"), "has search_activities");
    assert(names.includes("compare_countries"), "has compare_countries");
    assert(names.includes("get_funder_profile"), "has get_funder_profile");
    assert(names.includes("get_nz_tenders"), "has get_nz_tenders");
    assert(names.includes("update_data"), "has update_data");
    assert(names.length === 9, `expected 9 tools, got ${names.length}`);

    // get_country_summary
    const fiji = await send("tools/call", { name: "get_country_summary", arguments: { country: "Fiji" } });
    const fjText = fiji.result.content[0].text;
    assert(fjText.includes("Fiji — Aid Summary"), "fiji summary title");
    assert(fjText.includes("Reported spending (90 days)"), "fiji has reported spending label");

    // country by code
    const pg = await send("tools/call", { name: "get_country_summary", arguments: { country: "PG" } });
    assert(pg.result.content[0].text.includes("Papua New Guinea"), "PG resolves to PNG");

    // unknown country
    const bad = await send("tools/call", { name: "get_country_summary", arguments: { country: "Atlantis" } });
    assert(bad.result.content[0].text.includes("Country not found"), "unknown country handled");

    // get_dfat_pipeline — all
    const pipeline = await send("tools/call", { name: "get_dfat_pipeline", arguments: { status: "all" } });
    assert(pipeline.result.content[0].text.includes("DFAT Procurement Pipeline"), "pipeline title");

    // get_regional_overview
    const regional = await send("tools/call", { name: "get_regional_overview", arguments: {} });
    const regText = regional.result.content[0].text;
    assert(regText.includes("Regional Overview"), "regional overview title");
    assert(regText.includes("Papua New Guinea"), "regional has PNG");

    // search_lessons
    const lessons = await send("tools/call", { name: "search_lessons", arguments: { query: "education", limit: 3 } });
    const lesText = lessons.result.content[0].text;
    assert(lesText.includes("Evaluation Lessons"), "lessons title");
    assert(!lesText.includes("No lessons found"), "found education lessons");

    // compare_countries
    const compare = await send("tools/call", { name: "compare_countries", arguments: { country_a: "Fiji", country_b: "Samoa" } });
    assert(compare.result.content[0].text.includes("Fiji vs Samoa"), "compare title");

    // get_funder_profile
    const funder = await send("tools/call", { name: "get_funder_profile", arguments: { funder: "UNDP" } });
    assert(funder.result.content[0].text.includes("Funder Profile"), "funder profile title");

    // get_nz_tenders
    const nz = await send("tools/call", { name: "get_nz_tenders", arguments: {} });
    assert(nz.result.content[0].text.includes("NZ Pacific Tenders"), "nz tenders title");

    // Activity search — regression: must not crash on columnar index
    const actSearch = await send("tools/call", { name: "search_activities", arguments: { query: "climate", country: "Tonga", limit: 5 } });
    const actText = actSearch.result.content[0].text;
    assert(!actText.includes("is not iterable"), "activity search does not crash on columnar index");
    assert(actText.includes("Activities matching") || actText.includes("No activities found"), "activity search returns valid response");

    // Country alias — "PNG" should find Papua New Guinea in DFAT pipeline
    const pngPipeline = await send("tools/call", { name: "get_dfat_pipeline", arguments: { status: "all", country: "PNG" } });
    const pngPipeText = pngPipeline.result.content[0].text;
    assert(pngPipeText.includes("DFAT Procurement Pipeline"), "PNG alias works in DFAT pipeline");

    // Regional overview — DFAT counts should not all be zero
    assert(regText.includes("In the market:") && !regText.includes("In the market: 0\n- Planned: 0"), "regional DFAT counts not all zero");

    // NZ tenders — should show open vs completed breakdown
    const nzText = nz.result.content[0].text;
    assert(nzText.includes("open") && nzText.includes("completed"), "nz tenders show status breakdown");

    // Lessons corpus — should be loaded
    assert(!lesText.includes("not available"), "lessons corpus is loaded");

    // Country summary has coverage warnings section
    assert(fjText.includes("Coverage Warnings") || fjText.includes("Data Quality"), "country summary has data quality section");

    // Comparison has freshness warnings
    const cmpText = compare.result.content[0].text;
    assert(cmpText.includes("Data Freshness") || cmpText.includes("Note:"), "comparison includes data caveats");

  } finally {
    proc.kill();
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

function assert(condition, label) {
  if (condition) {
    passed++;
    console.log(`  PASS  ${label}`);
  } else {
    failed++;
    console.log(`  FAIL  ${label}`);
  }
}

run().catch(err => { console.error(err); process.exit(1); });
