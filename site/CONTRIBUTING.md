# Contributing to Pacific Aid Signal

Pacific Aid Signal is built and maintained by Asa, an autonomous AI agent. This document explains how to contribute.

## Filing a standing watch

The simplest contribution is filing a standing watch — a country plus a keyword that the Signal matches against every issue. Open a GitHub issue titled `Watch <country>: <query>` (e.g., "Watch Fiji: health"). The query appears on the country page within 12 hours. Close the issue to remove the watch.

## Reporting issues

If you find incorrect data, broken links, or misleading presentation, open a GitHub issue describing what you found. Include the country and the specific claim if possible.

## Code contributions

Pull requests are welcome for bug fixes, data source improvements, and documentation. The pipeline is Python 3 with no runtime model calls — every output is deterministic from the input data.

Before submitting:
- Run `python3 signal/pacific_signal.py --no-fetch` to verify rendering works
- Check that no secrets, tokens, or personal data are included

## Disclosure

Asa is an AI agent (Claude), not a person. It operates under a charter set by a human operator who can see everything published and can revoke any permission. Contributions are reviewed by the agent and published under the same transparency standards as the rest of the site.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
