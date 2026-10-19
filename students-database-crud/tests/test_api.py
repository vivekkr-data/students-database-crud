from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

BASE = {"name": "Demo Student", "date_of_birth": "2006-02-10", "email": "demo@example.com", "course": "CSE"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("ENABLE_OLLAMA", raising=False)
    with TestClient(create_app(tmp_path / "students.db")) as session:
        yield session


def add(client, **changes):
    response = client.post("/students", json={**BASE, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_crud(client):
    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/students", json=BASE)
    assert response.status_code == 201
    sid = response.json()["student_id"]
    assert response.headers["location"] == f"/students/{sid}"
    assert client.get(f"/students/{sid}").json()["name"] == BASE["name"]
    assert client.get("/students").json()["total"] == 1
    assert client.patch(f"/students/{sid}", json={"course": "ECE"}).json()["course"] == "ECE"
    replaced = client.put(f"/students/{sid}", json={"name": "New Name", "date_of_birth": "2005-01-01", "phone": "1234567890"})
    assert replaced.status_code == 200
    assert replaced.json()["course"] is None
    assert replaced.json()["email"] is None
    response = client.delete(f"/students/{sid}")
    assert response.status_code == 204 and response.content == b""
    assert client.get(f"/students/{sid}").status_code == 404


@pytest.mark.parametrize("changes", [
    {"name": " "}, {"name": "X"}, {"date_of_birth": "2005-02-30"},
    {"date_of_birth": str(date.today() + timedelta(days=1))}, {"date_of_birth": "1899-01-01"},
    {"email": "broken"}, {"email": None}, {"phone": "abcdefg"},
    {"phone": "12-34-56"}, {"enrollment_date": "2000-01-01"},
    {"student_id": 50}, {"unexpected": True}, {"name": "x" * 101},
])
def test_invalid_creation(client, changes):
    assert client.post("/students", json={**BASE, **changes}).status_code == 422
    assert client.get("/students").json()["total"] == 0


def test_duplicate_email_and_rollback(client):
    first = add(client)
    second = add(client, email="other@example.com")
    assert client.post("/students", json={**BASE, "email": "DEMO@example.com"}).status_code == 409
    assert client.patch(f"/students/{second['student_id']}", json={"email": first["email"]}).status_code == 409
    assert client.get(f"/students/{second['student_id']}").json()["email"] == "other@example.com"
    assert client.put(f"/students/{second['student_id']}", json=BASE).status_code == 409


@pytest.mark.parametrize("patch", [{}, {"name": None}, {"date_of_birth": None}, {"email": None}, {"enrollment_date": "2000-01-01"}, {"student_id": 7}])
def test_patch_constraints(client, patch):
    student = add(client)
    assert client.patch(f"/students/{student['student_id']}", json=patch).status_code == 422
    assert client.get(f"/students/{student['student_id']}").json() == student


def test_clear_optional_fields(client):
    student = add(client, phone="+91 9876543210")
    response = client.patch(f"/students/{student['student_id']}", json={"email": None, "course": None})
    assert response.status_code == 200
    assert response.json()["email"] is None
    assert response.json()["phone"] == student["phone"]


@pytest.mark.parametrize("method,body", [("get", None), ("delete", None), ("patch", {"name": "Nobody"}), ("put", BASE)])
def test_missing_student(client, method, body):
    assert client.request(method, "/students/999", json=body).status_code == 404


def test_filters_pagination_injection(client):
    add(client, name="Alpha Demo")
    add(client, name="Beta Demo", email="beta@example.com", date_of_birth="2005-01-01", course="ECE")
    add(client, name="Gamma", email="gamma@example.com")
    assert client.get("/students", params={"name": "DEMO"}).json()["total"] == 2
    assert client.get("/students", params={"course": "cse"}).json()["total"] == 2
    assert client.get("/students", params={"born_after": "2005-12-31"}).json()["total"] == 2
    assert client.get("/students", params={"born_before": "2006-02-10"}).json()["total"] == 1
    assert client.get("/students", params={"email": "BETA@example.com"}).json()["total"] == 1
    result = client.get("/students", params={"limit": 1, "offset": 1}).json()
    assert result["total"] == 3 and result["items"][0]["name"] == "Beta Demo"
    assert client.get("/students", params={"offset": 100}).json()["items"] == []
    for value in ("' OR 1=1 --", "%", "_"):
        assert client.get("/students", params={"name": value}).json()["total"] == 0
    assert client.get("/students").json()["total"] == 3


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "born_after=bad", "born_after=2007-01-01&born_before=2000-01-01"])
def test_invalid_filters(client, query):
    assert client.get("/students?" + query).status_code == 422


@pytest.mark.parametrize("sid", ["0", "-1", "abc"])
def test_invalid_ids(client, sid):
    assert client.get("/students/" + sid).status_code == 422


def test_persistence(tmp_path):
    path = tmp_path / "persistent.db"
    with TestClient(create_app(path)) as first:
        student = add(first)
    with TestClient(create_app(path)) as restarted:
        assert restarted.get(f"/students/{student['student_id']}").json() == student


def test_concurrent_creates(client):
    def create(index):
        return client.post("/students", json={**BASE, "email": f"demo{index}@example.com"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(create, range(12)))
    assert all(result.status_code == 201 for result in results)
    assert len({result.json()["student_id"] for result in results}) == 12


def test_ai_database_answers(client):
    assert client.post("/ai/ask", json={"question": "How many students are there?"}).json()["total"] == 0
    add(client)
    add(client, email="older@example.com", date_of_birth="2005-12-31")
    result = client.post("/ai/ask", json={"question": "List students born after 2005."}).json()
    assert result["total"] == 1 and len(result["records"]) == 1
    assert result["ollama_explanation"] is None
    assert "email" not in result["records"][0]
    assert client.post("/ai/ask", json={"question": "DROP TABLE students"}).status_code == 422
    assert client.get("/students").json()["total"] == 2


def test_ollama_mocked_success(client, monkeypatch):
    monkeypatch.setenv("ENABLE_OLLAMA", "true")
    def fake_post(url, **kwargs):
        assert url == "http://127.0.0.1:11434/api/chat"
        assert "SELECT" not in str(kwargs["json"])
        return httpx.Response(200, json={"message": {"content": "There are no students."}}, request=httpx.Request("POST", url))
    monkeypatch.setattr("app.ai.httpx.post", fake_post)
    result = client.post("/ai/ask", json={"question": "Count students"})
    assert result.status_code == 200
    assert result.json()["ollama_explanation"] == "There are no students."


@pytest.mark.parametrize("failure", ["connection", "malformed", "empty"])
def test_ollama_failure(client, monkeypatch, failure):
    monkeypatch.setenv("ENABLE_OLLAMA", "true")
    def fake_post(url, **kwargs):
        if failure == "connection":
            raise httpx.ConnectError("Offline")
        payload = {} if failure == "malformed" else {"message": {"content": ""}}
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))
    monkeypatch.setattr("app.ai.httpx.post", fake_post)
    assert client.post("/ai/ask", json={"question": "Count students"}).status_code == 503
    assert client.get("/health").status_code == 200


def test_docs(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert {"get", "put", "patch", "delete"} <= set(spec["paths"]["/students/{student_id}"])
