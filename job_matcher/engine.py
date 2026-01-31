# job_matcher/engine.py
from typing import List, Dict, Any, Optional

from job_matcher.models import JobRef
from job_matcher.discovery.null_provider import NullDiscovery

# Import your existing sources.
# If you add Lever/Ashby later, register them in FETCHERS below.
from job_matcher.sources.greenhouse import GreenhouseSource


def _normalize_mode(mode: str) -> str:
    m = (mode or "").strip().lower()
    if m not in ("company", "title", "hybrid"):
        raise ValueError("mode must be one of: company | title | hybrid")
    return m


def _get_fetcher(source_name: str):
    """
    Factory / registry for fetchers.
    Add new sources here (lever, ashby, etc.).
    """
    name = (source_name or "").strip().lower()
    if name == "greenhouse":
        return "greenhouse"
    raise ValueError(f"Unknown source: {source_name}")


def list_company_refs(config: Dict[str, Any]) -> List[JobRef]:
    """
    Company-forward entry point:
      sources.greenhouse.companies -> list jobs -> returns JobRef list
    """
    refs: List[JobRef] = []

    sources = config.get("sources") or {}
    gh = sources.get("greenhouse") or {}
    enabled = bool(gh.get("enabled", True))
    companies = gh.get("companies") or []

    if not enabled:
        return refs

    for company in companies:
        company_slug = str(company).strip()
        if not company_slug:
            continue

        src = GreenhouseSource(company_slug)
        # Assumes you have list fetching in your current GreenhouseSource via fetch_jobs().
        # We convert each fetched job to a JobRef (url + job_id if present).
        jobs = src.fetch_jobs()
        for j in jobs:
            url = j.get("url") or ""
            job_id = str(j.get("id") or j.get("job_id") or "") or None
            if not url:
                continue
            refs.append(JobRef(source="greenhouse", url=url, company=company_slug, job_id=job_id, extra={"from": "company"}))

    return refs


def discover_title_refs(config: Dict[str, Any]) -> List[JobRef]:
    """
    Title-forward entry point:
      discovery.queries -> discovery provider -> returns JobRef list
    """
    refs: List[JobRef] = []
    discovery_cfg = config.get("discovery") or {}
    enabled = bool(discovery_cfg.get("enabled", False))
    if not enabled:
        return refs

    queries = discovery_cfg.get("queries") or []
    provider_name = (discovery_cfg.get("provider") or "null").strip().lower()

    # For now, only the Null provider skeleton exists.
    # Later you’ll add Bing/Google/SerpAPI providers.
    provider = NullDiscovery()

    filters = config.get("filters") or {}

    for q in queries:
        q = str(q).strip()
        if not q:
            continue
        refs.extend(provider.discover(q, filters))

    return refs


def dedupe_refs(refs: List[JobRef]) -> List[JobRef]:
    """
    Deduplicate references. Prefer stable keys if present.
    """
    seen = set()
    out: List[JobRef] = []

    for r in refs:
        key = None
        if r.source and r.company and r.job_id:
            key = (r.source, r.company, r.job_id)
        else:
            key = (r.source, r.url)

        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    return out


def fetch_full_jobs(refs: List[JobRef]) -> List[Dict[str, Any]]:
    """
    Turn JobRefs into normalized job dicts.

    For now:
      - If the ref already contains full job dicts elsewhere in your pipeline, you can skip this.
      - Skeleton assumes sources implement fetch_job(ref). If not implemented yet, we can fall back.

    Minimal implementation: for Greenhouse, we can re-use fetch_jobs output as already-normalized.
    """
    jobs: List[Dict[str, Any]] = []

    for ref in refs:
        src = ref.source.lower()
        if src == "greenhouse":
            # If you later implement GreenhouseSource.fetch_job(ref), call it here.
            # For now, we just keep JobRef list as-is and let your existing refresh flow handle it.
            jobs.append({
                "source": ref.source,
                "company": ref.company or "",
                "url": ref.url,
                "job_id": ref.job_id,
            })
        else:
            # Unknown sources will be handled once implemented
            continue

    return jobs


def run_discovery_engine(config: Dict[str, Any]) -> List[JobRef]:
    """
    High-level entry:
      mode=company | title | hybrid
    Returns JobRefs (not full jobs) for maximum flexibility.
    """
    mode = _normalize_mode(config.get("mode", "company"))

    refs: List[JobRef] = []

    if mode in ("company", "hybrid"):
        refs.extend(list_company_refs(config))

    if mode in ("title", "hybrid"):
        refs.extend(discover_title_refs(config))

    return dedupe_refs(refs)
