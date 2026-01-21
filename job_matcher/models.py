from pydantic import BaseModel


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