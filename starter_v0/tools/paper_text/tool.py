from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from tools._shared import ROOT, TIMEOUT, err, fold_text, rate_limit, terms


ARXIV_DIR = ROOT / "arxiv_papers"
ARXIV_MIN_INTERVAL_SECONDS = 3.0
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PAGES_TO_SCAN = 200
_MODERN_ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$", re.IGNORECASE)
_LEGACY_ARXIV_ID = re.compile(r"^[a-z][a-z0-9.-]+/\d{7}(?:v\d+)?$", re.IGNORECASE)


def _arxiv_user_agent() -> str:
    return os.getenv("ARXIV_USER_AGENT", "AI20k-Day04-Research-Agent/1.0 (educational lab; contact: local)")


def _rate_limit_arxiv() -> None:
    rate_limit("arxiv", ARXIV_MIN_INTERVAL_SECONDS)


def _arxiv_id(value: str) -> str:
    raw = unquote((value or "").strip())
    if not raw:
        raise ValueError("An arXiv ID or URL is required")

    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
            raise ValueError("Only arxiv.org URLs are accepted")
        candidate = parsed.path.strip("/")
        for prefix in ("abs/", "pdf/"):
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix):]
                break
        if candidate.endswith(".pdf"):
            candidate = candidate[:-4]
    else:
        candidate = raw.removeprefix("arXiv:").removeprefix("arxiv:")

    candidate = candidate.strip("/")
    if not (_MODERN_ARXIV_ID.fullmatch(candidate) or _LEGACY_ARXIV_ID.fullmatch(candidate)):
        raise ValueError("Invalid arXiv ID or URL")
    return candidate


def _cache_stem(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_")


def _valid_cached_pdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 5:
        return False
    with path.open("rb") as file:
        return file.read(5) == b"%PDF-"


def _download_arxiv_pdf(arxiv_url: str) -> tuple[str, Path, str, bool]:
    arxiv_id = _arxiv_id(arxiv_url)
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    ARXIV_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARXIV_DIR / f"{_cache_stem(arxiv_id)}.pdf"
    if _valid_cached_pdf(output_path):
        return arxiv_id, output_path, pdf_url, True

    _rate_limit_arxiv()
    response = requests.get(pdf_url, headers={"User-Agent": _arxiv_user_agent()}, timeout=TIMEOUT, stream=True)
    response.raise_for_status()
    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_PDF_BYTES:
        raise ValueError(f"arXiv PDF exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MB limit")

    partial_path = output_path.with_suffix(".pdf.part")
    downloaded = 0
    try:
        with partial_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > MAX_PDF_BYTES:
                    raise ValueError(f"arXiv PDF exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MB limit")
                file.write(chunk)
        if not _valid_cached_pdf(partial_path):
            raise ValueError("arXiv response is not a valid PDF")
        partial_path.replace(output_path)
    finally:
        if partial_path.exists():
            partial_path.unlink()
    return arxiv_id, output_path, pdf_url, False


def _extract_pdf_pages(pdf_path: Path, pages_limit: int) -> tuple[list[dict[str, Any]], int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf first: pip install pypdf") from exc

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    pages_to_read = min(max(1, pages_limit), page_count, MAX_PAGES_TO_SCAN)
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages[:pages_to_read]):
        text = page.extract_text() or ""
        pages.append({"page_number": index + 1, "text": text})
    return pages, page_count


def _compact_text(text: str) -> str:
    return " ".join((text or "").split())


def _focus_excerpt(text: str, focus_query: str, limit: int) -> str:
    compact = _compact_text(text)
    if len(compact) <= limit:
        return compact

    folded = fold_text(compact)
    positions = [folded.find(term) for term in terms(focus_query)]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - limit // 3)
    end = min(len(compact), start + limit)
    if end - start < limit:
        start = max(0, end - limit)
    excerpt = compact[start:end].strip()
    if start:
        excerpt = "…" + excerpt
    if end < len(compact):
        excerpt += "…"
    return excerpt


def _select_evidence(
    pages: list[dict[str, Any]],
    *,
    focus_query: str,
    max_evidence: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    available = [page for page in pages if _compact_text(page.get("text", ""))]
    if not available:
        return []

    query_terms = terms(focus_query)
    phrase = fold_text(focus_query).strip()
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for page in available:
        folded = fold_text(page["text"])
        term_hits = sum(folded.count(term) for term in query_terms)
        phrase_bonus = 5 if phrase and phrase in folded else 0
        scored.append((term_hits + phrase_bonus, -int(page["page_number"]), page))

    if focus_query.strip():
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = [item for item in scored if item[0] > 0][:max_evidence]
        if not selected:
            return []
    else:
        selected = scored[:max_evidence]

    per_excerpt = max(80, min(1200, max_chars // max(1, len(selected)) - 40))
    evidence: list[dict[str, Any]] = []
    for score, _, page in selected:
        evidence.append({
            "page_number": page["page_number"],
            "excerpt": _focus_excerpt(page["text"], focus_query, per_excerpt),
            "match_score": score if focus_query.strip() else None,
        })
    return evidence


def _write_text_cache(path: Path, pages: list[dict[str, Any]]) -> None:
    content = "\n\n".join(
        f"--- Page {page['page_number']} ---\n{page['text'].strip()}"
        for page in pages
        if page["text"].strip()
    )
    path.write_text(content, encoding="utf-8")


def get_arxiv_paper_text(
    arxiv_url: str = "",
    max_pages: int = 5,
    max_chars: int = 8000,
    focus_query: str = "",
    max_evidence: int = 5,
) -> dict[str, Any]:
    try:
        arxiv_id, pdf_path, pdf_url, cached = _download_arxiv_pdf(arxiv_url)
        max_pages = max(1, min(int(max_pages or 5), 50))
        max_chars = max(1000, min(int(max_chars or 8000), 20000))
        max_evidence = max(1, min(int(max_evidence or 5), 10))
        pages_limit = MAX_PAGES_TO_SCAN if focus_query.strip() else max_pages
        pages, page_count = _extract_pdf_pages(pdf_path, pages_limit=pages_limit)
        evidence = _select_evidence(
            pages,
            focus_query=focus_query,
            max_evidence=max_evidence if focus_query.strip() else min(max_pages, max_evidence),
            max_chars=max_chars,
        )
        if not evidence:
            if focus_query.strip():
                raise RuntimeError(
                    "No extractable PDF passage matched focus_query; OCR and abstract fallback are disabled"
                )
            raise RuntimeError("The PDF contains no extractable text; OCR and abstract fallback are disabled")

        for item in evidence:
            item["pdf_url"] = pdf_url
            item["citation"] = f"[arXiv {arxiv_id}, p. {item['page_number']}]({pdf_url}#page={item['page_number']})"

        txt_path = pdf_path.with_suffix(".txt")
        _write_text_cache(txt_path, pages)
        combined_excerpt = "\n\n".join(
            f"[Page {item['page_number']}] {item['excerpt']}" for item in evidence
        )
        return {
            "tool": "get_arxiv_paper_text",
            "arxiv_id": arxiv_id,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": pdf_url,
            "pdf_path": str(pdf_path),
            "txt_path": str(txt_path),
            "cached": cached,
            "page_count": page_count,
            "pages_read": len(pages),
            "pages_selected": [item["page_number"] for item in evidence],
            "scan_truncated": page_count > len(pages),
            "focus_query": focus_query,
            "chars_returned": len(combined_excerpt),
            "evidence": evidence,
            "source_note": "Evidence was extracted from the arXiv PDF. arXiv preprints are not automatically peer reviewed.",
            "items": [{
                "title": f"arXiv paper {arxiv_id}",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": pdf_url,
                "arxiv_id": arxiv_id,
                "source": "arxiv.org",
                "summary": f"Extracted {len(evidence)} page-aware PDF passages for: {focus_query or 'the requested first pages'}.",
            }],
        }
    except Exception as exc:
        return err("get_arxiv_paper_text", exc)
