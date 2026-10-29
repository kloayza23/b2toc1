from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from .models import Level, Module


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    user: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    name: str
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class StartRequest(BaseModel):
    level: Level = Level.B2


class AnswerRequest(BaseModel):
    question_id: int
    selected_answer: str = Field(min_length=1, max_length=1000)


class QuestionOut(BaseModel):
    id: int
    level: Level
    module: Module
    position: int
    prompt: str
    context: str | None
    choices: list[str]
    model_config = ConfigDict(from_attributes=True)


class AssessmentOut(BaseModel):
    id: int
    level: Level
    status: str
    current_module: Module
    current_index: int
    answered: int
    total: int = 100
    progress_percent: float
    question: QuestionOut | None


class AnswerResult(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str
    assessment: AssessmentOut


class ResultOut(BaseModel):
    id: int
    level: Level
    status: str
    score: float
    module_scores: dict[str, float]
    answered: int
    started_at: datetime
    completed_at: datetime | None


class DashboardOut(BaseModel):
    active: AssessmentOut | None
    history: list[ResultOut]
    suggestions: list[str]


class VocabularyCreate(BaseModel):
    question_id: int
    word: str = Field(min_length=1, max_length=100)
    status: Literal["learning", "learned"] = "learning"


class VocabularyStatusUpdate(BaseModel):
    status: Literal["learning", "learned"]


class VocabularyWordOut(BaseModel):
    id: int
    question_id: int
    word: str
    status: str
    level: Level
    reading_title: str
    added_at: datetime
    learned_at: datetime | None


class ReadingVocabularyStats(BaseModel):
    question_id: int
    level: Level
    title: str
    total: int
    learning: int
    learned: int


class VocabularyOverview(BaseModel):
    total: int
    learning: int
    learned: int
    unique_words: int
    readings: list[ReadingVocabularyStats]
    words: list[VocabularyWordOut]

