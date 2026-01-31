from pydantic import BaseModel

from dataclasses import dataclass
from typing import Optional, Dict, Any


class JobPosting(BaseModel):
    title: str
    company: str
    description: str
    required_skills: set[str]
    preferred_skills: set[str]
    years_required: int | None = None


class ResumeProfile(BaseModel):
    skills: set[str]
    years_experience: int
    text: str


class MatchResult(BaseModel):
    job: JobPosting
    match_percent: float
    reasons: list[str]


@dataclass(frozen=True)
class JobRef:
    """
    A reference to a job posting discovered from any mechanism (company-forward or title-forward).
    The fetcher uses this to retrieve the full job details and normalize them.
    """
    source: str                 # e.g. "greenhouse", "lever", "custom"
    url: str                    # canonical job URL (or board URL)
    company: Optional[str] = None
    job_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None  # provider-specific metadata (optional)