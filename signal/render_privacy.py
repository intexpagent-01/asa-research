#!/usr/bin/env python3
"""Render site/privacy.html from PRIVACY.md content."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get("SIGNAL_SITE") or os.path.join(os.path.dirname(HERE), "site")
REPO = "https://github.com/intexpagent-01/asa-research"
style = re.search(r"<style>(.*?)</style>", open(os.path.join(SITE, "research.html")).read(), re.S).group(1)

extra = """
.container{max-width:760px} h2{font-size:1.2rem;margin:2rem 0 .6rem;letter-spacing:-.01em}
h3{font-size:1.05rem;margin:1.5rem 0 .4rem} p{margin-bottom:1rem}
ul{margin:0 0 1rem 1.2rem} li{margin-bottom:.45rem;font-size:.95rem} a{color:var(--series-1)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--gridline);font-size:.8rem;color:var(--text-muted)}
@media (max-width: 600px){.container{padding:1.5rem .9rem 2.5rem} footer{font-size:.75rem}}
"""

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy &mdash; Pacific Aid Signal</title>
<meta name="description" content="Privacy policy for Pacific Aid Signal. Minimal data collection by design: no analytics, no tracking, no cookies.">
<style>{style}{extra}</style></head><body><div class="container">
<header><p style="margin-bottom:.4rem"><a href="index.html" style="color:var(--text-muted);text-decoration:none">&larr; Home</a></p>
<h1>Privacy Policy</h1>
<p>Last updated: 17 October 2026</p></header>

<h2>What this project does</h2>
<p>Pacific Aid Signal is a public aid intelligence tool. It collects, processes, and publishes development aid data from public sources for 14 Pacific island countries.</p>

<h2>Data sources</h2>
<p>All aid data comes from public sources:</p>
<ul>
<li><strong>IATI</strong> (via d-portal): published aid transaction data from international funders</li>
<li><strong>World Bank Projects API</strong>: project details and evaluation ratings</li>
<li><strong>DFAT Development Procurement Pipeline</strong>: publicly listed procurement items</li>
<li><strong>DFAT Business Notifications</strong>: publicly posted business opportunities</li>
<li><strong>NZ GETS</strong>: publicly listed tenders</li>
<li><strong>AusConnect</strong>: publicly listed Pacific development opportunities</li>
<li><strong>SPC Procurement</strong>: publicly listed tenders</li>
<li><strong>UNDP Jobs</strong>: publicly listed positions</li>
</ul>
<p>No non-public, proprietary, or restricted data is used.</p>

<h2>Personal data collection</h2>

<h3>Website visitors</h3>
<p>The site is hosted on GitHub Pages. GitHub&rsquo;s own privacy practices apply to hosting; see <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub&rsquo;s Privacy Statement</a>. This project does not add analytics, tracking scripts, cookies, or any client-side data collection.</p>

<h3>Ask box</h3>
<p>The Ask box collects only the message text and a category selection (question, watch, or feedback). It does <strong>not</strong> collect or store:</p>
<ul>
<li>Name</li>
<li>Email address (except when voluntarily provided for brief requests)</li>
<li>Organisation</li>
<li>IP address</li>
<li>Cookies or device identifiers</li>
<li>Any other information about the sender</li>
</ul>
<p>Messages are stored in a Cloudflare KV namespace with a 90-day TTL. The project maintainer reads messages during scheduled sessions, quarantines raw text in a private file that is never published, and publishes only its own restatement and response on the public feedback board. A correspondent&rsquo;s exact words are never reproduced publicly.</p>

<h3>Standing watches (GitHub Issues)</h3>
<p>Standing watches are filed as GitHub issue titles. Only the title text is read (never the issue body). The GitHub username is used only for per-account caps (max 5 watches per account) and is never stored, displayed, or published. The watch query and issue number appear on the relevant country page; the author does not.</p>

<h3>Brief requests</h3>
<p>Brief requests collect an email address (provided voluntarily) for delivery purposes only. Email addresses are stored in the Ask box queue with the same 90-day TTL and are not shared with third parties.</p>

<h2>Contact information in source data</h2>
<p>DFAT business notifications and NZ GETS tenders sometimes contain contact names and email addresses. These are <strong>stripped at fetch time</strong> before storage. They are never stored in snapshots, published on the site, or included in data exports.</p>

<h2>Content moderation</h2>
<p>User-submitted content (standing watches and Ask box messages) is moderated through:</p>
<ul>
<li><strong>Character allowlist:</strong> only letters, numbers, spaces, and basic punctuation accepted</li>
<li><strong>Length caps:</strong> 3&ndash;60 characters for watches, 700 characters for Ask box messages</li>
<li><strong>Blocklist:</strong> known slur and profanity terms filtered at submission</li>
<li><strong>Rate limiting:</strong> 6 messages per IP per hour for the Ask box</li>
<li><strong>Per-account limits:</strong> max 5 watches per GitHub account, 10 issue-filed watches per country</li>
<li><strong>Human-in-the-loop review:</strong> all Ask box messages are reviewed during scheduled sessions before any response is published</li>
<li><strong>Quarantine:</strong> raw text is stored privately and never published directly; only the maintainer&rsquo;s restatement and response appear publicly</li>
</ul>

<h2>Data exports</h2>
<p>CSV and JSON data exports are available at <a href="download.html">pacificaidsignal.org/download.html</a>. These contain only aggregated aid data derived from public sources. No personal data is included in exports.</p>

<h2>Third-party services</h2>
<ul>
<li><strong>GitHub Pages:</strong> static site hosting</li>
<li><strong>Cloudflare Workers:</strong> Ask box endpoint (message storage only, no analytics)</li>
<li><strong>Stripe:</strong> payment processing for brief requests (Stripe&rsquo;s privacy policy applies; the project does not receive or store payment card details)</li>
</ul>

<h2>Applicable law</h2>
<p>This project operates from Australia. Australian privacy law (Privacy Act 1988) applies to the extent that personal information is handled. The project&rsquo;s data collection is minimal by design.</p>

<h2>Changes</h2>
<p>Changes to this policy will be documented with a date and committed to the repository&rsquo;s version history.</p>

<h2>Contact</h2>
<p>Questions about privacy can be submitted through the <a href="feedback.html">Ask box</a> on the site or via a <a href="{REPO}/issues">GitHub issue</a>.</p>

<footer>
<a href="index.html">Home</a> &middot;
<a href="about.html">About Asa</a> &middot;
<a href="signal.html">Pacific Aid Signal</a> &middot;
<a href="feedback.html">Feedback</a> &middot;
<a href="{REPO}">Code and data</a>
</footer>
</div></body></html>"""

out = os.path.join(SITE, "privacy.html")
open(out, "w").write(html)
print("rendered privacy.html", len(html) // 1024, "KB")
