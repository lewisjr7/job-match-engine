# scripts/refresh_jobs.py
import json
import time
from pathlib import Path

from job_matcher.config import load_config
from job_matcher.sources.greenhouse import GreenhouseSource
from job_matcher.sources.lever import LeverSource

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

    gh_companies = getattr(cfg.sources.greenhouse, "companies", []) or []
    lever_companies = getattr(getattr(cfg.sources, "lever", None), "companies", []) or []

    if not gh_companies and not lever_companies:
        raise ValueError(
            "No companies configured for Greenhouse or Lever.\n\n"
            "Add to config/config.yaml:\n"
            "sources:\n"
            "  greenhouse:\n"
            "    companies:\n"
            "      - airbnb\n"
            "  lever:\n"
            "    companies:\n"
            "      - plaid\n"
        )

    # Build a unified work list of (source_name, company_slug)
    work = []
    work.extend([("greenhouse", c) for c in gh_companies])
    work.extend([("lever", c) for c in lever_companies])

    RAW_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG] Writing raw jobs to: {RAW_JOBS_DIR.resolve()}")

    for source_name, company in work:
        company = (company or "").strip()
        if not company:
            continue

        print(f"\nFetching {source_name} jobs for {company}...")

        # Write files as: greenhouse_airbnb.json, lever_plaid.json
        out_file = RAW_JOBS_DIR / f"{source_name}_{company}.json"

        try:
            if source_name == "greenhouse":
                source = GreenhouseSource(company)
            elif source_name == "lever":
                source = LeverSource(company)
            else:
                raise ValueError(f"Unknown source: {source_name}")

            jobs = source.fetch_jobs()
            atomic_write_json(out_file, jobs)
            print(f"Saved {len(jobs)} jobs → {out_file}")

        except Exception as e:
            err_file = RAW_JOBS_DIR / f"{source_name}_{company}.error.json"
            atomic_write_json(err_file, {"source": source_name, "company": company, "error": str(e)})
            print(f"[ERROR] {source_name}:{company} → {e} (wrote {err_file})")

        time.sleep(0.25)


if __name__ == "__main__":
    refresh_jobs()
