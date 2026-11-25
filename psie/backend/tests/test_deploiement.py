import pathlib

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.config import DEFAULT_SECRET_KEY, Settings, production_problems, settings
from app.database import Base
from app.main import app

GOOD = dict(cookie_secure=True, secret_key="x" * 40, debug=False, two_factor_enabled=True,
            smtp_host="smtp.example.org", public_base_url="https://psie.example.org")


def test_production_checks_accept_a_sound_configuration():
    assert production_problems(Settings(**GOOD)) == []


def test_local_development_is_never_blocked():
    assert production_problems(Settings(cookie_secure=False)) == []


@pytest.mark.parametrize("change,fragment", [
    ({"secret_key": DEFAULT_SECRET_KEY}, "SECRET_KEY"),
    ({"secret_key": "court"}, "SECRET_KEY"),
    ({"debug": True}, "DEBUG"),
    ({"two_factor_enabled": False}, "TWO_FACTOR_ENABLED"),
    ({"smtp_host": ""}, "SMTP_HOST"),
    ({"public_base_url": "http://psie.example.org"}, "PUBLIC_BASE_URL"),
])
def test_production_checks_reject_dangerous_settings(change, fragment):
    problems = production_problems(Settings(**{**GOOD, **change}))
    assert any(fragment in p for p in problems), problems


def test_app_refuses_to_start_with_unsafe_production_config(monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", True)
    monkeypatch.setattr(settings, "secret_key", DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        with TestClient(app):
            pass


def test_security_headers_and_hsts(monkeypatch):
    client = TestClient(app)
    headers = client.get("/login").headers
    assert "script-src 'none'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["x-frame-options"] == "DENY" and "strict-transport-security" not in headers
    monkeypatch.setattr(settings, "cookie_secure", True)
    assert "max-age=31536000" in client.get("/login").headers["strict-transport-security"]


def test_pages_work_under_the_strict_content_security_policy():
    """Aucune page ne doit contenir de script ni de gestionnaire d'événement en ligne."""
    client = TestClient(app)
    for url in ("/", "/login", "/adhesion", "/apropos", "/membres", "/actualites"):
        page = client.get(url).text.lower()
        assert "<script" not in page and " onclick=" not in page and " onerror=" not in page, url


def test_health_endpoints():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/db").json() == {"status": "ok"}


def test_migrations_build_exactly_the_schema_of_the_models(monkeypatch, tmp_path):
    """Garde-fou : si on modifie un modèle sans écrire de migration, ce test échoue."""
    url = f"sqlite:///{tmp_path / 'migr.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    root = pathlib.Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert tables >= {"faitieres", "echeances", "paiements", "assemblees", "votes", "sanctions", "alembic_version"}
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == [], f"Modèles et migrations divergent : {diff}"
