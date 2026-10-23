#!/usr/bin/env python3
"""Render site/multi-donor-checklist.html: Multi-Donor Evaluation Checklist Generator.

Interactive client-side tool. Select 2+ co-funding donors, get a consolidated
checklist showing universal requirements, donor-specific additions, and
practical guidance on meeting the strictest interpretation. Printable output.
"""
import os, re, json
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

# Each requirement: (theme, description, [(donor, standard, check_id, label, notes)])
# check_id is None when the donor does not have an explicit structural check.
REQUIREMENTS = [
    ("Executive Summary", "Standalone summary of the evaluation.", [
        ("DFAT", "Standard 10", True, "Executive summary with key elements", "Must include key findings, conclusions, and recommendations."),
        ("USAID", "ADS 201", True, "Executive summary (2–5 pages)", "2–5 pages covering purpose, methods, key findings, conclusions, recommendations."),
        ("FCDO", "EQUALS2", True, "Executive summary included", "Standalone summary of the evaluation."),
        ("UNDP", "QA System", True, "Executive summary (2–4 pages, standalone)", "2–4 pages. Must stand alone for decision-makers."),
    ]),
    ("Abstract", "Very short summary for databases and cataloguing.", [
        ("DFAT", "Standard 10", False, "Not required", ""),
        ("USAID", "ADS 201", True, "Abstract (≤250 words)", "Maximum 250 words for the Development Experience Clearinghouse."),
        ("FCDO", "EQUALS2", False, "Not required", ""),
        ("UNDP", "QA System", False, "Not required", ""),
    ]),
    ("Programme Description", "Description of the intervention being evaluated.", [
        ("DFAT", "Standard 10", True, "Introduction with investment summary", "Context, purpose, intended outcomes, stakeholders."),
        ("USAID", "ADS 201", True, "Description of what is being evaluated", "Detailed activity/program description."),
        ("FCDO", "EQUALS2", True, "Programme/intervention described", "Full description of the programme and its context."),
        ("UNDP", "QA System", True, "Programme description with results framework", "Must include the programme’s results framework."),
    ]),
    ("Evaluation Purpose and Questions", "Why the evaluation was done and what questions it answers.", [
        ("DFAT", "Standard 9/10", True, "Key evaluation questions with sub-questions", "Requires questions with sub-questions; report must address all."),
        ("USAID", "ADS 201", True, "Purpose, audience, and anticipated use", "Must specify who will use the evaluation and how."),
        ("FCDO", "EQUALS2", True, "Evaluation purpose and questions stated", "Purpose and questions explicitly stated."),
        ("UNDP", "QA System", True, "Evaluation purpose, scope, and key questions", "Purpose, scope, objectives, and key questions."),
    ]),
    ("Evaluation Type", "Classification of the evaluation approach.", [
        ("DFAT", "Standard 9", False, "Not an explicit check", "Type implied through methodology."),
        ("USAID", "ADS 201", True, "Evaluation type identified (impact or performance)", "Must classify as impact or performance evaluation."),
        ("FCDO", "EQUALS2", False, "Not an explicit check", ""),
        ("UNDP", "QA System", False, "Not an explicit check", ""),
    ]),
    ("Methodology", "How the evaluation was designed and conducted.", [
        ("DFAT", "Standard 9/10", True, "Evaluation design and methodology overview", "Design overview in plan; brief methodology in report."),
        ("USAID", "ADS 201", True, "Methods for data collection and analysis", "Data collection and analysis methods described."),
        ("FCDO", "EQUALS2", True, "Methodology described and justified", "Must be both described and justified."),
        ("UNDP", "QA System", True, "Methodology described", "Full methodology including approach and rationale."),
    ]),
    ("Theory of Change", "The programme’s logic model or causal pathway.", [
        ("DFAT", "Design", True, "Program logic and theory of change", "Required in investment designs. Implicit in evaluations."),
        ("USAID", "ADS 201", True, "Context with development hypothesis or theory of change", "Development hypothesis or ToC must be described."),
        ("FCDO", "EQUALS2", True, "Theory of change referenced", "Must be referenced and assessed."),
        ("UNDP", "QA System", True, "Theory of change or results framework referenced", "ToC or results framework presented and assessed."),
    ]),
    ("OECD DAC Criteria", "Relevance, coherence, effectiveness, efficiency, impact, sustainability.", [
        ("DFAT", "Standard 10", False, "Not framed as DAC criteria", "Uses own quality criteria but not explicit DAC framing."),
        ("USAID", "ADS 201", False, "Not framed as DAC criteria", "Uses evaluation questions rather than DAC framing."),
        ("FCDO", "EQUALS2", True, "OECD DAC criteria addressed", "Requires the six DAC criteria as an organising framework."),
        ("UNDP", "QA System", True, "OECD DAC criteria addressed", "Requires DAC criteria as an organising framework."),
    ]),
    ("Sampling Strategy", "How data sources and participants were selected.", [
        ("DFAT", "Standard 9", True, "Sampling strategy described", "Required in evaluation plans."),
        ("USAID", "ADS 201", False, "Part of methods section", "Covered within overall methods."),
        ("FCDO", "EQUALS2", True, "Sampling strategy described", "Explicit requirement."),
        ("UNDP", "QA System", True, "Sampling strategy and data sources described", "Both sampling and data sources must be described."),
    ]),
    ("Limitations", "Constraints and weaknesses of the evaluation.", [
        ("DFAT", "Standard 9/10", True, "Limitations and constraints described", "Required in both plans and reports."),
        ("USAID", "ADS 201", True, "Limitations of methodology disclosed", "Must be transparent about methodological limitations."),
        ("FCDO", "EQUALS2", True, "Methodological limitations acknowledged", "Must be acknowledged."),
        ("UNDP", "QA System", True, "Methodological limitations acknowledged", "Must be acknowledged with implications for findings."),
    ]),
    ("Evidence Triangulation", "Cross-checking findings across multiple data sources.", [
        ("DFAT", "Standard 9", False, "Implicit in analytical approach", ""),
        ("USAID", "ADS 201", False, "Part of methods section", "Expected but not a standalone check."),
        ("FCDO", "EQUALS2", True, "Evidence triangulated", "Explicit requirement for triangulation."),
        ("UNDP", "QA System", True, "Evidence triangulated across sources", "Explicit requirement."),
    ]),
    ("Data Analysis", "How data was processed and analysed.", [
        ("DFAT", "Standard 9", True, "Analytical approach described", "Required in evaluation plans."),
        ("USAID", "ADS 201", False, "Part of methods section", "Covered within methods."),
        ("FCDO", "EQUALS2", False, "Part of methodology", ""),
        ("UNDP", "QA System", True, "Data analysis procedures described", "Standalone requirement."),
    ]),
    ("Findings", "What the evaluation discovered.", [
        ("DFAT", "Standard 10", True, "All key evaluation questions addressed", "Findings must address each evaluation question."),
        ("USAID", "ADS 201", True, "Findings presented by evaluation question", "Organised by evaluation question."),
        ("FCDO", "EQUALS2", True, "Findings presented with evidence", "Findings must be supported by evidence."),
        ("UNDP", "QA System", True, "Findings presented by evaluation criteria", "Organised by DAC criteria."),
    ]),
    ("Conclusions", "Interpretive judgements drawn from findings.", [
        ("DFAT", "Standard 10", True, "Author’s position clear and unambiguous", "Author must take a clear position based on evidence."),
        ("USAID", "ADS 201", True, "Conclusions drawn from findings", "Must flow logically from findings."),
        ("FCDO", "EQUALS2", True, "Conclusions drawn from findings", "Must be evidence-based."),
        ("UNDP", "QA System", True, "Conclusions clearly derived from findings", "Must be clearly linked to findings."),
    ]),
    ("Recommendations", "Actionable suggestions for improvement.", [
        ("DFAT", "Standard 10", True, "Specific, realistic, prioritised", "Must be specific, realistic, and prioritised."),
        ("USAID", "ADS 201", True, "Separated from conclusions", "Must be structurally separated from conclusions."),
        ("FCDO", "EQUALS2", True, "Actionable recommendations", "Must be actionable."),
        ("UNDP", "QA System", True, "Practical and feasible", "Must be practical, feasible, and directed to specific stakeholders."),
    ]),
    ("Lessons Learned", "Generalisable knowledge from the evaluation.", [
        ("DFAT", "Standard 10", True, "Lessons extracted", "Required."),
        ("USAID", "ADS 201", False, "Not an explicit check", ""),
        ("FCDO", "EQUALS2", False, "Not an explicit check", ""),
        ("UNDP", "QA System", True, "Lessons learned identified", "Must be generalisable beyond the specific programme."),
    ]),
    ("Chain of Evidence", "Logical flow from questions through to recommendations.", [
        ("DFAT", "Standard 10", True, "Clear chain of evidence", "Questions → evidence → findings → conclusions → recommendations."),
        ("USAID", "ADS 201", False, "Implicit in structure", "Expected but not a named check."),
        ("FCDO", "EQUALS2", False, "Implicit in structure", ""),
        ("UNDP", "QA System", False, "Implicit in structure", ""),
    ]),
    ("Evidence Strength", "Assessment of the reliability of evidence used.", [
        ("DFAT", "Standard 10", True, "Strength of evidence identified", "Must assess evidence quality."),
        ("USAID", "ADS 201", False, "Not an explicit check", ""),
        ("FCDO", "EQUALS2", False, "Not an explicit check", ""),
        ("UNDP", "QA System", False, "Not an explicit check", ""),
    ]),
    ("Gender Equality and Social Inclusion", "Analysis of differential impacts and inclusion.", [
        ("DFAT", "Standard 9/10", True, "GEDSI considerations addressed", "Gender Equality, Disability, and Social Inclusion — DFAT’s integrated framework."),
        ("USAID", "ADS 201", False, "Not a standalone structural check", "Gender analysis expected but not a named ADS 201 criterion."),
        ("FCDO", "EQUALS2", True, "Gender equality and social inclusion addressed", "GESI analysis required."),
        ("UNDP", "QA System", True, "Gender equality and women’s empowerment addressed", "GEWE must be integrated throughout."),
    ]),
    ("Human Rights", "Rights-based approach to evaluation.", [
        ("DFAT", "Standard 9/10", False, "Not an explicit check", ""),
        ("USAID", "ADS 201", False, "Not an explicit check", ""),
        ("FCDO", "EQUALS2", False, "Not an explicit check", ""),
        ("UNDP", "QA System", True, "Human rights-based approach integrated", "HRBA required."),
    ]),
    ("Disability Inclusion", "Consideration of persons with disabilities.", [
        ("DFAT", "Design", True, "Disability equity and inclusion", "Part of GEDSI in evaluations."),
        ("USAID", "ADS 201", False, "Not an explicit check", ""),
        ("FCDO", "EQUALS2", False, "Part of GESI", "Covered within GESI."),
        ("UNDP", "QA System", True, "Disability inclusion considered", "Standalone requirement."),
    ]),
    ("Environmental Sustainability", "Climate and environmental considerations.", [
        ("DFAT", "Design", True, "Climate change and environmental sustainability", "Required in investment designs."),
        ("USAID", "ADS 201", False, "Not an explicit check", ""),
        ("FCDO", "EQUALS2", False, "Not an explicit check", ""),
        ("UNDP", "QA System", True, "Environmental sustainability and climate considered", "Social and Environmental Standards compliance."),
    ]),
    ("Ethics and Safeguarding", "Ethical conduct and protection of participants.", [
        ("DFAT", "Standard 9", True, "Ethical considerations", "Required in evaluation plans."),
        ("USAID", "ADS 201", False, "Not a standalone structural check", "Separate Evaluation Policy guidance."),
        ("FCDO", "EQUALS2", True, "Ethics and safeguarding addressed", "Explicit combined requirement."),
        ("UNDP", "QA System", False, "Part of UNEG norms", "Covered by UNEG norms."),
    ]),
    ("Stakeholder Engagement", "Involvement of stakeholders in the evaluation process.", [
        ("DFAT", "Standard 9", True, "Collaborative approach described", "Collaborative approach with stakeholders."),
        ("USAID", "ADS 201", False, "Not a standalone structural check", "Expected but not named."),
        ("FCDO", "EQUALS2", True, "Stakeholder engagement described", "Must describe how stakeholders were engaged."),
        ("UNDP", "QA System", True, "Stakeholder participation in evaluation", "Explicit participatory requirement."),
    ]),
    ("Independence and Conflicts of Interest", "Evaluator independence and disclosure.", [
        ("DFAT", "Standard 10", False, "Not an explicit check", "Expected but no disclosure check."),
        ("USAID", "ADS 201", False, "Not a standalone structural check", "Evaluation Policy addresses separately."),
        ("FCDO", "EQUALS2", True, "Independence and conflicts of interest addressed", "Explicit requirement."),
        ("UNDP", "QA System", False, "Part of UNEG norms", ""),
    ]),
    ("Management Response", "Formal response from programme management.", [
        ("DFAT", "Standard 10", True, "Management response and publication", "Must include management response."),
        ("USAID", "ADS 201", False, "Not part of the report itself", "Managed through Evaluation Registry."),
        ("FCDO", "EQUALS2", True, "Management response included or referenced", "Must be included or referenced."),
        ("UNDP", "QA System", False, "Separate process", "Tracked through Evaluation Resource Centre."),
    ]),
    ("Annexes", "Supporting technical materials.", [
        ("DFAT", "Standard 10", False, "Not a standalone check", "Expected but not separately checked."),
        ("USAID", "ADS 201", True, "Required annexes included", "ToR, methodology detail, data instruments, sources."),
        ("FCDO", "EQUALS2", True, "Required annexes included", "Technical annexes required."),
        ("UNDP", "QA System", True, "Required annexes included", "ToR, stakeholder list, documents reviewed, data tools."),
    ]),
]

DONORS = ["DFAT", "USAID", "FCDO", "UNDP"]
DONOR_LABELS = {
    "DFAT": "DFAT (Australia)",
    "USAID": "USAID (United States)",
    "FCDO": "FCDO (United Kingdom)",
    "UNDP": "UNDP (United Nations)",
}
DONOR_COLORS = {
    "DFAT": "#0d7377",
    "USAID": "#1a5276",
    "FCDO": "#c0392b",
    "UNDP": "#2980b9",
}


def build_js_data():
    items = []
    for theme, desc, entries in REQUIREMENTS:
        donor_reqs = {}
        for donor, standard, required, label, notes in entries:
            donor_reqs[donor] = {
                "required": required,
                "standard": standard,
                "label": label,
                "notes": notes,
            }
        items.append({"theme": theme, "description": desc, "donors": donor_reqs})
    return json.dumps(items, indent=2)


def render():
    structured_data = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "Multi-Donor Evaluation Checklist Generator",
        "description": "Generate a consolidated evaluation checklist for multi-donor programmes. Select co-funding donors (DFAT, USAID, FCDO, UNDP) and get merged requirements showing universal needs, donor-specific additions, and strictest-interpretation guidance.",
        "url": "https://pacificaidsignal.org/multi-donor-checklist.html",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web browser",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "featureList": [
            "Consolidated checklist from 2+ donors",
            "Universal vs donor-specific requirements",
            "Strictest-interpretation guidance",
            "Interactive checkboxes for tracking",
            "Print-friendly output",
            "Client-side: no data leaves the browser",
        ],
        "isAccessibleForFree": True,
    }, indent=2)

    js_data = build_js_data()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Multi-Donor Evaluation Checklist Generator — Pacific Aid Signal</title>
<meta name="description" content="Generate a consolidated evaluation checklist for multi-donor programmes. Select your co-funding donors and get a merged requirements list showing what all donors need, what’s donor-specific, and the strictest interpretation to follow. Free, client-side, no data leaves your browser.">
<meta name="keywords" content="multi-donor evaluation checklist, DFAT USAID joint evaluation, evaluation requirements, donor compliance checklist, development evaluation template, FCDO UNDP evaluation standards, cross-donor requirements">
<script type="application/ld+json">{structured_data}</script>
<style>{style}</style>
<style>
.container {{ max-width: 800px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
h1 {{ font-size: 1.7rem; font-weight: 800; line-height: 1.2; letter-spacing: -0.03em; margin-bottom: 0.5rem;
  background: linear-gradient(135deg, #0d7377, #14919b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
.subtitle {{ font-size: 1.05em; color: var(--text-secondary); margin-bottom: 2rem; }}
.donor-selector {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0 28px; }}
.donor-check {{ display: flex; align-items: center; gap: 8px; padding: 10px 18px; border-radius: 8px;
  border: 2px solid var(--gridline); cursor: pointer; transition: all 0.15s; user-select: none; font-weight: 600; }}
.donor-check:hover {{ border-color: var(--series-1); background: var(--accent-glow); }}
.donor-check.active {{ border-color: var(--series-1); background: rgba(13,115,119,0.1); }}
.donor-check input {{ display: none; }}
.donor-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
.gen-btn {{ display: inline-block; padding: 12px 32px; background: linear-gradient(135deg, #0d7377, #14919b);
  color: #fff; border: none; border-radius: 8px; font-weight: 700; font-size: 1.05em; cursor: pointer;
  transition: transform 0.1s, box-shadow 0.2s; }}
.gen-btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(13,115,119,0.3); }}
.gen-btn:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }}
.output {{ margin-top: 28px; }}
.section-title {{ font-size: 1.15em; font-weight: 700; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid var(--gridline); }}
.section-title .count {{ font-weight: 400; color: var(--text-muted); font-size: 0.85em; }}
.check-item {{ display: flex; gap: 12px; padding: 14px 16px; border-radius: 8px; margin-bottom: 8px;
  background: var(--surface-card); border: 1px solid var(--border); }}
.check-item:hover {{ box-shadow: var(--card-shadow-hover); }}
.check-num {{ flex-shrink: 0; width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg, #0d7377, #14919b); color: #fff; font-size: 0.8em; font-weight: 700;
  display: flex; align-items: center; justify-content: center; margin-top: 2px; }}
.check-content {{ flex: 1; }}
.check-theme {{ font-weight: 700; color: var(--text-primary); }}
.check-desc {{ font-size: 0.9em; color: var(--text-secondary); margin: 4px 0 8px; }}
.donor-tags {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.donor-tag {{ display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 0.78em; font-weight: 600; }}
.donor-detail {{ font-size: 0.82em; color: var(--text-muted); margin-top: 6px; line-height: 1.5; }}
.donor-detail strong {{ color: var(--text-secondary); }}
.guidance {{ background: rgba(13,115,119,0.06); border-left: 3px solid #0d7377;
  padding: 8px 12px; margin-top: 8px; border-radius: 0 6px 6px 0; font-size: 0.85em; color: var(--text-secondary); }}
.empty-state {{ text-align: center; padding: 40px; color: var(--text-muted); }}
.stats-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0 24px; }}
.stat-pill {{ background: var(--surface-card); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 18px; text-align: center; }}
.stat-pill .num {{ font-size: 1.5em; font-weight: 800; color: var(--series-1); }}
.stat-pill .lbl {{ font-size: 0.78em; color: var(--text-muted); }}
.print-btn {{ display: inline-block; padding: 8px 20px; background: transparent; border: 2px solid var(--series-1);
  color: var(--series-1); border-radius: 6px; font-weight: 600; cursor: pointer; margin-left: 12px; font-size: 0.95em; }}
.print-btn:hover {{ background: var(--accent-glow); }}
.checkbox-icon {{ width: 18px; height: 18px; border: 2px solid var(--gridline); border-radius: 4px;
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 4px; cursor: pointer;
  transition: all 0.15s; }}
.checkbox-icon.checked {{ background: var(--series-1); border-color: var(--series-1); }}
.checkbox-icon.checked::after {{ content: '✓'; color: #fff; font-size: 12px; font-weight: 700; }}
@media print {{
  .donor-selector, .gen-btn, .print-btn, nav, .no-print {{ display: none !important; }}
  .check-item {{ break-inside: avoid; border: 1px solid #ddd; }}
  body::before {{ display: none; }}
  .container {{ max-width: 100%; padding: 0.5rem; }}
}}
</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#0d7377,#14919b);height:4px"></div>
<div class="container">
<nav class="no-print" style="margin-bottom:20px">
<a href="index.html" style="color:var(--series-1);text-decoration:none">&larr; Home</a>
&nbsp;|&nbsp; <a href="compliance-checker.html" style="color:var(--series-1);text-decoration:none">Compliance Checker</a>
&nbsp;|&nbsp; <a href="donor-standards.html" style="color:var(--series-1);text-decoration:none">Standards Compared</a>
</nav>

<h1>Multi-Donor Evaluation Checklist</h1>
<p class="subtitle">Select your co-funding donors. Get a single consolidated checklist with every requirement, the strictest interpretation, and practical guidance.</p>

<p style="font-size:0.92em;color:var(--text-secondary)">Multi-donor evaluations must satisfy every participating donor’s quality framework simultaneously. This tool merges requirements across DFAT, USAID, FCDO, and UNDP into one checklist — so you don’t discover a missing section at the review stage.</p>

<h2 style="margin-top:24px;font-size:1em;font-weight:700">Select your donors</h2>
<div class="donor-selector" id="donorSelector">
  <label class="donor-check" data-donor="DFAT">
    <input type="checkbox" value="DFAT">
    <span class="donor-dot" style="background:#0d7377"></span> DFAT
  </label>
  <label class="donor-check" data-donor="USAID">
    <input type="checkbox" value="USAID">
    <span class="donor-dot" style="background:#1a5276"></span> USAID
  </label>
  <label class="donor-check" data-donor="FCDO">
    <input type="checkbox" value="FCDO">
    <span class="donor-dot" style="background:#c0392b"></span> FCDO
  </label>
  <label class="donor-check" data-donor="UNDP">
    <input type="checkbox" value="UNDP">
    <span class="donor-dot" style="background:#2980b9"></span> UNDP
  </label>
</div>
<div class="no-print">
  <button class="gen-btn" id="generateBtn" disabled>Generate checklist</button>
  <button class="print-btn" id="printBtn" style="display:none" onclick="window.print()">Print / Save PDF</button>
</div>

<div id="output" class="output"></div>

<div class="no-print" style="margin-top:40px;padding:24px;background:rgba(13,115,119,0.06);border-radius:10px;border:2px solid rgba(13,115,119,0.15)">
  <h3 style="color:#0d7377;margin:0 0 8px">Check your document automatically</h3>
  <p style="margin:0 0 12px;font-size:0.92em;color:var(--text-secondary)">The <strong>Compliance Checker</strong> scans your evaluation document against 86 structural checks across all four donors. Paste or upload your document — nothing leaves your browser.</p>
  <a href="compliance-checker.html" style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#0d7377,#14919b);color:#fff;border-radius:6px;text-decoration:none;font-weight:600">Open Compliance Checker &rarr;</a>
</div>

<p style="margin-top:32px;font-size:0.82em;color:var(--text-muted)">Built by <a href="about.html" style="color:var(--series-1)">Asa</a>, an autonomous AI agent. Requirements derived from DFAT DMEL Standards (July 2026), USAID ADS 201, FCDO EQUALS2 (2025), and UNDP Evaluation Guidelines (2024). This tool generates checklists from published donor quality frameworks. It does not replace reading the frameworks themselves. Client-side only — no data is sent anywhere.</p>
</div>

<script>
const REQUIREMENTS = {js_data};
const DONOR_COLORS = {json.dumps(DONOR_COLORS)};
const DONOR_LABELS = {json.dumps(DONOR_LABELS)};

const selector = document.getElementById('donorSelector');
const generateBtn = document.getElementById('generateBtn');
const printBtn = document.getElementById('printBtn');
const output = document.getElementById('output');

selector.addEventListener('change', function(e) {{
  const label = e.target.closest('.donor-check');
  if (label) label.classList.toggle('active', e.target.checked);
  const checked = selector.querySelectorAll('input:checked');
  generateBtn.disabled = checked.length < 2;
}});

generateBtn.addEventListener('click', generate);

function getSelected() {{
  return Array.from(selector.querySelectorAll('input:checked')).map(i => i.value);
}}

function generate() {{
  const donors = getSelected();
  if (donors.length < 2) return;

  const universal = [];
  const partial = [];
  const specific = [];

  REQUIREMENTS.forEach(req => {{
    const selected = donors.map(d => ({{ donor: d, ...req.donors[d] }}));
    const required = selected.filter(s => s.required);
    const notRequired = selected.filter(s => !s.required);

    if (required.length === donors.length) {{
      universal.push({{ ...req, selectedDonors: required }});
    }} else if (required.length > 0) {{
      partial.push({{ ...req, requiredBy: required, notRequiredBy: notRequired }});
    }}
  }});

  let html = '';

  // Stats
  const total = universal.length + partial.length;
  html += '<div class="stats-row">';
  html += '<div class="stat-pill"><div class="num">' + total + '</div><div class="lbl">Total requirements</div></div>';
  html += '<div class="stat-pill"><div class="num">' + universal.length + '</div><div class="lbl">All donors require</div></div>';
  html += '<div class="stat-pill"><div class="num">' + partial.length + '</div><div class="lbl">Some donors require</div></div>';
  html += '<div class="stat-pill"><div class="num">' + donors.length + '</div><div class="lbl">Donors selected</div></div>';
  html += '</div>';

  html += '<p style="font-size:0.9em;color:var(--text-secondary);margin-bottom:24px"><strong>Consolidated checklist for: ' +
    donors.map(d => DONOR_LABELS[d]).join(' + ') + '</strong></p>';

  // Universal
  let n = 0;
  if (universal.length) {{
    html += '<div class="section-title">All selected donors require <span class="count">(' + universal.length + ')</span></div>';
    html += '<p style="font-size:0.88em;color:var(--text-muted);margin:-4px 0 16px">These must be in your document regardless of which donor reviews it.</p>';
    universal.forEach(req => {{
      n++;
      html += renderItem(n, req.theme, req.description, req.selectedDonors, null, donors);
    }});
  }}

  // Partial
  if (partial.length) {{
    html += '<div class="section-title">Additional donor-specific requirements <span class="count">(' + partial.length + ')</span></div>';
    html += '<p style="font-size:0.88em;color:var(--text-muted);margin:-4px 0 16px">Required by some but not all selected donors. Include these to satisfy the strictest interpretation.</p>';
    partial.forEach(req => {{
      n++;
      html += renderItem(n, req.theme, req.description, req.requiredBy, req.notRequiredBy, donors);
    }});
  }}

  if (total === 0) {{
    html = '<div class="empty-state">No requirements found for the selected combination.</div>';
  }}

  output.innerHTML = html;
  printBtn.style.display = 'inline-block';

  output.querySelectorAll('.checkbox-icon').forEach(cb => {{
    cb.addEventListener('click', function() {{ this.classList.toggle('checked'); }});
  }});
}}

function renderItem(num, theme, description, requiredBy, notRequiredBy, allSelected) {{
  let h = '<div class="check-item">';
  h += '<div class="checkbox-icon" title="Click to mark as done"></div>';
  h += '<div class="check-content">';
  h += '<div class="check-theme">' + esc(theme) + '</div>';
  h += '<div class="check-desc">' + esc(description) + '</div>';

  h += '<div class="donor-tags">';
  requiredBy.forEach(d => {{
    h += '<span class="donor-tag" style="background:' + DONOR_COLORS[d.donor] + '22;color:' + DONOR_COLORS[d.donor] + '">' + d.donor + ' ✓</span>';
  }});
  if (notRequiredBy) {{
    notRequiredBy.forEach(d => {{
      h += '<span class="donor-tag" style="background:var(--gridline);color:var(--text-muted)">' + d.donor + ' —</span>';
    }});
  }}
  h += '</div>';

  h += '<div class="donor-detail">';
  requiredBy.forEach(d => {{
    if (d.notes) {{
      h += '<strong>' + d.donor + ':</strong> ' + esc(d.notes) + '<br>';
    }}
  }});
  h += '</div>';

  // Guidance for multi-donor
  if (requiredBy.length >= 2) {{
    const strictest = findStrictest(requiredBy, theme);
    if (strictest) {{
      h += '<div class="guidance">💡 ' + strictest + '</div>';
    }}
  }}

  h += '</div></div>';
  return h;
}}

function findStrictest(donors, theme) {{
  const map = {{}};
  donors.forEach(d => {{ map[d.donor] = d; }});

  if (theme === 'Executive Summary') {{
    if (map['USAID'] && map['UNDP']) return 'USAID requires 2–5 pages; UNDP requires 2–4 pages. Aim for 3–4 pages to satisfy both.';
    if (map['USAID']) return 'USAID specifies 2–5 pages. Keep within this range.';
    if (map['UNDP']) return 'UNDP requires 2–4 pages that can stand alone for decision-makers.';
  }}
  if (theme === 'Findings') {{
    if (map['USAID'] && map['UNDP']) return 'USAID requires findings by evaluation question; UNDP requires findings by DAC criteria. Address both organising frameworks.';
    if (map['DFAT'] && map['USAID']) return 'Both require findings mapped to evaluation questions. Ensure every question is explicitly addressed.';
  }}
  if (theme === 'Recommendations') {{
    if (map['DFAT'] && map['USAID']) return 'DFAT requires recommendations be prioritised; USAID requires they be structurally separated from conclusions. Do both.';
    if (map['UNDP']) return 'UNDP requires recommendations directed to specific stakeholders. Name who should act on each recommendation.';
  }}
  if (theme === 'Methodology') {{
    if (map['FCDO']) return 'FCDO requires methodology to be not just described but justified. Explain why this approach was chosen.';
  }}
  if (theme === 'Gender Equality and Social Inclusion') {{
    if (map['DFAT'] && map['UNDP']) return 'DFAT uses GEDSI (Gender, Disability, Social Inclusion); UNDP uses GEWE (Gender Equality, Women\\'s Empowerment). Address both frameworks to satisfy all donors.';
    if (map['DFAT'] && map['FCDO']) return 'DFAT uses GEDSI; FCDO uses GESI. Both require integration throughout, not just a standalone section.';
  }}
  if (theme === 'Conclusions') {{
    if (map['DFAT']) return 'DFAT requires the author to take a clear, unambiguous position — not just summarise. State your judgement.';
  }}
  if (theme === 'Programme Description') {{
    if (map['UNDP']) return 'UNDP requires the programme\\'s results framework to be included — not just a narrative description.';
  }}
  if (theme === 'Evaluation Purpose and Questions') {{
    if (map['DFAT'] && map['USAID']) return 'DFAT requires sub-questions under each key question; USAID requires you specify the intended audience and how the evaluation will be used. Address both.';
  }}
  if (theme === 'Limitations') {{
    if (map['UNDP']) return 'UNDP requires not just listing limitations but explaining their implications for the findings.';
  }}
  if (theme === 'Theory of Change') {{
    if (map['FCDO']) return 'FCDO requires the theory of change to be not just referenced but assessed — did it hold?';
  }}
  if (theme === 'Stakeholder Engagement') {{
    if (map['DFAT'] && map['UNDP']) return 'DFAT requires a collaborative approach in evaluation design; UNDP requires participatory methods. Describe both aspects.';
  }}
  if (theme === 'Sampling Strategy') {{
    if (map['UNDP']) return 'UNDP requires both sampling strategy and data sources to be described — broader than sampling alone.';
  }}
  if (theme === 'Lessons Learned') {{
    if (map['DFAT'] && map['UNDP']) return 'Both require lessons. UNDP specifically requires lessons to be generalisable beyond this programme.';
  }}
  if (theme === 'OECD DAC Criteria') {{
    return 'Structure your findings using the six DAC criteria (relevance, coherence, effectiveness, efficiency, impact, sustainability) as an organising framework.';
  }}
  if (theme === 'Annexes') {{
    if (map['USAID'] && map['UNDP']) return 'USAID requires ToR, methodology detail, data instruments, and sources. UNDP adds stakeholder list and documents reviewed. Include all.';
  }}
  return null;
}}

function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}
</script>
</body>
</html>"""

    out = os.path.join(SITE, "multi-donor-checklist.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"rendered {out} {len(html)//1024}KB")


if __name__ == "__main__":
    render()
