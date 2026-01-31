# scripts/discover_jobs.py
import argparse
import json
from pathlib import Path
from typing import Any, Dict

import yaml

from job_matcher.engine import run_discovery_engine


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML mapping (dict). Got: {type(data)}")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Discover job references (company-forward/title-forward/hybrid)."
    )
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--out", default="data/results/discovered_refs.json")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    config = load_yaml(config_path)

    refs = run_discovery_engine(config)

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = [
        {
            "source": r.source,
            "url": r.url,
            "company": r.company,
            "job_id": r.job_id,
            "extra": r.extra,
        }
        for r in refs
    ]

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Discovered {len(payload)} job refs → {out_path}")


if __name__ == "__main__":
    main()
