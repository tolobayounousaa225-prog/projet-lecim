"""Page de connexion à deux entrées (faîtière / bureau de la PSIE) et « mot de passe oublié »."""
import datetime
import re

import pytest

from app import models, password_reset
from app.rate_limit import reset as reset_rate_limits
from app.security import verify_password

from .conftest import PASSWORD, client_for, make_faitiere, make_user

NEW = "Nouveau-mdp-2026"


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr("app.routers.reinitialisation.send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def link_in(mail) -> str:
    return re.search(r"https?://[^\s]+/mot-de-passe-oublie/[\w-]+", mail[2]).group(0)


def path_of(url: str) -> str:
    return "/" + url.split("/", 3)[3]


# ---------------------------------------------------------------- les deux entrées

def test_login_window_has_two_entry_buttons_logo_and_forgot_link(anon):
    page = anon.get("/login").text
    assert 'href="/login/faitiere"' in page and 'href="/login"' in page
    assert "Faîtière" in page and "Bureau de la PSIE" in page
    assert "/mot-de-passe-oublie" in page and "/static/logo.png" in page
    assert 'class="topbar"' not in page and 'href="/apropos"' not in page
    fa = anon.get("/login/faitiere").text
    assert "Espace faîtière" in fa and 'action="/login/faitiere"' in fa
    assert "Espace du bureau de la PSIE" in page and 'name="espace" value="bureau"' in page


def test_arabic_login_window(anon):
    anon.cookies.set("lang", "ar")
    page = anon.get("/login").text
    assert "فضاء مكتب المنصة" in page and "هل نسيتم كلمة المرور؟" in page and 'dir="rtl"' in page


def test_federation_and_bureau_each_log_in_through_their_own_window(db, anon):
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    make_user(db, "den@psie.ci", "den")
    assert anon.post("/login/faitiere", data={"email": "rep@psie.ci", "password": PASSWORD}).status_code == 303
    assert anon.post("/login", data={"email": "den@psie.ci", "password": PASSWORD, "espace": "bureau"}).status_code == 303


def test_wrong_window_gives_a_helpful_message_and_no_session(db):
    from fastapi.testclient import TestClient
    from app.main import app
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    make_user(db, "den@psie.ci", "den")
    c = TestClient(app, follow_redirects=False)
    r = c.post("/login", data={"email": "rep@psie.ci", "password": PASSWORD, "espace": "bureau"})
    assert r.status_code == 403 and "Faîtière" in r.text and "access_token" not in r.cookies
    r = c.post("/login/faitiere", data={"email": "den@psie.ci", "password": PASSWORD})
    assert r.status_code == 403 and "bureau de la PSIE" in r.text and "access_token" not in r.cookies
    assert c.get("/admin").status_code == 303                                  # toujours pas connecté


def test_wrong_window_is_only_revealed_after_the_right_password(db, anon):
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    bad = anon.post("/login", data={"email": "rep@psie.ci", "password": "mauvais", "espace": "bureau"})
    assert bad.status_code == 401 and "Faîtière" not in bad.text.split("auth-card")[1].split("<form")[0].replace("Faîtière</a>", "")


def test_old_clients_posting_without_the_window_field_still_work(db, anon):
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    assert anon.post("/login", data={"email": "rep@psie.ci", "password": PASSWORD}).status_code == 303


def test_errors_keep_the_user_in_the_same_window(db, anon):
    r = anon.post("/login/faitiere", data={"email": "x@psie.ci", "password": "nope"})
    assert r.status_code == 401 and 'action="/login/faitiere"' in r.text


# ---------------------------------------------------------------- mot de passe oublié

def test_forgot_password_sends_a_one_hour_single_use_link(db, anon, mails):
    make_user(db, "den@psie.ci", "den")
    r = anon.post("/mot-de-passe-oublie", data={"email": "DEN@psie.ci "})
    assert r.status_code == 200 and "lien de réinitialisation" in r.text
    assert len(mails) == 1 and mails[0][0] == "den@psie.ci"
    url = link_in(mails[0])
    assert url.startswith("http://localhost:8100/mot-de-passe-oublie/")
    assert anon.get(path_of(url)).status_code == 200
    assert anon.post(path_of(url), data={"new": NEW, "confirm": NEW}).status_code == 303
    user = db.query(models.User).filter_by(email="den@psie.ci").one()
    assert verify_password(NEW, user.hashed_password)
    assert anon.post("/login", data={"email": "den@psie.ci", "password": NEW}).status_code == 303
    assert anon.post("/login", data={"email": "den@psie.ci", "password": PASSWORD}).status_code == 401
    # usage unique
    assert anon.get(path_of(url)).status_code == 400
    assert anon.post(path_of(url), data={"new": "Autre-mdp-2026", "confirm": "Autre-mdp-2026"}).status_code == 400
    assert db.query(models.AuditLog).filter_by(action="reinitialisation_mdp").count() == 1


def test_the_answer_is_identical_for_unknown_and_known_accounts(db, anon, mails):
    make_user(db, "den@psie.ci", "den")
    known = anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    unknown = anon.post("/mot-de-passe-oublie", data={"email": "inconnu@psie.ci"})
    assert known.status_code == unknown.status_code == 200
    strip = lambda t: re.sub(r"\s+", " ", t.split("<main")[1])
    assert strip(known.text) == strip(unknown.text)
    assert [m[0] for m in mails] == ["den@psie.ci"]                          # un seul message, jamais pour l'inconnu


def test_disabled_accounts_get_no_link(db, anon, mails):
    user = make_user(db, "den@psie.ci", "den")
    user.is_active = False
    db.commit()
    assert anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"}).status_code == 200
    assert mails == []


def test_only_a_hash_of_the_token_is_stored(db, anon, mails):
    make_user(db, "den@psie.ci", "den")
    anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    token = link_in(mails[0]).rsplit("/", 1)[1]
    row = db.query(models.ReinitialisationMdp).one()
    assert row.token_hash == password_reset.hash_token(token) and token not in row.token_hash
    assert (row.expires_at - row.created_at) <= datetime.timedelta(minutes=61)


def test_expired_and_forged_links_are_refused(db, anon, mails):
    make_user(db, "den@psie.ci", "den")
    anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    url = path_of(link_in(mails[0]))
    row = db.query(models.ReinitialisationMdp).one()
    row.expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
    db.commit()
    assert anon.get(url).status_code == 400
    assert anon.post(url, data={"new": NEW, "confirm": NEW}).status_code == 400
    assert anon.get("/mot-de-passe-oublie/" + "a" * 43).status_code == 400
    user = db.query(models.User).filter_by(email="den@psie.ci").one()
    assert verify_password(PASSWORD, user.hashed_password)


def test_new_password_must_follow_the_policy_and_match(db, anon, mails):
    make_user(db, "den@psie.ci", "den")
    anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    url = path_of(link_in(mails[0]))
    assert anon.post(url, data={"new": NEW, "confirm": "autre"}).status_code == 400
    assert anon.post(url, data={"new": "court1", "confirm": "court1"}).status_code == 400
    assert anon.post(url, data={"new": "seulement-lettres", "confirm": "seulement-lettres"}).status_code == 400
    assert anon.get(url).status_code == 200                                    # le lien reste utilisable après une erreur
    assert anon.post(url, data={"new": NEW, "confirm": NEW}).status_code == 303


def test_a_new_request_invalidates_the_previous_link_after_the_cooldown(db, anon, mails):
    make_user(db, "den@psie.ci", "den")
    anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    assert len(mails) == 1                                                     # délai de 2 minutes entre deux messages
    db.query(models.ReinitialisationMdp).update({"created_at": datetime.datetime.utcnow() - datetime.timedelta(minutes=5)})
    db.commit()
    anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    assert len(mails) == 2
    assert anon.get(path_of(link_in(mails[0]))).status_code == 400            # l'ancien lien ne marche plus
    assert anon.get(path_of(link_in(mails[1]))).status_code == 200


def test_requests_are_rate_limited(db, anon, mails):
    reset_rate_limits()
    codes = [anon.post("/mot-de-passe-oublie", data={"email": f"x{i}@psie.ci"}).status_code for i in range(7)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_reset_unlocks_a_locked_account(db, anon, mails):
    user = make_user(db, "den@psie.ci", "den")
    user.locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    db.commit()
    anon.post("/mot-de-passe-oublie", data={"email": "den@psie.ci"})
    anon.post(path_of(link_in(mails[0])), data={"new": NEW, "confirm": NEW})
    assert anon.post("/login", data={"email": "den@psie.ci", "password": NEW}).status_code == 303


def test_reset_does_not_skip_the_two_factor_code(db, anon, mails, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "two_factor_enabled", True)
    monkeypatch.setattr("app.routers.auth.send_email", lambda *a, **k: True)
    make_user(db, "admin@psie.ci", "admin")
    anon.post("/mot-de-passe-oublie", data={"email": "admin@psie.ci"})
    anon.post(path_of(link_in(mails[0])), data={"new": NEW, "confirm": NEW})
    r = anon.post("/login", data={"email": "admin@psie.ci", "password": NEW})
    assert r.status_code == 303 and r.headers["location"] == "/login/verification" and "access_token" not in r.cookies


def test_success_message_is_shown_on_the_login_window(anon):
    assert "Mot de passe modifié" in anon.get("/login?reinit=1").text
    assert "Mot de passe modifié" not in anon.get("/login").text


def test_forgot_pages_are_bare_and_translated(anon):
    page = anon.get("/mot-de-passe-oublie").text
    assert 'class="topbar"' not in page and 'name="email"' in page
    anon.cookies.set("lang", "ar")
    assert "نسيان كلمة المرور" in anon.get("/mot-de-passe-oublie").text
