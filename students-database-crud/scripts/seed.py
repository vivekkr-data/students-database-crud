"""Load fictional samples through the running API without resetting its database."""
import argparse
import json
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    samples = json.loads((Path(__file__).resolve().parents[1] / "examples" / "students.json").read_text())
    created = skipped = 0
    try:
        with httpx.Client(base_url=args.url, timeout=10, trust_env=False) as client:
            for student in samples:
                response = client.post("/students", json=student)
                if response.status_code == 409:
                    skipped += 1
                else:
                    response.raise_for_status()
                    created += 1
    except httpx.HTTPError as exc:
        raise SystemExit(f"Seeding failed: {exc}. Start the API and check --url.")
    print(f"Created {created}; skipped {skipped} existing emails. No records deleted.")


if __name__ == "__main__":
    main()
