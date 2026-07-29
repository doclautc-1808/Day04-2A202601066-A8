from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import requests

from tools._shared import TIMEOUT, err, rate_limit


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_MIN_INTERVAL_SECONDS = 3.0
_MODERN_ARXIV_ID = r"\d{4}\.\d{4,5}(?:v\d+)?"
_LEGACY_ARXIV_ID = r"[a-z][a-z0-9.-]+/\d{7}(?:v\d+)?"


def _arxiv_user_agent() -> str:
    return os.getenv("ARXIV_USER_AGENT", "AI20k-Day04-Research-Agent/1.0 (educational lab; contact: local)")


def _rate_limit_arxiv() -> None:
    rate_limit("arxiv", ARXIV_MIN_INTERVAL_SECONDS)


def _arxiv_get(url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
    last_response: requests.Response | None = None
    for attempt in range(3):
        _rate_limit_arxiv()
        response = requests.get(url, params=params, headers={"User-Agent": _arxiv_user_agent()}, timeout=TIMEOUT)
        last_response = response
        if response.status_code != 429:
            return response
        time.sleep(3 * (attempt + 1))
    assert last_response is not None
    return last_response


def _arxiv_search_query(query: str) -> str:
    cleaned = " ".join((query or "").split())
    if not cleaned:
        raise ValueError("A non-empty arXiv search query is required")
    if ":" in cleaned:
        return cleaned
    terms = [term for term in re.findall(r"[A-Za-z0-9_\\-]+", cleaned) if len(term) > 1]
    return " AND ".join(f"all:{term}" for term in terms[:8]) or cleaned


def _arxiv_id(value: str) -> str:
    raw = (value or "").strip()
    parsed = urlparse(raw)
    candidate = parsed.path if parsed.scheme else raw
    match = re.search(rf"({_MODERN_ARXIV_ID}|{_LEGACY_ARXIV_ID})", candidate, re.IGNORECASE)
    return match.group(1) if match else ""


def _entry_text(entry: ET.Element, path: str, namespaces: dict[str, str]) -> str:
    node = entry.find(path, namespaces)
    return (node.text or "").strip() if node is not None and node.text else ""


def arxiv_search(query: str = "", max_results: int = 5, sort_by: str = "relevance") -> dict[str, Any]:
    try:
        max_results = max(1, min(int(max_results or 5), 10))
        sort_by = sort_by if sort_by in {"relevance", "lastUpdatedDate", "submittedDate"} else "relevance"
        params = {
            "search_query": _arxiv_search_query(query),
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }
        response = _arxiv_get(ARXIV_API_URL, params=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        namespaces = {
            "atom": "http://www.w3.org/2005/Atom",
            "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        total_node = root.find(".//opensearch:totalResults", namespaces)
        entries: list[dict[str, Any]] = []
        for entry in root.findall(".//atom:entry", namespaces):
            abs_url = _entry_text(entry, "./atom:id", namespaces)
            arxiv_id = _arxiv_id(abs_url)
            if not arxiv_id:
                continue
            links = [{"rel": link.get("rel"), "href": link.get("href"), "title": link.get("title")} for link in entry.findall("./atom:link", namespaces)]
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            primary = entry.find("./arxiv:primary_category", namespaces)
            summary = _entry_text(entry, "./atom:summary", namespaces).replace("\n", " ")
            entries.append({
                "arxiv_id": arxiv_id,
                "title": _entry_text(entry, "./atom:title", namespaces).replace("\n", " "),
                "summary": " ".join(summary.split()),
                "authors": [_entry_text(author, "./atom:name", namespaces) for author in entry.findall("./atom:author", namespaces)],
                "published": _entry_text(entry, "./atom:published", namespaces),
                "updated": _entry_text(entry, "./atom:updated", namespaces),
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": pdf_url,
                "source": "arxiv.org",
                "source_type": "preprint",
                "peer_review_status": "unknown_from_arxiv",
                "primary_category": primary.get("term") if primary is not None else None,
                "categories": [cat.get("term") for cat in entry.findall("./atom:category", namespaces)],
            })
        return {
            "tool": "arxiv_search",
            "query": query,
            "api_query": params["search_query"],
            "total_results": int(total_node.text) if total_node is not None and total_node.text else None,
            "items": entries,
            "selection_note": (
                "Results use arXiv relevance by default. For a balanced shortlist, prefer topical match first "
                "and use the updated date as a tie-breaker."
            ),
            "source_note": "arXiv records are preprints and are not automatically peer reviewed.",
            "rate_limit_note": "arXiv may return 429 if called too frequently; this tool waits at least 3 seconds between requests in-process.",
        }
    except Exception as exc:
        return err("arxiv_search", exc)
