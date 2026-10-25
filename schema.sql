CREATE TABLE IF NOT EXISTS students (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  stream TEXT NOT NULL,
  attendance REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marks (
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  term INTEGER NOT NULL,
  percent REAL NOT NULL,
  PRIMARY KEY (student_id, subject, term)
);

-- One row per round of career questions. Raw Jev probabilities are kept so
-- weights can change and old sessions be re-ranked without calling Jev again.
CREATE TABLE IF NOT EXISTS career_sessions (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  about_me TEXT NOT NULL,
  questions_json TEXT NOT NULL,
  answers_json TEXT,
  skills_json TEXT,
  judgments_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
