import requests
from typing import List, Dict, Optional

from job_matcher.sources.base import JobSource


class LeverSource(JobSource):
    def __init__(self, company: Optional[str] = None):
        self.company = company

    def fetch_jobs(self) -> List[Dict]:
        if not self.company:
            return []

        url = f"https://api.lever.co/v0/postings/{self.company}?mode=json"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        jobs = []
        for job in data:
            jobs.append(
                {
                    "id": job.get("id"),
                    "title": job.get("text"),
                    "company": self.company,
                    "location": job.get("categories", {}).get("location"),
                    "team": job.get("categories", {}).get("team"),
                    "description": job.get("descriptionPlain"),
                    "url": job.get("hostedUrl"),
                    "source": "lever",
                }
            )

        return jobs
