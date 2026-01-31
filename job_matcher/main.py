# job_matcher/main.py
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

from job_matcher.config import load_config
from job_matcher.matching import load_raw_jobs, score_jobs
from job_matcher.resume import load_resume_text

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a dict: {path}")
    return data


def _write_results(results: List[Dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / "results.json"
    out_csv = out_dir / "results.csv"

    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    fieldnames = [
        "score_percent",
        "company",
        "location",
        "title",
        "url",
        "posted_at",
        "created_at",
        "updated_at",
        "required_hit",
        "required_miss",
        "preferred_hit",
        "keywords_hit",
        "title_hit",
        "snippet",
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = dict(r)
            row["required_hit"] = ", ".join(r.get("required_hit", []))
            row["required_miss"] = ", ".join(r.get("required_miss", []))
            row["preferred_hit"] = ", ".join(r.get("preferred_hit", []))
            row["keywords_hit"] = ", ".join(r.get("keywords_hit", []))
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"Wrote {len(results)} matches → {out_json}")
    print(f"Wrote CSV → {out_csv}")


def run(config_path: str = "config/config.yaml") -> None:
    config_file = (REPO_ROOT / config_path).resolve()
    print(f"[DEBUG] Using config file: {config_file}")

    cfg = load_config(str(config_file))

    skills_file = config_file.parent / "skills.yaml"
    print(f"[DEBUG] Using skills file: {skills_file}")
    skills = _load_yaml_dict(skills_file)

    resume_path = cfg.resume.path
    print(f"[DEBUG] Resume path (as given): {resume_path}")
    resume_text = load_resume_text(resume_path)

    raw_dir = REPO_ROOT / "data" / "raw_jobs"
    raw_jobs = load_raw_jobs(str(raw_dir))
    if not raw_jobs:
        print(f"No raw jobs found in {raw_dir}. Run: python -m scripts.refresh_jobs")
        return

    # Pass plain dicts to scoring layer
    weights_dict = cfg.scoring.weights.model_dump()
    filters_dict = cfg.filters.model_dump()
    filters_dict["companies"] = cfg.sources.greenhouse.companies
    # ✅ pass new location policy block (if present)
    filters_dict["location_filters"] = (
        cfg.location_filters.model_dump() if getattr(cfg, "location_filters", None) else {}
    )

    print("[DEBUG] location_filters passed to matcher:", filters_dict["location_filters"])



    results = score_jobs(
        resume_text=resume_text,
        jobs=raw_jobs,
        skills=skills,
        weights=weights_dict,
        filters=filters_dict,
    )

    # Apply top_n from config.output
    results = results[: cfg.output.top_n]

    out_dir = REPO_ROOT / "data" / "results"
    _write_results(results, out_dir)


if __name__ == "__main__":
    run()
