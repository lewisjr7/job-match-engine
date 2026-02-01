# job_matcher/sources/greenhouse.py
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import HTTPError

from job_matcher.sources.base import JobSource


_JOB_ID_RE = re.compile(r"/jobs/(\d+)", re.IGNORECASE)


def _safe_str(x: Any) -> str:
    return x.strip() if isinstance(x, str) else ""


def _extract_id_from_url(url: str) -> Optional[str]:
    m = _JOB_ID_RE.search(url or "")
    return m.group(1) if m else None


def _stable_fallback_id(*parts: str) -> str:
    blob = "|".join([p for p in parts if p]).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()


class GreenhouseSource(JobSource):
    def __init__(self, company: str):
        self.company = company

    def fetch_jobs(self, existing_by_id: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Delta behavior:
        - Fetch list endpoint (cheap)
        - For each job, if we already have same updated_at, reuse the existing record (no detail call)
        - Otherwise fetch detail endpoint and update record
        """
        existing_by_id = existing_by_id or {}

        list_url = f"https://boards-api.greenhouse.io/v1/boards/{self.company}/jobs"

        try:
            response = requests.get(list_url, timeout=60)
            if response.status_code == 404:
                print(f"[SKIP] {self.company}: no Greenhouse board found")
                return []
            response.raise_for_status()
        except HTTPError as e:
            print(f"[ERROR] {self.company}: HTTP error → {e}")
            return []
        except requests.RequestException as e:
            print(f"[ERROR] {self.company}: request failed → {e}")
            return []

        jobs = response.json().get("jobs", [])
        results: List[Dict[str, Any]] = []

        for j in jobs:
            url = _safe_str(j.get("absolute_url") or j.get("url") or "")
            title = _safe_str(j.get("title") or "")

            # ✅ stable id
            job_id = j.get("id")
            if job_id is not None:
                job_id = str(job_id)
            else:
                parsed = _extract_id_from_url(url)
                job_id = parsed if parsed else _stable_fallback_id(self.company, title, url)

            list_updated_at = j.get("updated_at")

            # ✅ DELTA SHORT-CIRCUIT:
            # If we already have this job AND updated_at hasn't changed, reuse old record.
            existing = existing_by_id.get(job_id)
            if existing and (existing.get("updated_at") == list_updated_at) and existing.get("content"):
                results.append(existing)
                continue

            # Else fetch details
            try:
                detail_url = f"https://boards-api.greenhouse.io/v1/boards/{self.company}/jobs/{job_id}"
                detail = requests.get(detail_url, timeout=60)

                if detail.status_code == 404:
                    print(f"[WARN] {self.company}: detail 404 for {job_id} ({url})")
                    continue

                detail.raise_for_status()
                detail_json = detail.json()
            except requests.RequestException as e:
                print(f"[WARN] {self.company}: detail fetch failed for {job_id} → {e}")
                continue

            content_html = detail_json.get("content") or ""
            location = detail_json.get("location")

            if isinstance(location, dict):
                location = _safe_str(location.get("name"))
            else:
                location = _safe_str(location)

            record = {
                "id": job_id,
                "source": "greenhouse",
                "company": self.company,
                "title": title,
                "location": location,
                "content": content_html,
                "url": url,
                "created_at": detail_json.get("created_at"),
                "updated_at": detail_json.get("updated_at") or list_updated_at,
                "posted_at": detail_json.get("created_at") or list_updated_at,
            }

            results.append(record)

        return results
