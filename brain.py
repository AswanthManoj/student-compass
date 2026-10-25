"""Student Compass judgement: board-mark prediction, career questions (OpenAI), answer reading (Jev), career ranking."""

import json
import math
import random
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings, ThinkingEffort
from typesafe_sdk import AsyncTypeSafeClient, Choice, ChoiceAnswer, Noul, NoulAnswer

WRITE_QUESTIONS_AGENT = "career-write-questions"
SKILLS_DIR = Path(__file__).parent / "skills"

TERMS = ["Unit Test 1", "Half-Yearly", "Unit Test 2", "Pre-Board"]
TREND_DAMPING = 0.5  # carry only half the trend forward: one good test is not a habit
ATTENDANCE_MIN = 75  # CBSE minimum to sit the board exam

StreamId = Literal["pcm", "pcb", "commerce", "humanities"]
STREAMS: dict[StreamId, dict] = {
    "pcm": {"name": "Science (PCM)", "subjects": ["Physics", "Chemistry", "Mathematics", "English", "Computer Science"]},
    "pcb": {"name": "Science (PCB)", "subjects": ["Physics", "Chemistry", "Biology", "English", "Physical Education"]},
    "commerce": {"name": "Commerce", "subjects": ["Accountancy", "Business Studies", "Economics", "English", "Mathematics"]},
    "humanities": {"name": "Humanities", "subjects": ["History", "Political Science", "Psychology", "English", "Economics"]},
}
GRADES = [(91, "A1"), (81, "A2"), (71, "B1"), (61, "B2"), (51, "C1"), (41, "C2"), (33, "D"), (0, "E")]  # CBSE bands

CareerId = Literal["cs", "eng", "med", "sci", "design", "media", "law", "biz", "fin", "psy"]
SkillId = Literal["maths", "comm", "creative", "empathy", "lead", "hands"]
CAREERS: list[dict] = [
    {"id": "cs", "name": "Computer Science & AI", "blurb": "Software, data and AI: building the apps and systems people use every day.",
     "streams": ["pcm", "commerce"], "needs": "Needs Maths in class 12", "degrees": ["B.Tech CSE", "B.Sc Computer Science", "BCA"],
     "exams": ["JEE Main", "State CETs", "CUET"], "skills": {"maths": 1, "creative": .4, "hands": .3}},
    {"id": "eng", "name": "Engineering", "blurb": "Mechanical, civil, electrical and electronics: designing and building physical things.",
     "streams": ["pcm"], "needs": "Needs PCM in class 12", "degrees": ["B.Tech / B.E."],
     "exams": ["JEE Main", "JEE Advanced", "BITSAT", "State CETs"], "skills": {"maths": 1, "hands": 1}},
    {"id": "med", "name": "Medicine & Healthcare", "blurb": "Doctor, dentist, pharmacist, nurse or physiotherapist: caring for patients.",
     "streams": ["pcb"], "needs": "Needs PCB in class 12", "degrees": ["MBBS", "BDS", "B.Pharm", "B.Sc Nursing"],
     "exams": ["NEET-UG"], "skills": {"empathy": 1, "hands": .4, "maths": .3}},
    {"id": "sci", "name": "Research & Pure Science", "blurb": "Physics, chemistry, biology and maths research: finding out how the world works.",
     "streams": ["pcm", "pcb"], "needs": "Needs a science stream", "degrees": ["B.Sc", "BS-MS (IISER, NISER)"],
     "exams": ["IISER IAT", "NEST", "CUET"], "skills": {"maths": .9, "creative": .4}},
    {"id": "design", "name": "Design & Architecture", "blurb": "Product, fashion, communication and building design.",
     "streams": None, "needs": None, "degrees": ["B.Des", "B.Arch"],
     "exams": ["NID DAT", "UCEED", "NIFT", "NATA"], "skills": {"creative": 1, "hands": .5}},
    {"id": "media", "name": "Media, Writing & Arts", "blurb": "Journalism, film, content, advertising and the arts.",
     "streams": None, "needs": None, "degrees": ["BA Journalism & Mass Communication", "BA English", "BFA"],
     "exams": ["CUET", "University entrance tests"], "skills": {"comm": 1, "creative": .7}},
    {"id": "law", "name": "Law & Public Policy", "blurb": "Lawyer, legal adviser or civil services: arguing cases and shaping rules.",
     "streams": None, "needs": None, "degrees": ["BA LLB (5 years)", "BBA LLB"],
     "exams": ["CLAT", "AILET"], "skills": {"comm": 1, "lead": .5}},
    {"id": "biz", "name": "Business & Management", "blurb": "Starting, running and growing companies; marketing and operations.",
     "streams": None, "needs": None, "degrees": ["BBA", "Integrated MBA (IPM)"],
     "exams": ["IPMAT", "CUET", "NPAT"], "skills": {"lead": 1, "comm": .7}},
    {"id": "fin", "name": "Commerce & Finance", "blurb": "Chartered accountant, banking, investment and economics.",
     "streams": None, "needs": None, "degrees": ["B.Com", "CA", "BA Economics"],
     "exams": ["CA Foundation", "CUET"], "skills": {"maths": 1, "lead": .3}},
    {"id": "psy", "name": "Psychology & Social Work", "blurb": "Counselling, clinical psychology and community work.",
     "streams": None, "needs": None, "degrees": ["BA / B.Sc Psychology", "BSW"],
     "exams": ["CUET"], "skills": {"empathy": 1, "comm": .6}},
]
SKILLS: dict[SkillId, str] = {"maths": "Maths and logic", "comm": "Speaking and writing", "creative": "Creativity",
                              "empathy": "Caring for others", "lead": "Leading and organising", "hands": "Hands-on and technical"}
SUBJECT_FIT: dict[str, dict[str, float]] = {
    "Physics": {"eng": 1, "sci": .8, "cs": .4}, "Chemistry": {"sci": .8, "med": .7, "eng": .4},
    "Mathematics": {"cs": .9, "eng": .8, "fin": .7, "sci": .6, "biz": .4}, "Biology": {"med": 1, "sci": .7, "psy": .3},
    "Computer Science": {"cs": 1, "eng": .4}, "English": {"media": .9, "law": .7, "psy": .3},
    "Physical Education": {"med": .3, "psy": .2}, "Accountancy": {"fin": 1, "biz": .5}, "Business Studies": {"biz": 1, "fin": .4},
    "Economics": {"fin": .6, "biz": .6, "law": .4}, "History": {"law": .6, "media": .6},
    "Political Science": {"law": 1, "media": .4}, "Psychology": {"psy": 1, "med": .2},
}
PART_WEIGHTS = {"interests": .40, "skills": .30, "likes": .15, "marks": .15}
OFF_STREAM = 0.6  # a path the stream doesn't open is shown, but pushed down
NONE_OPTION = "none"

Percent = Annotated[float, Field(ge=0, le=100)]
Marks = dict[str, Annotated[list[Percent | None], Field(min_length=4, max_length=4)]]


# ---------- academics ----------

class Prediction(BaseModel):
    mid: float
    lo: float
    hi: float
    half: float
    slope: float
    spread: float
    tests: int
    penalty: float
    first: float
    last: float
    grade: str


class SubjectReport(BaseModel):
    subject: str
    values: list[float | None]
    prediction: Prediction | None


class Overall(BaseModel):
    mid: float
    lo: float
    hi: float
    tests: int
    grade: str
    confidence: Literal["High", "Medium", "Low"]


class Note(BaseModel):
    title: str
    detail: str


class AcademicReport(BaseModel):
    subjects: list[SubjectReport]
    overall: Overall | None
    advice: list[Note]
    strengths: list[str]


def grade(percent: float) -> str:
    return next(g for floor, g in GRADES if percent >= floor)


def _clamp(x: float) -> float:
    return min(100.0, max(0.0, x))


def predict(values: list[float | None], attendance: float) -> Prediction | None:
    """Best straight line through the tests, half its slope carried to the board exam."""
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if not pts:
        return None
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    slope = sum((x - mx) * (y - my) for x, y in pts) / sxx if sxx else 0.0
    residuals = [y - (my + slope * (x - mx)) for x, y in pts]
    spread = math.sqrt(sum(r * r for r in residuals) / (n - 2)) if n > 2 else 0.0
    penalty = (ATTENDANCE_MIN - attendance) * 0.3 if attendance < ATTENDANCE_MIN else 0.0
    mid = _clamp(my + slope * TREND_DAMPING * (len(TERMS) - mx) - penalty)
    half = 3 + spread + (len(TERMS) - n) * 2
    return Prediction(mid=mid, lo=_clamp(mid - half), hi=_clamp(mid + half), half=half, slope=slope, spread=spread,
                      tests=n, penalty=penalty, first=pts[0][1], last=pts[-1][1], grade=grade(mid))


def academic_report(stream: StreamId, marks: Marks, attendance: float) -> AcademicReport:
    subjects = [SubjectReport(subject=s, values=marks.get(s, [None] * 4), prediction=predict(marks.get(s, []), attendance))
                for s in STREAMS[stream]["subjects"]]
    scored = [(s.subject, s.prediction) for s in subjects if s.prediction]
    if not scored:
        return AcademicReport(subjects=subjects, overall=None, advice=[], strengths=[])

    mid = sum(p.mid for _, p in scored) / len(scored)
    half = sum(p.half for _, p in scored) / len(scored)
    overall = Overall(mid=mid, lo=_clamp(mid - half), hi=_clamp(mid + half), tests=max(p.tests for _, p in scored),
                      grade=grade(mid), confidence="High" if half <= 5 else "Medium" if half <= 9 else "Low")

    advice: list[Note] = []
    if attendance < ATTENDANCE_MIN:
        advice.append(Note(title=f"Attendance is {attendance:g}%", detail=(
            f"Boards such as CBSE need {ATTENDANCE_MIN}% to sit the exam. Missed classes are already pulling the "
            f"prediction down by about {round((ATTENDANCE_MIN - attendance) * 0.3)} points.")))
    by_weakest = sorted(scored, key=lambda sp: sp[1].mid)
    for subject, p in by_weakest:
        if p.tests >= 3 and p.slope <= -2:
            advice.append(Note(title=f"{subject} has dropped from {p.first:g} to {p.last:g}",
                               detail="Go back to the chapters from the last two tests and redo the questions that lost marks."))
        elif p.mid < 60:
            advice.append(Note(title=f"{subject} is heading for about {round(p.mid)}",
                               detail="Give it a fixed slot every day. Past board papers show quickly which topics cost the most marks."))
    if not advice and len(scored) > 1:
        (weak, wp), (strong, sp) = by_weakest[0], by_weakest[-1]
        if sp.mid - wp.mid >= 15:
            advice.append(Note(title=f"{weak} is {round(sp.mid - wp.mid)} points behind {strong}",
                               detail=f"Moving an hour a week from {strong} to {weak} is the cheapest way to lift the overall score."))

    strengths = [
        f"{s}: {f'up from {p.first:g} to {p.last:g}' if p.tests >= 2 and p.last > p.first else f'scoring {p.last:g}'}, heading for {p.grade}"
        for s, p in scored if p.mid >= 85 or (p.tests >= 3 and p.slope >= 2)
    ]
    return AcademicReport(subjects=subjects, overall=overall, advice=advice[:3], strengths=strengths)


# ---------- career questions (OpenAI) ----------

class Option(BaseModel):
    text: str
    careers: list[CareerId]


class Question(BaseModel):
    text: str
    options: list[Option]


class QuestionSet(BaseModel):
    questions: list[Question]


# The model writes one option per slot, so every question covers all ten paths by construction.
OPTION_SLOTS: dict[str, list[CareerId]] = {
    "tech": ["cs", "eng"], "science": ["sci"], "care": ["med", "psy"],
    "creative": ["design", "media"], "business": ["biz", "fin"], "fairness": ["law"],
}


class WrittenOptions(BaseModel):
    tech: str = Field(description="Building or fixing software, gadgets or machines.")
    science: str = Field(description="Finding out how things work: experiments, research, theory.")
    care: str = Field(description="Looking after people's health or feelings.")
    creative: str = Field(description="Making things look good or tell a story: design, art, media.")
    business: str = Field(description="Money, selling, running and growing something.")
    fairness: str = Field(description="Rules, fairness, arguing a case, public issues.")


class WrittenQuestion(BaseModel):
    text: str
    options: WrittenOptions


class WrittenQuestions(BaseModel):
    questions: list[WrittenQuestion] = Field(min_length=4, max_length=4)


def _skill(name: str) -> str:
    text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    return text.split("---", 2)[2].strip()  # drop the frontmatter


def write_questions_agent(model_name: str, api_key: str, thinking: ThinkingEffort | None) -> Agent[None, WrittenQuestions]:
    model = OpenAIResponsesModel(model_name, provider=OpenAIProvider(api_key=api_key))
    return Agent(model, name=WRITE_QUESTIONS_AGENT, output_type=WrittenQuestions, instructions=_skill(WRITE_QUESTIONS_AGENT),
                 model_settings=ModelSettings(thinking=thinking) if thinking else None)


async def write_questions(agent: Agent[None, WrittenQuestions], about_me: str, stream: StreamId) -> QuestionSet:
    student = {"about_me": about_me, "stream": STREAMS[stream]["name"], "subjects": STREAMS[stream]["subjects"]}
    result = await agent.run(json.dumps(student, ensure_ascii=False, indent=2))
    questions = []
    for q in result.output.questions:
        written = q.options.model_dump()
        slots = random.sample(list(OPTION_SLOTS), len(OPTION_SLOTS))  # so no path always comes first
        questions.append(Question(text=q.text, options=[Option(text=written[s], careers=OPTION_SLOTS[s]) for s in slots]))
    return QuestionSet(questions=questions)


# ---------- reading answers (Jev) ----------

class QuestionJudgment(BaseModel):
    probabilities: dict[str, float]
    confidence: float


class Judgments(BaseModel):
    questions: list[QuestionJudgment]
    likes: dict[str, float]


async def read_answers(api_key: str, about_me: str, questions: QuestionSet, answers: list[str], subjects: list[str]) -> Judgments:
    """One Jev call: a Choice per question over its options, a Noul per subject for enjoyment."""
    state = {"about_me": about_me, "answers": [{"question": q.text, "answer": a} for q, a in zip(questions.questions, answers)]}
    jev: dict[str, Choice | Noul] = {}
    for i, q in enumerate(questions.questions):
        criteria = {f"o{j}": o.text for j, o in enumerate(q.options)}
        criteria[NONE_OPTION] = "The answer matches none of these, or the student says they don't know."
        jev[f"q{i}"] = Choice(instructions=f"Which option is closest to what the student said in `answers[{i}].answer`?",
                              criteria=criteria)
    for s in subjects:
        jev[f"likes|{s}"] = Noul(instructions=f"Does the student, in `about_me` or `answers`, say they enjoy {s} or its topics?",
                                criteria={"true": f"Their own words show they like {s}.",
                                          "false": f"They don't mention {s}, or say they dislike it."})

    async with AsyncTypeSafeClient(api_key=api_key) as client:
        resp = await client.system_one(state=state, questions=jev)

    judged = []
    for i in range(len(questions.questions)):
        a = resp.answers[f"q{i}"]
        assert isinstance(a, ChoiceAnswer)
        judged.append(QuestionJudgment(probabilities=dict(a.probabilities), confidence=a.confidence))
    likes = {}
    for s in subjects:
        a = resp.answers[f"likes|{s}"]
        assert isinstance(a, NoulAnswer)
        likes[s] = a.noul
    return Judgments(questions=judged, likes=likes)


# ---------- ranking ----------

class RankedCareer(BaseModel):
    id: CareerId
    name: str
    blurb: str
    needs: str | None
    open: bool
    degrees: list[str]
    exams: list[str]
    score: float
    parts: dict[str, float]
    reasons: list[str]


class Confidence(BaseModel):
    value: float
    word: Literal["High", "Medium", "Low"]
    margin: float
    reading: float  # Jev's average certainty about the answers


class CareerReport(BaseModel):
    ranked: list[RankedCareer]
    confidence: Confidence
    questions: list[Question]
    judgments: Judgments


def _quote(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def rank(questions: QuestionSet, answers: list[str], judgments: Judgments, skills: dict[SkillId, int],
         stream: StreamId, academics: AcademicReport) -> CareerReport:
    mids = {s.subject: s.prediction.mid for s in academics.subjects if s.prediction}
    stream_subjects = STREAMS[stream]["subjects"]
    ranked = []
    for c in CAREERS:
        parts: dict[str, float] = {}
        reasons: list[tuple[float, str]] = []

        interests = 0.0
        for q, answer, j in zip(questions.questions, answers, judgments.questions):
            for key, p in j.probabilities.items():
                if key == NONE_OPTION:
                    continue
                option = q.options[int(key[1:])]
                if c["id"] in option.careers:
                    interests += p / len(questions.questions)
                    if p >= 0.5:
                        reasons.append((PART_WEIGHTS["interests"] * p / len(questions.questions), f"You said “{_quote(answer)}”"))
        parts["interests"] = interests

        fit_total = sum(c["skills"].values())
        level_sum = 0.0
        for s, fit in c["skills"].items():
            level = (skills[s] - 1) / 4
            level_sum += fit * level / fit_total
            if skills[s] >= 4:
                reasons.append((PART_WEIGHTS["skills"] * fit * level / fit_total, f"{SKILLS[s]}: {skills[s]} of 5"))
        parts["skills"] = level_sum

        related = [s for s in stream_subjects if c["id"] in SUBJECT_FIT.get(s, {})]
        if related:
            parts["likes"] = max(judgments.likes.get(s, 0.0) * SUBJECT_FIT[s][c["id"]] for s in related)
            for s in related:
                if judgments.likes.get(s, 0.0) >= 0.6:
                    reasons.append((PART_WEIGHTS["likes"] * SUBJECT_FIT[s][c["id"]] * judgments.likes[s], f"You said you enjoy {s}"))
            marked = [s for s in related if s in mids]
            if marked:
                w = sum(SUBJECT_FIT[s][c["id"]] for s in marked)
                parts["marks"] = sum(SUBJECT_FIT[s][c["id"]] * mids[s] / 100 for s in marked) / w
                for s in marked:
                    if mids[s] >= 80:
                        reasons.append((PART_WEIGHTS["marks"] * SUBJECT_FIT[s][c["id"]] * mids[s] / 100 / w,
                                        f"{s} heading for {round(mids[s])}"))

        raw = sum(PART_WEIGHTS[k] * v for k, v in parts.items()) / sum(PART_WEIGHTS[k] for k in parts)
        is_open = c["streams"] is None or stream in c["streams"]
        reasons.sort(key=lambda r: -r[0])
        ranked.append(RankedCareer(id=c["id"], name=c["name"], blurb=c["blurb"], needs=c["needs"], open=is_open,
                                   degrees=c["degrees"], exams=c["exams"], score=raw if is_open else raw * OFF_STREAM,
                                   parts=parts, reasons=[text for _, text in reasons[:3]]))
    ranked.sort(key=lambda r: -r.score)

    reading = sum(j.confidence * (1 - j.probabilities.get(NONE_OPTION, 0.0)) for j in judgments.questions) / len(judgments.questions)
    margin = ranked[0].score - ranked[1].score
    value = 0.5 * reading + 0.5 * min(1.0, margin / 0.08)
    confidence = Confidence(value=value, word="High" if value >= 0.75 else "Medium" if value >= 0.5 else "Low",
                            margin=margin, reading=reading)
    return CareerReport(ranked=ranked, confidence=confidence, questions=questions.questions, judgments=judgments)
