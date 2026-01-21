from job_matcher.matching import match_resume_to_jobs
from job_matcher.models import JobPosting


def test_basic_skill_matching():
    resume_text = "Python AWS Docker Kubernetes"

    jobs = [
        JobPosting(
            id="1",
            title="Backend Engineer",
            description="Python AWS experience required",
            skills=["python", "aws"],
        ),
        JobPosting(
            id="2",
            title="Frontend Engineer",
            description="React CSS HTML",
            skills=["react", "css"],
        ),
    ]

    results = match_resume_to_jobs(resume_text, jobs)

    assert len(results) == 2
    assert results[0].job.id == "1"
    assert results[0].score > results[1].score
