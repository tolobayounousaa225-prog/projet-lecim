from app import models

from .conftest import PASSWORD, client_for, make_faitiere, make_user

NEW = {"email": "Nouveau@PSIE.local", "full_name": "Nouveau", "role": "den", "password": PASSWORD}


def test_admin_creates_user_and_audit_logged(db):
    make_user(db, "admin@psie.local", "admin")
    client = client_for("admin@psie.local")
    assert client.post("/users", data=NEW).status_code == 303
    created = db.query(models.User).filter_by(email="nouveau@psie.local").one()
    assert created.role == "den"
    assert created.hashed_password != NEW["password"]
    assert db.query(models.AuditLog).filter_by(entity="user", action="creation").count() == 1
    assert client.get("/audit").status_code == 200
    # Le nouveau compte peut se connecter
    assert client_for("nouveau@psie.local").get("/admin").status_code == 200


def test_user_creation_rules(db):
    f = make_faitiere(db, "LECIM")
    make_user(db, "admin@psie.local", "admin")
    client = client_for("admin@psie.local")
    assert client.post("/users", data={**NEW, "password": "court1"}).status_code == 400
    assert client.post("/users", data={**NEW, "role": "inconnu"}).status_code == 400
    # un représentant doit être rattaché à une faîtière
    assert client.post("/users", data={**NEW, "role": "faitiere"}).status_code == 400
    rep = {**NEW, "email": "rep@psie.local", "role": "faitiere", "faitiere_id": str(f.id)}
    assert client.post("/users", data=rep).status_code == 303
    assert db.query(models.User).filter_by(email="rep@psie.local").one().faitiere_id == f.id
    assert client.post("/users", data=NEW).status_code == 303
    assert client.post("/users", data=NEW).status_code == 409  # e-mail déjà utilisé


def test_only_admin_manages_users(db):
    make_user(db, "den@psie.local", "den")
    client = client_for("den@psie.local")
    assert client.get("/users").status_code == 403
    assert client.post("/users", data=NEW).status_code == 403
    assert client.get("/audit").status_code == 403


def test_toggle_account(db):
    admin = make_user(db, "admin@psie.local", "admin")
    other = make_user(db, "den@psie.local", "den")
    client = client_for("admin@psie.local")
    assert client.post(f"/users/{admin.id}/toggle").status_code == 400  # pas soi-même
    client.post(f"/users/{other.id}/toggle")
    db.refresh(other)
    assert other.is_active is False


def test_init_db_is_idempotent(db):
    from scripts import init_db

    init_db.run()
    init_db.run()
    sigles = sorted(f.sigle for f in db.query(models.Faitiere).all())
    assert sigles == ["AL HIKMA", "CHERIFLA", "HINNEH", "IQRA", "LECIM", "OEECI"]
    assert db.query(models.User).filter_by(role="admin").count() == 1
