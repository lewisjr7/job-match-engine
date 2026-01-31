# job_matcher/discovery/__init__.py
from job_matcher.discovery.base import JobDiscovery
from job_matcher.discovery.null_provider import NullDiscovery

__all__ = ["JobDiscovery", "NullDiscovery"]
