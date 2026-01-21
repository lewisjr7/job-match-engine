import json
from pathlib import Path

from job_matcher.sources.greenhouse import GreenhouseSource
from job_matcher.sources.lever import LeverSource

RAW_JOBS_DIR = Path("data/raw_jobs")


def refresh_jobs():
    RAW_JOBS_DIR.mkdir(parents=True, exist_ok=True)

    sources = [
        GreenhouseSource(),
        LeverSource(),
    ]

    all_jobs = []

    for source in sources:
        print(f"Fetching jobs from {source.name}...")
        jobs = source.fetch_jobs()
        all_jobs.extend(jobs)

    output_file = RAW_JOBS_DIR / "jobs.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2)

    print(f"Saved {len(all_jobs)} jobs → {output_file}")


if __name__ == "__main__":
    refresh_jobs()
