from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
import os
import sqlite3

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query, Response
from pydantic import EmailStr, ValidationError
from . import database
from .ai import answer_question
from .schemas import Question, StudentCreate, StudentOut, StudentPage, StudentPatch

ROOT = Path(__file__).resolve().parent.parent


def create_app(database_path=None):
    path = Path(database_path or os.getenv("STUDENT_DB_PATH", str(ROOT / "data" / "students.db"))).resolve()

    @asynccontextmanager
    async def lifespan(app):
        database.initialize(path)
        yield

    app = FastAPI(title="Students Database CRUD Application", version="1.0.0",
                  description="EWB internship project: validated student records with persistent SQLite storage.",
                  lifespan=lifespan)
    app.state.database_path = path

    def required_student(db, student_id):
        student = database.find_student(db, student_id)
        if not student:
            raise HTTPException(404, "Student not found")
        return student

    def validate_merged(data):
        try:
            return StudentCreate.model_validate(data).model_dump(mode="json")
        except ValidationError as exc:
            raise HTTPException(422, "; ".join(error["msg"] for error in exc.errors()))

    @app.get("/", tags=["Service"])
    def root():
        return {"project": app.title, "docs": "/docs", "health": "/health"}

    @app.get("/health", tags=["Service"])
    def health():
        with database.connect(path) as db:
            db.execute("SELECT COUNT(*) FROM students").fetchone()
        return {"status": "ok", "database": "sqlite"}

    @app.post("/students", response_model=StudentOut, status_code=201, tags=["Students"])
    def create_student(student: StudentCreate, response: Response):
        try:
            with database.connect(path) as db:
                result = database.insert_student(db, student.model_dump(mode="json"))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "A student with this email already exists")
        response.headers["Location"] = f"/students/{result['student_id']}"
        return result

    @app.get("/students", response_model=StudentPage, tags=["Students"])
    def get_students(name: str | None = Query(None, min_length=1, max_length=100),
                     course: str | None = Query(None, min_length=1, max_length=100),
                     email: EmailStr | None = None, born_after: date | None = None,
                     born_before: date | None = None, limit: int = Query(20, ge=1, le=100),
                     offset: int = Query(0, ge=0)):
        if born_after and born_before and born_after >= born_before:
            raise HTTPException(422, "born_after must be earlier than born_before")
        with database.connect(path) as db:
            return database.list_students(db, limit, offset, name=name, course=course,
                                          email=email, born_after=born_after, born_before=born_before)

    @app.get("/students/{student_id}", response_model=StudentOut, tags=["Students"])
    def get_student(student_id: int = ApiPath(ge=1)):
        with database.connect(path) as db:
            return required_student(db, student_id)

    @app.put("/students/{student_id}", response_model=StudentOut, tags=["Students"])
    def put_student(student: StudentCreate, student_id: int = ApiPath(ge=1)):
        try:
            with database.connect(path) as db:
                required_student(db, student_id)
                return database.replace_student(db, student_id, student.model_dump(mode="json"))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "A student with this email already exists")

    @app.patch("/students/{student_id}", response_model=StudentOut, tags=["Students"])
    def patch_student(student: StudentPatch, student_id: int = ApiPath(ge=1)):
        try:
            with database.connect(path) as db:
                # Reserve the write transaction before read/merge to avoid lost partial updates.
                db.execute("BEGIN IMMEDIATE")
                current = required_student(db, student_id)
                current.pop("student_id")
                current.update(student.model_dump(mode="json", exclude_unset=True))
                return database.replace_student(db, student_id, validate_merged(current))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "A student with this email already exists")

    @app.delete("/students/{student_id}", status_code=204, tags=["Students"])
    def delete_student(student_id: int = ApiPath(ge=1)):
        with database.connect(path) as db:
            cursor = db.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
            if cursor.rowcount == 0:
                raise HTTPException(404, "Student not found")
        return Response(status_code=204)

    @app.post("/ai/ask", tags=["Optional AI"])
    def ask(question: Question):
        with database.connect(path) as db:
            return answer_question(db, question.question)

    return app


app = create_app()
