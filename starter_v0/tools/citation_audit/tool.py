from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tools._shared import err
from tools.paper_text.tool import ARXIV_DIR, _arxiv_id, _cache_stem


def _compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def _cached_pages(path: Path) -> dict[int, str]:
    if not path.is_file():
        return {}
    content = path.read_text(encoding="utf-8")
    parts = re.split(r"--- Page (\d+) ---\n", content)
    pages: dict[int, str] = {}
    for index in range(1, len(parts), 2):
        pages[int(parts[index])] = _compact(parts[index + 1])
    return pages


def _auditable_excerpt(value: Any) -> str:
    return _compact(value).strip("…").strip()


def _audit_evidence(
    evidence: dict[str, Any],
    *,
    arxiv_id: str,
    inherited_pdf_url: str,
    cached_pages: dict[int, str],
) -> dict[str, Any]:
    issues: list[str] = []
    page_number = evidence.get("page_number")
    excerpt = _auditable_excerpt(evidence.get("excerpt"))
    pdf_url = str(evidence.get("pdf_url") or inherited_pdf_url or "").strip()

    if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1:
        issues.append("invalid_page_number")
    if not excerpt:
        issues.append("missing_excerpt")

    if not pdf_url:
        issues.append("missing_pdf_url")
    else:
        parsed = urlparse(pdf_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"arxiv.org", "www.arxiv.org"}:
            issues.append("non_arxiv_pdf_url")
        else:
            try:
                url_id = _arxiv_id(pdf_url)
                if url_id != arxiv_id:
                    issues.append("arxiv_id_url_mismatch")
            except ValueError:
                issues.append("invalid_arxiv_pdf_url")

    if not cached_pages:
        issues.append("cached_text_missing")
    elif isinstance(page_number, int) and not isinstance(page_number, bool) and page_number > 0:
        page_text = cached_pages.get(page_number)
        if page_text is None:
            issues.append("page_not_in_cache")
        elif excerpt and excerpt not in page_text:
            issues.append("excerpt_not_found_on_page")

    canonical_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    citation = (
        f"[arXiv {arxiv_id}, p. {page_number}]({canonical_url}#page={page_number})"
        if isinstance(page_number, int) and not isinstance(page_number, bool) and page_number > 0
        else None
    )
    return {
        "valid": not issues,
        "page_number": page_number,
        "excerpt": evidence.get("excerpt") or "",
        "pdf_url": pdf_url,
        "citation": citation,
        "issues": issues,
    }


def audit_arxiv_citations(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    try:
        papers = items or []
        paper_results: list[dict[str, Any]] = []
        evidence_checked = 0
        valid_evidence = 0

        for item in papers:
            if not isinstance(item, dict):
                raise ValueError("Every paper item must be an object")
            paper_issues: list[str] = []
            try:
                arxiv_id = _arxiv_id(str(item.get("arxiv_id") or item.get("url") or ""))
            except ValueError:
                arxiv_id = ""
                paper_issues.append("invalid_arxiv_id")

            evidence_items = item.get("evidence") or []
            if not isinstance(evidence_items, list):
                raise ValueError("Paper evidence must be an array")
            if not evidence_items:
                paper_issues.append("missing_evidence")

            cache_path = ARXIV_DIR / f"{_cache_stem(arxiv_id)}.txt" if arxiv_id else Path("")
            pages = _cached_pages(cache_path) if arxiv_id else {}
            audited: list[dict[str, Any]] = []
            for evidence in evidence_items:
                if not isinstance(evidence, dict):
                    raise ValueError("Every evidence item must be an object")
                result = _audit_evidence(
                    evidence,
                    arxiv_id=arxiv_id,
                    inherited_pdf_url=str(item.get("pdf_url") or ""),
                    cached_pages=pages,
                )
                audited.append(result)
                evidence_checked += 1
                valid_evidence += int(result["valid"])

            paper_valid = not paper_issues and bool(audited) and all(result["valid"] for result in audited)
            paper_results.append({
                "arxiv_id": arxiv_id,
                "valid": paper_valid,
                "issues": paper_issues,
                "evidence": audited,
            })

        return {
            "tool": "audit_arxiv_citations",
            "valid": bool(paper_results) and all(item["valid"] for item in paper_results),
            "papers_checked": len(paper_results),
            "evidence_checked": evidence_checked,
            "valid_evidence": valid_evidence,
            "paper_results": paper_results,
            "audit_policy": "Every excerpt must match its claimed page in the local paper_text cache.",
        }
    except Exception as exc:
        return err("audit_arxiv_citations", exc)
