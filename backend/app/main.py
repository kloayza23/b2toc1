from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .auth import create_token, current_user, hash_password, verify_password
from .config import get_settings
from .database import Base, engine, get_db
from .models import Answer, Assessment, Question, User, utcnow
from .questions import OllamaGenerationError, generate_assessment_questions
from .schemas import AnswerRequest, AnswerResult, AssessmentOut, DashboardOut, LoginRequest, RegisterRequest, ResultOut, StartRequest, TokenOut, UserOut
from .services import assessment_out, next_question, result_out, suggestions


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
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
    except OllamaGenerationError as exc:
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

