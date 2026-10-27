import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-bytes"
os.environ["OPENAI_API_KEY"] = "sk-test-only-not-a-real-key"
os.environ["OPENAI_MODEL"] = "gpt-4o-mini"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Module, Question


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    def fake_generation(assessment_id, level):
        generated = []
        for module in Module:
            for position in range(1, 26):
                choices = [f"Opción {letter} {position}" for letter in "ABCD"]
                correct_index = (-((position - 1) % 4)) % 4
                generated.append(Question(
                    assessment_id=assessment_id, level=level, module=module, position=position,
                    prompt=f"Pregunta generada para {module.value} número {position}",
                    context=f"Contexto generado {position}" if module in (Module.reading, Module.listening) else None,
                    choices=choices, correct_answer=choices[correct_index],
                    explanation="Explicación generada para la prueba.",
                ))
        return generated

    monkeypatch.setattr("app.main.generate_assessment_questions", fake_generation)

    def override_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth(client):
    response = client.post("/api/auth/register", json={"username": "ada", "name": "Ada Test", "email": "ada@example.com", "password": "securepass123"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

