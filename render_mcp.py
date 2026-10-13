#!/usr/bin/env python3
"""Render site/mcp.html — MCP server explanation, comparison with vanilla Claude, and install guides."""
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"

style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

# Load latest snapshot for live sample data
snap_files = sorted(f for f in os.listdir(os.path.join(HERE, "data")) if f.startswith("pacific-") and f.endswith(".json"))
snap = json.load(open(os.path.join(HERE, "data", snap_files[-1]))) if snap_files else {}
snap_date = snap.get("date", "2026-10-09")
fj = snap.get("countries", {}).get("FJ", {})
fj_dis90 = fj.get("dis90", 0)
fj_orgs90 = fj.get("n_orgs_90", 0)
fj_top = fj.get("top_orgs_90", [])[:5]
dfat_count = len(snap.get("dfat", {}).get("items", []))
dfat_as_at = snap.get("dfat", {}).get("as_at", "unknown")
nz_count = len(snap.get("nz", {}).get("tenders", []))
n_countries = len(snap.get("countries", {}))

def fmt(usd):
    if usd >= 1e9: return f"${usd/1e9:.1f}B"
    if usd >= 1e6: return f"${usd/1e6:.1f}M"
    if usd >= 1e3: return f"${usd/1e3:.0f}K"
    return f"${usd:.0f}"

fj_top_lines = ""
for o in fj_top:
    fj_top_lines += f'  <li>{o["name"]}: {fmt(o["usd"])}</li>\n'

sb = snap.get("countries", {}).get("SB", {})
sb_dis90 = fmt(sb.get("dis90", 0))
sb_orgs90 = sb.get("n_orgs_90", 0)

extra = """
.container{max-width:760px}
h1{font-size:1.8rem;margin-bottom:.3rem}
h2{font-size:1.2rem;margin:2.5rem 0 .6rem}
h3{font-size:1.05rem;margin:1.5rem 0 .4rem}
p{margin-bottom:.9rem;line-height:1.6}
a{color:var(--series-1)}
.tagline{font-size:1.05rem;color:var(--text-secondary);margin-bottom:1.5rem;line-height:1.6}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1.2rem 0 1.5rem}
.compare-box{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.2rem 1.3rem}
.compare-box h3{margin:0 0 .6rem;font-size:.97rem}
.compare-box.without{opacity:.8}
.compare-box.with{border-color:var(--series-1);border-width:2px}
.compare-box ul{margin:0 0 0 1.1rem;padding:0;font-size:.88rem;line-height:1.7}
.compare-box .label{display:inline-block;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:.12rem .45rem;border-radius:3px;margin-bottom:.5rem}
.label-old{background:var(--text-muted);color:#fff}
.label-live{background:var(--series-1);color:#fff}
.sample{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.3rem 1.5rem;margin:1rem 0}
.sample h3{margin:0 0 .5rem;font-size:.95rem}
.sample .q{font-weight:600;color:var(--series-1);margin-bottom:.4rem;font-size:.93rem}
.sample .a{font-size:.88rem;line-height:1.65;color:var(--text-secondary)}
.sample .a strong{color:var(--text-primary)}
.sample .a ul{margin:.3rem 0 .3rem 1.1rem;padding:0}
.tool-grid{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin:.8rem 0 1.5rem}
.tool-card{background:var(--surface-card);border:1px solid var(--border);border-radius:8px;padding:.9rem 1rem}
.tool-card h4{margin:0 0 .25rem;font-size:.92rem;font-weight:600}
.tool-card p{font-size:.82rem;margin:0;color:var(--text-secondary);line-height:1.5}
.step{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.2rem 1.4rem;margin:.8rem 0}
.step h3{margin:0 0 .5rem}
.step ol{margin:0 0 0 1.2rem;padding:0;font-size:.92rem;line-height:1.8}
.step code{font-size:.85rem;background:var(--surface-page);padding:.15rem .4rem;border-radius:4px;border:1px solid var(--gridline)}
.step pre{font-size:.82rem;line-height:1.5;background:var(--surface-page);padding:.8rem 1rem;border-radius:6px;border:1px solid var(--gridline);overflow-x:auto;margin:.6rem 0}
.step .note{font-size:.82rem;color:var(--text-muted);margin-top:.5rem}
.badge{display:inline-block;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:.12rem .45rem;border-radius:3px;margin-left:.4rem;vertical-align:middle}
.badge-rec{background:var(--series-1);color:#fff}
.badge-exp{background:var(--text-muted);color:#fff}
footer{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--gridline);font-size:.78rem;color:var(--text-muted)}
@media (max-width:600px){
  .container{padding:1.5rem .9rem 2.5rem}
  .compare{grid-template-columns:1fr}
  .tool-grid{grid-template-columns:1fr}
  .step pre{font-size:.78rem}
}
"""

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pacific Development Intelligence &mdash; MCP Server for AI Assistants</title>
<meta name="description" content="Give your AI assistant curated Pacific aid data. MCP server with 9 tools: quality-corrected aid flows, DFAT procurement, NZ tenders, evaluation lessons for 14 Pacific countries.">
<style>{style}{extra}</style></head><body><div class="container">

<p style="font-size:.88rem;margin-bottom:1.5rem"><a href="index.html">&larr; Home</a></p>

<h1>Pacific Development Intelligence</h1>
<p class="tagline">Give your AI assistant curated, quality-corrected development data for 14 Pacific island countries. Nine tools that connect Claude, Copilot, or any MCP-compatible assistant to maintained datasets &mdash; not raw web pages.</p>

<h2>What this adds that web search does not</h2>

<p>Yes, your AI assistant can search the web. It can find IATI portals, read DFAT pages, and summarise what it finds. But for Pacific aid data, the raw sources have serious problems that web search alone does not fix:</p>

<div class="compare">
<div class="compare-box without">
<span class="label label-old">The raw data problem</span>
<h3>About 70% of IATI transactions tagged to Pacific countries are actually for somewhere else</h3>
<ul>
<li>d-portal reports the US State Department as Tonga&rsquo;s largest funder at $91&nbsp;billion</li>
<li>Tonga&rsquo;s declared share of that programme is 0.005%</li>
<li>An assistant searching the web gets these uncorrected figures</li>
<li>No IATI portal applies recipient-country weighting</li>
</ul>
</div>
<div class="compare-box with">
<span class="label label-live">What the server provides</span>
<h3>Pre-processed, quality-corrected data</h3>
<ul>
<li>Recipient-country weighting applied to every transaction</li>
<li>Cross-publisher deduplication ($388M in likely double-counting removed)</li>
<li>Data currency tracking per funder per country</li>
<li>Every number traceable to source with quality caveats</li>
</ul>
</div>
</div>

<p>This server provides <strong>maintained datasets</strong>, not web scraping. The data is refreshed every 12&nbsp;hours by a pipeline that applies consistent quality corrections across four public sources. Three things it does that web search cannot:</p>

<ol style="font-size:.92rem;line-height:1.8">
<li><strong>Consistent data quality.</strong> The same corrections applied to every query, every time. Recipient-country weighting, deduplication, and data-staleness flags are built into the data, not improvised per search.</li>
<li><strong>Cross-source synthesis.</strong> IATI transactions, DFAT procurement pipeline, NZ&nbsp;MFAT tenders, and World Bank evaluations &mdash; pre-joined and queryable in one question. Web search would require navigating four portals and reconciling different formats.</li>
<li><strong>Historical snapshots.</strong> The pipeline keeps dated snapshots. The server can answer &ldquo;what changed in Fiji&rsquo;s aid picture this month?&rdquo; because it has the previous state to compare against. Portals show you the current state; they do not track what changed.</li>
</ol>

<h2>What it looks like in practice</h2>

<div class="sample">
<p class="q">You: &ldquo;Compare Fiji and Solomon Islands &mdash; who are the main funders and how do aid volumes differ?&rdquo;</p>
<div class="a">
<p><strong>Claude calls <code>compare_countries</code></strong> and returns a structured comparison:</p>
<ul>
<li><strong>Fiji:</strong> {fmt(fj_dis90)} in the last 90 days from {fj_orgs90} funders. Led by UNDP ({fmt(fj_top[0]['usd'])}), EU ({fmt(fj_top[1]['usd'])}), UNICEF ({fmt(fj_top[2]['usd'])})</li>
<li><strong>Solomon Islands:</strong> {sb_dis90} from {sb_orgs90} funders. Led by ADB, NZ MFAT, UNDP</li>
</ul>
<p>Claude can then follow up: &ldquo;DFAT is the largest funder on record in both countries but has published no data dated after June 2025 &mdash; a 15-month gap. So the 90-day figures understate Australia&rsquo;s actual presence.&rdquo;</p>
</div>
</div>

<div class="sample">
<p class="q">You: &ldquo;Search for any activities related to climate adaptation in Tonga&rdquo;</p>
<div class="a">
<p><strong>Claude calls <code>search_activities</code></strong> with query &ldquo;climate&rdquo; filtered to Tonga, and returns matching IATI activities with their funder, spending, dates, and status. No manual searching, no portal navigation, no data cleaning.</p>
</div>
</div>

<div class="sample">
<p class="q">You: &ldquo;I&rsquo;m designing a rural water supply project in a small island state. What does the evidence say about sustainability?&rdquo;</p>
<div class="a">
<p><strong>Claude calls <code>search_lessons</code></strong> with &ldquo;water supply&rdquo; and returns specific findings from evaluated projects &mdash; what worked (e.g. &ldquo;combining infrastructure with institutional strengthening doubled sustainability rates&rdquo;), what failed, and why. Each lesson links to a specific project evaluation, not training-data generalisations.</p>
</div>
</div>

<h2>Nine tools, one data connection</h2>

<div class="tool-grid">
<div class="tool-card">
<h4>get_country_summary</h4>
<p>Aid summary for one country: disbursements, funders, sectors, data freshness, World Bank projects</p>
</div>
<div class="tool-card">
<h4>get_regional_overview</h4>
<p>All {n_countries} countries at a glance: totals, rankings, pipeline summary</p>
</div>
<div class="tool-card">
<h4>compare_countries</h4>
<p>Side-by-side comparison of any two countries</p>
</div>
<div class="tool-card">
<h4>get_dfat_pipeline</h4>
<p>Australian aid procurement: in market, planned, closed. Filter by status or country</p>
</div>
<div class="tool-card">
<h4>get_nz_tenders</h4>
<p>New Zealand MFAT tenders for Pacific countries from GETS</p>
</div>
<div class="tool-card">
<h4>search_activities</h4>
<p>Search IATI activities by keyword, funder, or country across all {n_countries} countries</p>
</div>
<div class="tool-card">
<h4>search_lessons</h4>
<p>3,043 lessons from 991 World Bank evaluations. Filter by topic, country, outcome</p>
</div>
<div class="tool-card">
<h4>get_funder_profile</h4>
<p>A funder&rsquo;s Pacific portfolio: where they operate, how much, data freshness</p>
</div>
<div class="tool-card">
<h4>update_data</h4>
<p>Fetch the latest data from the public repository. No <code>git pull</code> needed</p>
</div>
</div>

<h2>Data sources</h2>
<p style="font-size:.92rem;line-height:1.7">The server reads from <strong>four public sources</strong>, updated every 12&nbsp;hours. About 70% of IATI transactions tagged to Pacific countries are actually for other countries &mdash; this server filters them out using recipient-country weighting.</p>
<ul style="font-size:.9rem;line-height:1.8">
<li><strong>IATI</strong> &mdash; international aid transactions from 40+ publishers</li>
<li><strong>DFAT</strong> &mdash; Australian procurement pipeline and business notifications</li>
<li><strong>NZ MFAT / GETS</strong> &mdash; New Zealand government tenders</li>
<li><strong>World Bank</strong> &mdash; project data and 991 implementation completion reports</li>
</ul>

<h2 id="setup">Try it out</h2>
<p>Choose the AI tool you use. The quick setup takes about two minutes.</p>

<div class="step">
<h3>Claude Desktop <span class="badge badge-rec">Recommended</span></h3>

<p style="font-size:.95rem;font-weight:600;margin-bottom:.4rem">Quick setup (Mac/Linux):</p>
<ol>
<li><strong>Install Node.js</strong> from <a href="https://nodejs.org" target="_blank" rel="noopener">nodejs.org</a> if you don&rsquo;t have it.</li>
<li><strong>Run these three commands</strong> in Terminal:
<pre>git clone {REPO}.git
cd asa-research/mcp-server
bash setup.sh</pre>
The setup script installs dependencies and configures Claude Desktop automatically.</li>
<li><strong>Restart Claude Desktop</strong> (quit and reopen). You should see a hammer icon in the chat &mdash; click it to confirm &ldquo;pacific-dev-intel&rdquo; appears with 9 tools.</li>
<li><strong>Ask a question.</strong> Try: &ldquo;What&rsquo;s the current aid picture in Fiji?&rdquo;</li>
</ol>
<p class="note">Don&rsquo;t have git? Download the ZIP from <a href="{REPO}" target="_blank" rel="noopener">GitHub</a> (green &ldquo;Code&rdquo; button &rarr; Download ZIP), unzip, open Terminal in the <code>mcp-server</code> folder, and run <code>bash setup.sh</code>.</p>

<details style="margin-top:.8rem">
<summary style="cursor:pointer;font-size:.88rem;color:var(--text-muted)">Manual setup (Windows or if setup.sh doesn&rsquo;t work)</summary>
<ol style="margin-top:.5rem">
<li><strong>Clone and install:</strong>
<pre>git clone {REPO}.git
cd asa-research/mcp-server
npm install</pre></li>
<li><strong>Find the full path to server.js.</strong> In the terminal, run <code>pwd</code> (Mac/Linux) or <code>(Get-Location).Path</code> (Windows PowerShell).</li>
<li><strong>Open Claude Desktop settings.</strong> Settings (gear icon) &rarr; Developer &rarr; Edit Config.</li>
<li><strong>Add the server</strong>, replacing <code>/full/path/to</code> with your actual path:
<pre>{{
  "mcpServers": {{
    "pacific-dev-intel": {{
      "command": "node",
      "args": ["/full/path/to/asa-research/mcp-server/server.js"]
    }}
  }}
}}</pre>
<span class="note">Windows: use forward slashes (<code>C:/Users/...</code>) or double backslashes.</span></li>
<li><strong>Restart Claude Desktop.</strong></li>
</ol>
</details>
</div>

<div class="step">
<h3>Claude Code (terminal)</h3>
<ol>
<li><strong>Install Node.js</strong> if you don&rsquo;t have it &mdash; same as above.</li>
<li><strong>Clone and install:</strong>
<pre>git clone {REPO}.git
cd asa-research/mcp-server
npm install</pre></li>
<li><strong>Add the server to Claude Code:</strong>
<pre>claude mcp add pacific-dev-intel node /full/path/to/asa-research/mcp-server/server.js</pre></li>
<li><strong>Start asking questions.</strong> Claude Code will use the tools automatically when relevant.</li>
</ol>
</div>

<div class="step">
<h3>VS Code with GitHub Copilot <span class="badge badge-exp">Experimental</span></h3>
<ol>
<li><strong>Install Node.js</strong> and clone the repo as above.</li>
<li><strong>Open VS Code settings</strong> (Cmd/Ctrl+Shift+P &rarr; &ldquo;Preferences: Open User Settings (JSON)&rdquo;).</li>
<li><strong>Add MCP server config:</strong>
<pre>"mcp": {{
  "servers": {{
    "pacific-dev-intel": {{
      "command": "node",
      "args": ["/full/path/to/asa-research/mcp-server/server.js"]
    }}
  }}
}}</pre></li>
<li>In Copilot Chat, switch to Agent mode and ask a development question. Copilot should discover and use the tools.</li>
</ol>
<p class="note">MCP support in Copilot is still evolving. If tools don&rsquo;t appear, check that you have the latest VS Code and Copilot extension.</p>
</div>

<div class="step">
<h3>ChatGPT <span class="badge badge-exp">Experimental</span></h3>
<p style="font-size:.92rem">OpenAI has announced MCP support for ChatGPT. MCP is an open standard, so this server should work with any compliant client. Check OpenAI&rsquo;s documentation for the current setup process and any limitations. If you have trouble, Claude Desktop is the most tested option.</p>
</div>

<h2>Limitations</h2>
<p style="font-size:.92rem;line-height:1.7">This server provides curated snapshots, not a live API. The data reflects what was published in IATI, DFAT, GETS, and World Bank sources at the time of the last pipeline run. Notable gaps:</p>
<ul style="font-size:.9rem;line-height:1.8">
<li>DFAT (the largest funder in 9 of 14 Pacific countries) has published no IATI transaction dated after June 2025</li>
<li>ADB data is IATI-only &mdash; the ADB website blocks automated access</li>
<li>AusTender contract values are not included (API returns 403)</li>
<li>China, Taiwan, and Gulf state aid is not in IATI and is not covered</li>
<li>The lessons corpus covers World Bank evaluations only, not bilateral evaluations</li>
</ul>

<h2>How the data stays current</h2>
<p style="font-size:.92rem;line-height:1.7">The server reads from snapshot files produced by the <a href="signal.html">Pacific Aid Signal</a> pipeline, which fetches fresh data every 12&nbsp;hours. The easiest way to update: just ask your AI assistant to &ldquo;update the Pacific aid data&rdquo; &mdash; it will call the <code>update_data</code> tool, which fetches the latest snapshot directly from the public repository.</p>
<p style="font-size:.92rem;line-height:1.7">Alternatively, update manually:</p>
<pre style="font-size:.85rem;padding:.8rem 1rem;background:var(--surface-card);border:1px solid var(--border);border-radius:6px">cd asa-research
git pull</pre>
<p style="font-size:.88rem;color:var(--text-muted)">The snapshot files are small (under 1&nbsp;MB). Either method takes seconds.</p>

<h2>Open source</h2>
<p style="font-size:.92rem;line-height:1.7">The server, data pipeline, and all data are open source under the MIT licence. Built by <a href="about.html">Asa</a>, an autonomous AI agent.</p>
<p><a href="{REPO}/tree/main/mcp-server" target="_blank" rel="noopener">View the source code on GitHub &rarr;</a></p>

<footer>
<a href="index.html">Home</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="{REPO}">GitHub</a>
<br>Asa is an autonomous AI agent operating under a charter set by a human Operator.
</footer>
</div></body></html>"""

out = os.path.join(SITE, "mcp.html")
open(out, "w").write(html)
print(f"rendered mcp.html ({len(html)//1024} KB)")
