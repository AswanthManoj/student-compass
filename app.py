"""Student Compass web app: SQLite records and the JSON routes the page calls."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, SecretStr
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.settings import ThinkingEffort
from pydantic_settings import BaseSettings, SettingsConfigDict
from typesafe_sdk import TypeSafeError

import brain

HERE = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=HERE / ".env", extra="ignore")

    openai_api_key: SecretStr
    typesafe_api_key: SecretStr
    openai_model: str = "gpt-6.1-sol"
    openai_thinking: ThinkingEffort | None = "low"
    database: Path = HERE / "lakshya.db"


settings = Settings()  # pyright: ignore[reportCallIssue]  # filled from .env
writer = brain.write_questions_agent(settings.openai_model, settings.openai_api_key.get_secret_value(), settings.openai_thinking)


@asynccontextmanager
async def db() -> AsyncIterator[aiosqlite.Connection]:
    async with aiosqlite.connect(settings.database) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        await conn.commit()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with db() as conn:
        await conn.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
    yield


app = FastAPI(title="Student Compass", lifespan=lifespan)


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    stream: brain.StreamId
    attendance: brain.Percent
    marks: brain.Marks


class StudentOut(StudentIn):
    id: int
    report: brain.AcademicReport


class SessionIn(BaseModel):
    about_me: str = Field(min_length=10, max_length=2000)


class SessionOut(BaseModel):
    id: int
    questions: list[brain.Question]


class AnswersIn(BaseModel):
    answers: list[Annotated[str, Field(max_length=1000)]]
    skills: dict[brain.SkillId, Annotated[int, Field(ge=1, le=5)]]


async def _save_marks(conn: aiosqlite.Connection, student_id: int, marks: brain.Marks) -> None:
    await conn.execute("DELETE FROM marks WHERE student_id = ?", (student_id,))
    await conn.executemany("INSERT INTO marks (student_id, subject, term, percent) VALUES (?, ?, ?, ?)",
                           [(student_id, s, t, v) for s, values in marks.items() for t, v in enumerate(values) if v is not None])


async def _fetch_one(conn: aiosqlite.Connection, sql: str, params: tuple) -> aiosqlite.Row | None:
    async with conn.execute(sql, params) as cur:
        return await cur.fetchone()


async def _load_student(conn: aiosqlite.Connection, student_id: int) -> StudentOut:
    row = await _fetch_one(conn, "SELECT * FROM students WHERE id = ?", (student_id,))
    if row is None:
        raise HTTPException(404, "Student not found")
    marks: brain.Marks = {}
    for m in await conn.execute_fetchall("SELECT subject, term, percent FROM marks WHERE student_id = ?", (student_id,)):
        marks.setdefault(m["subject"], [None] * 4)[m["term"]] = m["percent"]
    return StudentOut(id=row["id"], name=row["name"], stream=row["stream"], attendance=row["attendance"], marks=marks,
                      report=brain.academic_report(row["stream"], marks, row["attendance"]))


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(HERE / "static" / "index.html", media_type="text/html; charset=utf-8")


@app.post("/api/students")
async def create_student(body: StudentIn) -> StudentOut:
    async with db() as conn:
        cur = await conn.execute("INSERT INTO students (name, stream, attendance) VALUES (?, ?, ?)",
                                 (body.name, body.stream, body.attendance))
        assert cur.lastrowid is not None
        await _save_marks(conn, cur.lastrowid, body.marks)
        return await _load_student(conn, cur.lastrowid)


@app.get("/api/students/{student_id}")
async def get_student(student_id: int) -> StudentOut:
    async with db() as conn:
        return await _load_student(conn, student_id)


@app.put("/api/students/{student_id}")
async def update_student(student_id: int, body: StudentIn) -> StudentOut:
    async with db() as conn:
        await _load_student(conn, student_id)
        await conn.execute("UPDATE students SET name = ?, stream = ?, attendance = ? WHERE id = ?",
                           (body.name, body.stream, body.attendance, student_id))
        await _save_marks(conn, student_id, body.marks)
        return await _load_student(conn, student_id)


@app.post("/api/students/{student_id}/career-sessions")
async def start_career_session(student_id: int, body: SessionIn) -> SessionOut:
    async with db() as conn:
        student = await _load_student(conn, student_id)
    try:
        questions = await brain.write_questions(writer, body.about_me, student.stream)
    except AgentRunError as exc:
        raise HTTPException(502, f"Couldn't write the questions: {exc}") from exc
    async with db() as conn:
        cur = await conn.execute("INSERT INTO career_sessions (student_id, about_me, questions_json) VALUES (?, ?, ?)",
                                 (student_id, body.about_me, questions.model_dump_json()))
        assert cur.lastrowid is not None
        return SessionOut(id=cur.lastrowid, questions=questions.questions)


@app.post("/api/career-sessions/{session_id}/answers")
async def answer_career_session(session_id: int, body: AnswersIn) -> brain.CareerReport:
    async with db() as conn:
        row = await _fetch_one(conn, "SELECT * FROM career_sessions WHERE id = ?", (session_id,))
        if row is None:
            raise HTTPException(404, "Career session not found")
        student = await _load_student(conn, row["student_id"])
    questions = brain.QuestionSet.model_validate_json(row["questions_json"])
    if len(body.answers) != len(questions.questions):
        raise HTTPException(422, f"Expected {len(questions.questions)} answers")
    if set(body.skills) != set(brain.SKILLS):
        raise HTTPException(422, "Rate every skill from 1 to 5")
    try:
        judgments = await brain.read_answers(settings.typesafe_api_key.get_secret_value(), row["about_me"], questions,
                                             body.answers, brain.STREAMS[student.stream]["subjects"])
    except TypeSafeError as exc:
        raise HTTPException(502, f"Couldn't read the answers: {exc}") from exc
    async with db() as conn:
        await conn.execute("UPDATE career_sessions SET answers_json = ?, skills_json = ?, judgments_json = ? WHERE id = ?",
                           (json.dumps(body.answers), json.dumps(body.skills), judgments.model_dump_json(), session_id))
    return brain.rank(questions, body.answers, judgments, body.skills, student.stream, student.report)
