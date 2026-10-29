from contextlib import asynccontextmanager
import re
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .auth import create_token, current_user, hash_password, verify_password
from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .models import Answer, Assessment, Module, Question, User, VocabularyWord, utcnow
from .questions import QuestionGenerationError, generate_assessment_questions
from .schemas import AnswerRequest, AnswerResult, AssessmentOut, DashboardOut, LoginRequest, ReadingVocabularyStats, RegisterRequest, ResultOut, StartRequest, TokenOut, UserOut, VocabularyCreate, VocabularyOverview, VocabularyStatusUpdate, VocabularyWordOut
from .services import assessment_out, next_question, result_out, suggestions
from .seed import seed_demo_user


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    if settings.demo_seed_enabled:
        with SessionLocal() as db:
            seed_demo_user(
                db,
                username=settings.demo_username,
                email=settings.demo_email,
                name=settings.demo_name,
                password=settings.demo_password,
            )
    yield


app = FastAPI(title="B2 to C1 API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    user = User(
        username=data.username.lower(),
        email=data.email.lower(),
        name=data.name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese usuario o correo")
    db.refresh(user)
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@app.post("/api/auth/login", response_model=TokenOut)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    identity = data.user.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(func.lower(User.username) == identity, func.lower(User.email) == identity)
        )
    )
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@app.post("/api/assessments", response_model=AssessmentOut, status_code=201)
def start(data: StartRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    active = db.scalar(select(Assessment).where(Assessment.user_id == user.id, Assessment.status == "in_progress"))
    if active:
        return assessment_out(db, active)
    item = Assessment(user_id=user.id, level=data.level)
    db.add(item)
    try:
        db.flush()
        item.questions = generate_assessment_questions(item.id, data.level)
        db.commit()
        db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        active = db.scalar(select(Assessment).where(Assessment.user_id == user.id, Assessment.status == "in_progress"))
        if active:
            return assessment_out(db, active)
        raise HTTPException(status_code=503, detail="No se pudo reservar una evaluación nueva. Inténtalo nuevamente.") from exc
    except QuestionGenerationError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="No se pudo guardar la evaluación generada. Inténtalo nuevamente.") from exc
    return assessment_out(db, item)


@app.get("/api/assessments/current", response_model=AssessmentOut | None)
def current(user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(Assessment).where(Assessment.user_id == user.id, Assessment.status == "in_progress").order_by(Assessment.started_at.desc()))
    return assessment_out(db, item) if item else None


@app.post("/api/assessments/{assessment_id}/answers", response_model=AnswerResult)
def answer(assessment_id: int, data: AnswerRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(Assessment, assessment_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    if item.status != "in_progress":
        raise HTTPException(status_code=409, detail="La evaluación ya terminó")
    question = db.get(Question, data.question_id)
    if not question or question.level != item.level or question.assessment_id != item.id:
        raise HTTPException(status_code=400, detail="Pregunta inválida")
    expected = next_question(db, item)
    if not expected or expected.id != question.id:
        raise HTTPException(status_code=409, detail="Responde la pregunta actual antes de continuar")
    if db.scalar(select(Answer).where(Answer.assessment_id == item.id, Answer.question_id == question.id)):
        raise HTTPException(status_code=409, detail="Esta pregunta ya fue respondida")
    if data.selected_answer not in question.choices:
        raise HTTPException(status_code=400, detail="La respuesta no pertenece a las opciones de la pregunta")
    correct = data.selected_answer == question.correct_answer
    db.add(Answer(assessment_id=item.id, question_id=question.id, selected_answer=data.selected_answer, is_correct=correct))
    db.flush()
    answered = db.scalar(select(func.count(Answer.id)).where(Answer.assessment_id == item.id)) or 0
    following = next_question(db, item)
    item.current_index = answered
    if following:
        item.current_module = following.module
    if answered >= 100:
        item.status = "completed"
        item.completed_at = utcnow()
        correct_answers = db.scalar(
            select(func.count(Answer.id)).where(Answer.assessment_id == item.id, Answer.is_correct.is_(True))
        ) or 0
        item.total_score = 100 * correct_answers / answered
    db.commit()
    db.refresh(item)
    return AnswerResult(correct=correct, correct_answer=question.correct_answer, explanation=question.explanation, assessment=assessment_out(db, item))


@app.get("/api/assessments/{assessment_id}/results", response_model=ResultOut)
def results(assessment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(Assessment, assessment_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    return result_out(item)


@app.get("/api/dashboard", response_model=DashboardOut)
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = list(db.scalars(select(Assessment).where(Assessment.user_id == user.id).order_by(Assessment.started_at.desc())).all())
    active = next((item for item in items if item.status == "in_progress"), None)
    history = [result_out(item) for item in items if item.status == "completed"]
    return DashboardOut(active=assessment_out(db, active) if active else None, history=history, suggestions=suggestions(history))


def _vocabulary_word_out(item: VocabularyWord) -> VocabularyWordOut:
    question = item.question
    return VocabularyWordOut(
        id=item.id,
        question_id=item.question_id,
        word=item.word,
        status=item.status,
        level=question.level,
        reading_title=f"Lectura {question.position} · {question.level.value}",
        added_at=item.added_at,
        learned_at=item.learned_at,
    )


@app.post("/api/vocabulary", response_model=VocabularyWordOut, status_code=201)
def save_vocabulary_word(data: VocabularyCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    question = db.scalar(
        select(Question)
        .join(Assessment, Assessment.id == Question.assessment_id)
        .where(Question.id == data.question_id, Assessment.user_id == user.id)
    )
    if not question or question.module != Module.reading:
        raise HTTPException(status_code=404, detail="Lectura no encontrada")
    word = data.word.strip(" .,;:!?\"'()[]{}“”‘’").strip()
    if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿ]+)*", word):
        raise HTTPException(status_code=422, detail="Selecciona una sola palabra válida")
    normalized = word.casefold().replace("’", "'")
    item = db.scalar(
        select(VocabularyWord).where(
            VocabularyWord.user_id == user.id,
            VocabularyWord.question_id == question.id,
            VocabularyWord.normalized_word == normalized,
        )
    )
    now = utcnow()
    if item is None:
        item = VocabularyWord(
            user_id=user.id,
            question_id=question.id,
            word=word,
            normalized_word=normalized,
            status=data.status,
            learned_at=now if data.status == "learned" else None,
        )
        db.add(item)
    else:
        item.word = word
        item.status = data.status
        item.learned_at = now if data.status == "learned" else None
    db.commit()
    db.refresh(item)
    return _vocabulary_word_out(item)


@app.patch("/api/vocabulary/{word_id}", response_model=VocabularyWordOut)
def update_vocabulary_word(word_id: int, data: VocabularyStatusUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(VocabularyWord).where(VocabularyWord.id == word_id, VocabularyWord.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Palabra no encontrada")
    item.status = data.status
    item.learned_at = utcnow() if data.status == "learned" else None
    db.commit()
    db.refresh(item)
    return _vocabulary_word_out(item)


@app.get("/api/vocabulary", response_model=VocabularyOverview)
def vocabulary_overview(question_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = (
        select(VocabularyWord)
        .join(Question, Question.id == VocabularyWord.question_id)
        .where(VocabularyWord.user_id == user.id)
        .order_by(VocabularyWord.updated_at.desc())
    )
    if question_id is not None:
        query = query.where(VocabularyWord.question_id == question_id)
    items = list(db.scalars(query).all())
    groups: dict[int, list[VocabularyWord]] = {}
    for item in items:
        groups.setdefault(item.question_id, []).append(item)
    readings = []
    for source_id, source_items in groups.items():
        question = source_items[0].question
        readings.append(ReadingVocabularyStats(
            question_id=source_id,
            level=question.level,
            title=f"Lectura {question.position} · {question.level.value}",
            total=len(source_items),
            learning=sum(item.status == "learning" for item in source_items),
            learned=sum(item.status == "learned" for item in source_items),
        ))
    return VocabularyOverview(
        total=len(items),
        learning=sum(item.status == "learning" for item in items),
        learned=sum(item.status == "learned" for item in items),
        unique_words=len({item.normalized_word for item in items}),
        readings=readings,
        words=[_vocabulary_word_out(item) for item in items],
    )

