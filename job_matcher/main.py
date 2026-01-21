from job_matcher.config import load_config
from job_matcher.resume import load_resume_text




def run(config_path: str):
    config = load_config(config_path)
    resume_text = load_resume_text(config.resume["path"])
    print("Resume loaded. Ready for matching.")


if __name__ == "__main__":
    run("config/config.yaml")