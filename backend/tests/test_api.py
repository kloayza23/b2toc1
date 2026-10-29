from collections import Counter

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import verify_password
from app.database import get_db
from app.models import Assessment, User


def test_registration_login_and_identity(client):
    payload = {"username": "lin", "name": "Lin Test", "email": "lin@example.com", "password": "securepass123"}
    created = client.post("/api/auth/register", json=payload)
    assert created.status_code == 201
    token = created.json()["access_token"]
    identity = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert identity["email"] == payload["email"]
    assert identity["username"] == payload["username"]
    assert client.post("/api/auth/login", json={"user": payload["username"], "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"user": payload["username"], "password": payload["password"]}).status_code == 200
    assert client.post("/api/auth/login", json={"user": payload["email"], "password": payload["password"]}).status_code == 200
    assert client.post("/api/auth/register", json=payload).status_code == 409

    db = next(client.app.dependency_overrides[get_db]())
    stored = db.scalar(select(User).where(User.username == payload["username"]))
    assert stored.password_hash != payload["password"]
    assert verify_password(payload["password"], stored.password_hash)
    db.close()


def test_demo_seed_is_idempotent_and_login_works(client):
    from app.seed import seed_demo_user

    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)
    try:
        for _ in range(2):
            seed_demo_user(
                db,
                username="demo",
                email="demo@example.com",
                name="Usuario Demo",
                password="LevelUpDemo2026!",
            )
        assert db.scalar(select(func.count(User.id)).where(User.username == "demo")) == 1
    finally:
        db_dependency.close()

    response = client.post(
        "/api/auth/login",
        json={"user": "demo", "password": "LevelUpDemo2026!"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "demo@example.com"


def test_assessment_answer_is_saved_and_resumable(client, auth, monkeypatch):
    started = client.post("/api/assessments", headers=auth, json={"level": "B2"})
    assert started.status_code == 201
    assessment = started.json()
    assert assessment["total"] == 100
    assert assessment["question"]["module"] == "speech"
    question = assessment["question"]

    def must_not_regenerate(*_):
        raise AssertionError("reanudar no debe llamar a OpenAI")

    monkeypatch.setattr("app.main.generate_assessment_questions", must_not_regenerate)
    restarted = client.post("/api/assessments", headers=auth, json={"level": "C1"})
    assert restarted.status_code == 201
    assert restarted.json()["id"] == assessment["id"]
    assert restarted.json()["level"] == "B2"

    answered = client.post(
        f"/api/assessments/{assessment['id']}/answers",
        headers=auth,
        json={"question_id": question["id"], "selected_answer": question["choices"][0]},
    )
    assert answered.status_code == 200
    assert answered.json()["assessment"]["answered"] == 1
    db = next(client.app.dependency_overrides[get_db]())
    persisted = db.get(Assessment, assessment["id"])
    assert persisted.current_index == 1
    db.close()

    resumed = client.get("/api/assessments/current", headers=auth).json()
    assert resumed["id"] == assessment["id"]
    assert resumed["answered"] == 1
    assert resumed["question"]["id"] != question["id"]
    duplicate = client.post(
        f"/api/assessments/{assessment['id']}/answers",
        headers=auth,
        json={"question_id": question["id"], "selected_answer": question["choices"][0]},
    )
    assert duplicate.status_code == 409


def test_dashboard_has_deterministic_suggestions(client, auth):
    dashboard = client.get("/api/dashboard", headers=auth)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["active"] is None
    assert len(body["suggestions"]) == 3


def test_reading_vocabulary_is_saved_and_grouped_by_reading(client, auth):
    current = client.post("/api/assessments", headers=auth, json={"level": "B2"}).json()
    speech_question_id = current["question"]["id"]
    for _ in range(50):
        question = current["question"]
        response = client.post(
            f"/api/assessments/{current['id']}/answers",
            headers=auth,
            json={"question_id": question["id"], "selected_answer": question["choices"][0]},
        )
        assert response.status_code == 200
        current = response.json()["assessment"]

    reading = current["question"]
    assert reading["module"] == "reading"
    created = client.post(
        "/api/vocabulary",
        headers=auth,
        json={"question_id": reading["id"], "word": "Determination", "status": "learning"},
    )
    assert created.status_code == 201
    word_id = created.json()["id"]

    updated = client.post(
        "/api/vocabulary",
        headers=auth,
        json={"question_id": reading["id"], "word": "determination", "status": "learned"},
    )
    assert updated.status_code == 201
    assert updated.json()["id"] == word_id

    overview = client.get("/api/vocabulary", headers=auth).json()
    assert overview["total"] == 1
    assert overview["unique_words"] == 1
    assert overview["learned"] == 1
    assert overview["readings"][0]["question_id"] == reading["id"]
    assert overview["readings"][0]["learned"] == 1

    changed = client.patch(
        f"/api/vocabulary/{word_id}", headers=auth, json={"status": "learning"}
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "learning"
    assert client.get(
        f"/api/vocabulary?question_id={reading['id']}", headers=auth
    ).json()["learning"] == 1

    assert client.post(
        "/api/vocabulary",
        headers=auth,
        json={"question_id": speech_question_id, "word": "hello", "status": "learning"},
    ).status_code == 404
    assert client.post(
        "/api/vocabulary",
        headers=auth,
        json={"question_id": reading["id"], "word": "two words", "status": "learning"},
    ).status_code == 422


def test_full_assessment_completes_with_four_modules(client, auth):
    current = client.post("/api/assessments", headers=auth, json={"level": "A2"}).json()
    seen_modules = Counter()
    for index in range(100):
        question = current["question"]
        seen_modules[question["module"]] += 1
        correct_index = (-((question["position"] - 1) % len(question["choices"]))) % len(question["choices"])
        selected_index = (correct_index + 1) % len(question["choices"]) if question["module"] == "speech" else correct_index
        selected = question["choices"][selected_index]
        response = client.post(
            f"/api/assessments/{current['id']}/answers",
            headers=auth,
            json={"question_id": question["id"], "selected_answer": selected},
        )
        assert response.status_code == 200, (index, response.text)
        current = response.json()["assessment"]
        if index == 24:
            assert current["current_module"] == "writing"
        elif index == 49:
            assert current["current_module"] == "reading"
        elif index == 74:
            assert current["current_module"] == "listening"
    assert current["status"] == "completed"
    assert current["question"] is None
    assert seen_modules == {"speech": 25, "writing": 25, "reading": 25, "listening": 25}
    result = client.get(f"/api/assessments/{current['id']}/results", headers=auth).json()
    assert result["score"] == 75
    assert result["module_scores"] == {"speech": 0, "writing": 100, "reading": 100, "listening": 100}
    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert dashboard["history"][0]["id"] == current["id"]
    assert "expresión oral" in dashboard["suggestions"][0]

    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)
    try:
        persisted = db.get(Assessment, current["id"])
        assert persisted.current_index == 100
        assert persisted.current_module.value == "listening"
    finally:
        db_dependency.close()


def test_protected_routes_require_token(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/vocabulary").status_code == 401


def test_rejects_tampered_token_and_answer_outside_choices(client, auth):
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    forged = jwt.encode({"sub": "999999"}, "wrong-secret-that-is-also-at-least-32-bytes", algorithm="HS256")
    assert client.get("/api/dashboard", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        "test-secret-that-is-at-least-32-bytes",
        algorithm="HS256",
    )
    assert client.get("/api/dashboard", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

    assessment = client.post("/api/assessments", headers=auth, json={"level": "B2"}).json()
    response = client.post(
        f"/api/assessments/{assessment['id']}/answers",
        headers=auth,
        json={"question_id": assessment["question"]["id"], "selected_answer": "respuesta inventada"},
    )
    assert response.status_code == 400
    assert client.get("/api/assessments/current", headers=auth).json()["answered"] == 0


def test_cors_only_allows_configured_origins(client):
    allowed = client.options(
        "/api/dashboard",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"

    rejected = client.options(
        "/api/dashboard",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_openai_unavailable_returns_actionable_error(client, auth, monkeypatch):
    from app.questions import QuestionGenerationError

    def unavailable(*_):
        raise QuestionGenerationError("OpenAI no está disponible; revisa OPENAI_API_KEY")

    monkeypatch.setattr("app.main.generate_assessment_questions", unavailable)
    response = client.post("/api/assessments", headers=auth, json={"level": "B1"})
    assert response.status_code == 503
    assert "OpenAI" in response.json()["detail"]
    assert client.get("/api/assessments/current", headers=auth).json() is None
    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)
    try:
        assert db.scalar(select(func.count(Assessment.id))) == 0
    finally:
        db_dependency.close()


def test_openai_structured_batch_is_validated(monkeypatch):
    from app.models import Level, Module
    from app.questions import GeneratedBatch, _request_batch

    captured = {}

    class FakeResponses:
        def parse(self, **kwargs):
            captured.update(kwargs)
            questions = [{
                "prompt": f"Selecciona la respuesta correcta para el ejercicio número {i}",
                "context": None,
                "choices": [f"A{i}", f"B{i}", f"C{i}", f"D{i}"],
                "correct_answer": f"A{i}",
                "explanation": "Esta es la respuesta apropiada para el objetivo evaluado.",
            } for i in range(25)]
            return type("Response", (), {"output_parsed": GeneratedBatch.model_validate({"questions": questions})})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr("app.questions.OpenAI", FakeClient)
    batch = _request_batch(Level.B2, Module.writing)
    assert len(batch.questions) == 25
    assert captured["model"] == "gpt-4o-mini"
    assert captured["text_format"] is GeneratedBatch
    assert captured["client"]["api_key"] == "sk-test-only-not-a-real-key"


def test_openai_invalid_or_duplicate_batch_is_rejected(monkeypatch):
    from app.models import Level, Module
    from app.questions import GeneratedBatch, QuestionGenerationError, _request_batch

    class FakeResponses:
        def parse(self, **_):
            questions = [{
                "prompt": "Este prompt se repite en todas las preguntas",
                "context": None,
                "choices": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "explanation": "Explicación suficientemente extensa.",
            } for _ in range(25)]
            return type("Response", (), {"output_parsed": GeneratedBatch.model_validate({"questions": questions})})()

    class FakeClient:
        def __init__(self, **_):
            self.responses = FakeResponses()

    monkeypatch.setattr("app.questions.OpenAI", FakeClient)
    with pytest.raises(QuestionGenerationError):
        _request_batch(Level.B2, Module.writing)


def test_openai_generates_exactly_four_valid_batches(monkeypatch):
    from app.models import Level
    from app.questions import GeneratedBatch, generate_assessment_questions

    calls = []

    class FakeResponses:
        def parse(self, **kwargs):
            user_prompt = kwargs["input"][1]["content"]
            module = next(name for name in ("speech", "writing", "reading", "listening") if f"module {name}" in user_prompt)
            calls.append((module, kwargs["model"]))
            needs_context = module in {"reading", "listening"}
            questions = [{
                "prompt": f"Pregunta única {module} generada número {i}",
                "context": f"Contexto en inglés {module} {i}" if needs_context else None,
                "choices": [f"A{i}", f"B{i}", f"C{i}", f"D{i}"],
                "correct_answer": f"A{i}",
                "explanation": "Explicación suficientemente extensa para validar.",
            } for i in range(25)]
            return type("Response", (), {"output_parsed": GeneratedBatch.model_validate({"questions": questions})})()

    class FakeClient:
        def __init__(self, **_):
            self.responses = FakeResponses()

    monkeypatch.setattr("app.questions.OpenAI", FakeClient)
    questions = generate_assessment_questions(42, Level.C1)
    assert len(questions) == 100
    assert Counter(question.module.value for question in questions) == {
        "speech": 25, "writing": 25, "reading": 25, "listening": 25,
    }
    assert calls == [("speech", "gpt-4o-mini"), ("writing", "gpt-4o-mini"), ("reading", "gpt-4o-mini"), ("listening", "gpt-4o-mini")]


def test_persistence_failure_rolls_back_and_returns_503(client, auth, monkeypatch):
    original_commit = Session.commit

    def fail_commit(_):
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post("/api/assessments", headers=auth, json={"level": "B2"})
    assert response.status_code == 503
    assert "guardar" in response.json()["detail"]
    monkeypatch.setattr(Session, "commit", original_commit)
    assert client.get("/api/assessments/current", headers=auth).json() is None

