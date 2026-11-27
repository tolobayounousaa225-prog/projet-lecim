import pytest

import app.signatures as sg
from app import models

from .conftest import client_for, make_faitiere, make_user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def world(db, monkeypatch):
    for email, role in (("den@psie.ci", "den"), ("sec@psie.ci", "secretaire"), ("ca@psie.ci", "administrateur_ca"), ("com@psie.ci", "communication")):
        make_user(db, email, role)
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    mails = []
    monkeypatch.setattr(sg, "send_email", lambda to, subject, body: mails.append((to, body)) or True)
    den = client_for("den@psie.ci")
    den.post("/documents", data={"titre": "Règlement 2026", "categorie": "statuts"}, files={"fichier": ("r.pdf", PDF, "application/pdf")})
    return den, mails, db.query(models.Document).one()


def code_from(mails):
    return mails[-1][1].split(": ")[1][:6]


def test_signing_a_document_needs_the_emailed_code_and_records_the_fingerprint(db, world):
    den, mails, doc = world
    url = f"/signatures/document/{doc.id}"
    assert den.get(url).status_code == 200
    assert den.post(f"{url}/confirmer", data={"code": "123456"}).headers["location"].endswith("error=code")      # pas de code demandé
    assert den.post(f"{url}/code").status_code == 303 and len(mails) == 1 and mails[0][0] == "den@psie.ci"
    assert den.post(f"{url}/confirmer", data={"code": "000000"}).headers["location"].endswith("error=wrong")
    ok = den.post(f"{url}/confirmer", data={"code": code_from(mails)})
    assert ok.status_code == 303 and ok.headers["location"] == url
    s = db.query(models.Signature).one()
    assert s.signer_nom == "den@psie.ci" and s.doc_sha256 == doc.sha256 and s.doc_type == "document"
    assert "Règlement 2026" in den.get(url).text
    assert den.post(f"{url}/confirmer", data={"code": code_from(mails)}).headers["location"].endswith("error=code")   # un code ne sert qu'une fois
    audit = db.query(models.AuditLog).filter_by(action="signature").one()
    assert doc.sha256[:12] in audit.detail


def test_codes_expire_lock_after_five_wrong_attempts_and_have_a_cooldown(db, world):
    den, mails, doc = world
    url = f"/signatures/document/{doc.id}"
    den.post(f"{url}/code")
    assert den.post(f"{url}/code").headers["location"].endswith("error=wait") and len(mails) == 1       # une minute entre deux envois
    good = code_from(mails)
    for _ in range(5):
        den.post(f"{url}/confirmer", data={"code": "999999" if good != "999999" else "111111"})
    assert den.post(f"{url}/confirmer", data={"code": good}).headers["location"].endswith("error=code")  # bloqué : le bon code ne passe plus
    assert db.query(models.Signature).count() == 0
    row = db.query(models.CodeSignature)
    den.post(f"{url}/code")
    import datetime
    for r in db.query(models.CodeSignature):
        r.expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
        r.created_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    db.commit()
    assert den.post(f"{url}/confirmer", data={"code": code_from(mails)}).headers["location"].endswith("error=code")   # expiré


def test_a_code_is_bound_to_the_person_and_the_document(db, world):
    den, mails, doc = world
    sec = client_for("sec@psie.ci")
    den.post("/documents", data={"titre": "Autre", "categorie": "autre"}, files={"fichier": ("a.pdf", PDF, "application/pdf")})
    other = db.query(models.Document).filter_by(titre="Autre").one()
    den.post(f"/signatures/document/{doc.id}/code")
    code = code_from(mails)
    assert sec.post(f"/signatures/document/{doc.id}/confirmer", data={"code": code}).headers["location"].endswith("error=code")   # pas le code d'un autre
    assert den.post(f"/signatures/document/{other.id}/confirmer", data={"code": code}).headers["location"].endswith("error=code")  # pas un autre document
    assert db.query(models.Signature).count() == 0


def test_who_may_sign(db, world):
    den, mails, doc = world
    com, ca = client_for("com@psie.ci"), client_for("ca@psie.ci")
    assert com.post(f"/signatures/document/{doc.id}/code").status_code == 403           # lecture seule
    assert ca.post(f"/signatures/document/{doc.id}/code").status_code == 403
    rep = client_for("rep@psie.ci")
    assert rep.get(f"/signatures/document/{doc.id}").status_code == 403 and rep.post(f"/signatures/document/{doc.id}/code").status_code == 403
    assert den.get("/signatures/inconnu/1").status_code == 404 and den.get("/signatures/document/999").status_code == 404


def test_public_verification_detects_a_document_changed_after_signing_and_pdf_certificate(db, world, anon):
    den, mails, doc = world
    den.post(f"/signatures/document/{doc.id}/code")
    den.post(f"/signatures/document/{doc.id}/confirmer", data={"code": code_from(mails)})
    s = db.query(models.Signature).one()
    page = anon.get(f"/verifier/signature/{s.token}", headers={"accept": "text/html"})
    assert page.status_code == 200 and "document inchangé" in page.text and "Règlement 2026" in page.text and 'class="topbar"' not in page.text
    assert "den@psie.ci" in page.text and "SHA-256" in page.text
    pdf = den.get(f"/signatures/{s.id}/certificat.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert anon.get(f"/signatures/{s.id}/certificat.pdf").status_code in (303, 401, 403)     # certificat : connecté seulement
    doc.sha256 = "0" * 64                                                                   # le document a été remplacé
    db.commit()
    assert "a changé depuis la signature" in anon.get(f"/verifier/signature/{s.token}", headers={"accept": "text/html"}).text
    assert anon.get("/verifier/signature/inconnu").status_code == 404
