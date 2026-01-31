# Job Match Engine


Personal Python project that:
- Fetches job postings by filter
- Compares them against a resume
- Produces a percent match score
- Ranks jobs by best fit


## Setup
```bash
pip install -r requirements.txt

# Job Match Engine

A Python-based job matching engine for **personal job search automation**.

This tool:
- fetches job postings from ATS platforms (currently Greenhouse)
- parses and normalizes job descriptions
- compares them against your resume
- scores and ranks jobs using configurable criteria
- outputs actionable results (JSON + CSV)

This is a **decision-support system**, not an auto-apply bot.

---

# TL;DR – Quick Start (Happy Path)

# bash
git clone <repo>
cd job-match-engine

MAC:
python3 -m venv .venv
source .venv/bin/activate

WINDOWS:
python -m venv .venv
.venv\Scripts\Activate

pip install -r requirements.txt

python -m scripts.refresh_jobs
python -m scripts.run_matcher --config config/config.yaml




Architecture------------------------------------------------------------------

job-match-engine/
├── config/
│   ├── config.yaml        # Main config (resume, filters, weights, companies)
│   └── skills.yaml        # Required/preferred skills and target titles
├── data/
│   ├── raw_jobs/          # Cached raw job postings (JSON)
│   └── results/           # Final scored output
├── job_matcher/
│   ├── config.py          # Pydantic config schema (SINGLE SOURCE OF TRUTH)
│   ├── main.py            # Orchestration layer
│   ├── matching.py        # Matching + scoring logic
│   ├── resume.py          # Resume parsing
│   └── sources/
│       └── greenhouse.py  # Greenhouse ATS integration
├── scripts/
│   ├── refresh_jobs.py    # Job ingestion
│   └── run_matcher.py     # Run scoring pipeline
├── requirements.txt
└── README.md
