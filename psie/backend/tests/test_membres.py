import datetime

from app import models

from .conftest import client_for, make_faitiere, make_user

NEW = {"nom": "Ligue Test", "sigle": "ltest", "categorie": "ordinaire", "statut": "actif"}


def test_secretaire_creates_and_edits_member(db):
    make_user(db, "sec@psie.local", "secretaire")
    client = client_for("sec@psie.local")
    response = client.post("/faitieres/new", data=NEW)
    assert response.status_code == 303
    f = db.query(models.Faitiere).one()
    assert f.sigle == "LTEST"  # sigle normalisé en majuscules
    client.post(f"/faitieres/{f.id}/edit", data={**NEW, "statut": "suspendu"})
    db.refresh(f)
    assert f.statut == "suspendu"
    actions = [a.action for a in db.query(models.AuditLog).all()]
    assert "creation" in actions and "modification" in actions


def test_duplicate_acronym_rejected(db):
    make_user(db, "sec@psie.local", "secretaire")
    make_faitiere(db, "LTEST")
    client = client_for("sec@psie.local")
    assert client.post("/faitieres/new", data=NEW).status_code == 409


def test_invalid_category_rejected(db):
    make_user(db, "sec@psie.local", "secretaire")
    client = client_for("sec@psie.local")
    assert client.post("/faitieres/new", data={**NEW, "categorie": "inconnue"}).status_code == 400


def test_read_only_roles_cannot_write(db):
    f = make_faitiere(db, "LECIM")
    for role in ("commissaire", "administrateur_ca", "finances"):
        make_user(db, f"{role}@psie.local", role)
        client = client_for(f"{role}@psie.local")
        assert client.get("/faitieres").status_code == 200
        assert client.post("/faitieres/new", data=NEW).status_code == 403
        assert client.post(f"/faitieres/{f.id}/edit", data=NEW).status_code == 403
        assert client.post("/mandats", data={"organe": "CA", "full_name": "Z"}).status_code == 403


def test_representative_sees_only_own_faitiere(db):
    mine = make_faitiere(db, "LECIM")
    other = make_faitiere(db, "IQRA")
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=mine.id)
    client = client_for("rep@psie.local")
    assert client.get(f"/faitieres/{mine.id}").status_code == 200
    assert client.get(f"/faitieres/{other.id}").status_code == 404
    # Pas d'accès à l'annuaire, aux mandats globaux, aux comptes, ni à l'édition
    for url in ("/faitieres", "/admin", "/mandats", "/users", "/audit", f"/faitieres/{mine.id}/edit"):
        assert client.get(url).status_code == 403, url
    assert client.post(f"/faitieres/{mine.id}/edit", data=NEW).status_code == 403


def test_mandate_defaults_to_three_years(db):
    f = make_faitiere(db, "LECIM")
    make_user(db, "sec@psie.local", "secretaire")
    client = client_for("sec@psie.local")
    client.post("/mandats", data={
        "organe": "CA", "full_name": "Administrateur Un", "faitiere_id": str(f.id), "date_debut": "2026-05-03",
    })
    mandat = db.query(models.Mandat).one()
    assert mandat.date_fin == datetime.date(2029, 5, 3)
    assert mandat.faitiere_id == f.id


def test_mandate_validation(db):
    make_user(db, "sec@psie.local", "secretaire")
    client = client_for("sec@psie.local")
    assert client.post("/mandats", data={"organe": "XX", "full_name": "A"}).status_code == 400
    assert client.post("/mandats", data={"organe": "CA", "full_name": "A", "faitiere_id": "999"}).status_code == 400
    bad = {"organe": "CA", "full_name": "A", "date_debut": "2026-05-03", "date_fin": "2025-01-01"}
    assert client.post("/mandats", data=bad).status_code == 400
    assert client.post("/mandats", data={"organe": "CA", "full_name": "A", "date_debut": "pas-une-date"}).status_code == 400


def test_open_redirect_blocked_on_mandate_creation(db):
    make_user(db, "sec@psie.local", "secretaire")
    client = client_for("sec@psie.local")
    response = client.post("/mandats", data={"organe": "CC", "full_name": "A", "next": "//evil.example"})
    assert response.headers["location"] == "/mandats"


def test_dashboard_flags_expiring_mandates(db):
    today = datetime.date.today()
    db.add_all([
        models.Mandat(organe="CA", full_name="Bientot", date_fin=today + datetime.timedelta(days=30)),
        models.Mandat(organe="CA", full_name="Expire", date_fin=today - datetime.timedelta(days=1)),
        models.Mandat(organe="CA", full_name="Lointain", date_fin=today + datetime.timedelta(days=900)),
    ])
    make_faitiere(db, "LECIM")
    make_faitiere(db, "ADH", categorie="honneur")
    db.commit()
    make_user(db, "den@psie.local", "den")
    page = client_for("den@psie.local").get("/admin").text
    assert "Bientot" in page and "Expire" in page and "Lointain" not in page


def test_honorary_member_is_not_active_member(db):
    f = make_faitiere(db, "HON", categorie="honneur")
    assert not f.is_membre_actif
    assert make_faitiere(db, "ORD", categorie="ordinaire").is_membre_actif
