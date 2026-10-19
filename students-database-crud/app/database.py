"""SQLite connections are short-lived; writes commit or roll back together."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

FIELDS = ("name", "date_of_birth", "email", "phone", "course", "address", "enrollment_date")


@contextmanager
def connect(path):
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                email TEXT COLLATE NOCASE UNIQUE,
                phone TEXT,
                course TEXT,
                address TEXT,
                enrollment_date TEXT,
                CHECK (email IS NOT NULL OR phone IS NOT NULL)
            )
        """)


def find_student(db, student_id):
    row = db.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    return dict(row) if row else None


def where_clause(name=None, course=None, born_after=None, born_before=None, email=None):
    conditions, values = [], []
    if name:
        # Literal substring matching: %, _ and quotes never become SQL syntax.
        conditions.append("instr(lower(name), lower(?)) > 0")
        values.append(name)
    if course:
        conditions.append("course = ? COLLATE NOCASE")
        values.append(course)
    if email:
        conditions.append("email = ? COLLATE NOCASE")
        values.append(str(email))
    for field, operator, value in (("date_of_birth", ">", born_after), ("date_of_birth", "<", born_before)):
        if value:
            conditions.append(f"{field} {operator} ?")
            values.append(str(value))
    return (" WHERE " + " AND ".join(conditions) if conditions else ""), values


def list_students(db, limit=20, offset=0, **filters):
    where, values = where_clause(**filters)
    total = db.execute("SELECT COUNT(*) FROM students" + where, values).fetchone()[0]
    rows = db.execute("SELECT * FROM students" + where + " ORDER BY student_id LIMIT ? OFFSET ?",
                      [*values, limit, offset]).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": [dict(row) for row in rows]}


def insert_student(db, data):
    placeholders = ", ".join("?" for _ in FIELDS)
    cursor = db.execute(f"INSERT INTO students ({', '.join(FIELDS)}) VALUES ({placeholders})",
                        [data.get(field) for field in FIELDS])
    return find_student(db, cursor.lastrowid)


def replace_student(db, student_id, data):
    assignments = ", ".join(f"{field} = ?" for field in FIELDS)
    db.execute(f"UPDATE students SET {assignments} WHERE student_id = ?",
               [*[data.get(field) for field in FIELDS], student_id])
    return find_student(db, student_id)
