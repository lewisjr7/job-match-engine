# scripts/refresh_jobs.py
import json
import time
from pathlib import Path

from job_matcher.config import load_config
from job_matcher.sources.greenhouse import GreenhouseSource

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_JOBS_DIR = REPO_ROOT / "data" / "raw_jobs"


def atomic_write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def refresh_jobs(config_path: str = "config/config.yaml"):
    config_file = (REPO_ROOT / config_path).resolve()
    cfg = load_config(str(config_file))

    companies = cfg.sources.greenhouse.companies
    if not companies:
        raise ValueError(
            "No Greenhouse companies configured.\n"
            "Add to config/config.yaml:\n"
            "sources:\n  greenhouse:\n    companies:\n      - airbnb\n"
        )

    RAW_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG] Writing raw jobs to: {RAW_JOBS_DIR.resolve()}")

    for company in companies:
        print(f"\nFetching jobs for {company}...")
        out_file = RAW_JOBS_DIR / f"{company}.json"

        try:
            source = GreenhouseSource(company)
            jobs = source.fetch_jobs()
            atomic_write_json(out_file, jobs)
            print(f"Saved {len(jobs)} jobs → {out_file}")

        except Exception as e:
            err_file = RAW_JOBS_DIR / f"{company}.error.json"
            atomic_write_json(err_file, {"company": company, "error": str(e)})
            print(f"[ERROR] {company}: {e} (wrote {err_file})")

        time.sleep(0.25)


if __name__ == "__main__":
    refresh_jobs()
