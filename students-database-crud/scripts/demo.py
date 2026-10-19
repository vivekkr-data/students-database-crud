"""Reproducible API transcript using a separate temporary SQLite database."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from app.main import create_app


def main():
    with TemporaryDirectory() as folder:
        with TestClient(create_app(Path(folder) / "demo.db")) as client:
            steps = [
                ("POST", "/students", {"name": "Demo Student", "date_of_birth": "2006-02-10", "email": "demo@example.com", "course": "CSE"}),
                ("GET", "/students", None),
                ("GET", "/students/1", None),
                ("PATCH", "/students/1", {"course": "Data Science"}),
                ("GET", "/students?course=Data%20Science", None),
                ("POST", "/ai/ask", {"question": "How many students are there?"}),
                ("DELETE", "/students/1", None),
                ("GET", "/students/1", None),
            ]
            for method, url, body in steps:
                response = client.request(method, url, json=body)
                print(f"\n{method} {url}")
                if body is not None:
                    print("Request:", json.dumps(body))
                print("Status:", response.status_code)
                print(json.dumps(response.json(), indent=2) if response.content else "(empty response)")


if __name__ == "__main__":
    main()
