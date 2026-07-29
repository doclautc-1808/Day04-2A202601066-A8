---
name: citation_audit
track: bonus
kind: local_validator
provider: Local cached arXiv text
requires_env: []
inputs: [items]
outputs: [valid, paper_results, evidence_checked, valid_evidence]
side_effect: false
---
# citation_audit

Audits page-level evidence before a Paper Scout report is formatted. It validates
arXiv IDs and PDF URLs, requires positive page numbers and non-empty excerpts,
then checks that each excerpt occurs on the claimed page in the text cache written
by `paper_text`.

This tool makes no network or model calls. Missing cached text is reported as a
failed audit; it never accepts an abstract as PDF evidence.
