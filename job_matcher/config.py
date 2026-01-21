import yaml
from pydantic import BaseModel


class Weights(BaseModel):
    required_skills: float
    preferred_skills: float
    semantic_similarity: float
    experience: float
    title_similarity: float


class Filters(BaseModel):
    keywords: list[str]
    locations: list[str]
    remote_only: bool
    min_match_percent: int


class Scoring(BaseModel):
    weights: Weights


class Config(BaseModel):
    resume: dict
    filters: Filters
    scoring: Scoring
    output: dict




def load_config(path: str) -> Config:
    with open(path) as f:
        cfg = Config(**yaml.safe_load(f))
        total = sum(cfg.scoring.weights.model_dump().values())
        assert abs(total - 1.0) < 0.01, "Scoring weights must sum to 1.0"
        return cfg