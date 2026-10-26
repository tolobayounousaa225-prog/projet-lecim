from app import models
from app.login_security import MAX_FAILED_LOGIN_ATTEMPTS

from .conftest import PASSWORD, client_for, make_faitiere, make_user


def test_pages_require_login(anon):
    for url in ("/admin", "/faitieres", "/mandats", "/users", "/audit"):
        response = anon.get(url)
        assert response.status_code == 303 and response.headers["location"] == "/login", url


def test_login_ok_redirects_by_role(db):
    f = make_faitiere(db, "LECIM")
    make_user(db, "den@psie.local", "den")
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=f.id)
    assert client_for("den@psie.local").get("/portail").headers["location"] == "/admin"
    rep = client_for("rep@psie.local")
    assert rep.get("/portail").headers["location"] == f"/faitieres/{f.id}"


def test_login_wrong_password(db, anon):
    make_user(db, "den@psie.local", "den")
    response = anon.post("/login", data={"email": "den@psie.local", "password": "mauvais123"})
    assert response.status_code == 401
    assert "access_token" not in response.cookies


def test_account_locks_after_repeated_failures(db, anon):
    make_user(db, "den@psie.local", "den")
    for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
        anon.post("/login", data={"email": "den@psie.local", "password": "mauvais123"})
    # Même avec le bon mot de passe, le compte reste verrouillé
    response = anon.post("/login", data={"email": "den@psie.local", "password": PASSWORD})
    assert response.status_code == 429


def test_disabled_account_cannot_login(db, anon):
    user = make_user(db, "den@psie.local", "den")
    user.is_active = False
    db.commit()
    response = anon.post("/login", data={"email": "den@psie.local", "password": PASSWORD})
    assert response.status_code == 401


def test_csrf_foreign_origin_rejected(db):
    make_user(db, "sec@psie.local", "secretaire")
    client = client_for("sec@psie.local")
    response = client.post(
        "/faitieres/new", data={"nom": "X", "sigle": "X"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert db.query(models.Faitiere).count() == 0


def test_same_origin_post_accepted(db):
    make_user(db, "sec@psie.local", "secretaire")
    client = client_for("sec@psie.local")
    response = client.post(
        "/faitieres/new", data={"nom": "X", "sigle": "x"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 303


def test_language_switch_sets_rtl(anon):
    anon.cookies.set("lang", "ar")
    page = anon.get("/login")
    assert 'dir="rtl"' in page.text and 'lang="ar"' in page.text
    anon.cookies.set("lang", "fr")
    assert 'dir="ltr"' in anon.get("/login").text


def test_data_labels_follow_language(db):
    make_faitiere(db, "LECIM")
    make_user(db, "den@psie.local", "den")
    client = client_for("den@psie.local")
    assert "Membre fondateur" in client.get("/faitieres").text
    client.cookies.set("lang", "ar")
    page = client.get("/faitieres").text
    assert "عضو مؤسس" in page and "Membre fondateur" not in page
