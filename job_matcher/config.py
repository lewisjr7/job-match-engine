# job_matcher/config.py
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
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_only: bool = True
    min_match_percent: int = 70

    include_title_keywords: list[str] = Field(default_factory=list)
    exclude_title_keywords: list[str] = Field(default_factory=list)


class Scoring(BaseModel):
    weights: Weights


class Output(BaseModel):
    top_n: int = 20000
    explain: bool = True


class GreenhouseSourceCfg(BaseModel):
    companies: List[str] = Field(default_factory=list)


class Sources(BaseModel):
    greenhouse: GreenhouseSourceCfg = Field(default_factory=GreenhouseSourceCfg)


class Config(BaseModel):
    version: int = 1
    resume: Resume
    filters: Filters
    scoring: Scoring
    output: Output = Field(default_factory=Output)
    sources: Sources = Field(default_factory=Sources)

class Filters(BaseModel):
    keywords: list[str]
    locations: list[str]
    remote_only: bool
    min_match_percent: int

    # ✅ add these (defaults avoid breaking older configs)
    include_title_keywords: list[str] = []
    exclude_title_keywords: list[str] = []

def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    cfg = Config(**raw)

    total = sum(cfg.scoring.weights.model_dump().values())
    assert abs(total - 1.0) < 0.01, "Scoring weights must sum to 1.0"

    return cfg
