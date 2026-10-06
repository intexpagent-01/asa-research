#!/usr/bin/env python3
"""Render site/dev.html: unlisted review page for the Operator.

Direct links to all briefs without paywall or navigation. Not linked
from any public page. Created Wake 123 per Operator directive (383520927).
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

extra = """
.container{max-width:740px}
h1{font-size:1.5rem;margin-bottom:.3rem}
p{margin-bottom:.9rem;line-height:1.6}
a{color:var(--series-1)}
.card{background:var(--surface-card);border:1px solid var(--border);border-radius:10px;padding:1.2rem 1.5rem;margin:.8rem 0;box-shadow:var(--card-shadow)}
.card h3{margin:0 0 .3rem;font-size:1rem}
.card p{font-size:.88rem;margin-bottom:.3rem;color:var(--text-secondary)}
.card a{font-size:.9rem;font-weight:600}
.note{font-size:.82rem;color:var(--text-muted);font-style:italic}
footer{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--gridline);font-size:.78rem;color:var(--text-muted)}
"""

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Asa &mdash; Dev review area</title>
<meta name="robots" content="noindex, nofollow">
<style>{style}{extra}</style></head><body><div class="container">
<h1>Dev review area</h1>
<p class="note">This page is not linked from the public site. It exists for the Operator to review and share briefs directly.</p>

<h2 style="font-size:1.1rem;margin:1.5rem 0 .5rem">Intelligence briefs</h2>

<div class="card">
<h3>PLMSP &mdash; Pacific Labour Mobility ($230M)</h3>
<p>Full intelligence brief. Currently the public sample on the homepage.</p>
<a href="plmsp-brief.html">Open brief &rarr;</a>
</div>

<div class="card">
<h3>PWLES &mdash; Pacific Women Lead ($170M)</h3>
<p>Unlisted. Restored per Operator directive (383520921). Not linked from the public site.</p>
<a href="pwles-brief.html">Open brief &rarr;</a>
</div>

<div class="card">
<h3>Strongim Ekonomi &mdash; Solomon Islands economic governance</h3>
<p>Unlisted. Made private per Operator directive (383520922).</p>
<a href="strongim-ekonomi-brief.html">Open brief &rarr;</a>
</div>

<div class="card">
<h3>PASC &mdash; PacificAus Sport: Community</h3>
<p>Unlisted. Removed from public site for conflict of interest (383520918/920).</p>
<a href="pasc-brief.html">Open brief &rarr;</a>
</div>

<div class="card">
<h3>ESIP 2 &mdash; Assessment form</h3>
<p>Structured micro-assessment for the ESIP 2 retrospective validation.</p>
<a href="assess-esip2.html">Open &rarr;</a>
</div>

<h2 style="font-size:1.1rem;margin:1.5rem 0 .5rem">Quick links</h2>
<p style="font-size:.88rem;line-height:2">
<a href="index.html">Home page</a> &middot;
<a href="signal.html">Current issue</a> &middot;
<a href="feedback.html">Ask queue / feedback board</a> &middot;
<a href="field-notes.html">Field notes</a> &middot;
<a href="search.html">Search</a>
</p>

<footer>This page is not indexed by search engines and is not linked from any public page on the site.</footer>
</div></body></html>"""

out = os.path.join(SITE, "dev.html")
open(out, "w").write(html)
print("rendered dev.html (dev review area)", len(html) // 1024, "KB")
