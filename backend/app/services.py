from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Answer, Assessment, Module, Question
from .schemas import AssessmentOut, QuestionOut, ResultOut

MODULE_ORDER = [Module.speech, Module.writing, Module.reading, Module.listening]
MODULE_LABELS = {"speech": "expresión oral", "writing": "escritura", "reading": "lectura", "listening": "escucha"}


def next_question(db: Session, assessment: Assessment) -> Question | None:
    answered_ids = select(Answer.question_id).where(Answer.assessment_id == assessment.id)
    for module in MODULE_ORDER:
        question = db.scalar(
            select(Question)
            .where(
                Question.level == assessment.level,
                Question.assessment_id == assessment.id,
                Question.module == module,
                Question.id.not_in(answered_ids),
            )
            .order_by(Question.position)
        )
        if question:
            return question
    return None


def assessment_out(db: Session, assessment: Assessment) -> AssessmentOut:
    answered = len(assessment.answers)
    question = None if assessment.status == "completed" else next_question(db, assessment)
    return AssessmentOut(
        id=assessment.id,
        level=assessment.level,
        status=assessment.status,
        current_module=question.module if question else assessment.current_module,
        current_index=answered,
        answered=answered,
        progress_percent=round(answered, 1),
        question=QuestionOut.model_validate(question) if question else None,
    )


def result_out(assessment: Assessment) -> ResultOut:
    totals: dict[str, list[bool]] = defaultdict(list)
    for answer in assessment.answers:
        totals[answer.question.module.value].append(answer.is_correct)
    scores = {module.value: round(100 * sum(totals[module.value]) / max(len(totals[module.value]), 1), 1) for module in MODULE_ORDER}
    score = round(100 * sum(a.is_correct for a in assessment.answers) / max(len(assessment.answers), 1), 1)
    return ResultOut(
        id=assessment.id,
        level=assessment.level,
        status=assessment.status,
        score=score,
        module_scores=scores,
        answered=len(assessment.answers),
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
    )


def local_suggestions(history: list[ResultOut]) -> list[str]:
    if not history:
        return [
            "Completa tu primera evaluación para recibir un plan personalizado.",
            "Reserva 20 minutos sin interrupciones y usa auriculares para Listening.",
            "Responde con calma: el objetivo es encontrar tu punto de partida real.",
        ]
    latest = history[0]
    ordered = sorted(latest.module_scores.items(), key=lambda item: item[1])
    weakest, score = ordered[0]
    second = ordered[1][0]
    return [
        f"Prioriza {MODULE_LABELS[weakest]}: obtuvo {score:.0f}%. Practica 15 minutos diarios esta semana.",
        f"Refuerza también {MODULE_LABELS[second]} con ejercicios breves y revisa cada error.",
        "Repite la evaluación después de 7 días de práctica para medir tu avance.",
    ]


def suggestions(history: list[ResultOut]) -> list[str]:
    return local_suggestions(history)

