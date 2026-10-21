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


# ── DFAT Investment Design Quality Assessment (9 criteria) ────────────
# Based on DFAT's Investment Design Quality Assessment Tool scoring matrix.
# Each criterion is scored 1-6 (Very Poor to Very Good) by appraisers.
# These structural checks detect whether the required content is present.

INVESTMENT_DESIGN_CHECKS = OrderedDict([
    ("relevance", {
        "label": "Relevance to development context and partner priorities",
        "standard": "IDQ-1",
        "description": "Alignment to partner government priorities and regional/global frameworks; evidence of development need; stakeholder consultation",
        "indicators": [
            r"\bpartner\s+government\b|\bhost\s+government\b|\brecipient\s+government\b",
            r"\balign(?:ment|ed|s)?\b.*\b(?:priorit|strateg|framework|policy)\b",
            r"\bdevelopment\s+context\b|\bcontext\s+analysis\b|\bsituation(?:al)?\s+analysis\b",
            r"\bevidence\s+of\s+need\b|\bneeds?\s+assessment\b|\bproblem\s+analysis\b|\bscoping\s+(?:study|mission|consult)\b|\bdesign\s+consult(?:ation|ing)\b",
            r"\bstakeholder\s+consult(?:ation|ed|ing)\b",
            r"\bpacific\s+(?:islands?\s+)?(?:forum|strategy|plan|framework)\b|\bregional\s+(?:framework|strategy|plan)\b|\bSDG\b|\bSendai\b",
        ],
        "min_matches": 3,
    }),
    ("effectiveness", {
        "label": "Program logic and theory of change",
        "standard": "IDQ-2",
        "description": "Clear program logic or theory of change; end-of-program outcomes (EOPOs); intermediate outcomes; assumptions stated",
        "indicators": [
            r"\bprogram\s+logic\b|\bprogramme\s+logic\b|\blogic\s+model\b",
            r"\btheory\s+of\s+change\b|\bToC\b",
            r"\b(?:end.of.(?:program|programme|investment)\s+outcome|EOPO)s?\b",
            r"\bintermediate\s+outcome(?:s)?\b|\bIO\s*\d\b",
            r"\bassumption(?:s)?\b.*\b(?:stat|identif|test|list)\b|\bkey\s+assumptions?\b",
            r"\bprogram\s+objective\b|\bprogramme\s+objective\b|\binvestment\s+objective\b",
        ],
        "min_matches": 3,
    }),
    ("efficiency", {
        "label": "Value for money and delivery efficiency",
        "standard": "IDQ-3",
        "description": "Budget with adequate detail; value for money analysis; governance arrangements; delivery model justified",
        "indicators": [
            r"\bvalue\s+for\s+money\b|\bVfM\b",
            r"\bbudget\b.*\b(?:detail|break|alloc|summar)\b|\bindicat(?:ive|ed)\s+budget\b",
            r"\bgovernance\b.*\b(?:arrang|structur|committee|board)\b",
            r"\bdelivery\s+(?:model|mechanism|approach|modality|partner)\b",
            r"\bcost.effect(?:ive|iveness)\b|\bunit\s+cost\b|\bbenchmark\b",
            r"\b(?:AUD|USD|GBP)\s*\$?\s*\d+\b|\bmillion\b.*\b(?:over|across|budget)\b",
        ],
        "min_matches": 3,
    }),
    ("mel", {
        "label": "Monitoring, evaluation and learning framework",
        "standard": "IDQ-4",
        "description": "MEL plan or framework; indicators at outcome and output level; baseline approach; evaluation schedule; data collection",
        "indicators": [
            r"\bMEL\s+(?:plan|framework|system|approach)\b|\bmonitoring.*evaluation.*learning\b",
            r"\bindicator(?:s)?\b.*\b(?:output|outcome|impact|performance)\b|\bperformance\s+(?:indicator|framework|measure)\b",
            r"\bbaseline\b",
            r"\bevaluation\b.*\b(?:plan|schedul|mid.term|final|independent)\b",
            r"\bdata\s+collect(?:ion|ed|ing)\b|\bdata\s+(?:source|management|quality)\b",
            r"\badaptive\s+management\b|\blearn(?:ing)\s+(?:plan|agenda|approach)\b",
        ],
        "min_matches": 3,
    }),
    ("sustainability", {
        "label": "Sustainability and locally led development",
        "standard": "IDQ-5",
        "description": "Exit strategy or transition plan; local ownership; capacity building; partner government role post-program",
        "indicators": [
            r"\bsustainab(?:ility|le)\b",
            r"\bexit\s+(?:strategy|plan|approach)\b|\btransition\s+(?:plan|strategy|approach)\b",
            r"\blocal(?:ly)?\s+(?:led|owned|ownership|driven)\b|\blocalis(?:ation|ed)\b",
            r"\bcapacity\s+(?:build(?:ing)?|develop(?:ment|ing)?|strengthen(?:ing)?)\b",
            r"\bhandover\b|\btransfer\b.*\b(?:ownership|responsibility|government)\b",
        ],
        "min_matches": 3,
    }),
    ("gender_equality", {
        "label": "Gender equality",
        "standard": "IDQ-6",
        "description": "Gender analysis; GEDSI strategy; sex-disaggregated data; gender-responsive indicators; PSEAH addressed",
        "indicators": [
            r"\bgender\s+(?:equality|equity|analysis|assessment|strategy|responsive|sensitive|mainstream(?:ing)?)\b",
            r"\bGEDSI\b|\bgender(?:,?\s+(?:equality|equity))?,?\s+disability\b.*\bsocial\s+inclusion\b",
            r"\bsex.disaggregat(?:e|ed|ion)\b|\bdisaggregat(?:e|ed|ion)\b.*\bsex\b|\bdisaggregat(?:e|ed|ion)\b.*\bgender\b",
            r"\bwomen(?:'s)?\s+(?:empower|participat|leadership|decision|economic)\b|\bwomen\s+and\s+girl\b",
            r"\bPSEAH\b|\bsexual\s+exploit(?:ation|ed)\b.*\b(?:abuse|harass)\b|\bprevention\s+of\s+sexual\b",
            r"\bgender\s+(?:budget|alloc)\b|\b(?:budget|alloc)\b.*\bgender\b",
        ],
        "min_matches": 3,
    }),
    ("disability", {
        "label": "Disability equity and inclusion",
        "standard": "IDQ-7",
        "description": "Disability inclusion strategy; OPD engagement; accessibility standards; disability-disaggregated data",
        "indicators": [
            r"\bdisability\b.*\b(?:inclus|equit|mainstream|strategy|action)\b",
            r"\bOPDs?\b|\borganis(?:ation|ization)s?\s+of\s+persons?\s+with\s+disabilit(?:y|ies)\b",
            r"\baccessib(?:le|ility)\b",
            r"\buniversal\s+design\b",
            r"\bdisability.disaggregat(?:e|ed|ion)\b|\bdisability\s+data\b",
            r"\breasonable\s+accommodat(?:ion|ions)\b",
        ],
        "min_matches": 2,
    }),
    ("climate", {
        "label": "Climate change and environmental sustainability",
        "standard": "IDQ-8",
        "description": "Climate risk assessment; environmental safeguards; climate resilience; environmental impact assessment",
        "indicators": [
            r"\bclimate\s+(?:change|risk|adapt|resilien|action|strateg)\b",
            r"\benvironment(?:al)?\s+(?:impact|assessment|safeguard|sustainab|management)\b",
            r"\bclimate\s+(?:vulnerab(?:ility|le)|screen(?:ing|ed)?|proof(?:ing|ed)?|smart)\b",
            r"\bemissions?\b|\bcarbon\b|\bnet.?zero\b|\brenewable\s+energy\b",
            r"\bdisaster\s+(?:risk|resilien|prepar|ready)\b",
        ],
        "min_matches": 2,
    }),
    ("risk_management", {
        "label": "Risk management and safeguards",
        "standard": "IDQ-9",
        "description": "Risk assessment and register; fraud control; environmental and social safeguards; child protection",
        "indicators": [
            r"\brisk\s+(?:management|assessment|register|matrix|framework|analysis)\b",
            r"\bfraud\s+(?:control|risk|prevention|mitigation)\b|\banti.fraud\b",
            r"\bsafeguard(?:s|ing)?\b.*\b(?:environment|social|child|policy)\b",
            r"\bchild\s+protect(?:ion|ed|ing)\b",
            r"\bdue\s+diligence\b",
            r"\b(?:residual|inherent)\s+risk\b|\brisk\s+(?:rating|level|appetite|tolerance)\b",
        ],
        "min_matches": 3,
    }),
])


# ── USAID ADS 201: Evaluation Report Requirements ──────────────────────
# Based on USAID Evaluation Report Requirements (ADS 201 Mandatory Reference,
# revised December 2023) and the 76-factor Evaluation Report Checklist.
# These checks cover the mandatory structural elements of a USAID evaluation report.

USAID_REPORT_CHECKS = OrderedDict([
    ("evaluation_type", {
        "label": "Evaluation type identified (impact or performance)",
        "standard": "ADS-1",
        "description": "Report must identify whether it is an impact evaluation or performance evaluation",
        "indicators": [
            r"\bimpact\s+evaluation\b",
            r"\bperformance\s+evaluation\b",
            r"\b(?:type|kind)\s+of\s+evaluation\b",
            r"\bformative\s+evaluation\b|\bsummative\s+evaluation\b",
            r"\b(?:quasi.?experimental|experimental|randomized|RCT)\b",
        ],
        "min_matches": 1,
    }),
    ("abstract", {
        "label": "Abstract (≤250 words)",
        "standard": "ADS-2",
        "description": "Abstract of not more than 250 words briefly describing what was evaluated, evaluation questions, methods, and key findings or conclusions",
        "indicators": [
            r"\babstract\b",
            r"\bbrief\s+(?:summary|description|overview)\b",
            r"\bsummary\b.*\bkey\s+findings?\b|\bkey\s+findings?\b.*\bsummary\b",
        ],
        "min_matches": 1,
    }),
    ("executive_summary", {
        "label": "Executive summary (2-5 pages)",
        "standard": "ADS-3",
        "description": "Executive summary summarizing purpose, background, evaluation questions, methods, findings, and conclusions",
        "indicators": [
            r"\bexecutive\s+summary\b",
            r"\bsummary\s+of\s+(?:key\s+)?findings?\b",
            r"\boverview\b.*\b(?:evaluation|assessment|review)\b",
        ],
        "min_matches": 1,
    }),
    ("purpose_audience", {
        "label": "Evaluation purpose, audience, and anticipated use",
        "standard": "ADS-4",
        "description": "States the commissioning operating unit, purpose of evaluation, audience for, and anticipated use(s)",
        "indicators": [
            r"\bpurpose\s+of\s+(?:the\s+|this\s+)?evaluation\b|\bevaluation\s+purpose\b",
            r"\baudience\b|\bintended\s+(?:user|reader|audience)s?\b",
            r"\banticipated\s+use\b|\buse\(?s?\)?\s+of\s+(?:the\s+|this\s+)?evaluation\b|\bhow\s+(?:the\s+)?(?:evaluation|findings)\s+will\s+be\s+used\b",
            r"\bcommissioning\b|\boperating\s+unit\b|\bUSAID\s*[/\\]\s*\w+\b",
        ],
        "min_matches": 2,
    }),
    ("program_description", {
        "label": "Description of what is being evaluated",
        "standard": "ADS-5",
        "description": "Describes the specific strategy, project, activity, or intervention including award numbers, award dates, funding levels, and implementing partners",
        "indicators": [
            r"\baward\s+(?:number|date|period)\b|\bcontract\s+number\b|\bcooperative\s+agreement\b",
            r"\bimplementing\s+partner\b|\bprime\s+(?:contractor|partner|recipient|implementer)\b",
            r"\bfunding\s+(?:level|amount)\b|\btotal\s+(?:funding|budget|estimated\s+cost|value)\b|(?:USD|US\s*\$|\$)\s*[\d,.]+\s*(?:million|billion)?\b",
            r"\b(?:project|activity|program(?:me)?|intervention)\s+(?:description|background|overview)\b",
            r"\bstart\s+date\b|\bend\s+date\b|\bperiod\s+of\s+performance\b|\blife\s+of\s+(?:project|activity)\b",
        ],
        "min_matches": 3,
    }),
    ("context_toc", {
        "label": "Context with development hypothesis or theory of change",
        "standard": "ADS-6",
        "description": "Country and/or sector context; specific problem or opportunity; development hypothesis, theory of change, or logic model",
        "indicators": [
            r"\b(?:country|sector|national|local|political|socio.?economic|development|regional|program(?:me)?|project)\s+context\b|\bcontext(?:ual)?\s+(?:analysis|background|overview)\b",
            r"\bdevelopment\s+hypothesis\b|\btheory\s+of\s+change\b|\bToC\b|\blogic\s+model\b|\bresults\s+framework\b",
            r"\bproblem\s+(?:statement|analysis|being\s+addressed)\b|\bopportunity\b.*\baddress\b",
            r"\bcausal\s+(?:chain|pathway|mechanism|relationship)\b",
            r"\boperating\s+(?:context|environment)\b|\bintroduction\s+and\s+background\b|\bprogram\s+(?:context|background|description)\b",
        ],
        "min_matches": 2,
    }),
    ("evaluation_questions", {
        "label": "Evaluation questions explicitly stated",
        "standard": "ADS-7",
        "description": "Evaluation questions clearly stated in the report",
        "indicators": [
            r"\bevaluation\s+question(?:s)?\b",
            r"\b(?:EQ|RQ)\s*\d\b",
            r"\bkey\s+question(?:s)?\b",
            r"\bresearch\s+question(?:s)?\b",
            r"\bquestion(?:s)?\s+guid(?:e|ed|ing)\b",
        ],
        "min_matches": 1,
    }),
    ("methods", {
        "label": "Evaluation methods for data collection and analysis",
        "standard": "ADS-8",
        "description": "Description of evaluation methods for data collection and analysis",
        "indicators": [
            r"\bmethodolog(?:y|ies|ical)\b|\bevaluation\s+(?:design|approach|method)\b",
            r"\bdata\s+collect(?:ion|ed|ing)\b",
            r"\bdata\s+analysis\b|\banalytical?\s+(?:approach|method|framework)\b",
            r"\binterview(?:s|ed)?\b|\bfocus\s+group\b|\bsurvey\b|\bquestionnaire\b",
            r"\bdocument\s+review\b|\bliterature\s+review\b|\bdesk\s+review\b",
            r"\bsampl(?:e|ing)\b|\bselection\s+criteria\b|\bresponse\s+rate\b",
        ],
        "min_matches": 3,
    }),
    ("limitations", {
        "label": "Limitations of evaluation methodology disclosed",
        "standard": "ADS-9",
        "description": "Limitations disclosed with particular attention to limitations associated with the evaluation methodology",
        "indicators": [
            r"\blimitation(?:s)?\b",
            r"\bconstraint(?:s)?\b.*\b(?:method|data|evaluat)\b",
            r"\bbias(?:es)?\b",
            r"\bcaveat\b|\bshortcoming\b",
            r"\bexternal\s+validity\b|\bgenerali[sz]abilit(?:y|ies)\b",
        ],
        "min_matches": 2,
    }),
    ("findings", {
        "label": "Findings presented by evaluation question",
        "standard": "ADS-10",
        "description": "Evaluation findings presented, ideally organized by evaluation question",
        "indicators": [
            r"\bfinding(?:s)?\b",
            r"\bkey\s+finding(?:s)?\b|\bmain\s+finding(?:s)?\b",
            r"\b(?:the\s+)?(?:evaluation|data|evidence|analysis)\s+(?:found|reveal|show|indicate|suggest|demonstrate)s?\b",
            r"\bfinding(?:s)?\s+(?:on|for|from|regarding|related\s+to)\b",
        ],
        "min_matches": 2,
    }),
    ("conclusions", {
        "label": "Conclusions drawn from findings",
        "standard": "ADS-11",
        "description": "Conclusions are interpretive statements based on the findings; clearly linked to evidence",
        "indicators": [
            r"\bconclusion(?:s)?\b",
            r"\b(?:in|to)\s+conclude\b|\bconcluding\s+(?:remark|observation)\b",
            r"\boverall\s+(?:assessment|conclusion|judgement)\b",
            r"\bthe\s+(?:evaluation|evidence|data|ET|team|analysis)\s+(?:supports?|suggests?|indicates?|demonstrates?|concluded|found|revealed|showed|confirmed|determined)\b",
            r"\bconcluded\s+that\b",
            r"\bfindings\s+and\s+conclusions\b",
        ],
        "min_matches": 2,
    }),
    ("recommendations", {
        "label": "Recommendations separated from conclusions",
        "standard": "ADS-12",
        "description": "If recommendations are included, they must be separate from conclusions; actionable and directed to specific stakeholders",
        "indicators": [
            r"\brecommendation(?:s)?\b",
            r"\brecommend(?:s|ed)?\s+that\b",
            r"\b(?:USAID|mission|implementing\s+partner|government)\s+should\b",
            r"\bactionable\b.*\brecommend\b|\brecommend\b.*\bactionable\b",
            r"\brecommendation\s+\d\b",
        ],
        "min_matches": 2,
    }),
    ("annexes", {
        "label": "Required annexes included",
        "standard": "ADS-13",
        "description": "Annexes including evaluation design matrix, data collection instruments, conflict of interest disclosures",
        "indicators": [
            r"\bannex(?:es|ure)?\b|\bappendix\b|\bappendices\b",
            r"\bevaluation\s+(?:design\s+)?matrix\b|\b(?:evaluation|research)\s+(?:design|framework)\b.*\bannex\b",
            r"\bconflict\s+of\s+interest\b|\bdisclosure\b",
            r"\bdata\s+collection\s+instrument\b|\binterview\s+(?:guide|protocol)\b|\bsurvey\s+instrument\b",
            r"\b(?:scope|statement)\s+of\s+work\b|\bToR\b|\bterms?\s+of\s+reference\b",
        ],
        "min_matches": 2,
    }),
])


# ── FCDO Evaluation Policy 2025 / EQUALS2: Evaluation Report Requirements ──

FCDO_REPORT_CHECKS = OrderedDict([
    ("executive_summary", {
        "label": "Executive summary included",
        "standard": "FCDO-1",
        "description": "Stand-alone executive summary covering the programme, evaluation objectives, methodology, key findings, conclusions, and recommendations",
        "indicators": [
            r"\bexecutive\s+summary\b",
            r"\bsummary\s+of\s+(?:key\s+)?findings?\b",
            r"\bsummary\s+of\s+(?:key\s+)?(?:conclusions?|recommendations?)\b",
        ],
        "min_matches": 1,
    }),
    ("programme_description", {
        "label": "Programme/intervention described",
        "standard": "FCDO-2",
        "description": "Description of the programme or intervention being evaluated, including funding, duration, geography, implementing partners",
        "indicators": [
            r"\bprogramme\s+(?:description|overview|background|summary)\b|\bdescription\s+of\s+(?:the\s+)?(?:programme|intervention|project)\b",
            r"\bimplementing\s+(?:partner|organisation|agency)\b|\bmanaging\s+(?:agent|contractor)\b",
            r"\bfunding\b|\bbudget\b|\b(?:GBP|£)\s*[\d,.]+\b|\bmillion\b",
            r"\bduration\b|\btimeframe\b|\b\d+[- ]year\b|\bperiod\s+of\b",
            r"\bgeograph(?:y|ic|ical)\b|\bcountr(?:y|ies)\b.*\b(?:focus|target|cover)\b",
        ],
        "min_matches": 3,
    }),
    ("evaluation_purpose", {
        "label": "Evaluation purpose and questions stated",
        "standard": "FCDO-3",
        "description": "Clear statement of evaluation purpose, intended audience, and evaluation questions",
        "indicators": [
            r"\bpurpose\s+of\s+(?:the\s+|this\s+)?evaluation\b|\bevaluation\s+purpose\b|\bobjective(?:s)?\s+of\s+(?:the\s+|this\s+)?evaluation\b",
            r"\bevaluation\s+question(?:s)?\b|\bkey\s+(?:evaluation\s+)?question(?:s)?\b",
            r"\b(?:EQ|KEQ|RQ)\s*\d\b",
            r"\bintended\s+(?:audience|user)s?\b|\baudience\s+for\b",
        ],
        "min_matches": 2,
    }),
    ("methodology", {
        "label": "Methodology described and justified",
        "standard": "FCDO-4",
        "description": "Evaluation methodology described, justified, and appropriate for the evaluation questions (EQUALS2 methodological rigour criterion)",
        "indicators": [
            r"\bmethodolog(?:y|ies|ical)\b",
            r"\bevaluation\s+(?:design|approach|method)s?\b|\b(?:research|analytical)\s+(?:design|approach|method|framework)\b",
            r"\bqualitative\b|\bquantitative\b|\bmixed[- ]method\b",
            r"\bdata\s+collect(?:ion|ed|ing)\b",
            r"\binterview(?:s|ed)?\b|\bfocus\s+group\b|\bsurvey\b|\bdocument\s+review\b|\bsite\s+visit\b|\bcase\s+stud(?:y|ies)\b",
            r"\bjustif(?:y|ied|ication)\b.*\b(?:method|approach|design)\b|\b(?:method|approach|design)\b.*\bjustif(?:y|ied|ication)\b",
        ],
        "min_matches": 3,
    }),
    ("dac_criteria", {
        "label": "OECD DAC evaluation criteria addressed",
        "standard": "FCDO-5",
        "description": "Report addresses OECD DAC criteria: relevance, coherence, effectiveness, efficiency, impact, sustainability",
        "indicators": [
            r"\brelevance\b",
            r"\bcoherence\b",
            r"\beffectiveness\b",
            r"\befficiency\b",
            r"\bimpact\b",
            r"\bsustainabilit(?:y|ies)\b",
            r"\b(?:OECD\s+)?DAC\s+(?:criteria|evaluation)\b",
        ],
        "min_matches": 3,
    }),
    ("sampling", {
        "label": "Sampling strategy described",
        "standard": "FCDO-6",
        "description": "Sampling strategy described and appropriate; data sources adequate and reliable (EQUALS2 criterion)",
        "indicators": [
            r"\bsampl(?:e|ing)\s+(?:strateg|approach|method|design|framework|size|selection)\b|\bsampl(?:e|ing)\b",
            r"\bselection\s+criteria\b|\bpurposive\b|\brandom\b|\bstratif(?:y|ied|ication)\b|\bsnowball\b",
            r"\bdata\s+source(?:s)?\b",
            r"\bresponse\s+rate\b|\bsample\s+size\b|\bn\s*=\s*\d+\b",
            r"\brepresentativ(?:e|eness)\b",
        ],
        "min_matches": 2,
    }),
    ("limitations", {
        "label": "Methodological limitations acknowledged",
        "standard": "FCDO-7",
        "description": "Limitations acknowledged with discussion of their impact on findings (EQUALS2 criterion)",
        "indicators": [
            r"\blimitation(?:s)?\b",
            r"\bconstraint(?:s)?\b",
            r"\bbias(?:es)?\b",
            r"\bcaveat(?:s)?\b|\bshortcoming(?:s)?\b",
            r"\b(?:methodolog|data|time|resource|access)\w*\s+(?:limitation|constraint|challenge|gap)\b",
        ],
        "min_matches": 2,
    }),
    ("triangulation", {
        "label": "Evidence triangulated",
        "standard": "FCDO-8",
        "description": "Findings clear and adequately triangulated across multiple sources or methods (EQUALS2 criterion)",
        "indicators": [
            r"\btriangulat(?:e|ed|ion|ing)\b",
            r"\bcross[- ]?validat(?:e|ed|ion|ing)\b|\bcorroborat(?:e|ed|ion|ing)\b",
            r"\bmultiple\s+(?:data\s+)?source(?:s)?\b|\bdiverse\s+(?:data\s+)?source(?:s)?\b",
            r"\bconverg(?:e|ence|ing)\b.*\bevidence\b|\bevidence\b.*\bconverg(?:e|ence|ing)\b",
        ],
        "min_matches": 1,
    }),
    ("findings", {
        "label": "Findings presented with evidence",
        "standard": "FCDO-9",
        "description": "Evaluation findings presented clearly, traceable through evidence to analysis (EQUALS2 criterion)",
        "indicators": [
            r"\bfinding(?:s)?\b",
            r"\bkey\s+finding(?:s)?\b|\bmain\s+finding(?:s)?\b",
            r"\b(?:the\s+)?(?:evaluation|evidence|data|analysis)\s+(?:found|reveal|show|indicate|suggest|demonstrate)s?\b",
            r"\bfinding(?:s)?\s+(?:on|for|from|regarding|related\s+to|against)\b",
        ],
        "min_matches": 2,
    }),
    ("conclusions", {
        "label": "Conclusions drawn from findings",
        "standard": "FCDO-10",
        "description": "Conclusions are interpretive statements based on the findings, drawing useful lessons",
        "indicators": [
            r"\bconclusion(?:s)?\b",
            r"\b(?:in|to)\s+conclude\b|\bconcluding\b",
            r"\boverall\s+(?:assessment|conclusion|judgement|judgment)\b",
            r"\bconcluded\s+that\b",
            r"\bfindings\s+and\s+conclusions\b",
            r"\blesson(?:s)?\s+(?:learn(?:ed|t)|emerg(?:ed|ing))\b",
        ],
        "min_matches": 2,
    }),
    ("recommendations", {
        "label": "Actionable recommendations included",
        "standard": "FCDO-11",
        "description": "Clear, actionable recommendations directed to specific stakeholders",
        "indicators": [
            r"\brecommendation(?:s)?\b",
            r"\brecommend(?:s|ed)?\s+that\b",
            r"\b(?:FCDO|DFID|government|programme\s+team|implementing\s+partner)\s+should\b",
            r"\brecommendation\s+\d\b",
            r"\bactionable\b",
        ],
        "min_matches": 2,
    }),
    ("gesi", {
        "label": "Gender equality and social inclusion addressed",
        "standard": "FCDO-12",
        "description": "Gender Equality and Social Inclusion (GESI) considerations integrated throughout design, analysis, and findings",
        "indicators": [
            r"\bgender\s+(?:equality|equity|analysis|mainstreaming|responsive|sensitive|dimension)\b|\bgender\b.*\binclusion\b",
            r"\bGESI\b",
            r"\bsocial\s+inclusion\b|\binclusi(?:ve|on|vity)\b",
            r"\bdisabilit(?:y|ies)\b|\bmarginali[sz](?:ed|ation)\b|\bvulnerab(?:le|ility)\b",
            r"\bdisaggregate(?:d|ion)\b.*\b(?:data|sex|gender|age)\b",
            r"\bwomen\b.*\bgirl\b|\bgirl\b.*\bwomen\b|\bwomen\s+and\s+girls?\b",
            r"\binclusive\s+data\s+charter\b",
        ],
        "min_matches": 2,
    }),
    ("ethics_safeguarding", {
        "label": "Ethics and safeguarding addressed",
        "standard": "FCDO-13",
        "description": "Ethical considerations, safeguarding, informed consent, and do-no-harm principles addressed",
        "indicators": [
            r"\bethic(?:s|al)\b",
            r"\bsafeguard(?:s|ing)\b",
            r"\binformed\s+consent\b|\bconsent\b",
            r"\bdo[- ]no[- ]harm\b|\bharm\s+(?:mitigation|reduction|prevention)\b",
            r"\bdata\s+protect(?:ion|ed)\b|\bconfidentialit(?:y|ies)\b|\banoymi[sz](?:e|ed|ation)\b",
            r"\bethic(?:s|al)\s+(?:review|approval|clearance|committee|board)\b|\b(?:IRB|ERB)\b",
        ],
        "min_matches": 2,
    }),
    ("theory_of_change", {
        "label": "Theory of change referenced",
        "standard": "FCDO-14",
        "description": "Theory of change, results framework, or logical framework referenced or included",
        "indicators": [
            r"\btheory\s+of\s+change\b|\bToC\b",
            r"\blogic(?:al)?\s+(?:model|framework)\b|\blogframe\b",
            r"\bresults?\s+(?:framework|chain)\b",
            r"\bcausal\s+(?:chain|pathway|mechanism|link)\b",
            r"\bimpact\s+pathway\b|\bchange\s+pathway\b",
        ],
        "min_matches": 1,
    }),
    ("independence_conflicts", {
        "label": "Independence and conflicts of interest addressed",
        "standard": "FCDO-15",
        "description": "Evaluator independence confirmed; conflicts of interest disclosed (EQUALS2 independence criterion)",
        "indicators": [
            r"\bindependen(?:ce|t)\b",
            r"\bconflict(?:s)?\s+of\s+interest\b",
            r"\bdisclosure\b|\btransparenc(?:y|ies)\b",
            r"\bimpartial(?:ity)?\b|\bobjectiv(?:e|ity)\b",
            r"\bfree(?:dom)?\s+(?:from|of)\s+(?:interference|influence|bias)\b",
        ],
        "min_matches": 2,
    }),
    ("stakeholder_engagement", {
        "label": "Stakeholder engagement described",
        "standard": "FCDO-16",
        "description": "Engagement with stakeholders and beneficiaries in the evaluation process",
        "indicators": [
            r"\bstakeholder\s+(?:engagement|consultation|input|feedback|participation|involvement|workshop)\b",
            r"\bconsult(?:ation|ed|ing)\b.*\b(?:stakeholder|beneficiar|partner|government)\b",
            r"\bbeneficiar(?:y|ies)\b",
            r"\bparticipat(?:ory|ion|ing|ed)\b",
            r"\bplural\s+views?\b|\bdiverse\s+(?:perspective|voice|view|opinion)s?\b",
        ],
        "min_matches": 2,
    }),
    ("management_response", {
        "label": "Management response included or referenced",
        "standard": "FCDO-17",
        "description": "Management response with acceptance levels and assigned actions (FCDO mandatory publication standard)",
        "indicators": [
            r"\bmanagement\s+response\b",
            r"\baction\s+plan\b|\bfollow[- ]up\s+(?:action|plan)\b",
            r"\b(?:accept|reject|partially\s+accept)\b.*\brecommendation\b|\brecommendation\b.*\b(?:accept|reject)\b",
            r"\bresponsible\s+(?:person|party|officer|unit|team)\b|\baction\s+(?:owner|lead)\b",
        ],
        "min_matches": 1,
    }),
    ("annexes", {
        "label": "Required annexes included",
        "standard": "FCDO-18",
        "description": "Annexes including terms of reference, evaluation matrix, data collection instruments",
        "indicators": [
            r"\bannex(?:es|ure)?\b|\bappendix\b|\bappendices\b",
            r"\bterms?\s+of\s+reference\b|\bToR\b",
            r"\bevaluation\s+(?:design\s+)?matrix\b",
            r"\bdata\s+collection\s+(?:instrument|tool)s?\b|\binterview\s+(?:guide|protocol|schedule)\b|\bsurvey\s+(?:instrument|questionnaire)\b",
        ],
        "min_matches": 2,
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
            if re.search(pattern, text_lower, re.IGNORECASE):
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
    if "usaid" in doc_type.lower():
        standard_label = "ADS 201"
        donor = "USAID"
    elif "fcdo" in doc_type.lower():
        standard_label = "Evaluation Policy 2025 / EQUALS2"
        donor = "FCDO"
    elif "design" in doc_type.lower():
        standard_label = "Investment Design Quality"
        donor = "DFAT"
    elif "plan" in doc_type.lower():
        standard_label = "DMEL Standard 9"
        donor = "DFAT"
    else:
        standard_label = "DMEL Standard 10"
        donor = "DFAT"

    lines = []
    lines.append(f"{donor} {standard_label} Compliance Check — {doc_type}")
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
        design_signals = len(re.findall(r"\binvestment\s+design\b", text_lower))
        design_signals += len(re.findall(r"\bdesign\s+document\b", text_lower))
        design_signals += len(re.findall(r"\bprogram\s*logic\b", text_lower))
        usaid_signals = len(re.findall(r"\bUSAID\b", text))
        usaid_signals += len(re.findall(r"\bADS\s+201\b", text))
        usaid_signals += len(re.findall(r"\boperating\s+unit\b", text_lower))
        usaid_signals += len(re.findall(r"\bdevelopment\s+hypothesis\b", text_lower))
        fcdo_signals = len(re.findall(r"\bFCDO\b", text))
        fcdo_signals += len(re.findall(r"\bDFID\b", text))
        fcdo_signals += len(re.findall(r"\bEQUALS\b", text))
        fcdo_signals += len(re.findall(r"\bUK\s+(?:aid|government|ODA)\b", text_lower))
        fcdo_signals += len(re.findall(r"\b(?:GBP|£)\s*[\d,.]+\b", text))
        if usaid_signals >= 3:
            doc_type = "USAID Evaluation Report"
        elif fcdo_signals >= 3:
            doc_type = "FCDO Evaluation Report"
        elif design_signals > plan_signals and design_signals > report_signals:
            doc_type = "Investment Design"
        elif plan_signals > report_signals:
            doc_type = "Evaluation Plan"
        else:
            doc_type = "Evaluation Report"

    if "usaid" in doc_type.lower():
        checks = USAID_REPORT_CHECKS
    elif "fcdo" in doc_type.lower():
        checks = FCDO_REPORT_CHECKS
    elif "design" in doc_type.lower():
        checks = INVESTMENT_DESIGN_CHECKS
    elif "plan" in doc_type.lower():
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
        print("Usage: python3 dfat-compliance-checker.py <text-file> [plan|report|design|usaid|fcdo]")
        print("       Checks document text against DFAT DMEL / USAID ADS 201 / FCDO EQUALS2")
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
