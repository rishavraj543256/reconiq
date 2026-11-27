import os
os.environ["DATABASE_URL"] = "sqlite:///./test-reconiq.db"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests"
import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(): return TestClient(app)


def register(client, email="analyst@example.com", org="Acme Finance"):
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "CorrectHorse123!", "full_name": "Test Analyst", "organization_name": org})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth(client): return register(client)
