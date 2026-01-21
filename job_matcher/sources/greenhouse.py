import requests
from .base import JobSource


class GreenhouseSource(JobSource):
    def __init__(self, company: str):
        self.company = company


def fetch_jobs(self):
    url = f"https://boards-api.greenhouse.io/v1/boards/{self.company}/jobs"
    return requests.get(url).json().get("jobs", [])