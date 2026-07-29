---
name: papers
track: bonus
kind: live_api
provider: arXiv API
requires_env: [ARXIV_USER_AGENT]
inputs: [query, max_results, sort_by]
outputs: [items, total_results]
side_effect: false
---
# papers

Searches arXiv through the official public Atom API; no data API key is needed.
Requests carry `ARXIV_USER_AGENT` and are spaced by at least three seconds.

Use this tool for topic-based paper discovery. Results include canonical abstract
and PDF URLs, dates, categories, authors, and a reminder that arXiv preprints are
not automatically peer reviewed. Prefer topical relevance first and the updated
date as a tie-breaker when building a shortlist.
