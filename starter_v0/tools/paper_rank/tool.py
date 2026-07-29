from __future__ import annotations

from datetime import datetime
from typing import Any

from tools._shared import err, fold_text, terms


def _updated_timestamp(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _relevance_score(item: dict[str, Any], query: str) -> tuple[int, list[str]]:
    query_terms = terms(query)
    title = fold_text(str(item.get("title") or ""))
    summary = fold_text(str(item.get("summary") or ""))
    categories = fold_text(" ".join(str(value) for value in item.get("categories") or []))
    phrase = fold_text(query).strip()

    title_hits = sum(title.count(term) for term in query_terms)
    summary_hits = sum(summary.count(term) for term in query_terms)
    category_hits = sum(categories.count(term) for term in query_terms)
    coverage = sum(1 for term in query_terms if term in f"{title} {summary} {categories}")
    phrase_bonus = 8 if phrase and phrase in f"{title} {summary}" else 0
    score = title_hits * 5 + category_hits * 3 + summary_hits + coverage * 2 + phrase_bonus

    reasons: list[str] = []
    if title_hits:
        reasons.append(f"{title_hits} title term match(es)")
    if category_hits:
        reasons.append(f"{category_hits} category term match(es)")
    if summary_hits:
        reasons.append(f"{summary_hits} abstract term match(es)")
    if phrase_bonus:
        reasons.append("exact phrase match")
    if not reasons:
        reasons.append("no lexical topic match")
    return score, reasons


def rank_arxiv_papers(
    items: list[dict[str, Any]] | None = None,
    query: str = "",
    limit: int = 3,
) -> dict[str, Any]:
    try:
        candidates = items or []
        if not query.strip():
            raise ValueError("A non-empty ranking query is required")
        limit = max(1, min(int(limit or 3), 10))

        scored: list[tuple[int, float, str, dict[str, Any]]] = []
        for item in candidates:
            if not isinstance(item, dict):
                raise ValueError("Every paper candidate must be an object")
            score, reasons = _relevance_score(item, query)
            enriched = {
                **item,
                "relevance_score": score,
                "rank_reason": "; ".join(reasons),
            }
            scored.append((
                score,
                _updated_timestamp(item.get("updated")),
                str(item.get("title") or "").lower(),
                enriched,
            ))

        scored.sort(key=lambda value: (-value[0], -value[1], value[2]))
        selected: list[dict[str, Any]] = []
        for rank, (_, _, _, item) in enumerate(scored[:limit], start=1):
            selected.append({**item, "rank": rank})

        return {
            "tool": "rank_arxiv_papers",
            "query": query,
            "total_candidates": len(candidates),
            "selected_count": len(selected),
            "items": selected,
            "ranking_policy": "Topical relevance first; updated date breaks ties.",
        }
    except Exception as exc:
        return err("rank_arxiv_papers", exc)
