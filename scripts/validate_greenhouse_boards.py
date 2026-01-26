import sys
import time
import yaml
import requests

CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else "config/config.yaml"

def main():
    cfg = yaml.safe_load(open(CONFIG_PATH, "r", encoding="utf-8"))
    companies = (
        cfg.get("sources", {})
          .get("greenhouse", {})
          .get("companies", [])
    )

    ok, bad = [], []
    for c in companies:
        if not isinstance(c, str) or not c.strip():
            continue
        token = c.strip()
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                ok.append(token)
                print(f"[OK]   {token}")
            else:
                bad.append((token, r.status_code))
                print(f"[BAD]  {token} -> {r.status_code}")
        except Exception as e:
            bad.append((token, str(e)))
            print(f"[ERR]  {token} -> {e}")
        time.sleep(0.2)

    out = {"greenhouse_valid_companies": ok, "greenhouse_invalid_companies": bad}
    open("data/greenhouse_board_validation.yaml", "w", encoding="utf-8").write(
        yaml.safe_dump(out, sort_keys=False)
    )
    print("\nWrote: data/greenhouse_board_validation.yaml")

if __name__ == "__main__":
    main()
