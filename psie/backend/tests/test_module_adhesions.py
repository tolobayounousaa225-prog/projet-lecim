"""Module 3 : pièces du dossier d'adhésion, compte du représentant, rappels."""
import datetime
import io
import re

import pytest
from PIL import Image

from app import models, rappels
from app.security import verify_password

from .conftest import PASSWORD, client_for, make_faitiere, make_user

TODAY = datetime.date.today()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (30, 20), (20, 120, 60)).save(out, "PNG")
    return out.getvalue()


FORM = {"nom": "Association Al Nour", "sigle": "NOUR", "representant_nom": "Koné Ali", "representant_fonction": "Président",
        "email": "ali@nour.ci", "telephone": "+225 07 00 00 00 00", "accepte_statuts": "on", "accepte_cotisations": "on"}


@pytest.fixture
def staff(db):
    for who, role in (("den", "den"), ("sec", "secretaire"), ("ca", "administrateur_ca"), ("exam", "examens")):
        make_user(db, f"{who}@psie.ci", role)
    return None


@pytest.fixture
def mails(monkeypatch):
    sent = []

    def fake(to, subject, body, attachments=None):
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    for target in ("app.adhesion.send_email", "app.routers.public.send_email", "app.rappels.send_email", "app.gouvernance.send_email"):
        monkeypatch.setattr(target, fake)
    return sent


def apply(anon, files=None, **over):
    return anon.post("/adhesion", data={**FORM, **over}, files=files or {})


def accept(db, client, d):
    client.post(f"/adhesions/{d.id}/avis", data={"avis": "favorable"})
    return client.post(f"/adhesions/{d.id}/decision", data={"decision": "accepter", "reference": "AGO-2026-01"})


# ---------------------------------------------------------------- pièces du dossier

def test_applicant_can_attach_statutes_and_receipt(db, anon, staff, mails):
    r = apply(anon, files={"statuts_file": ("statuts.pdf", PDF, "application/pdf"),
                           "recepisse_file": ("recepisse.png", png(), "image/png")})
    assert r.status_code == 200
    d = db.query(models.DemandeAdhesion).one()
    pieces = {p.type: p for p in db.query(models.PieceDemande).filter_by(demande_id=d.id)}
    assert set(pieces) == {"statuts", "recepisse"} and pieces["statuts"].extension == "pdf" and pieces["recepisse"].extension == "png"
    page = client_for("den@psie.ci").get(f"/adhesions/{d.id}").text
    assert "statuts.pdf" in page and "recepisse.png" in page and "Documents du dossier" in page


def test_the_application_works_without_any_file(db, anon, staff, mails):
    assert apply(anon).status_code == 200 and db.query(models.PieceDemande).count() == 0


@pytest.mark.parametrize("name,content,ctype", [
    ("faux.pdf", b"MZ ceci n'est pas un pdf", "application/pdf"),
    ("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/svg+xml"),
    ("gros.pdf", b"%PDF-" + b"0" * (16 * 1024 * 1024), "application/pdf"),
])
def test_dangerous_files_refuse_the_whole_application(db, anon, staff, mails, name, content, ctype):
    r = apply(anon, files={"statuts_file": (name, content, ctype)})
    assert r.status_code == 400
    assert db.query(models.DemandeAdhesion).count() == 0 and db.query(models.PieceDemande).count() == 0 and mails == []


def test_pieces_are_only_for_the_bodies_of_the_psie(db, anon, staff, mails):
    apply(anon, files={"statuts_file": ("statuts.pdf", PDF, "application/pdf")})
    d, piece = db.query(models.DemandeAdhesion).one(), db.query(models.PieceDemande).one()
    assert client_for("exam@psie.ci").get(f"/adhesions/{d.id}/pieces/{piece.id}").status_code == 403    # autre secrétariat
    got = client_for("ca@psie.ci").get(f"/adhesions/{d.id}/pieces/{piece.id}")
    assert got.status_code == 200 and got.content == PDF and "attachment" in got.headers["content-disposition"]
    assert got.headers["cache-control"] == "private, no-store"
    assert anon.get(f"/adhesions/{d.id}/pieces/{piece.id}").status_code == 303
    assert client_for("den@psie.ci").get(f"/adhesions/{d.id}/pieces/9999").status_code == 404
    assert client_for("den@psie.ci").get(f"/adhesions/9999/pieces/{piece.id}").status_code == 404


def test_pieces_follow_the_new_member_when_accepted(db, anon, staff, mails):
    apply(anon, files={"statuts_file": ("statuts.pdf", PDF, "application/pdf"), "recepisse_file": ("r.png", png(), "image/png")})
    d = db.query(models.DemandeAdhesion).one()
    assert accept(db, client_for("den@psie.ci"), d).status_code == 303
    db.expire_all()
    f = db.query(models.Faitiere).filter_by(sigle="NOUR").one()
    assert sorted(p.type for p in db.query(models.PieceFaitiere).filter_by(faitiere_id=f.id)) == ["recepisse", "statuts"]
    assert "statuts.pdf" in client_for("den@psie.ci").get(f"/faitieres/{f.id}").text


def test_refused_application_creates_no_member_and_no_account(db, anon, staff, mails):
    apply(anon, files={"statuts_file": ("statuts.pdf", PDF, "application/pdf")})
    d = db.query(models.DemandeAdhesion).one()
    den = client_for("den@psie.ci")
    den.post(f"/adhesions/{d.id}/decision", data={"decision": "refuser", "reference": "AGO-2026-01", "motif": "Dossier incomplet"})
    assert db.query(models.Faitiere).count() == 0 and db.query(models.User).filter_by(email="ali@nour.ci").count() == 0
    assert db.query(models.PieceFaitiere).count() == 0


# ---------------------------------------------------------------- compte du représentant

def test_acceptance_creates_the_federation_account_and_invites_the_representative(db, anon, staff, mails):
    apply(anon)
    d = db.query(models.DemandeAdhesion).one()
    accept(db, client_for("den@psie.ci"), d)
    user = db.query(models.User).filter_by(email="ali@nour.ci").one()
    f = db.query(models.Faitiere).filter_by(sigle="NOUR").one()
    assert user.role == "faitiere" and user.faitiere_id == f.id and user.full_name == "Koné Ali" and user.is_active
    invite = next(m for m in mails if m["to"] == "ali@nour.ci" and "acceptée" in m["body"])
    link = re.search(r"https?://\S+/mot-de-passe-oublie/[\w-]+", invite["body"]).group(0)
    assert "7 jours" in invite["body"] and PASSWORD not in invite["body"]
    # personne ne peut se connecter avant d'avoir choisi son mot de passe, puis le lien fonctionne une seule fois
    assert anon.post("/login/faitiere", data={"email": "ali@nour.ci", "password": "devine-moi-1"}).status_code == 401
    path = "/" + link.split("/", 3)[3]
    assert anon.post(path, data={"new": "Mon-espace-2026", "confirm": "Mon-espace-2026"}).status_code == 303
    assert anon.post("/login/faitiere", data={"email": "ali@nour.ci", "password": "Mon-espace-2026"}).status_code == 303
    assert anon.get(path).status_code == 400


def test_invitation_link_lasts_a_week(db, anon, staff, mails):
    apply(anon)
    accept(db, client_for("den@psie.ci"), db.query(models.DemandeAdhesion).one())
    token = db.query(models.ReinitialisationMdp).one()
    delta = token.expires_at - token.created_at
    assert datetime.timedelta(days=6, hours=23) < delta <= datetime.timedelta(days=7, minutes=1)


def test_existing_account_is_never_overwritten_by_an_acceptance(db, anon, staff, mails):
    other = make_faitiere(db, "AUTRE")
    existing = make_user(db, "ali@nour.ci", "faitiere", faitiere_id=other.id, name="Déjà là")
    apply(anon)
    accept(db, client_for("den@psie.ci"), db.query(models.DemandeAdhesion).one())
    db.expire_all()
    same = db.query(models.User).filter_by(email="ali@nour.ci").one()
    assert same.id == existing.id and same.faitiere_id == other.id and verify_password(PASSWORD, same.hashed_password)
    invite = next(m for m in mails if m["to"] == "ali@nour.ci" and "acceptée" in m["body"])
    assert "mot-de-passe-oublie" not in invite["body"]                                  # aucun lien d'invitation


def test_acceptance_still_requires_a_favourable_ca_opinion(db, anon, staff, mails):
    apply(anon)
    d = db.query(models.DemandeAdhesion).one()
    r = client_for("den@psie.ci").post(f"/adhesions/{d.id}/decision", data={"decision": "accepter", "reference": "AGO-1"})
    assert r.status_code == 400 and db.query(models.User).filter_by(email="ali@nour.ci").count() == 0


def test_applicant_is_told_when_the_examination_starts(db, anon, staff, mails):
    apply(anon)
    d = db.query(models.DemandeAdhesion).one()
    c = client_for("den@psie.ci")
    c.post(f"/adhesions/{d.id}/examen", data={"notes": "Dossier reçu"})
    assert [m["subject"] for m in mails if m["to"] == "ali@nour.ci"].count(f"PSIE — Demande d'adhésion {d.code} : en cours d'examen") == 1
    c.post(f"/adhesions/{d.id}/examen", data={"notes": "Mise à jour"})                  # un seul message, pas un par enregistrement
    assert sum("en cours d'examen" in m["subject"] for m in mails) == 1


def test_public_form_offers_the_file_fields(anon):
    page = anon.get("/adhesion").text
    assert 'enctype="multipart/form-data"' in page and 'name="statuts_file"' in page and 'name="recepisse_file"' in page
    anon.cookies.set("lang", "ar")
    assert "وصل التصريح" in anon.get("/adhesion").text


# ---------------------------------------------------------------- rappels

def old_application(db, days, etat="nouvelle", avis=None, sigle="OLD"):
    d = models.DemandeAdhesion(code=f"ADH-{sigle}", nom=sigle, sigle=sigle, representant_nom="X", email=f"{sigle}@x.ci",
                               telephone="0700000000", etat=etat, avis_ca=avis, accepte_statuts=True, accepte_cotisations=True,
                               created_at=datetime.datetime.utcnow() - datetime.timedelta(days=days))
    db.add(d)
    db.commit()
    return d


def test_pending_applications_are_reported_once(db, staff, mails):
    old_application(db, 10)                                                         # à examiner
    old_application(db, 20, "en_examen", sigle="LONG")                              # avis du CA attendu
    old_application(db, 3, sigle="NEW")                                             # trop récente
    old_application(db, 40, "acceptee", "favorable", sigle="DONE")                  # traitée
    assert rappels.send_regulatory_reminders(db, TODAY) == 2
    assert sorted(m["to"] for m in mails) == ["den@psie.ci", "sec@psie.ci"]
    body = mails[0]["body"]
    assert "OLD" in body and "pas encore examinée" in body and "LONG" in body and "avis écrit du CA" in body
    assert "NEW" not in body and "DONE" not in body
    assert rappels.send_regulatory_reminders(db, TODAY) == 0

