#!/usr/bin/env python3
"""
DFAT DMEL Compliance Checker — Prototype (Wake 179, updated Wake 181)

Structural presence/absence checker for DFAT evaluation documents
against DMEL Standards 9 (Evaluation Plans) and 10 (Evaluation Reports).

No model calls. Deterministic. Same design philosophy as the Signal.

Wake 180: Fixed word-boundary bugs on stems (methodolog, triangulat, etc.)
and broadened indicators after testing on real DFAT evaluation reports
(Team Up MTR, Pacific Fiscal Budget Support).

Wake 181: Systematic fix of plural word-boundary bugs (question/questions,
finding/findings, outcome/outcomes, etc.). Added flexible timeframe
patterns. Fixed purpose-of-evaluation regex. Web tool built.

Input: text content of a development evaluation document
Output: compliance scorecard showing which required elements are present/absent
"""

import re
import sys
import json
from collections import OrderedDict


# ── DFAT DMEL Standard 9: Evaluation Plan Requirements ──────────────────

STANDARD_9_CHECKS = OrderedDict([
    ("collaborative_approach", {
        "label": "Collaborative approach described",
        "standard": "9.1",
        "description": "Evaluator consulted DFAT and stakeholders; stakeholders had opportunity to comment on the plan",
        "indicators": [
            r"\bconsult(?:ation|ed|ing)\b",
            r"\bstakeholder\s+(?:engagement|consultation|input|feedback|participation)\b",
            r"\bcollaborat(?:ive|ion|ed|ing)\b",
            r"\bpartner\s+government\b",
            r"\bbeneficiar(?:y|ies)\b",
            r"\bparticipat(?:ory|ion|ing|ed)\b",
        ],
        "min_matches": 2,
    }),
    ("program_description", {
        "label": "Program/investment described with purpose and users",
        "standard": "9.2",
        "description": "Brief summary of investment, EOPOs, timeframe, budget, location, problems/opportunities",
        "indicators": [
            r"\b(?:end.of.(?:program|investment)\s+outcomes?|EOPOs?)\b",
            r"\btimeframe\b|\byear\s+(?:of|plan)\b|\bduration\b|\bperiod\s+of\s+(?:the\s+)?(?:investment|program)\b|\b\d+[- ]year\b|\bover\s+(?:a\s+)?\d+\s+years?\b",
            r"\bbudget\b|\btotal\s+value\b|\b(?:AUD|USD)\s*\$?\s*\d+\b|\bmillion\b",
            r"\bpurpose\s+of\s+(?:the\s+|this\s+)?(?:evaluation|review)\b|\b(?:evaluation|review)\s+purpose\b",
            r"\bprimary\s+(?:intended\s+)?users?\b|\bintended\s+audience\b",
        ],
        "min_matches": 3,
    }),
    ("methodology_overview", {
        "label": "Evaluation design and methodology overview",
        "standard": "9.3",
        "description": "Short paragraph orienting reader to overall evaluation design — exploratory/descriptive/causal, major methods",
        "indicators": [
            r"\bevaluation\s+design\b|\b(?:review|evaluation)\s+approach\b",
            r"\bmethodolog(?:y|ical|ies)\b",
            r"\bqualitative\b|\bquantitative\b|\bmixed.method\b",
            r"\bcase\s+stud(?:y|ies)\b",
            r"\bdata\s+collection\b",
            r"\binterview\b|\bfocus\s+group\b|\bsurvey\b|\bdocument\s+review\b|\bsite\s+visit\b",
        ],
        "min_matches": 3,
    }),
    ("limitations", {
        "label": "Limitations and constraints described",
        "standard": "9.4",
        "description": "Known shortcomings impacting scope and confidence; not generic; includes implications",
        "indicators": [
            r"\blimitation(?:s)?\b",
            r"\bconstraint(?:s)?\b",
            r"\b(?:time|resource|data)\s+(?:limitation|constraint|availability)\b",
            r"\bpolitical\s+sensitiv(?:e|ity|ities)\b",
            r"\bcaveat\b|\bshortcoming\b",
        ],
        "min_matches": 2,
    }),
    ("evaluation_questions", {
        "label": "Key evaluation questions with sub-questions",
        "standard": "9.5",
        "description": "Key evaluation questions refined with sub-questions; mutual understanding with DFAT",
        "indicators": [
            r"\b(?:key\s+)?(?:evaluation|review)\s+question(?:s)?\b",
            r"\bsub.question\b",
            r"\b(?:KEQ|EQ|RQ)\s*\d\b",
            r"\binformation\s+requirement\b",
            r"\bGEDSI\b|\bgender\s+equality\b.*\bquestion\b",
        ],
        "min_matches": 2,
    }),
    ("priority_questions", {
        "label": "Priority questions identified",
        "standard": "9.6",
        "description": "Clear which questions are higher priority; emphasis reflected in plan",
        "indicators": [
            r"\bpriori(?:ty|ties|tise|tised)\b.*\bquestion\b",
            r"\bmost\s+important\s+(?:information|questions?)\b",
            r"\bemphasis\b.*\bquestions?\b",
            r"\bhigh(?:er|est)?\s+priority\b",
        ],
        "min_matches": 1,
    }),
    ("flexibility", {
        "label": "Flexibility for unexpected issues",
        "standard": "9.7",
        "description": "Plan allows room to explore emergent issues; built into questioning or schedule",
        "indicators": [
            r"\bflexibi?l(?:e|ity)\b",
            r"\bemergent\s+issue\b",
            r"\bunexpected\b.*\b(?:issues?|findings?)\b",
            r"\badaptiv(?:e|ely)\b",
        ],
        "min_matches": 1,
    }),
    ("methods_per_question", {
        "label": "Data collection methods linked to questions",
        "standard": "9.8",
        "description": "Methods described for each question; not summary statements unlinked to questions",
        "indicators": [
            r"\bevaluation\s+matrix\b",
            r"\bmethod(?:s|ology)?\b.*\bquestion\b|\bquestion\b.*\bmethod(?:s|ology)?\b",
            r"\binterview\s+(?:guide|protocol|schedule)\b|\bsurvey\s+instrument\b|\bquestionnaire\b",
            r"\bdata\s+collection\s+method(?:s|ology)?\b",
            r"\bmonitoring\s+data\b",
        ],
        "min_matches": 2,
    }),
    ("sampling", {
        "label": "Sampling strategy described",
        "standard": "9.9",
        "description": "Clear sampling rationale; sufficient for credible, defensible findings",
        "indicators": [
            r"\bsampl(?:e|ing)\b",
            r"\bpurposive\b|\brandom(?:ly|ised)?\b|\bstratified\b|\bsnowball\b",
            r"\bselection\s+criteria\b",
            r"\brepresentativ(?:e|eness)\b",
            r"\brespondent(?:s)?\b",
        ],
        "min_matches": 2,
    }),
    ("analytical_approach", {
        "label": "Analytical approach described",
        "standard": "9.10",
        "description": "How data will be analysed; triangulation approach clear",
        "indicators": [
            r"\banalys(?:is|e|ed|ing|tical)\b.*\bapproach\b|\bapproach\b.*\banalys(?:is|e|ed|ing)\b",
            r"\btriangulat(?:e|ion|ed|ing)\b",
            r"\bthematic\s+analysis\b|\bcontent\s+analysis\b|\bcoding\b",
            r"\bdata\s+analys(?:is|ed)\b",
        ],
        "min_matches": 2,
    }),
    ("gedsi", {
        "label": "GEDSI considerations addressed",
        "standard": "9.11",
        "description": "Gender equality, disability, social inclusion integrated into methods and analysis",
        "indicators": [
            r"\bGEDSI\b",
            r"\bgender\s+equality\b",
            r"\bdisability\b.*\binclusi(?:on|ve)\b|\binclusi(?:on|ve)\b.*\bdisability\b",
            r"\bsocial\s+inclusion\b",
            r"\bmarginali[sz](?:ed|ation)\b",
            r"\bsex.disaggregat(?:e|ed|ion)\b",
            r"\bwomen\b.*\bgirl\b|\bgirl\b.*\bwomen\b",
        ],
        "min_matches": 2,
    }),
    ("ethics", {
        "label": "Ethical considerations",
        "standard": "9.12",
        "description": "Ethical approach to data collection; safety of respondents; informed consent",
        "indicators": [
            r"\bethic(?:s|al)\b",
            r"\binformed\s+consent\b",
            r"\bconfidentialit(?:y|ies)\b",
            r"\bsafety\b.*\b(?:respondent|participant)\b|\b(?:respondent|participant)\b.*\bsafety\b",
            r"\bdo\s+no\s+harm\b",
            r"\bsafeguard(?:s|ing)?\b",
        ],
        "min_matches": 2,
    }),
    ("schedule", {
        "label": "Schedule and timeline provided",
        "standard": "9.13",
        "description": "Workplan with dates and milestones; data collection schedule",
        "indicators": [
            r"\bschedule\b|\btimeline\b|\bworkplan\b|\bwork\s+plan\b",
            r"\bmilestone(?:s)?\b",
            r"\bdeliverabl(?:e|es)\b",
            r"\b(?:inception|draft|final)\s+report\b",
            r"\bfield\s*(?:work|visit|mission)\b",
        ],
        "min_matches": 2,
    }),
    ("quality_assurance", {
        "label": "Quality assurance approach",
        "standard": "9.14",
        "description": "How quality will be maintained; peer review; internal QA processes",
        "indicators": [
            r"\bquality\s+assurance\b|\bQA\b",
            r"\bpeer\s+review\b",
            r"\binternal\s+review\b",
            r"\bquality\s+control\b",
        ],
        "min_matches": 1,
    }),
])


# ── DFAT DMEL Standard 10: Evaluation Report Requirements ───────────────

STANDARD_10_CHECKS = OrderedDict([
    ("executive_summary", {
        "label": "Executive summary with key elements",
        "standard": "10.1",
        "description": "Key findings, analysis, recommendations, GEDSI info, resource implications; proportionate length",
        "indicators": [
            r"\bexecutive\s+summary\b|\bsummary\s+of\s+(?:key\s+)?findings\b",
            r"\bkey\s+finding(?:s)?\b|\bmain\s+finding(?:s)?\b",
            r"\brecommendation(?:s)?\b.*\bsummar(?:y|ise|ised)\b|\bsummar(?:y|ise)\b.*\brecommendation\b",
            r"\boverview\b",
        ],
        "min_matches": 2,
    }),
    ("introduction", {
        "label": "Introduction with investment summary",
        "standard": "10.2",
        "description": "Total value, years, stage, delivery mechanism, key outcomes, key issues from ToR",
        "indicators": [
            r"\bintroduction\b|\bbackground\b",
            r"\btotal\s+value\b|\b(?:AUD|USD)\s*\$?\s*\d+\b|\bmillion\b",
            r"\bdelivery\s+mechanism\b|\bimplementing\s+partner\b|\bmanaging\s+contractor\b",
            r"\b(?:terms?\s+of\s+reference|ToR)\b",
        ],
        "min_matches": 2,
    }),
    ("methodology_summary", {
        "label": "Brief methodology summary",
        "standard": "10.3",
        "description": "Summary of significant methodological features; evidentiary basis convincing",
        "indicators": [
            r"\bmethodolog(?:y|ical|ies)\b|\bapproach\s+and\s+method\b",
            r"\bevidence\s+base\b|\bevidentiary\s+basis\b",
            r"\bdata\s+collect(?:ion|ed)\b",
            r"\binterview(?:s|ed|ee)?\b",
            r"\bfocus\s+group\b|\bFGD\b|\bgroup\s+discussion\b",
            r"\bsurvey\b|\bdocument(?:ary)?\s+review\b|\bsite\s+visit\b",
        ],
        "min_matches": 2,
    }),
    ("limitations_report", {
        "label": "Key limitations described",
        "standard": "10.4",
        "description": "Limitations at front of report; guidance where reader should be cautious about findings",
        "indicators": [
            r"\blimitation(?:s)?\b",
            r"\bcaution\b|\bcautious(?:ly)?\b|\bcaveat\b",
            r"\bconfidence\b.*\bfinding\b|\bfinding\b.*\bconfidence\b",
            r"\bstrength\s+of\s+(?:the\s+)?evidence\b",
            r"\bshortcoming(?:s)?\b|\bweakness(?:es)?\b",
        ],
        "min_matches": 2,
    }),
    ("questions_addressed", {
        "label": "All key evaluation questions addressed",
        "standard": "10.5",
        "description": "Easy to identify where each question is addressed; gaps explained",
        "indicators": [
            r"\b(?:key\s+)?(?:evaluation|review)\s+question(?:s)?\b",
            r"\b(?:KEQ|EQ|RQ)\s*\d\b",
            r"\bfindings?\b.*\bquestions?\b|\bquestions?\b.*\bfindings?\b",
            r"\bagainst\s+(?:the\s+)?(?:evaluation|review)\s+(?:criteria|framework|questions?)\b",
        ],
        "min_matches": 2,
    }),
    ("author_position", {
        "label": "Author's position clear and unambiguous",
        "standard": "10.6",
        "description": "Evaluator states position clearly; not just findings for DFAT to interpret",
        "indicators": [
            r"\b(?:we|the\s+(?:review|evaluation)\s+team)\s+(?:find|found|conclude|assess|judge|consider|recommend|note)\b",
            r"\bprofessional\s+judg(?:e)?ment\b",
            r"\bin\s+(?:our|the\s+team'?s?)\s+(?:view|assessment|judgement|opinion)\b",
            r"\boverall\s+(?:assessment|findings?|conclusions?)\b|\bon\s+balance\b",
            r"\bthe\s+(?:evaluation|review)\s+(?:finds|found|concludes|concluded|assessed|determined)\b",
        ],
        "min_matches": 1,
    }),
    ("chain_of_evidence", {
        "label": "Clear chain of evidence (questions->evidence->findings->conclusions->recommendations)",
        "standard": "10.7",
        "description": "Readers can trace from data through analysis to findings to conclusions to recommendations",
        "indicators": [
            r"\bchain\s+of\s+evidence\b|\bevidence.based\b",
            r"\bfindings?\b.*\bconclusions?\b",
            r"\bconclusions?\b.*\brecommendations?\b",
            r"\bevidence\b.*\b(?:support|suggest|indicate|show|demonstrate)\b",
            r"\banalysis\b.*\b(?:findings?|reveals?|shows?|indicates?)\b",
        ],
        "min_matches": 2,
    }),
    ("evidence_strength", {
        "label": "Strength of evidence identified",
        "standard": "10.8",
        "description": "Degree to which views are shared; strong vs weak evidence distinguished",
        "indicators": [
            r"\bstrength\s+of\s+(?:the\s+)?evidence\b|\bevidence\s+(?:base|quality|strength)\b",
            r"\bstrong(?:ly)?\s+(?:evidence|support|suggest|indicate)\b|\bweak\s+evidence\b",
            r"\btriangulat(?:e|ion|ed|ing)\b",
            r"\bvalidat(?:e|ed|ion|ing)\b",
            r"\brobust(?:ness)?\b|\bsuggestive\b|\bindicative\b|\bconclusive\b",
        ],
        "min_matches": 2,
    }),
    ("gender_findings", {
        "label": "Gender equality and social inclusion findings",
        "standard": "10.9",
        "description": "GEDSI results reported; unintended gender outcomes explored",
        "indicators": [
            r"\bgender\s+equality\b|\bgender\s+(?:outcomes?|results?|findings?|impacts?|analysis)\b",
            r"\bGEDSI\b",
            r"\bwomen(?:'s)?\b.*\b(?:participation|empowerment|outcomes?|impacts?)\b",
            r"\bdisability\b.*\binclusi(?:on|ve)\b",
            r"\bsex.disaggregat(?:e|ed|ion)\b",
            r"\bsocial\s+inclusion\b",
        ],
        "min_matches": 2,
    }),
    ("recommendations", {
        "label": "Recommendations specific, realistic, prioritised",
        "standard": "10.10",
        "description": "Directed to specific actors; achievable; prioritised; resource implications noted",
        "indicators": [
            r"\brecommendation(?:s)?\b",
            r"\bpriori(?:ty|ties|tise|tised)\b.*\brecommendations?\b|\brecommendations?\b.*\bpriori\b",
            r"\b(?:DFAT|partner|government|ministry)\s+should\b",
            r"\bresource\s+implication(?:s)?\b",
            r"\brecommendation\s+\d\b|\brecommend(?:s|ed)?\s+that\b",
        ],
        "min_matches": 2,
    }),
    ("lessons", {
        "label": "Lessons extracted",
        "standard": "10.11",
        "description": "Lessons learned clearly articulated; distinguish from recommendations",
        "indicators": [
            r"\blesson(?:s)?\s+(?:learn(?:ed|t)|identif|extract)\b",
            r"\blessons?\b",
            r"\blearn(?:ed|t|ing)\b.*\bfuture\b|\bfuture\b.*\blearn\b",
            r"\bkey\s+lessons?\b|\bimportant\s+lessons?\b",
        ],
        "min_matches": 2,
    }),
    ("management_response", {
        "label": "Management response and publication",
        "standard": "10.12",
        "description": "Management response included or referenced; publication plan clear",
        "indicators": [
            r"\bmanagement\s+response\b",
            r"\bpubli(?:sh|cation|shed)\b.*\breport\b|\breport\b.*\bpubli(?:sh|cation|shed)\b",
            r"\bDFAT\s+(?:website|portal)\b",
        ],
        "min_matches": 1,
    }),
])


def check_document(text, standard_checks):
    """Check document text against a set of standard requirements.

    Returns dict of results per check: {present, score, matched_indicators, detail}
    """
    text_lower = text.lower()
    results = OrderedDict()

    for check_id, check in standard_checks.items():
        matched = []
        for pattern in check["indicators"]:
            if re.search(pattern, text_lower):
                matched.append(pattern)

        present = len(matched) >= check["min_matches"]
        score = min(len(matched) / len(check["indicators"]), 1.0)

        results[check_id] = {
            "label": check["label"],
            "standard": check["standard"],
            "present": present,
            "score": round(score, 2),
            "matched": len(matched),
            "total_indicators": len(check["indicators"]),
            "min_required": check["min_matches"],
            "description": check["description"],
        }

    return results


def score_document(results):
    """Calculate overall compliance score."""
    present = sum(1 for r in results.values() if r["present"])
    total = len(results)
    weighted_score = sum(r["score"] for r in results.values()) / total
    return {
        "criteria_met": present,
        "criteria_total": total,
        "compliance_pct": round(present / total * 100),
        "weighted_score": round(weighted_score * 100),
    }


def format_report(results, overall, doc_type="Evaluation Plan"):
    """Format a human-readable compliance report."""
    standard_label = "DMEL Standard 9" if "plan" in doc_type.lower() else "DMEL Standard 10"

    lines = []
    lines.append(f"DFAT {standard_label} Compliance Check — {doc_type}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Overall: {overall['criteria_met']}/{overall['criteria_total']} criteria met "
                 f"({overall['compliance_pct']}%)")
    lines.append(f"Weighted indicator score: {overall['weighted_score']}%")
    lines.append("")

    # Present criteria
    present = [(k, v) for k, v in results.items() if v["present"]]
    absent = [(k, v) for k, v in results.items() if not v["present"]]

    if present:
        lines.append("PRESENT:")
        for _, r in present:
            lines.append(f"  [✓] {r['label']} ({r['standard']}) — "
                        f"{r['matched']}/{r['total_indicators']} indicators")

    lines.append("")

    if absent:
        lines.append("GAPS (action needed):")
        for _, r in absent:
            lines.append(f"  [✗] {r['label']} ({r['standard']}) — "
                        f"{r['matched']}/{r['total_indicators']} indicators")
            lines.append(f"      Required: {r['description']}")
    else:
        lines.append("No gaps found — all criteria have structural indicators present.")

    lines.append("")
    lines.append("Note: This checks for structural presence of required elements, "
                 "not quality or depth. A document may contain keywords without "
                 "substantively addressing the criterion.")

    return "\n".join(lines)


def check_text(text, doc_type="auto"):
    """Main entry point. Detects document type and runs appropriate checks."""
    text_lower = text.lower()

    if doc_type == "auto":
        plan_signals = len(re.findall(r"\bevaluation\s+plan\b", text_lower))
        report_signals = len(re.findall(r"\bevaluation\s+report\b", text_lower))
        if plan_signals > report_signals:
            doc_type = "Evaluation Plan"
        else:
            doc_type = "Evaluation Report"

    if "plan" in doc_type.lower():
        checks = STANDARD_9_CHECKS
    else:
        checks = STANDARD_10_CHECKS

    results = check_document(text, checks)
    overall = score_document(results)
    report = format_report(results, overall, doc_type)

    return {
        "doc_type": doc_type,
        "results": results,
        "overall": overall,
        "report": report,
    }


# ── CLI usage ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 dfat-compliance-checker.py <text-file> [plan|report]")
        print("       Checks document text against DFAT DMEL Standards")
        sys.exit(1)

    filepath = sys.argv[1]
    doc_type = sys.argv[2] if len(sys.argv) > 2 else "auto"

    with open(filepath) as f:
        text = f.read()

    result = check_text(text, doc_type)
    print(result["report"])
    print()
    print(f"Document type detected: {result['doc_type']}")
    print(f"Text length: {len(text):,} characters")
