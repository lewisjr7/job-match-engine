# job_matcher/sources/lever.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests

from job_matcher.sources.base import JobSource


_REMOTE_RE = re.compile(
    r"\b(remote|work from home|wfh|distributed|anywhere)\b", re.IGNORECASE
)
_HYBRID_RE = re.compile(r"\b(hybrid)\b", re.IGNORECASE)


def _safe_str(x: Any) -> str:
    return (x or "").strip() if isinstance(x, str) else ""


def _flatten_list(values: List[str]) -> str:
    cleaned = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    return " | ".join(dict.fromkeys(cleaned))  # de-dupe, preserve order


def _detect_remote(*texts: str) -> bool:
    blob = " ".join([t for t in texts if t]).lower()
    return bool(_REMOTE_RE.search(blob))


def _detect_hybrid(*texts: str) -> bool:
    blob = " ".join([t for t in texts if t]).lower()
    return bool(_HYBRID_RE.search(blob))


class LeverSource(JobSource):
    """
    Fetch postings from Lever's public endpoint:
    https://api.lever.co/v0/postings/{company}?mode=json

    Notes:
    - Lever's structured "categories.location" is often NOT "Remote"
      even when the role is remote/hybrid.
    - We therefore build a normalized 'location' plus 'is_remote' using:
        - categories.location
        - workplaceType (if present)
        - job description text
        - any additional lever fields that may hint remote/hybrid
    """

    def __init__(self, company: Optional[str] = None):
        self.company = _safe_str(company) or None

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        if not self.company:
            return []

        url = f"https://api.lever.co/v0/postings/{self.company}?mode=json"

        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        jobs: List[Dict[str, Any]] = []
        for job in data:
            if not isinstance(job, dict):
                continue

            job_id = _safe_str(job.get("id"))
            title = _safe_str(job.get("text"))
            hosted_url = _safe_str(job.get("hostedUrl"))

            categories = job.get("categories") or {}
            if not isinstance(categories, dict):
                categories = {}

            # Lever structured fields
            loc_struct = _safe_str(categories.get("location"))
            team = _safe_str(categories.get("team"))
            dept = _safe_str(categories.get("department"))
            commitment = _safe_str(categories.get("commitment"))

            # Some Lever accounts include workplaceType / remote flags (not always present)
            workplace_type = _safe_str(job.get("workplaceType"))  # e.g., "remote", "hybrid", "onsite"
            # descriptionPlain is sometimes None; description can be HTML
            desc_plain = _safe_str(job.get("descriptionPlain"))
            desc_html = _safe_str(job.get("description"))

            # Build a richer "location-ish" string
            location_parts: List[str] = []
            if loc_struct:
                location_parts.append(loc_struct)
            if workplace_type:
                location_parts.append(workplace_type)
            # Sometimes commitment/team embed hints like "Remote"
            if commitment:
                location_parts.append(commitment)
            if team:
                location_parts.append(team)
            if dept:
                location_parts.append(dept)

            location_norm = _flatten_list(location_parts)

            # Remote/hybrid detection: look at structured + description
            is_remote = _detect_remote(location_norm, desc_plain, desc_html, title)
            is_hybrid = _detect_hybrid(location_norm, desc_plain, desc_html, title)

            # Normalize to the fields your matcher already expects:
            # - it uses job["content"] and job["location"] / job["location_name"]
            # We provide "content" and "location" explicitly.
            jobs.append(
                {
                    "id": job_id,
                    "title": title,
                    "company": self.company,   # lever "company" slug
                    "location": location_norm or loc_struct,  # best effort
                    "team": team,
                    "department": dept,
                    "commitment": commitment,
                    "workplace_type": workplace_type,
                    "is_remote": is_remote,
                    "is_hybrid": is_hybrid,
                    # Provide both "content" and "description" for compatibility
                    "content": desc_html or desc_plain,
                    "description": desc_plain,
                    "url": hosted_url,
                    "source": "lever",
                    # These may exist in some payloads; keep if present
                    "created_at": job.get("createdAt"),
                    "updated_at": job.get("updatedAt"),
                    "posted_at": job.get("createdAt") or job.get("updatedAt"),
                }
            )

        return jobs
