from __future__ import annotations

from typing import List
import yaml
from pydantic import BaseModel, Field


class Resume(BaseModel):
    path: str


class Weights(BaseModel):
    required_skills: float
    preferred_skills: float
    semantic_similarity: float
    experience: float
    title_similarity: float


class Filters(BaseModel):
    keywords: List[str] = Field(default_factory=list)

    # Title filters
    include_title_keywords: List[str] = Field(default_factory=list)
    exclude_title_keywords: List[str] = Field(default_factory=list)

    # Legacy/simple location filtering (optional to keep)
    locations: List[str] = Field(default_factory=list)
    remote_only: bool = True

    min_match_percent: int = 70


class LocationFilters(BaseModel):
    # “keep options open” structure you were aiming for
    allow_remote: bool = True
    allowed_countries: List[str] = Field(default_factory=list)
    allowed_states: List[str] = Field(default_factory=list)
    allowed_cities: List[str] = Field(default_factory=list)


class Scoring(BaseModel):
    weights: Weights


class Output(BaseModel):
    top_n: int = 20000
    explain: bool = True


class GreenhouseSourceCfg(BaseModel):
    companies: List[str] = Field(default_factory=list)


class LeverSourceCfg(BaseModel):
    companies: List[str] = Field(default_factory=list)


class Sources(BaseModel):
    greenhouse: GreenhouseSourceCfg = Field(default_factory=GreenhouseSourceCfg)
    lever: LeverSourceCfg = Field(default_factory=LeverSourceCfg)


class Config(BaseModel):
    version: int = 1
    resume: Resume
    filters: Filters
    location_filters: LocationFilters = Field(default_factory=LocationFilters)
    scoring: Scoring
    output: Output = Field(default_factory=Output)
    sources: Sources = Field(default_factory=Sources)


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = Config(**raw)

    total = sum(cfg.scoring.weights.model_dump().values())
    if abs(total - 1.0) >= 0.01:
        raise ValueError(f"Scoring weights must sum to 1.0 (got {total})")

    return cfg
