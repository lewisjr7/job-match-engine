# job_matcher/resume.py
from pathlib import Path


def load_resume_text(path: str) -> str:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Resume not found: {p}")

    # Try pdfplumber
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(str(p)) as pdf:
            parts = []
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
            return "\n".join(parts)
    except ImportError:
        pass

    # Try PyPDF2
    try:
        from PyPDF2 import PdfReader  # type: ignore
        reader = PdfReader(str(p))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except ImportError as e:
        raise ImportError(
            "No PDF reader installed. Install one:\n"
            "  pip install pdfplumber\n"
            "or:\n"
            "  pip install PyPDF2\n"
        ) from e
