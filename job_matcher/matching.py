# job_matcher/matching.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from job_matcher.scoring import calculate_match_score
from job_matcher.utils import html_to_text


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

# canonical US signals
_US_TOKENS = [
    "united states",
    "united states of america",
    "usa",
    "u.s.",
    "u.s",
]

# US state abbreviations (lowercase)
_US_STATE_ABBRS = {
    "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in","ia","ks","ky","la","me",
    "md","ma","mi","mn","ms","mo","mt","ne","nv","nh","nj","nm","ny","nc","nd","oh","ok","or","pa",
    "ri","sc","sd","tn","tx","ut","vt","va","wa","wv","wi","wy","dc",
}

# US state names (lowercase)
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


def _looks_like_us_location(location_text: str) -> bool:
    """
    IMPORTANT: Only pass ACTUAL location-ish text here.
    Do NOT pass job descriptions. Job descriptions often contain "About us",
    which will create false positives if we look for "us".
    """
    t = f" {_normalize(location_text)} "
    if not t.strip():
        return False

    # Explicit US tokens
    if any(f" {tok} " in t for tok in _US_TOKENS):
        return True

    # Standalone "US" token (avoid matching "business")
    if re.search(r"(^|[\s,|/(\[])us([\s,|/)\]]|$)", t):
        return True

    # State name present
    for name in _US_STATE_NAMES:
        if f" {name} " in t or f"{name}," in t or f"{name}|" in t or f"{name}/" in t:
            return True

    # State abbreviation token present (TX, CA, WI, etc.)
    # Matches: ", tx", " tx ", "|tx|", "(tx)", "/tx"
    hits = re.findall(r"(?:^|[\s,|/(\[])([a-z]{2})(?:$|[\s,|/)\]])", t)
    return any(h in _US_STATE_ABBRS for h in hits)


def _match_states(text: str, allowed_states: List[str]) -> bool:
    if not allowed_states:
        return False

    t = f" {_normalize(text)} "
    for st in allowed_states:
        s = _normalize(st)
        if not s:
            continue

        # 2-letter abbreviation boundary match
        if len(s) == 2 and re.search(rf"(?:^|[\s,|/(\[])({re.escape(s)})(?:$|[\s,|/)\]])", t):
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


def _extract_location_text(job: Dict[str, Any], title: str) -> str:
    """
    DO NOT use the full job description as a location fallback.
    It contains "About us" and other strings that can trip US detection.

    If location is missing, we only use title as a very weak hint for "remote".
    """
    loc = (job.get("location") or job.get("location_name") or "").strip()
    if loc:
        return loc

    # Weak fallback: title only (helps detect remote sometimes)
    return title.strip()


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

    # We consider "new mode" active if the key exists in filters dict (even if empty dict)
    # But we can only enforce rules if it has meaningful keys.
    has_new = bool(lf)

    # ----------------------------
    # NEW MODE (location_filters)
    # ----------------------------
    if has_new:
        allow_remote = bool(lf.get("allow_remote", True))

        allowed_countries = [_normalize(x) for x in (lf.get("allowed_countries") or []) if _normalize(x)]
        allowed_states = [_normalize(x) for x in (lf.get("allowed_states") or []) if _normalize(x)]
        allowed_cities = [_normalize(x) for x in (lf.get("allowed_cities") or []) if _normalize(x)]

        wants_us_only = any(x in ("united states", "usa", "us") for x in allowed_countries)
        job_is_remote = is_remote(loc)

        # REMOTE jobs
        if job_is_remote:
            if not allow_remote:
                return False

            # If user constrained countries, enforce them.
            # If that includes US, require US signals (state name/abbr also counts).
            if allowed_countries:
                if wants_us_only:
                    return _looks_like_us_location(loc)
                # Otherwise require any allowed country token present
                return any(c in loc for c in allowed_countries)

            # No country constraint -> allow any remote
            return True

        # NON-REMOTE jobs
        if wants_us_only and not _looks_like_us_location(loc):
            return False

        # City/state constraints only apply to NON-REMOTE (so they don't block US-remote)
        if allowed_states or allowed_cities:
            return _match_cities(loc, allowed_cities) or _match_states(loc, allowed_states)

        return True

    # ----------------------------
    # LEGACY MODE (filters.locations + remote_only)
    # ----------------------------
    wanted = [_normalize(x) for x in (legacy_locations or []) if _normalize(x)]
    remote_only = bool(legacy_remote_only or False)

    wants_us = any(x in ("united states", "usa", "us") for x in wanted)
    wants_remote = any("remote" in x for x in wanted)

    # If config wants US but we have no usable location text, reject (prevents "About us" false positives)
    if wants_us and not loc:
        return False

    # If remote_only is enabled, job must be remote
    if remote_only and not is_remote(loc):
        return False

    # If user wants US, enforce US signals (includes state abbreviations/names)
    if wants_us and not _looks_like_us_location(loc):
        return False

    # If user wants remote explicitly, enforce remote
    if wants_remote and not is_remote(loc):
        return False

    # If any legacy constraints existed, and we satisfied them, accept
    if wanted:
        return True

    return True


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
    keywords = filters.get("keywords", []) or []
    min_pct = int(filters.get("min_match_percent", 0))

    include_title_keywords = filters.get("include_title_keywords", []) or []
    exclude_title_keywords = filters.get("exclude_title_keywords", []) or []

    # Greenhouse company allowlist (only enforced for greenhouse jobs)
    allowed_companies = set(
        c.strip().lower()
        for c in (filters.get("companies", []) or [])
        if isinstance(c, str) and c.strip()
    )

    # New location policy block (passed from main.py if you wire it)
    location_filters = filters.get("location_filters") or {}

    # Legacy location fields
    legacy_locations = filters.get("locations", []) or []
    legacy_remote_only = bool(filters.get("remote_only", False))

    results: List[Dict[str, Any]] = []

    for job in jobs:
        company = (job.get("company") or "").strip()
        source = (job.get("source") or "").strip().lower()

        # Enforce allowlist only for greenhouse jobs
        if source == "greenhouse" and allowed_companies and company.lower() not in allowed_companies:
            continue

        title = (job.get("title") or "").strip()

        if not is_title_included(title, include_title_keywords):
            continue
        if is_title_excluded(title, exclude_title_keywords):
            continue

        content = job.get("content") or job.get("description") or ""
        content_text = html_to_text(content) if ("<" in str(content)) else (content or "")

        # Use ONLY location-ish text for location policy (no description fallback)
        location_raw = (job.get("location") or job.get("location_name") or "").strip()
        location_text = _extract_location_text(job, title)

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
                "location": location_raw,  # keep the original field for output (can be empty)
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
