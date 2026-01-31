# job_matcher/discovery/null_provider.py
from typing import List, Dict, Any
from job_matcher.discovery.base import JobDiscovery
from job_matcher.models import JobRef


class NullDiscovery(JobDiscovery):
    """
    A placeholder provider that returns nothing.
    Useful for wiring/testing without adding external dependencies yet.
    """
    def discover(self, query: str, filters: Dict[str, Any]) -> List[JobRef]:
        return []