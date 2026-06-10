from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable, Optional


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def generate_paper_id(title: str, authors: Iterable[str] = (), year: Optional[int] = None) -> str:
    """Create a stable, readable paper id from title, first author and year."""
    clean_title = " ".join(str(title or "").split())
    if not clean_title:
        raise ValueError("title is required to generate a paper_id")

    author = _first_author_token(authors)
    year_part = str(year) if year else "undated"
    slug = _slugify_title(clean_title)
    digest = hashlib.sha1(clean_title.casefold().encode("utf-8")).hexdigest()[:8]
    return f"{year_part}-{author}-{slug}-{digest}"


def _first_author_token(authors: Iterable[str]) -> str:
    for raw_author in authors:
        author = str(raw_author).strip()
        if author:
            token = re.split(r"[\s,]+", author)[-1]
            return _slugify(token, fallback="unknown")
    return "unknown"


def _slugify_title(title: str) -> str:
    words = []
    for token in re.findall(r"[A-Za-z0-9]+", _ascii_fold(title).lower()):
        if token not in _STOPWORDS:
            words.append(token)
        if len(words) >= 8:
            break
    return "-".join(words) or "untitled"


def _slugify(text: str, fallback: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", _ascii_fold(text).lower()).strip("-")
    return token or fallback


def _ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

