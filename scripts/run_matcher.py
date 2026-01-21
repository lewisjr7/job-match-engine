import argparse
from job_matcher.main import run


parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
args = parser.parse_args()


run(args.config)