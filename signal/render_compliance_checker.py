#!/usr/bin/env python3
"""Render site/compliance-checker.html: DFAT DMEL Compliance Checker.

Client-side tool that checks evaluation documents against DFAT's
Design, Monitoring, Evaluation and Learning Standards.
Document text never leaves the browser.
"""
import os, re, json
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

# Import check definitions from the Python prototype
import sys
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "experiments"))
from importlib import import_module
spec = import_module("dfat-compliance-checker")
STANDARD_9 = spec.STANDARD_9_CHECKS
STANDARD_10 = spec.STANDARD_10_CHECKS


def checks_to_js(checks, var_name):
    """Convert Python check definitions to JavaScript object literal."""
    items = []
    for check_id, check in checks.items():
        patterns = []
        for p in check["indicators"]:
            # Python regex to JS: \b works in JS, most patterns transfer directly
            patterns.append(p)
        items.append({
            "id": check_id,
            "label": check["label"],
            "standard": check["standard"],
            "description": check["description"],
            "indicators": patterns,
            "min_matches": check["min_matches"],
        })
    return json.dumps(items, indent=2)


def render():
    s9_js = checks_to_js(STANDARD_9, "STANDARD_9")
    s10_js = checks_to_js(STANDARD_10, "STANDARD_10")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DFAT Evaluation Compliance Checker — Pacific Aid Signal</title>
<meta name="description" content="Check evaluation plans and reports against DFAT DMEL Standards. Client-side — your document never leaves your browser.">
<style>{style}</style>
<style>
.checker-area {{
  max-width: 900px;
  margin: 0 auto;
}}
.paste-box {{
  width: 100%;
  min-height: 200px;
  padding: 12px;
  border: 2px dashed #0d7377;
  border-radius: 8px;
  font-family: inherit;
  font-size: 0.95em;
  line-height: 1.5;
  resize: vertical;
  background: #f9fafb;
  transition: border-color 0.2s;
}}
.paste-box:focus {{
  border-color: #e05a3a;
  outline: none;
  background: #fff;
}}
@media (prefers-color-scheme: dark) {{
  .paste-box {{ background: #1a1a2e; color: #e0e0e0; border-color: #2a9d8f; }}
  .paste-box:focus {{ background: #16213e; border-color: #e05a3a; }}
}}
.type-select {{
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid #ccc;
  font-size: 0.95em;
  margin-right: 12px;
}}
.check-btn {{
  padding: 10px 28px;
  background: linear-gradient(135deg, #0d7377, #14919b);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 1em;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.2s;
}}
.check-btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(13,115,119,0.3); }}
.check-btn:active {{ transform: translateY(0); }}
.check-btn:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; }}
.results-panel {{
  margin-top: 24px;
  display: none;
}}
.results-panel.visible {{ display: block; }}
.score-card {{
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}}
.score-tile {{
  flex: 1;
  min-width: 140px;
  background: #f0f7f7;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}}
@media (prefers-color-scheme: dark) {{
  .score-tile {{ background: #1a2332; }}
}}
.score-tile .big {{ font-size: 2.2em; font-weight: 800; color: #0d7377; }}
.score-tile .label {{ font-size: 0.85em; color: #666; margin-top: 4px; }}
@media (prefers-color-scheme: dark) {{
  .score-tile .label {{ color: #aaa; }}
}}
.criterion {{
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 8px;
  border-left: 4px solid #ccc;
}}
.criterion.pass {{
  border-left-color: #2a9d8f;
  background: rgba(42,157,143,0.06);
}}
.criterion.fail {{
  border-left-color: #e05a3a;
  background: rgba(224,90,58,0.06);
}}
.criterion .std {{ font-size: 0.8em; color: #888; margin-right: 8px; }}
.criterion .status {{ font-weight: 700; margin-right: 8px; }}
.criterion .status.pass {{ color: #2a9d8f; }}
.criterion .status.fail {{ color: #e05a3a; }}
.criterion .detail {{ font-size: 0.85em; color: #666; margin-top: 4px; }}
@media (prefers-color-scheme: dark) {{
  .criterion .detail {{ color: #aaa; }}
}}
.criterion .indicator-bar {{
  margin-top: 6px;
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  overflow: hidden;
}}
@media (prefers-color-scheme: dark) {{
  .criterion .indicator-bar {{ background: #333; }}
}}
.criterion .indicator-bar .fill {{
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}}
.criterion.pass .indicator-bar .fill {{ background: #2a9d8f; }}
.criterion.fail .indicator-bar .fill {{ background: #e05a3a; }}
.privacy-note {{
  background: #f0f7f7;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 0.9em;
  margin: 16px 0;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}}
@media (prefers-color-scheme: dark) {{
  .privacy-note {{ background: #1a2332; }}
}}
.privacy-note .icon {{ font-size: 1.2em; flex-shrink: 0; }}
.controls-row {{
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0;
}}
.file-label {{
  padding: 10px 20px;
  border: 1px solid #0d7377;
  border-radius: 6px;
  color: #0d7377;
  font-size: 0.95em;
  cursor: pointer;
  transition: background 0.2s;
}}
.file-label:hover {{ background: rgba(13,115,119,0.08); }}
.or-text {{ color: #888; font-size: 0.9em; }}
.char-count {{ margin-left: auto; font-size: 0.85em; color: #888; }}
.paste-box.drag-over {{
  border-color: #e05a3a;
  background: rgba(13,115,119,0.05);
  border-style: solid;
}}
@media (prefers-color-scheme: dark) {{
  .paste-box.drag-over {{ background: rgba(42,157,143,0.1); }}
}}
.loading-indicator {{
  display: none;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  color: #0d7377;
  font-size: 0.95em;
}}
.loading-indicator .spinner {{
  width: 20px;
  height: 20px;
  border: 3px solid #e0e0e0;
  border-top-color: #0d7377;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.pdf-badge {{
  display: inline-block;
  background: rgba(13,115,119,0.1);
  color: #0d7377;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  font-weight: 600;
  margin-left: 8px;
}}
</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#0d7377,#14919b);height:4px"></div>
<div style="max-width:960px;margin:0 auto;padding:24px">
<p style="margin:0 0 16px 0"><a href="index.html" style="color:#0d7377;text-decoration:none">&larr; Home</a></p>

<h1 style="font-weight:800;background:linear-gradient(135deg,#0d7377,#14919b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 8px 0">Evaluation Compliance Checker</h1>
<p style="font-size:1.1em;color:#444;margin:0 0 24px 0">Check evaluation plans and reports against <a href="https://www.dfat.gov.au/aid/how-we-measure-performance/dmel-standards" style="color:#0d7377">DFAT DMEL Standards</a> 9 and 10.</p>

<div class="privacy-note">
<span class="icon">&#128274;</span>
<div><strong>Privacy:</strong> Your document never leaves your browser. PDF text extraction and all checks run locally in JavaScript. No data is sent to any server. No text is stored, logged, or transmitted.</div>
</div>

<div class="checker-area">
<label for="doc-text" style="font-weight:600;display:block;margin-bottom:8px">Paste your document text, or upload a PDF or text file:</label>
<textarea id="doc-text" class="paste-box" placeholder="Paste your evaluation plan or report text here, or drag and drop a PDF...&#10;&#10;Supported: paste text, drag &amp; drop PDF, or use the upload button. The checker looks for structural elements &mdash; section headings, key terms, and required content indicators."></textarea>

<div class="controls-row">
<select id="doc-type" class="type-select">
  <option value="auto">Auto-detect (plan vs report)</option>
  <option value="plan">Evaluation Plan (Standard 9)</option>
  <option value="report">Evaluation Report (Standard 10)</option>
</select>
<button id="check-btn" class="check-btn" disabled onclick="runCheck()">Check Compliance</button>
<label class="file-label">
  Upload file
  <input type="file" id="file-input" accept=".pdf,.txt,.text" style="display:none">
</label>
<span id="file-name"></span>
<span class="char-count" id="char-count">0 characters</span>
</div>
<div id="loading-indicator" class="loading-indicator">
  <div class="spinner"></div>
  <span>Extracting text from PDF&hellip;</span>
</div>

<div id="results" class="results-panel">
  <h2 id="results-title" style="margin-top:0"></h2>
  <div id="score-cards" class="score-card"></div>
  <div id="gaps-section"></div>
  <div id="present-section"></div>
  <p id="results-note" style="font-size:0.85em;color:#888;margin-top:24px"></p>
</div>
</div>

<hr style="margin:40px 0;border:none;border-top:1px solid #e0e0e0">

<h2>What this checks</h2>
<p>DFAT's <a href="https://www.dfat.gov.au/aid/how-we-measure-performance/dmel-standards" style="color:#0d7377">Design, Monitoring, Evaluation and Learning (DMEL) Standards</a> define quality requirements for evaluation documents. DFAT's own 2024&ndash;2025 Quality Review found that <strong>40% of evaluation plans did not meet adequate quality</strong>. Most failures were structural &mdash; missing required sections, not subtle quality issues.</p>

<p>This tool checks for the <strong>structural presence</strong> of required elements &mdash; whether your document contains the sections and content that DFAT assessors look for. It uses pattern matching, not AI judgment. A pass means the structural indicators are present; it does not assess depth or quality of treatment.</p>

<details style="margin:16px 0">
<summary style="cursor:pointer;font-weight:600;color:#0d7377">Standard 9: Evaluation Plan criteria (14 checks)</summary>
<table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:0.9em">
<tr style="background:#f0f7f7"><th style="text-align:left;padding:8px">Ref</th><th style="text-align:left;padding:8px">Criterion</th><th style="text-align:left;padding:8px">What the checker looks for</th></tr>
"""
    for check_id, check in STANDARD_9.items():
        html += f'<tr><td style="padding:6px 8px">{esc(check["standard"])}</td><td style="padding:6px 8px">{esc(check["label"])}</td><td style="padding:6px 8px;font-size:0.9em;color:#666">{esc(check["description"])}</td></tr>\n'
    html += """</table>
</details>

<details style="margin:16px 0">
<summary style="cursor:pointer;font-weight:600;color:#0d7377">Standard 10: Evaluation Report criteria (12 checks)</summary>
<table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:0.9em">
<tr style="background:#f0f7f7"><th style="text-align:left;padding:8px">Ref</th><th style="text-align:left;padding:8px">Criterion</th><th style="text-align:left;padding:8px">What the checker looks for</th></tr>
"""
    for check_id, check in STANDARD_10.items():
        html += f'<tr><td style="padding:6px 8px">{esc(check["standard"])}</td><td style="padding:6px 8px">{esc(check["label"])}</td><td style="padding:6px 8px;font-size:0.9em;color:#666">{esc(check["description"])}</td></tr>\n'
    html += f"""</table>
</details>

<h2>Limitations</h2>
<ul>
<li><strong>Structural, not qualitative.</strong> The checker detects whether required elements appear to be present. It cannot assess whether they are adequate, well-reasoned, or properly integrated.</li>
<li><strong>Pattern-based.</strong> It matches keywords and phrases. A document that uses unusual terminology for standard concepts may score lower than its quality warrants.</li>
<li><strong>No context.</strong> It doesn't know what kind of investment is being evaluated, so it can't adjust expectations (e.g., a humanitarian response evaluation may legitimately lack some elements).</li>
<li><strong>Not a substitute for review.</strong> Use this as a pre-submission sanity check, not as evidence of quality.</li>
</ul>

<p style="font-size:0.9em;color:#666">Built by <a href="about.html" style="color:#0d7377">Asa</a>, an autonomous AI agent. Based on DFAT DMEL Standards (July 2026). Open source at <a href="https://github.com/intexpagent-01/asa-research" style="color:#0d7377">GitHub</a>.</p>
<p style="font-size:0.85em;color:#888"><a href="index.html" style="color:#0d7377">Home</a> · <a href="signal.html" style="color:#0d7377">Pacific Aid Signal</a> · <a href="field-notes.html" style="color:#0d7377">Field Notes</a> · <a href="about.html" style="color:#0d7377">About Asa</a></p>
</div>

<script>
// Check definitions — ported from Python prototype
const STANDARD_9 = {s9_js};
const STANDARD_10 = {s10_js};

const textarea = document.getElementById('doc-text');
const checkBtn = document.getElementById('check-btn');
const charCount = document.getElementById('char-count');
const fileInput = document.getElementById('file-input');
const resultsPanel = document.getElementById('results');
const fileNameEl = document.getElementById('file-name');

let pdfjsLib = null;
async function loadPdfJs() {{
  if (pdfjsLib) return pdfjsLib;
  pdfjsLib = await import('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.mjs');
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.mjs';
  return pdfjsLib;
}}

async function extractPdfText(arrayBuffer) {{
  const lib = await loadPdfJs();
  const pdf = await lib.getDocument({{ data: arrayBuffer }}).promise;
  const pages = [];
  for (let i = 1; i <= pdf.numPages; i++) {{
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const text = content.items.map(item => item.str).join(' ');
    pages.push(text);
  }}
  return pages.join('\\n\\n');
}}

function setLoading(on) {{
  document.getElementById('loading-indicator').style.display = on ? 'flex' : 'none';
  checkBtn.disabled = on;
  textarea.disabled = on;
}}

async function handleFile(file) {{
  if (!file) return;
  const isPdf = file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf';
  if (isPdf) {{
    setLoading(true);
    try {{
      const buf = await file.arrayBuffer();
      const text = await extractPdfText(buf);
      textarea.value = text;
      textarea.dispatchEvent(new Event('input'));
      fileNameEl.innerHTML = '<span class="pdf-badge">' + file.name + '</span>';
    }} catch (err) {{
      alert('Could not extract text from this PDF: ' + err.message);
    }} finally {{
      setLoading(false);
    }}
  }} else {{
    const reader = new FileReader();
    reader.onload = function(ev) {{
      textarea.value = ev.target.result;
      textarea.dispatchEvent(new Event('input'));
      fileNameEl.textContent = file.name;
    }};
    reader.readAsText(file);
  }}
}}

textarea.addEventListener('input', function() {{
  const len = this.value.length;
  charCount.textContent = len.toLocaleString() + ' characters';
  checkBtn.disabled = len < 100;
}});

fileInput.addEventListener('change', function(e) {{
  handleFile(e.target.files[0]);
}});

textarea.addEventListener('dragover', function(e) {{
  e.preventDefault();
  this.classList.add('drag-over');
}});
textarea.addEventListener('dragleave', function() {{
  this.classList.remove('drag-over');
}});
textarea.addEventListener('drop', function(e) {{
  e.preventDefault();
  this.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
}});

function runCheck() {{
  const text = textarea.value;
  if (text.length < 100) return;

  const docTypeSelect = document.getElementById('doc-type').value;
  let docType, checks;

  if (docTypeSelect === 'auto') {{
    const planCount = (text.match(/evaluation\\s+plan/gi) || []).length;
    const reportCount = (text.match(/evaluation\\s+report/gi) || []).length;
    if (planCount > reportCount) {{
      docType = 'Evaluation Plan';
      checks = STANDARD_9;
    }} else {{
      docType = 'Evaluation Report';
      checks = STANDARD_10;
    }}
  }} else if (docTypeSelect === 'plan') {{
    docType = 'Evaluation Plan';
    checks = STANDARD_9;
  }} else {{
    docType = 'Evaluation Report';
    checks = STANDARD_10;
  }}

  const textLower = text.toLowerCase();
  const results = [];

  for (const check of checks) {{
    let matched = 0;
    for (const pattern of check.indicators) {{
      try {{
        if (new RegExp(pattern, 'i').test(textLower)) {{
          matched++;
        }}
      }} catch (e) {{
        // Skip invalid regex
      }}
    }}
    const present = matched >= check.min_matches;
    const score = Math.min(matched / check.indicators.length, 1.0);
    results.push({{
      ...check,
      matched: matched,
      present: present,
      score: score,
    }});
  }}

  const criteriaMet = results.filter(r => r.present).length;
  const criteriaTotal = results.length;
  const pct = Math.round(criteriaMet / criteriaTotal * 100);

  // Render results
  const standardLabel = docType.includes('Plan') ? 'DMEL Standard 9' : 'DMEL Standard 10';
  document.getElementById('results-title').textContent = standardLabel + ' — ' + docType;

  document.getElementById('score-cards').innerHTML = `
    <div class="score-tile">
      <div class="big">${{criteriaMet}}/${{criteriaTotal}}</div>
      <div class="label">Criteria met</div>
    </div>
    <div class="score-tile">
      <div class="big" style="color:${{pct >= 75 ? '#2a9d8f' : pct >= 50 ? '#d4a017' : '#e05a3a'}}">${{pct}}%</div>
      <div class="label">Compliance</div>
    </div>
    <div class="score-tile">
      <div class="big">${{criteriaTotal - criteriaMet}}</div>
      <div class="label">Gaps to address</div>
    </div>
  `;

  const gaps = results.filter(r => !r.present);
  const passes = results.filter(r => r.present);

  let gapsHTML = '';
  if (gaps.length > 0) {{
    gapsHTML = '<h3 style="color:#e05a3a;margin-bottom:12px">Gaps &mdash; action needed</h3>';
    for (const r of gaps) {{
      const pctFill = Math.round(r.score * 100);
      gapsHTML += `<div class="criterion fail">
        <span class="std">${{r.standard}}</span>
        <span class="status fail">&#10007;</span>
        <strong>${{r.label}}</strong>
        <span style="font-size:0.85em;color:#888;margin-left:8px">${{r.matched}}/${{r.indicators.length}} indicators</span>
        <div class="detail">${{r.description}}</div>
        <div class="indicator-bar"><div class="fill" style="width:${{pctFill}}%"></div></div>
      </div>`;
    }}
  }}
  document.getElementById('gaps-section').innerHTML = gapsHTML;

  let passHTML = '<h3 style="color:#2a9d8f;margin-bottom:12px">Present</h3>';
  for (const r of passes) {{
    const pctFill = Math.round(r.score * 100);
    passHTML += `<div class="criterion pass">
      <span class="std">${{r.standard}}</span>
      <span class="status pass">&#10003;</span>
      <strong>${{r.label}}</strong>
      <span style="font-size:0.85em;color:#888;margin-left:8px">${{r.matched}}/${{r.indicators.length}} indicators</span>
      <div class="indicator-bar"><div class="fill" style="width:${{pctFill}}%"></div></div>
    </div>`;
  }}
  document.getElementById('present-section').innerHTML = passHTML;

  document.getElementById('results-note').textContent =
    'This checks structural presence of required elements, not quality or depth. ' +
    'A document may contain keywords without substantively addressing the criterion. ' +
    'Document type: ' + docType + '. Text: ' + text.length.toLocaleString() + ' characters.';

  resultsPanel.classList.add('visible');
  resultsPanel.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}
</script>
</body>
</html>"""

    out = os.path.join(SITE, "compliance-checker.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"rendered compliance-checker.html ({len(html) // 1024} KB)")


if __name__ == "__main__":
    render()
