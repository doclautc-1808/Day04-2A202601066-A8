from __future__ import annotations

from typing import Any

from tools._shared import domain


def _src(item: dict[str, Any]) -> str:
    src = item.get("source") or domain(item.get("url", ""))
    url = item.get("url") or ""
    return f"[{src}]({url})" if url else (src or "")


def _bullet(item: dict[str, Any]) -> str:
    text = (item.get("summary") or item.get("title") or "").strip().replace("\n", " ")
    if len(text) > 280:
        text = text[:277] + "..."
    return f"- {text} - {_src(item)}"


def _field(item: dict[str, Any], name: str) -> str:
    value = item.get(name)
    return str(value).strip() if value else "Chưa đủ bằng chứng để kết luận."


def _paper_citation(item: dict[str, Any], evidence: dict[str, Any]) -> str:
    arxiv_id = item.get("arxiv_id") or "arXiv"
    page = evidence.get("page_number")
    pdf_url = evidence.get("pdf_url") or item.get("pdf_url") or item.get("url") or ""
    if page and pdf_url:
        return f"[arXiv {arxiv_id}, p. {page}]({pdf_url}#page={page})"
    if pdf_url:
        return f"[arXiv {arxiv_id}]({pdf_url})"
    return f"arXiv {arxiv_id}"


def _paper_scout(items: list[dict[str, Any]], headline: str) -> str:
    parts = [f"# {headline or 'Research Paper Scout'}", "", "> Nguồn: arXiv preprints; không mặc định đã qua peer review.", ""]
    for index, item in enumerate(items[:10], start=1):
        title = item.get("title") or f"Paper {index}"
        authors = item.get("authors") or []
        author_text = ", ".join(str(author) for author in authors) if isinstance(authors, list) else str(authors)
        parts += [
            f"## {index}. {title}",
            "",
            f"- **Tác giả:** {author_text or 'Không có metadata'}",
            f"- **Vấn đề:** {_field(item, 'problem')}",
            f"- **Phương pháp:** {_field(item, 'method')}",
            f"- **Kết quả:** {_field(item, 'result')}",
            f"- **Hạn chế:** {_field(item, 'limitation')}",
            f"- **Khả năng áp dụng:** {_field(item, 'implementation_relevance')}",
        ]
        evidence = item.get("evidence") or []
        if evidence:
            parts += ["", "### Dẫn chứng PDF", ""]
            for passage in evidence[:5]:
                excerpt = " ".join(str(passage.get("excerpt") or "").split())
                if len(excerpt) > 500:
                    excerpt = excerpt[:497] + "..."
                parts.append(f'- “{excerpt}” — {_paper_citation(item, passage)}')
        else:
            parts += ["", "- **Dẫn chứng PDF:** Không có; không sử dụng abstract để thay thế.", ""]
        parts.append("")
    return "\n".join(parts).strip()


def render_digest(items: list[dict[str, Any]] | None = None, template: str = "sections", headline: str = "") -> dict[str, Any]:
    items = items or []
    if template == "paper_scout":
        markdown = _paper_scout(items, headline)
    elif template == "brief":
        markdown = (f"**{headline}**\n\n" if headline else "") + "\n".join(_bullet(item) for item in items[:5])
    elif template == "bullets":
        markdown = "\n".join(_bullet(item) for item in items)
    elif template == "thread":
        markdown = "\n\n".join(f"{index + 1}/ {_bullet(item)[2:]}" for index, item in enumerate(items))
    elif template == "daily_ai_vn":
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            groups.setdefault(item.get("section", "Tin chính"), []).append(item)
        parts = [f"**{headline or 'Tin tức hôm nay'}**", ""]
        for section, section_items in groups.items():
            parts += [f"**{section}**", *[_bullet(item) for item in section_items], ""]
        markdown = "\n".join(parts)
    else:
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            groups.setdefault(item.get("section", "Tổng hợp"), []).append(item)
        parts = ([f"# {headline}", ""] if headline else [])
        for section, section_items in groups.items():
            parts += [f"## {section}", *[_bullet(item) for item in section_items], ""]
        markdown = "\n".join(parts)
    return {"tool": "render_digest", "template": template, "markdown": markdown, "item_count": len(items)}
