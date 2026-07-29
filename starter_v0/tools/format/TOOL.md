---
name: format
track: core
kind: local_formatter
requires_env: []
inputs: [items, template, headline]
outputs: [markdown, item_count]
side_effect: false
---
# format

Formats already-collected items into a markdown digest. It does not fetch data.
The `paper_scout` template renders problem, method, result, limitation,
implementation relevance, and page-level PDF citations for arXiv papers. Missing
evidence is shown explicitly rather than filled from an abstract.
