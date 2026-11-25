from app import models
from app.security import verify_password

from .conftest import PASSWORD, client_for, make_user

NEW = "Nouveau-mdp-2026"


def test_user_changes_own_password(db, anon):
    make_user(db, "den@psie.local", "den")
    c = client_for("den@psie.local")
    r = c.post("/mot-de-passe", data={"current": PASSWORD, "new": NEW, "confirm": NEW})
    assert r.status_code == 200 and "modifié" in r.text
    user = db.query(models.User).filter_by(email="den@psie.local").one()
    assert verify_password(NEW, user.hashed_password) and not verify_password(PASSWORD, user.hashed_password)
    assert db.query(models.AuditLog).filter_by(action="changement_mdp").count() == 1
    assert anon.post("/login", data={"email": "den@psie.local", "password": PASSWORD}).status_code == 401
    assert anon.post("/login", data={"email": "den@psie.local", "password": NEW}).status_code == 303


def test_password_change_validation(db):
    make_user(db, "den@psie.local", "den")
    c = client_for("den@psie.local")
    assert c.post("/mot-de-passe", data={"current": "faux", "new": NEW, "confirm": NEW}).status_code == 401
    assert c.post("/mot-de-passe", data={"current": PASSWORD, "new": NEW, "confirm": "autre"}).status_code == 400
    assert c.post("/mot-de-passe", data={"current": PASSWORD, "new": "court1", "confirm": "court1"}).status_code == 400
    assert c.post("/mot-de-passe", data={"current": PASSWORD, "new": "seulement-lettres", "confirm": "seulement-lettres"}).status_code == 400
    assert c.post("/mot-de-passe", data={"current": PASSWORD, "new": PASSWORD, "confirm": PASSWORD}).status_code == 400
    user = db.query(models.User).filter_by(email="den@psie.local").one()
    assert verify_password(PASSWORD, user.hashed_password)  # rien n'a changé


def test_wrong_current_password_locks_the_account(db):
    make_user(db, "den@psie.local", "den")
    c = client_for("den@psie.local")
    codes = [c.post("/mot-de-passe", data={"current": "faux", "new": NEW, "confirm": NEW}).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 429]
    assert c.post("/mot-de-passe", data={"current": PASSWORD, "new": NEW, "confirm": NEW}).status_code == 429


def test_password_page_requires_login(anon):
    assert anon.get("/mot-de-passe").status_code == 303
    assert anon.post("/mot-de-passe", data={"current": "x", "new": NEW, "confirm": NEW}).status_code == 303


def test_admin_resets_forgotten_password_and_unlocks(db, anon):
    make_user(db, "admin@psie.local", "admin")
    target = make_user(db, "den@psie.local", "den")
    for _ in range(5):
        anon.post("/login", data={"email": "den@psie.local", "password": "faux1234"})
    assert anon.post("/login", data={"email": "den@psie.local", "password": PASSWORD}).status_code == 429
    admin = client_for("admin@psie.local")
    assert admin.post(f"/users/{target.id}/password", data={"password": "court"}).status_code == 400
    assert admin.post(f"/users/{target.id}/password", data={"password": NEW}).status_code == 303
    assert anon.post("/login", data={"email": "den@psie.local", "password": NEW}).status_code == 303
    assert db.query(models.AuditLog).filter_by(action="reinitialisation_mdp").count() == 1


def test_only_admin_can_reset_passwords(db):
    target = make_user(db, "fin@psie.local", "finances")
    make_user(db, "den@psie.local", "den")
    assert client_for("den@psie.local").post(f"/users/{target.id}/password", data={"password": NEW}).status_code == 403
