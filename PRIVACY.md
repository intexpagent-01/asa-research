# Privacy Policy

**Last updated:** 17 October 2026

## What this project does

Pacific Aid Signal is a public aid intelligence tool. It collects, processes, and publishes development aid data from public sources for 14 Pacific island countries.

## Data sources

All aid data comes from public sources:
- **IATI** (via d-portal): published aid transaction data from international funders
- **World Bank Projects API**: project details and evaluation ratings
- **DFAT Development Procurement Pipeline**: publicly listed procurement items
- **DFAT Business Notifications**: publicly posted business opportunities
- **NZ GETS (Government Electronic Tenders Service)**: publicly listed tenders
- **AusConnect**: publicly listed Pacific development opportunities
- **SPC Procurement**: publicly listed tenders
- **UNDP Jobs**: publicly listed positions

No non-public, proprietary, or restricted data is used.

## Personal data collection

### Website visitors

The site is hosted on GitHub Pages. GitHub's own privacy practices apply to hosting; see [GitHub's Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement). The project does not add analytics, tracking scripts, cookies, or any client-side data collection to the site.

### Ask box

The Ask box collects only the message text and a category selection (question, watch, or feedback). It does **not** collect or store:
- Name
- Email address
- Organisation
- IP address
- Cookies or device identifiers
- Any information about the sender

Messages are stored in a Cloudflare KV namespace with a 90-day TTL. The project maintainer reads messages during scheduled sessions, quarantines raw text in a private file that is never published, and publishes only its own restatement and response on the public feedback board. A correspondent's exact words are never reproduced publicly.

### Standing watches (GitHub Issues)

Standing watches are filed as GitHub issue titles. Only the title text is read (never the issue body). The GitHub username associated with the issue is used only for per-account caps (max 5 watches per account) and is never stored, displayed, or published. The watch query and issue number appear on the relevant country page; the author does not.

### Brief requests

Brief requests submitted through the site collect an email address (provided voluntarily by the requester) for delivery purposes only. Email addresses are stored in the Ask box queue with the same 90-day TTL and are not shared with third parties.

## Data processing

### IATI transaction data

Approximately 70% of transactions tagged to Pacific countries in IATI are explicitly for other countries. The pipeline applies recipient-country weighting to correct this. Cross-publisher deduplication removes double-counted transactions. These are data quality corrections, not editorial choices — the methodology is documented at [pacificaidsignal.org/methodology.html](https://pacificaidsignal.org/methodology.html).

### Contact information in source data

DFAT business notifications and NZ GETS tenders sometimes contain contact names and email addresses. These are **stripped at fetch time** before storage. They are never stored in snapshots, published on the site, or included in data exports.

## Data exports

CSV and JSON data exports are available at [pacificaidsignal.org/download.html](https://pacificaidsignal.org/download.html). These contain only aggregated aid data derived from public sources. No personal data is included in exports.

## Third-party services

- **GitHub Pages**: static site hosting
- **Cloudflare Workers**: Ask box endpoint (message storage only, no analytics)
- **Stripe**: payment processing for brief requests (Stripe's privacy policy applies; the project does not receive or store payment card details)

## Applicable law

This project operates from Australia. Australian privacy law (Privacy Act 1988) applies to the extent that personal information is handled. The project's data collection is minimal by design: it does not collect personal information from website visitors, and the Ask box is designed to function without any identifying information.

## Changes

Changes to this policy will be documented with a date and committed to the repository's version history.

## Contact

Questions about privacy can be submitted through the Ask box on the site or via a GitHub issue on this repository.
