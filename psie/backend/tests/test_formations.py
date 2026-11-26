import datetime

import pytest

from app import models

from .conftest import client_for, make_faitiere, make_user

TODAY = datetime.date.today()


@pytest.fixture
def world(db):
    a, b = make_faitiere(db, "LECIM"), make_faitiere(db, "IQRA")
    for email, role, kw in (("form@psie.ci", "formation", {}), ("den@psie.ci", "den", {}), ("com@psie.ci", "communication", {}),
                            ("rep-a@psie.ci", "faitiere", {"faitiere_id": a.id}), ("rep-b@psie.ci", "faitiere", {"faitiere_id": b.id})):
        make_user(db, email, role, **kw)
    form = client_for("form@psie.ci")
    form.post("/formations", data={"titre": "Gestion d'un établissement", "duree": "3 jours"})
    f = db.query(models.Formation).one()
    form.post(f"/formations/{f.id}/sessions", data={"date_debut": TODAY.isoformat(), "lieu": "Abidjan", "places": "2"})
    return a, b, form, db.query(models.SessionFormation).one()


def test_staff_create_sessions_and_federations_are_notified(db, world):
    a, b, form, s = world
    assert s.statut == "ouverte" and s.places == 2
    n = db.query(models.Notification).join(models.User).filter(models.User.email == "rep-a@psie.ci").one()
    assert "Nouvelle session" in n.titre
    assert form.post(f"/formations/{s.formation_id}/sessions", data={"date_debut": TODAY.isoformat(), "date_fin": "2000-01-01", "lieu": "x"}).status_code == 400
    assert client_for("com@psie.ci").get("/formations").status_code == 403                      # Communication : pas dans la rubrique
    assert client_for("com@psie.ci").post("/formations", data={"titre": "x"}).status_code == 403


def test_a_federation_enrolls_only_its_own_staff_and_sees_only_them(db, world):
    a, b, form, s = world
    ra, rb = client_for("rep-a@psie.ci"), client_for("rep-b@psie.ci")
    assert ra.post(f"/formations/sessions/{s.id}/inscrire", data={"nom": "Moussa Traoré", "fonction": "Directeur", "faitiere_id": str(b.id)}).status_code == 303
    i = db.query(models.InscriptionFormation).one()
    assert i.faitiere_id == a.id                                                                # l'identifiant de faîtière envoyé est ignoré
    assert ra.post(f"/formations/sessions/{s.id}/inscrire", data={"nom": "moussa traoré"}).status_code == 409   # doublon
    rb.post(f"/formations/sessions/{s.id}/inscrire", data={"nom": "Awa Koné"})
    assert "Moussa Traoré" in ra.get(f"/formations/sessions/{s.id}").text and "Awa Koné" not in ra.get(f"/formations/sessions/{s.id}").text
    page = form.get(f"/formations/sessions/{s.id}").text
    assert "Moussa Traoré" in page and "Awa Koné" in page
    assert rb.post(f"/formations/inscriptions/{i.id}/annuler").status_code == 404               # pas l'inscription d'une autre
    assert ra.post(f"/formations/sessions/{s.id}/inscrire", data={"nom": "Troisième"}).status_code == 400   # session complète (2 places)
    assert any("Inscription" in n.titre for n in db.query(models.Notification).join(models.User).filter(models.User.email == "form@psie.ci"))


def test_attendance_then_certificates_with_public_verification(db, world, anon):
    a, b, form, s = world
    ra = client_for("rep-a@psie.ci")
    ra.post(f"/formations/sessions/{s.id}/inscrire", data={"nom": "Moussa Traoré"})
    ra.post(f"/formations/sessions/{s.id}/inscrire", data={"nom": "Absent Un"})
    present, absent = db.query(models.InscriptionFormation).order_by(models.InscriptionFormation.id).all()
    assert ra.post(f"/formations/sessions/{s.id}/terminer").status_code == 403                   # pas à la faîtière de se délivrer des certificats
    assert form.post(f"/formations/sessions/{s.id}/terminer", data={"present": str(present.id)}).status_code == 303
    db.expire_all()
    assert present.statut == "present" and present.certificat_numero == f"FORM-{TODAY.year}-0001" and absent.statut == "absent" and absent.certificat_token is None
    pdf = ra.get(f"/formations/inscriptions/{present.id}/certificat.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert ra.get(f"/formations/inscriptions/{absent.id}/certificat.pdf").status_code == 404     # pas de certificat sans présence
    assert client_for("rep-b@psie.ci").get(f"/formations/inscriptions/{present.id}/certificat.pdf").status_code == 404
    page = anon.get(f"/verifier/certificat/{present.certificat_token}", headers={"accept": "text/html"})
    assert page.status_code == 200 and "Moussa Traoré" in page.text and f"FORM-{TODAY.year}-0001" in page.text and 'class="topbar"' not in page.text
    assert anon.get("/verifier/certificat/inconnu").status_code == 404
    assert form.post(f"/formations/sessions/{s.id}/terminer", data={}).status_code == 400        # une session ne se termine qu'une fois
    assert any("Certificats" in n.titre for n in db.query(models.Notification).join(models.User).filter(models.User.email == "rep-a@psie.ci"))


def test_future_sessions_cannot_be_finished_and_closed_ones_refuse_enrollment(db, world):
    a, b, form, s = world
    form.post(f"/formations/{s.formation_id}/sessions", data={"date_debut": (TODAY + datetime.timedelta(days=30)).isoformat(), "lieu": "Bouaké"})
    future = db.query(models.SessionFormation).order_by(models.SessionFormation.id.desc()).first()
    assert form.post(f"/formations/sessions/{future.id}/terminer", data={}).status_code == 400
    assert form.post(f"/formations/sessions/{future.id}/statut", data={"statut": "cloturee"}).status_code == 303
    assert client_for("rep-a@psie.ci").post(f"/formations/sessions/{future.id}/inscrire", data={"nom": "Tard"}).status_code == 400
    assert form.post(f"/formations/sessions/{future.id}/statut", data={"statut": "terminee"}).status_code == 400
    form.post(f"/formations/sessions/{future.id}/statut", data={"statut": "annulee"})
    assert client_for("rep-a@psie.ci").get(f"/formations/sessions/{future.id}").status_code == 404     # une session annulée n'est plus proposée
