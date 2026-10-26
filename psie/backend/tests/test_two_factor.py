import re

import pytest

from app import emailing, models
from app.config import settings
from app.routers import auth as auth_router

from .conftest import PASSWORD, make_user
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def two_factor(monkeypatch):
    monkeypatch.setattr(settings, "two_factor_enabled", True)
    sent = []

    def fake_send(to, subject, body):
        sent.append((to, body))
        return True

    monkeypatch.setattr(auth_router, "send_email", fake_send)
    return sent


def new_client():
    return TestClient(app, follow_redirects=False)


def code_from(sent):
    return re.search(r"\b(\d{6})\b", sent[-1][1]).group(1)


def test_admin_login_requires_code(db, two_factor):
    make_user(db, "admin@psie.local", "admin")
    c = new_client()
    r = c.post("/login", data={"email": "admin@psie.local", "password": PASSWORD})
    assert r.status_code == 303 and r.headers["location"] == "/login/verification"
    assert "access_token" not in c.cookies          # pas encore de session
    assert c.get("/admin").status_code == 303        # toujours renvoyé vers la connexion
    r = c.post("/login/verification", data={"code": code_from(two_factor)})
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    assert c.get("/admin").status_code == 200


def test_wrong_code_rejected_then_locked(db, two_factor):
    make_user(db, "fin@psie.local", "finances")
    c = new_client()
    c.post("/login", data={"email": "fin@psie.local", "password": PASSWORD})
    good = code_from(two_factor)
    bad = "000000" if good != "000000" else "111111"
    for _ in range(4):
        assert c.post("/login/verification", data={"code": bad}).status_code == 401
    assert c.post("/login/verification", data={"code": bad}).status_code == 429  # 5e échec : verrouillé
    # Même le bon code ne passe plus
    assert c.post("/login/verification", data={"code": good}).status_code == 429
    assert "access_token" not in c.cookies


def test_other_roles_skip_second_factor(db, two_factor):
    make_user(db, "den@psie.local", "den")
    c = new_client()
    r = c.post("/login", data={"email": "den@psie.local", "password": PASSWORD})
    assert r.headers["location"] == "/admin" and two_factor == []


def test_login_fails_closed_when_email_unavailable(db, monkeypatch):
    monkeypatch.setattr(settings, "two_factor_enabled", True)
    monkeypatch.setattr(auth_router, "send_email", lambda *a: False)
    make_user(db, "admin@psie.local", "admin")
    c = new_client()
    r = c.post("/login", data={"email": "admin@psie.local", "password": PASSWORD})
    assert r.status_code == 503 and "access_token" not in c.cookies


def test_pending_token_cannot_be_used_as_session(db, two_factor):
    make_user(db, "admin@psie.local", "admin")
    c = new_client()
    c.post("/login", data={"email": "admin@psie.local", "password": PASSWORD})
    pending = c.cookies.get("two_factor_pending")
    other = new_client()
    other.cookies.set("access_token", pending)
    assert other.get("/admin").status_code == 303


def test_no_smtp_means_email_not_sent():
    assert emailing.send_email("a@b.c", "x", "y") is False  # SMTP non configuré en test
