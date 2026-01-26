import requests
from requests.exceptions import HTTPError
from .base import JobSource

class GreenhouseSource(JobSource):
    def __init__(self, company: str):
        self.company = company

    def fetch_jobs(self):
        list_url = f"https://boards-api.greenhouse.io/v1/boards/{self.company}/jobs"

        try:
            response = requests.get(list_url, timeout=60)

            # Explicitly handle "board not found"
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
        results = []

        for job in jobs:
            try:
                detail_url = f"https://boards-api.greenhouse.io/v1/boards/{self.company}/jobs/{job['id']}"
                detail = requests.get(detail_url, timeout=60)
                detail.raise_for_status()
                detail_json = detail.json()
            except requests.RequestException as e:
                print(f"[WARN] {self.company}: detail fetch failed for {job.get('id')} → {e}")
                continue

            results.append({
                "company": self.company,
                "location": (
                    detail_json.get("location", {}).get("name")
                    or job.get("location", {}).get("name")
                ),
                "title": job.get("title"),
                "content": detail_json.get("content", ""),
                "url": job.get("absolute_url"),
                "updated_at": job.get("updated_at"),
                "created_at": detail_json.get("created_at"),
                "posted_at": detail_json.get("created_at") or job.get("updated_at"),
            })


        return results
