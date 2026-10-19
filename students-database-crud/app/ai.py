"""Optional local AI explanation of strictly parsed, read-only questions."""
import os
import re
import httpx
from fastapi import HTTPException
from .database import list_students


def answer_question(db, question):
    normalized = question.strip().lower().rstrip("?.!")
    if re.fullmatch(r"(?:how many students(?: are there)?|count students)", normalized):
        page = list_students(db, limit=1)
        facts = f"There are {page['total']} students in the database."
        records = []
    else:
        match = re.fullmatch(r"list students born after (19\d{2}|20\d{2})", normalized)
        if not match:
            raise HTTPException(422, "Supported questions: 'How many students are there?' or 'List students born after 2005.'")
        # 'After 2005' means strictly after the end of that calendar year.
        page = list_students(db, limit=100, born_after=f"{match.group(1)}-12-31")
        records = [{key: row[key] for key in ("student_id", "name", "date_of_birth")} for row in page["items"]]
        facts = f"{page['total']} students were born after {match.group(1)}. Showing {len(records)} records."
    explanation = None
    if os.getenv("ENABLE_OLLAMA", "false").lower() == "true":
        try:
            # Only aggregate facts are shared; student names/contact details stay out of the prompt.
            response = httpx.post("http://127.0.0.1:11434/api/chat", timeout=30, trust_env=False, json={
                "model": os.getenv("OLLAMA_MODEL", "llama3.2:1b"), "stream": False,
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": "Restate the supplied database facts in one sentence. Do not add facts."},
                    {"role": "user", "content": facts},
                ],
            })
            response.raise_for_status()
            explanation = response.json()["message"]["content"]
            if not isinstance(explanation, str) or not explanation.strip():
                raise ValueError("Empty model response")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise HTTPException(503, "Ollama is unavailable or returned an invalid response. Start Ollama and pull the configured model, or disable ENABLE_OLLAMA.")
    return {"answer": facts, "total": page["total"], "records": records,
            "truncated": page["total"] > len(records) if records else False,
            "source": "sqlite", "ollama_explanation": explanation}
