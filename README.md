# GovDOSS KIS4

KIS4 evaluates Simple, Secure, Sustainable and Scalable as simultaneous design constraints. This package evaluates explicit caller-supplied criteria, positive weights, rationale, threshold, dimension minimums, maturity caps, traceable evidence and critical gates. Missing evidence is not a neutral score. Failed/unknown critical gates suppress the composite; a weak dimension cannot be compensated by other dimensions. Rubric design, confidence, maturity caps, evidence truth and sensitivity analysis remain accountable reviewer judgments.

## Status and authority

Version 0.1.0 is a reviewable offline reference package for the user-created `mgllc/KIS4` repository. Repository existence is verified; default-branch installation and scheduled build activation require normal PR review. It has no network client, identity provider, policy enforcement point, model API, database, scheduler daemon or deployment integration. A `ready-for-review` result is never approval, permission, execution, independent verification or assurance certification. Input evidence references are assertions; the package does not dereference or authenticate them.

## Run

Python 3.12 or newer, no runtime dependencies:

```sh
python -m kis4 < examples/scorecard.json
python -m unittest discover -s tests -v
python -m pip install setuptools==84.1.0 wheel==0.48.0
python scripts/ooda_cycle.py
```

CLI reads at most 100 KB from stdin, rejects duplicate keys and non-finite JSON constants, and emits JSON. Exit 0: ready for review; 1: gaps/revision required; 2: invalid input. The public Python API is `kis4.assess(record)`. Examples are synthetic and must never be used as real authority/evidence. SOA4 example validity dates intentionally expire; production records need actual evidence and current validity.

## Contract

`examples/scorecard.json` demonstrates the schema 1 input. Unknown fields grant no capability. All required textual fields must be nonempty. Review source and tests for exact validation behavior. API records are in-memory and never execute content. Changing record semantics requires a reviewed versioned change and compatibility tests.

## Continuous OODA cycle

- Observe: capture repository, exact source SHA, run ID and interpreter from CI.
- Orient: identify the actual failed check and coverage limits using test/build receipts.
- Decide: apply a 15-minute build budget and stop on the first failed check.
- Act: run unit/CLI tests, build wheel and sdist, install the wheel offline into an isolated environment, and exercise the installed package.
- Verify: record exit statuses and package digests in `cycle-result.json`.
- Learn: feed evidence to the existing workspace engineering operator; propose bounded fixes through review. No automatic source rewriting or gate changes.

The proposed workflow runs on push, PR, manual dispatch and daily schedule after it is reviewed and installed on the new repository default branch. Until then, it is a template, not an active scheduler. No publish, merge, approve or permission-write step exists. Operator limits remain two active maintenance/onboarding PRs and two attempts per normalized failure fingerprint. No-change cycles produce no repair commits. Outcome artifacts last 14 days; PR/commit history retains durable repair decisions. This is engineering continuity, not autonomous model training.

## Source and ownership

Derived from GovDOSS's canonical Sites website, version 36, source `ff82151ac1c8d21b065dc084f84bf32baf433024`: `app/visuals/visual-data.ts`, `app/visuals/kis4/page.tsx`, and `/visuals/ooda`. Website: https://govdoss.com/visuals/kis4. The accompanying evidence/authority boundaries follow inspected GovDOSS KIS4 and OODA skills. Website definitions are the source concepts; JSON schema, API, stricter complete-evidence rule, CLI and build workflow are implementation choices for review, not claims that the website specified software interfaces.

No open-source license or trademark grant is inferred. GovDOSS ownership and repository visibility must be preserved when provisioning. Do not publish a package to an external registry as a build check.
