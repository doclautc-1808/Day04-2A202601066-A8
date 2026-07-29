---
name: paper_rank
track: bonus
kind: local_ranker
provider: Local deterministic scoring
requires_env: []
inputs: [items, query, limit]
outputs: [items, total_candidates, selected_count]
side_effect: false
---
# paper_rank

Ranks metadata already returned by `papers`. It does not call arXiv or an LLM.

Topical relevance is the primary sort key: title matches receive the highest
weight, followed by category and abstract matches. The arXiv `updated` timestamp
is used only as a tie-breaker, matching the Paper Scout selection policy.
