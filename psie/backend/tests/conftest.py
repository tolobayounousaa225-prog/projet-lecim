import os
import tempfile

# Base de test : fichier SQLite jetable, défini AVANT l'import de l'application.
# TEST_DATABASE_URL permet de lancer la même suite sur PostgreSQL (utilisé par la CI).
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    _tmp.close()
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["SECRET_KEY"] = "cle-de-test"
os.environ["SCHEDULER_ENABLED"] = "false"
# La double authentification est testée à part (test_two_factor.py)
os.environ["TWO_FACTOR_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password  # noqa: E402

PASSWORD = "Motdepasse1"


@pytest.fixture(autouse=True)
def clean_db():
    from app import rate_limit

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limit.reset()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_user(db, email, role, faitiere_id=None, name=None, origine_id=None):
    user = models.User(
        email=email, full_name=name or email, role=role,
        hashed_password=hash_password(PASSWORD), faitiere_id=faitiere_id, faitiere_origine_id=origine_id,
    )
    db.add(user)
    db.commit()
    return user


def make_faitiere(db, sigle, categorie="fondateur"):
    f = models.Faitiere(sigle=sigle, nom=f"Faîtière {sigle}", categorie=categorie)
    db.add(f)
    db.commit()
    return f


def client_for(email):
    """Client connecté (cookie de session posé par le vrai formulaire de connexion)."""
    client = TestClient(app, follow_redirects=False)
    response = client.post("/login", data={"email": email, "password": PASSWORD})
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def anon():
    return TestClient(app, follow_redirects=False)
