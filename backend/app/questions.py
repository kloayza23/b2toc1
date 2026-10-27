from typing import Annotated

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .config import get_settings
from .models import Level, Module, Question


class QuestionGenerationError(RuntimeError):
    """OpenAI could not produce a complete, valid batch."""


Choice = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=12, max_length=700)
    context: str | None = Field(default=None, max_length=2500)
    choices: list[Choice] = Field(min_length=4, max_length=4)
    correct_answer: str = Field(min_length=1, max_length=255)
    explanation: str = Field(min_length=8, max_length=1000)

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, value: list[str]) -> list[str]:
        cleaned = [choice.strip() for choice in value]
        if any(not choice for choice in cleaned) or len({choice.casefold() for choice in cleaned}) != 4:
            raise ValueError("las opciones deben ser distintas y no vacías")
        return cleaned

    @model_validator(mode="after")
    def validate_answer(self):
        self.prompt = self.prompt.strip()
        self.explanation = self.explanation.strip()
        self.context = self.context.strip() if self.context else None
        self.correct_answer = self.correct_answer.strip()
        if not self.prompt or not self.explanation:
            raise ValueError("prompt y explanation no pueden estar vacíos")
        if self.correct_answer not in self.choices:
            raise ValueError("correct_answer debe coincidir exactamente con una opción")
        return self


class GeneratedBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[GeneratedQuestion] = Field(min_length=25, max_length=25)

    @model_validator(mode="after")
    def validate_unique_prompts(self):
        prompts = [item.prompt.casefold() for item in self.questions]
        if len(set(prompts)) != len(prompts):
            raise ValueError("las 25 preguntas deben tener prompts distintos")
        return self


MODULE_GUIDANCE = {
    Module.speech: "oral communication, pronunciation choices, natural expressions and conversational responses",
    Module.writing: "grammar, cohesion, register, sentence editing and written communication",
    Module.reading: "reading comprehension, inference, vocabulary in context and author intent; include a useful English passage in context",
    Module.listening: "listening comprehension, inference, detail and speaker intent; include an English transcript in context for text-to-speech",
}


def _request_batch(level: Level, module: Module) -> GeneratedBatch:
    settings = get_settings()
    if not settings.openai_api_key:
        raise QuestionGenerationError(
            "Falta OPENAI_API_KEY. Configúrala en el archivo .env y reinicia el backend."
        )
    system = (
        "You create rigorous CEFR English assessments. Return only data matching the JSON schema. "
        "Every item must be original, unambiguous and appropriate for the requested CEFR level. "
        "Use exactly four distinct choices and copy one exactly into correct_answer. "
        "Write prompts and explanations in Spanish; learning material and choices may be English. "
        "Do not number prompts or reuse items."
    )
    user = (
        f"Generate exactly 25 questions for CEFR level {level.value}, module {module.value}. "
        f"Focus on {MODULE_GUIDANCE[module]}. For reading and listening, context is required on every item."
    )
    try:
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=1,
        )
        response = client.responses.parse(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=GeneratedBatch,
        )
        batch = response.output_parsed
        if batch is None:
            raise ValueError("el modelo no devolvió preguntas estructuradas")
        if module in (Module.reading, Module.listening) and any(not item.context for item in batch.questions):
            raise ValueError("faltan contextos")
        return batch
    except Exception as exc:
        raise QuestionGenerationError(
            f"No se pudieron generar las preguntas de {module.value}. Comprueba OPENAI_API_KEY, "
            f"la facturación de API y el acceso al modelo '{settings.openai_model}'."
        ) from exc


def generate_assessment_questions(assessment_id: int, level: Level) -> list[Question]:
    questions: list[Question] = []
    for module in (Module.speech, Module.writing, Module.reading, Module.listening):
        batch = _request_batch(level, module)
        questions.extend(
            Question(
                assessment_id=assessment_id,
                level=level,
                module=module,
                position=position,
                prompt=item.prompt,
                context=item.context,
                choices=item.choices,
                correct_answer=item.correct_answer,
                explanation=item.explanation,
            )
            for position, item in enumerate(batch.questions, start=1)
        )
    prompts = [question.prompt.strip().casefold() for question in questions]
    if len(questions) != 100 or len(set(prompts)) != 100:
        raise QuestionGenerationError("OpenAI no generó 100 preguntas únicas para la evaluación.")
    return questions
