# Acceptance and verification

- Website definitions mapped to offline assessment API, bounded JSON CLI and synthetic examples.
- SOA4: exact subject/object/operation/trace binding; separate identity, policy, approval, validity/revocation and action outcome gates; no authority granted.
- KIS4: simultaneous dimension floors, explicit caller weights and rationale, traceability, critical gates and maturity caps; no organizational approval granted.
- CLI: malformed, duplicate-key, oversized and non-finite JSON rejected; exit statuses distinguish malformed input from evidence gaps.
- OODA runner: unit/CLI suite, wheel+sdist build, isolated offline wheel install, installed tests and package-origin check. Stops on failure and writes a result artifact.
- Regression observed during development: setuptools mutates sys.argv between build calls. Capturing the output argument before invoking build_wheel prevents sdist from being written to the wrong location. Package existence checks failed before this correction; both package cycles passed afterward.
- Local Python 3.12 tests and package checks passed. Python 3.13 and GitHub execution are verified only by the exact PR-head CI results, not this authored document.

Coverage limitations: record assertions and evidence links are not independently verified. No real authentication, external authorization, customer requests, hosted deployment, model behavior or long-term operational effectiveness is tested. No package publication is part of CI.

Promotion is a normal human-reviewed PR merge. Continuous daily rebuilding begins only when the workflow is on the default branch. Each result feeds the existing workspace engineering operator; this package creates no second automation owner and does not self-modify.
