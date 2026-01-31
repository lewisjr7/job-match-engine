# job_matcher/discovery/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from job_matcher.models import JobRef


class JobDiscovery(ABC):
    """
    Discovery providers turn a title query + filters into job references (JobRef).
    They do NOT fetch full descriptions. Fetchers (sources/*) handle that.
    """

    @abstractmethod
    def discover(self, query: str, filters: Dict[str, Any]) -> List[JobRef]:
        raise NotImplementedError