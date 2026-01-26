# job_matcher/scoring.py
from dataclasses import dataclass
from typing import Dict, List, Tuple

from job_matcher.utils import normalize_text, unique_lower


@dataclass
class ScoreBreakdown:
    total_percent: float
    required_hit: List[str]
    required_miss: List[str]
    preferred_hit: List[str]
    keywords_hit: List[str]
    title_hit: bool
    components: Dict[str, float]


def _hits(haystack: str, terms: List[str]) -> Tuple[List[str], List[str]]:
    hits, misses = [], []
    for t in terms:
        if t and t in haystack:
            hits.append(t)
        else:
            misses.append(t)
    return hits, misses


def calculate_match_score(
    resume_text: str,
    job_text: str,
    job_title: str,
    skills: Dict[str, List[str]],
    weights: Dict[str, float],
    keywords: List[str],
) -> ScoreBreakdown:
    """
    Returns an explainable score 0-100 and what matched/missed.
    """
    resume_n = normalize_text(resume_text)
    job_n = normalize_text(job_text)
    title_n = normalize_text(job_title)

    required = unique_lower(skills.get("required", []))
    preferred = unique_lower(skills.get("preferred", []))
    titles = unique_lower(skills.get("titles", []))
    keywords = unique_lower(keywords)

    # combine resume + job to detect overlap signals in either
    combined = f"{resume_n} {job_n}"

    req_hit, req_miss = _hits(combined, required)
    pref_hit, _ = _hits(combined, preferred)
    kw_hit, _ = _hits(job_n, keywords)

    # component scores normalized 0..1
    required_score = (len(req_hit) / max(1, len(required))) if required else 0.0
    preferred_score = (len(pref_hit) / max(1, len(preferred))) if preferred else 0.0
    keyword_score = (len(kw_hit) / max(1, len(keywords))) if keywords else 0.0

    title_hit = False
    if titles:
        title_hit = any(t in title_n for t in titles)
    title_score = 1.0 if title_hit else 0.0

    # weights (defaults if missing)
    w_required = float(weights.get("required_skills", 0.3))
    w_preferred = float(weights.get("preferred_skills", 0.2))
    w_semantic = float(weights.get("semantic_similarity", 0.0))  # not used yet
    w_experience = float(weights.get("experience", 0.0))         # not used yet
    w_title = float(weights.get("title_similarity", 0.1))

    # We’ll treat "semantic" and "experience" as 0 for now unless you implement them.
    # Normalize active weights so total is stable.
    active_total = w_required + w_preferred + w_title
    if active_total <= 0:
        active_total = 1.0

    w_required /= active_total
    w_preferred /= active_total
    w_title /= active_total

    total = (
        required_score * w_required +
        preferred_score * w_preferred +
        title_score * w_title
    )

    total_percent = round(total * 100.0, 2)

    components = {
        "required_score": round(required_score, 4),
        "preferred_score": round(preferred_score, 4),
        "keyword_score": round(keyword_score, 4),
        "title_score": round(title_score, 4),
        "w_required": round(w_required, 4),
        "w_preferred": round(w_preferred, 4),
        "w_title": round(w_title, 4),
        "w_semantic_unused": round(w_semantic, 4),
        "w_experience_unused": round(w_experience, 4),
    }

    return ScoreBreakdown(
        total_percent=total_percent,
        required_hit=req_hit,
        required_miss=req_miss,
        preferred_hit=pref_hit,
        keywords_hit=kw_hit,
        title_hit=title_hit,
        components=components,
    )
