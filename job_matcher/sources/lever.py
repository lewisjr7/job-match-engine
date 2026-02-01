# job_matcher/sources/lever.py
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

import requests

from job_matcher.sources.base import JobSource


_REMOTE_RE = re.compile(r"\b(remote|work from home|wfh|distributed|anywhere|telecommute)\b", re.IGNORECASE)
_HYBRID_RE = re.compile(r"\b(hybrid)\b", re.IGNORECASE)


def _safe_str(x: Any) -> str:
    return x.strip() if isinstance(x, str) else ""


def _flatten_parts(parts: List[str]) -> str:
    # de-dupe while preserving order
    out: List[str] = []
    seen = set()
    for p in parts:
        p = _safe_str(p)
        if not p:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return " | ".join(out)


def _detect_remote(*texts: str) -> bool:
    blob = " ".join([t for t in texts if t]).lower()
    return bool(_REMOTE_RE.search(blob))


def _detect_hybrid(*texts: str) -> bool:
    blob = " ".join([t for t in texts if t]).lower()
    return bool(_HYBRID_RE.search(blob))


def _ms_to_iso(ms: Any) -> Optional[str]:
    """
    Lever uses epoch milliseconds for createdAt/updatedAt.
    Convert to ISO-8601 UTC for consistent sorting and CSV friendliness.
    """
    if ms is None:
        return None
    try:
        # Some payloads might be strings; coerce safely
        ms_int = int(ms)
        if ms_int <= 0:
            return None
        return datetime.fromtimestamp(ms_int / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None


class LeverSource(JobSource):
    """
    Fetch postings from Lever's public endpoint:
      https://api.lever.co/v0/postings/{company}?mode=json
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

            loc_struct = _safe_str(categories.get("location"))
            team = _safe_str(categories.get("team"))
            dept = _safe_str(categories.get("department"))
            commitment = _safe_str(categories.get("commitment"))

            workplace_type = _safe_str(job.get("workplaceType"))  # sometimes: "remote", "hybrid", "onsite"
            desc_plain = _safe_str(job.get("descriptionPlain"))
            desc_html = _safe_str(job.get("description"))

            created_at = _ms_to_iso(job.get("createdAt"))
            updated_at = _ms_to_iso(job.get("updatedAt"))
            posted_at = created_at  # Lever doesn't always have a distinct "posted" timestamp

            # Build normalized location string
            parts: List[str] = []
            if loc_struct:
                parts.append(loc_struct)
            if workplace_type:
                parts.append(workplace_type)
            if commitment:
                parts.append(commitment)

            # Remote/hybrid detection: use title + description + structured bits
            is_remote = _detect_remote(loc_struct, workplace_type, commitment, title, desc_plain, desc_html)
            is_hybrid = _detect_hybrid(loc_struct, workplace_type, commitment, title, desc_plain, desc_html)

            # Make "location" more useful to your matcher:
            # If it's remote/hybrid, ensure the word "remote"/"hybrid" appears.
            if is_remote and "remote" not in " ".join(parts).lower():
                parts.append("remote")
            if is_hybrid and "hybrid" not in " ".join(parts).lower():
                parts.append("hybrid")

            location_norm = _flatten_parts(parts) or loc_struct or workplace_type or ""

            # Prefer plain description; fall back to HTML
            content = desc_plain or desc_html or ""

            jobs.append(
                {
                    "id": job_id,
                    "title": title,
                    "company": self.company,
                    "location": location_norm,
                    "team": team,
                    "department": dept,
                    "commitment": commitment,
                    "url": hosted_url,
                    "source": "lever",

                    # Keep both fields for compatibility:
                    # - matching.py reads job.get("content") or job.get("description")
                    "content": content,
                    "description": content,

                    # ✅ normalized ISO strings
                    "posted_at": posted_at,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

        return jobs
