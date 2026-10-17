"""Page-aware structural and recursive text chunking."""
from dataclasses import dataclass
import re


_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_ARTICLE_PATTERN = re.compile(
    r"(?im)^\s*((?:article|chapitre|section)\s+[\w.-]+[^\n]*)\s*$")


@dataclass(frozen=True)
class Page:
    number: int
    text: str


@dataclass(frozen=True)
class Chunk:
    content: str
    article: str | None
    page_start: int
    page_end: int
    token_count: int


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text)


def _clean(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _split_paragraph(paragraph: str, max_tokens: int,
                     overlap_tokens: int) -> list[str]:
    words = _tokens(paragraph)
    if len(words) <= max_tokens:
        return [paragraph]
    result = []
    start = 0
    step = max_tokens - overlap_tokens
    while start < len(words):
        result.append(" ".join(words[start:start + max_tokens]))
        start += step
    return result


def _article_for(text: str, current: str | None) -> tuple[str | None, str]:
    match = _ARTICLE_PATTERN.match(text)
    if match:
        return match.group(1).strip(), text[match.end():].strip()
    return current, text


def chunk_pages(pages: list[Page], contract_id: str | None,
                max_tokens: int = 450, overlap_tokens: int = 60,
                formula: str | None = None,
                global_scope: bool = False) -> list[Chunk]:
    if max_tokens < 1 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("Chunk size must be positive and exceed its overlap")
    scopes = sum((contract_id is not None, formula is not None, global_scope))
    if scopes != 1:
        raise ValueError("Choose exactly one contract, formula, or global scope")

    chunks: list[Chunk] = []
    current_article: str | None = None
    if contract_id is not None:
        context = f"Contrat {contract_id}"
    elif formula is not None:
        context = f"Formule {formula}"
    else:
        context = "Document général PrediCare"

    for page in pages:
        section_lines: list[str] = []

        def flush_section() -> None:
            if not section_lines:
                return
            body = " ".join(section_lines)
            for piece in _split_paragraph(body, max_tokens, overlap_tokens):
                prefix = f"[{context}"
                if current_article:
                    prefix += f" > {current_article}"
                prefix += "] "
                content = prefix + piece
                chunks.append(Chunk(
                    content=content,
                    article=current_article,
                    page_start=page.number,
                    page_end=page.number,
                    token_count=len(_tokens(content)),
                ))

        for line in _clean(page.text).splitlines():
            article, body = _article_for(line, current_article)
            if _ARTICLE_PATTERN.match(line):
                flush_section()
                section_lines.clear()
                current_article = article
            if body:
                section_lines.append(body)
        flush_section()
    return chunks
