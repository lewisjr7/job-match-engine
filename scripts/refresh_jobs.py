# scripts/refresh_jobs.py
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

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


def read_existing_jobs(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def index_by_id(jobs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for j in jobs:
        if not isinstance(j, dict):
            continue
        jid = j.get("id")
        if jid is None:
            continue
        out[str(jid)] = j
    return out


def merge_jobs(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge by id:
      - keep all existing
      - overwrite with incoming for same id
      - append new ids
    """
    existing_map = index_by_id(existing)
    for j in incoming:
        if not isinstance(j, dict):
            continue
        jid = j.get("id")
        if jid is None:
            continue
        existing_map[str(jid)] = j

    # return stable ordering: newest-ish first if posted_at exists, else keep map order
    merged = list(existing_map.values())
    merged.sort(key=lambda x: (x.get("posted_at") or x.get("updated_at") or ""), reverse=True)
    return merged


def jobs_changed(existing: List[Dict[str, Any]], merged: List[Dict[str, Any]]) -> bool:
    """
    Cheap change detector:
    - different count OR
    - any id missing/present change OR
    - any updated_at change
    """
    ex = index_by_id(existing)
    mg = index_by_id(merged)

    if len(ex) != len(mg):
        return True

    for jid, mj in mg.items():
        ej = ex.get(jid)
        if ej is None:
            return True
        if (ej.get("updated_at") or "") != (mj.get("updated_at") or ""):
            return True

    return False


def refresh_jobs(config_path: str = "config/config.yaml"):
    config_file = (REPO_ROOT / config_path).resolve()
    cfg = load_config(str(config_file))

    gh_companies = (cfg.sources.greenhouse.companies or []) if getattr(cfg, "sources", None) else []
    lever_companies = (cfg.sources.lever.companies or []) if getattr(cfg, "sources", None) and getattr(cfg.sources, "lever", None) else []

    if not gh_companies and not lever_companies:
        raise ValueError("No companies configured for greenhouse or lever under sources: ...")

    RAW_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG] Writing raw jobs to: {RAW_JOBS_DIR.resolve()}")

    # ----------------------------
    # GREENHOUSE DELTA
    # ----------------------------
    for company in gh_companies:
        company_slug = company.strip().lower()
        out_file = RAW_JOBS_DIR / f"greenhouse_{company_slug}.json"

        existing = read_existing_jobs(out_file)
        existing_by_id = index_by_id(existing)

        print(f"\n[GREENHOUSE] {company_slug}: existing={len(existing_by_id)}")
        try:
            source = GreenhouseSource(company_slug)
            incoming = source.fetch_jobs(existing_by_id=existing_by_id)

            merged = merge_jobs(existing, incoming)
            changed = jobs_changed(existing, merged)

            if changed:
                atomic_write_json(out_file, merged)
                print(f"[GREENHOUSE] {company_slug}: wrote={len(merged)} (incoming={len(incoming)}) → {out_file.name}")
            else:
                print(f"[GREENHOUSE] {company_slug}: no changes (incoming={len(incoming)})")

        except Exception as e:
            err_file = RAW_JOBS_DIR / f"greenhouse_{company_slug}.error.json"
            atomic_write_json(err_file, {"source": "greenhouse", "company": company_slug, "error": str(e)})
            print(f"[ERROR] greenhouse {company_slug}: {e} (wrote {err_file.name})")

        time.sleep(0.25)

    # ----------------------------
    # LEVER DELTA (single call, merge/write-delta)
    # ----------------------------
    for company in lever_companies:
        company_slug = company.strip().lower()
        out_file = RAW_JOBS_DIR / f"lever_{company_slug}.json"

        existing = read_existing_jobs(out_file)
        existing_by_id = index_by_id(existing)

        print(f"\n[LEVER] {company_slug}: existing={len(existing_by_id)}")
        try:
            source = LeverSource(company_slug)
            incoming = source.fetch_jobs()

            merged = merge_jobs(existing, incoming)
            changed = jobs_changed(existing, merged)

            if changed:
                atomic_write_json(out_file, merged)
                print(f"[LEVER] {company_slug}: wrote={len(merged)} (incoming={len(incoming)}) → {out_file.name}")
            else:
                print(f"[LEVER] {company_slug}: no changes (incoming={len(incoming)})")

        except Exception as e:
            err_file = RAW_JOBS_DIR / f"lever_{company_slug}.error.json"
            atomic_write_json(err_file, {"source": "lever", "company": company_slug, "error": str(e)})
            print(f"[ERROR] lever {company_slug}: {e} (wrote {err_file.name})")

        time.sleep(0.25)


if __name__ == "__main__":
    refresh_jobs()
