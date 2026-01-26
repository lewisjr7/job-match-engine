# job_matcher/matching.py
import json
from pathlib import Path
from typing import Any, Dict, List

from job_matcher.scoring import calculate_match_score
from job_matcher.utils import html_to_text


def load_raw_jobs(raw_jobs_dir: str = "data/raw_jobs") -> List[Dict[str, Any]]:
    p = Path(raw_jobs_dir)
    if not p.exists():
        return []

    jobs: List[Dict[str, Any]] = []
    for fp in sorted(p.glob("*.json")):
        if fp.name.endswith(".error.json"):
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                jobs.extend(data)
        except Exception:
            continue
    return jobs


def is_title_excluded(title: str, exclude_keywords: List[str]) -> bool:
    if not title or not exclude_keywords:
        return False
    title_lower = title.lower()
    return any((kw or "").lower() in title_lower for kw in exclude_keywords)


def is_title_included(title: str, include_keywords: List[str]) -> bool:
    if not include_keywords:
        return True
    if not title:
        return False
    title_lower = title.lower()
    return any((kw or "").lower() in title_lower for kw in include_keywords)


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def is_remote(text: str) -> bool:
    t = _normalize(text)
    return any(x in t for x in ["remote", "work from home", "wfh", "distributed", "anywhere"])


def is_us(text: str) -> bool:
    t = _normalize(text)
    us_tokens = [
        "united states",
        "u.s.",
        "u.s",
        "usa",
        "us ",
        " united states ",
        "us-remote",
        "us remote",
        "united states of america",
    ]
    return any(tok in t for tok in us_tokens) or t.endswith(" us") or " us)" in t


def location_matches(job_location: str, filters_locations: List[str], remote_only: bool) -> bool:
    loc = _normalize(job_location)
    wanted = [_normalize(x) for x in (filters_locations or []) if _normalize(x)]

    if remote_only and not is_remote(loc):
        return False

    if not wanted:
        return True

    wants_us = any(x in ("united states", "usa", "us") for x in wanted)
    if wants_us and not is_us(loc):
        return False

    wants_remote = any("remote" in x for x in wanted)
    if wants_remote and not is_remote(loc):
        return False

    if wants_us or wants_remote:
        return True

    return any(x in loc for x in wanted)


def score_jobs(
    resume_text: str,
    jobs: List[Dict[str, Any]],
    skills: Dict[str, List[str]],
    weights: Dict[str, float],
    filters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    keywords = filters.get("keywords", [])
    min_pct = int(filters.get("min_match_percent", 0))

    include_title_keywords = filters.get("include_title_keywords", []) or []
    exclude_title_keywords = filters.get("exclude_title_keywords", []) or []

    allowed_companies = set(
        c.strip().lower()
        for c in (filters.get("companies", []) or [])
        if isinstance(c, str) and c.strip()
    )

    locations_filter = filters.get("locations", []) or []
    remote_only = bool(filters.get("remote_only", False))

    results: List[Dict[str, Any]] = []

    for job in jobs:
        company = job.get("company", "") or ""

        if allowed_companies and company.lower() not in allowed_companies:
            continue

        title = job.get("title", "") or ""

        if not is_title_included(title, include_title_keywords):
            continue
        if is_title_excluded(title, exclude_title_keywords):
            continue

        content_html = job.get("content", "") or ""
        content_text = html_to_text(content_html)

        # ✅ Use a single variable for location everywhere
        location = (job.get("location") or job.get("location_name") or "").strip()

        # Fallback if structured location is missing
        location_text = location or f"{title} {content_text}"

        if not location_matches(location_text, locations_filter, remote_only):
            continue

        url = job.get("url", "") or ""
        updated_at = job.get("updated_at")
        created_at = job.get("created_at")
        posted_at = job.get("posted_at") or created_at or updated_at

        breakdown = calculate_match_score(
            resume_text=resume_text,
            job_text=content_text,
            job_title=title,
            skills=skills,
            weights=weights,
            keywords=keywords,
        )

        if breakdown.total_percent < min_pct:
            continue

        results.append(
            {
                "company": company,
                "location": location,  # ✅ now defined
                "title": title,
                "url": url,
                "score_percent": breakdown.total_percent,
                "required_hit": breakdown.required_hit,
                "required_miss": breakdown.required_miss,
                "preferred_hit": breakdown.preferred_hit,
                "keywords_hit": breakdown.keywords_hit,
                "title_hit": breakdown.title_hit,
                "posted_at": posted_at,
                "created_at": created_at,
                "updated_at": updated_at,
                "components": breakdown.components,
                "snippet": (content_text[:260] + "…") if len(content_text) > 260 else content_text,
            }
        )

    results.sort(key=lambda r: r["score_percent"], reverse=True)
    return results
