# job_matcher/matching.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from job_matcher.scoring import calculate_match_score
from job_matcher.utils import html_to_text


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def _parse_dt(x) -> float:
    """
    Returns a sortable timestamp (seconds). Works with:
    - ISO strings: 2026-01-31T...
    - Lever ms ints: 1738...
    - None
    """
    if x is None:
        return 0.0
    # Lever sometimes stores epoch ms in raw fields
    if isinstance(x, (int, float)):
        # assume ms if huge
        if x > 10_000_000_000:
            return float(x) / 1000.0
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return 0.0
        # ISO-ish
        try:
            # handle trailing Z
            s = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s).timestamp()
        except Exception:
            return 0.0
    return 0.0

def _job_dedupe_key(j: dict) -> str:
    url = (j.get("url") or "").strip()
    if url:
        return f"url::{url}"

    source = _norm(j.get("source") or "")
    company = _norm(j.get("company") or "")

    jid = (j.get("id") or "").strip()
    if jid:
        return f"id::{source}::{company}::{jid}"

    title = _norm(j.get("title") or "")
    loc = _norm(j.get("location") or j.get("location_name") or "")
    return f"fuzzy::{source}::{company}::{title}::{loc}"

def _job_quality_score(j: dict) -> Tuple[int, float, int]:
    """
    Higher is better:
    1) longer text content
    2) newer updated/created
    3) has id
    """
    content = j.get("content") or j.get("description") or ""
    text_len = len(str(content))
    newest = max(
        _parse_dt(j.get("updated_at")),
        _parse_dt(j.get("created_at")),
        _parse_dt(j.get("updatedAt")),
        _parse_dt(j.get("createdAt")),
    )
    has_id = 1 if (j.get("id") or "").strip() else 0
    return (text_len, newest, has_id)

def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    """
    Deduplicate by stable key and keep the best-quality record.
    """
    best_by_key: dict[str, dict] = {}
    for j in jobs:
        if not isinstance(j, dict):
            continue
        k = _job_dedupe_key(j)
        prev = best_by_key.get(k)
        if prev is None:
            best_by_key[k] = j
            continue
        if _job_quality_score(j) > _job_quality_score(prev):
            best_by_key[k] = j
    return list(best_by_key.values())

# ----------------------------
# IO
# ----------------------------

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
        if not (fp.name.startswith("greenhouse_") or fp.name.startswith("lever_")):
            continue
    return jobs


# ----------------------------
# Title filters
# ----------------------------

def is_title_excluded(title: str, exclude_keywords: List[str]) -> bool:
    if not title or not exclude_keywords:
        return False
    t = title.lower()
    return any((kw or "").lower() in t for kw in exclude_keywords)


def is_title_included(title: str, include_keywords: List[str]) -> bool:
    if not include_keywords:
        return True
    if not title:
        return False
    t = title.lower()
    return any((kw or "").lower() in t for kw in include_keywords)


# ----------------------------
# Location helpers
# ----------------------------

def _normalize(s: Optional[str]) -> str:
    return (s or "").strip().lower()


_REMOTE_TOKENS = [
    "remote",
    "work from home",
    "wfh",
    "distributed",
    "anywhere",
    "home-based",
    "telecommute",
]

_US_STATE_ABBRS = {
    "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in","ia","ks","ky","la","me",
    "md","ma","mi","mn","ms","mo","mt","ne","nv","nh","nj","nm","ny","nc","nd","oh","ok","or","pa",
    "ri","sc","sd","tn","tx","ut","vt","va","wa","wv","wi","wy","dc",
}

_US_STATE_NAMES = {
    "alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia",
    "hawaii","idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts",
    "michigan","minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey",
    "new mexico","new york","north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island",
    "south carolina","south dakota","tennessee","texas","utah","vermont","virginia","washington","west virginia",
    "wisconsin","wyoming","district of columbia","washington dc","d.c.",
}


def is_remote(text: str) -> bool:
    t = _normalize(text)
    return any(tok in t for tok in _REMOTE_TOKENS)


def _has_explicit_us_token(text: str) -> bool:
    """
    Catch explicit US markers (incl. U.S. / (U.S.)).
    """
    t = f" {_normalize(text)} "
    if " united states " in t or " united states of america " in t or " usa " in t:
        return True

    # u.s., u.s, (u.s.)
    if re.search(r"(?<![a-z])u\.?s\.?(?![a-z])", t):
        return True

    # standalone 'us' (avoid 'business')
    if re.search(r"(?<![a-z])us(?![a-z])", t):
        return True

    return False


def _has_us_state_abbr(text: str) -> bool:
    """
    IMPORTANT FIX:
    Only treat state abbreviations as valid if they appear in ORIGINAL TEXT
    as uppercase tokens (e.g., 'TX', 'CA', 'WI').
    This prevents the word 'or' from being interpreted as Oregon.
    """
    original = text or ""
    hits = re.findall(r"(?:^|[\s,|/(\-)])([A-Z]{2})(?:$|[\s,|/)\-])", f" {original} ")
    return any(h.lower() in _US_STATE_ABBRS for h in hits)


def _has_us_state_name(text: str) -> bool:
    t = f" {_normalize(text)} "
    return any(f" {name} " in t for name in _US_STATE_NAMES)


def _looks_like_us_location(text: str) -> bool:
    """
    US signals (strict enough to reject 'Remote Poland' / 'Remote Spain' / Canada Remote),
    but permissive enough for 'Texas | remote' and 'Remote (U.S.)'.
    """
    if _has_explicit_us_token(text):
        return True
    if _has_us_state_abbr(text):
        return True
    if _has_us_state_name(text):
        return True
    return False


def _match_states(text: str, allowed_states: List[str]) -> bool:
    if not allowed_states:
        return False

    t = f" {_normalize(text)} "
    for st in allowed_states:
        s = _normalize(st)
        if not s:
            continue

        # 2-letter abbreviation boundary match (case-insensitive)
        if len(s) == 2 and re.search(rf"(?:^|[\s,|/(\-)]){re.escape(s)}(?:$|[\s,|/)\-])", t):
            return True

        # full-name substring match
        if f" {s} " in t or s in t:
            return True

    return False


def _match_cities(text: str, allowed_cities: List[str]) -> bool:
    if not allowed_cities:
        return False
    t = _normalize(text)
    for city in allowed_cities:
        c = _normalize(city)
        if c and c in t:
            return True
    return False


# ----------------------------
# Location policy
# ----------------------------

def location_matches_policy(
    *,
    job_location_text: str,
    location_filters: Dict[str, Any] | None,
    legacy_locations: List[str] | None,
    legacy_remote_only: bool | None,
) -> bool:
    loc = _normalize(job_location_text)

    lf = location_filters or {}
    has_new = bool(lf)

    # ----------------------------
    # NEW MODE (location_filters)
    # ----------------------------
    if has_new:
        allow_remote = bool(lf.get("allow_remote", True))

        allowed_countries = [
            _normalize(x) for x in (lf.get("allowed_countries") or []) if _normalize(x)
        ]
        allowed_states = [
            _normalize(x) for x in (lf.get("allowed_states") or []) if _normalize(x)
        ]
        allowed_cities = [
            _normalize(x) for x in (lf.get("allowed_cities") or []) if _normalize(x)
        ]

        wants_us_only = any(x in ("united states", "usa", "us") for x in allowed_countries)
        job_is_remote = is_remote(loc)

        # REMOTE JOBS
        if job_is_remote:
            if not allow_remote:
                return False
            if wants_us_only:
                return _looks_like_us_location(job_location_text)
            if allowed_countries:
                return any(c in loc for c in allowed_countries)
            return True

        # NON-REMOTE JOBS
        if wants_us_only and not _looks_like_us_location(job_location_text):
            return False

        # City/state filters apply only to NON-REMOTE
        if allowed_states or allowed_cities:
            return _match_cities(loc, allowed_cities) or _match_states(loc, allowed_states)

        return True

    # ----------------------------
    # LEGACY MODE
    # ----------------------------
    wanted = [_normalize(x) for x in (legacy_locations or []) if _normalize(x)]
    remote_only = bool(legacy_remote_only or False)

    if remote_only and not is_remote(loc):
        return False
    if not wanted:
        return True

    wants_us = any(x in ("united states", "usa", "us") for x in wanted)
    wants_remote = any("remote" in x for x in wanted)

    if wants_us and not _looks_like_us_location(job_location_text):
        return False
    if wants_remote and not is_remote(loc):
        return False

    if wants_us or wants_remote:
        return True

    return any(x in loc for x in wanted)


# ----------------------------
# Scoring pipeline
# ----------------------------

def score_jobs(
    resume_text: str,
    jobs: List[Dict[str, Any]],
    skills: Dict[str, List[str]],
    weights: Dict[str, float],
    filters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    before = len(jobs)
    jobs = dedupe_jobs(jobs)
    after = len(jobs)
    if after != before:
        print(f"[DEBUG] Deduped jobs: {before} -> {after} (removed {before-after})")
    keywords = filters.get("keywords", []) or []
    min_pct = int(filters.get("min_match_percent", 0))

    include_title_keywords = filters.get("include_title_keywords", []) or []
    exclude_title_keywords = filters.get("exclude_title_keywords", []) or []

    allowed_companies = set(
        c.strip().lower()
        for c in (filters.get("companies", []) or [])
        if isinstance(c, str) and c.strip()
    )

    location_filters = filters.get("location_filters") or {}
    legacy_locations = filters.get("locations", []) or []
    legacy_remote_only = bool(filters.get("remote_only", False))

    results: List[Dict[str, Any]] = []

    for job in jobs:
        company = (job.get("company") or "").strip()
        source = (job.get("source") or "").strip().lower()

        if source == "greenhouse" and allowed_companies and company.lower() not in allowed_companies:
            continue

        title = (job.get("title") or "").strip()
        if not is_title_included(title, include_title_keywords):
            continue
        if is_title_excluded(title, exclude_title_keywords):
            continue

        content = job.get("content") or job.get("description") or ""
        content_text = html_to_text(content) if ("<" in str(content)) else (content or "")

        location = (job.get("location") or job.get("location_name") or "").strip()
        location_text = location or f"{title} {content_text}"

        if not location_matches_policy(
            job_location_text=location_text,
            location_filters=location_filters,
            legacy_locations=legacy_locations,
            legacy_remote_only=legacy_remote_only,
        ):
            continue

        url = (job.get("url") or "").strip()
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
                "source": job.get("source", ""),
                "company": company,
                "location": location,
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
