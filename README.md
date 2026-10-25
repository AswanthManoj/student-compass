# Student Compass

Class 12 project: predicts board marks from tests and attendance, and suggests
career paths. It comes in two separate versions that share no code or data.

## Terminal version (the project report and viva)

`terminal/main.py` is a menu-driven program in plain Python with SQLite and
PrettyTable. The career quiz scores answers with points, so it needs no AI,
no API keys and no internet. It creates `compass.db` in the folder it runs from.

```bash
cd terminal
uv run --project .. python main.py
```

Without uv: `pip install prettytable`, then `python main.py`.

## Web version (the demo)

An OpenAI gpt-6 model writes four questions around what the student says about themselves;
Jev (TypeSafe) reads the student's free-text answers into probabilities; plain
code ranks the paths.

| File | Job |
|---|---|
| `app.py` | FastAPI routes, settings, SQLite (aiosqlite) |
| `brain.py` | marks prediction, question writing, answer reading, ranking |
| `schema.sql` | tables: students, marks, career_sessions |
| `skills/career-write-questions/SKILL.md` | the question writer's instructions |
| `static/index.html` | the page |

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` and `TYPESAFE_API_KEY`.
`OPENAI_MODEL` and `OPENAI_THINKING` are optional (defaults `gpt-6.1-sol`, `low`).

```bash
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000. Others on the same Wi-Fi open
`http://<this computer's IP>:8000`.
