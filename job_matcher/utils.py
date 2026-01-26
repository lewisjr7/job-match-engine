# job_matcher/utils.py
import re
import html
from typing import Iterable, List


_ws_re = re.compile(r"\s+")
_tag_re = re.compile(r"<[^>]+>")


def normalize_text(text: str) -> str:
    """Lowercase and collapse whitespace."""
    if not text:
        return ""
    text = html.unescape(text)
    text = _ws_re.sub(" ", text).strip().lower()
    return text


def html_to_text(maybe_html: str) -> str:
    """
    Strip HTML tags using stdlib-only approach.
    Not perfect, but good enough for ATS descriptions.
    """
    if not maybe_html:
        return ""
    s = html.unescape(maybe_html)
    s = _tag_re.sub(" ", s)
    s = _ws_re.sub(" ", s).strip()
    return s


def unique_lower(items: Iterable[str]) -> List[str]:
    out = []
    seen = set()
    for x in items or []:
        if not x:
            continue
        k = x.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out
