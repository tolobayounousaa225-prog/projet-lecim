import datetime

import pytest

from app import models

from .conftest import client_for, make_user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def staff(db):
    for email, role in (("den@psie.ci", "den"), ("sec@psie.ci", "secretaire"), ("ca@psie.ci", "administrateur_ca"),
                        ("com@psie.ci", "communication"), ("cc@psie.ci", "commissaire"), ("adm@psie.ci", "admin")):
        make_user(db, email, role)


def upload(client, url="/documents", **data):
    data.setdefault("titre", "Statuts 2026")
    return client.post(url, data=data, files={"fichier": ("statuts.pdf", PDF, "application/pdf")})


def test_documents_upload_download_restricted_and_validation(db, staff):
    den, com = client_for("den@psie.ci"), client_for("com@psie.ci")
    assert upload(den, categorie="statuts").status_code == 303
    assert upload(den, titre="Secret", categorie="decision", restreint="1").status_code == 303
    page = com.get("/documents").text                                           # lecture seule : voit le public, pas le restreint
    assert "Statuts 2026" in page and "Secret" not in page
    d = db.query(models.Document).filter_by(titre="Statuts 2026").one()
    r = com.get(f"/documents/{d.id}/fichier")
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    secret = db.query(models.Document).filter_by(titre="Secret").one()
    assert com.get(f"/documents/{secret.id}/fichier").status_code == 404
    assert den.get(f"/documents/{secret.id}/fichier").status_code == 200
    assert upload(com).status_code == 403 and com.post(f"/documents/{d.id}/supprimer").status_code == 403
    bad = den.post("/documents", data={"titre": "x", "categorie": "autre"}, files={"fichier": ("x.pdf", b"pas un pdf", "application/pdf")})
    assert bad.status_code == 400
    assert den.post("/documents", data={"titre": "x", "categorie": "inconnue"}, files={"fichier": ("x.pdf", PDF, "application/pdf")}).status_code == 400
    assert den.post(f"/documents/{d.id}/supprimer").status_code == 303


def test_faitiere_accounts_cannot_reach_the_module(db, staff):
    from .conftest import make_faitiere
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    rep = client_for("rep@psie.ci")
    for url in ("/documents", "/courrier", "/conventions"):
        assert rep.get(url).status_code == 403, url
    assert rep.post("/courrier", data={"sens": "arrivee", "correspondant": "x", "objet": "y"}).status_code == 403


def test_mail_numbering_follow_up_and_reply(db, staff):
    den = client_for("den@psie.ci")
    year = datetime.date.today().year
    r = den.post("/courrier", data={"sens": "arrivee", "date_courrier": f"{year}-03-02", "correspondant": "Ministère", "objet": "Invitation",
                                    "echeance": "2020-01-01"})
    assert r.status_code == 303
    den.post("/courrier", data={"sens": "arrivee", "date_courrier": f"{year}-03-03", "correspondant": "ONG", "objet": "Don"})
    den.post("/courrier", data={"sens": "depart", "date_courrier": f"{year}-03-03", "correspondant": "ONG", "objet": "Merci"})
    numeros = [c.numero for c in db.query(models.Courrier).order_by(models.Courrier.id)]
    assert numeros == [f"ARR-{year}-0001", f"ARR-{year}-0002", f"DEP-{year}-0001"]
    first = db.query(models.Courrier).filter_by(numero=f"ARR-{year}-0001").one()
    assert first.en_retard and "en retard" in den.get("/courrier").text
    den.post("/courrier", data={"sens": "depart", "correspondant": "Ministère", "objet": "Réponse", "reponse_a_id": str(first.id)})
    db.expire_all()
    assert db.get(models.Courrier, first.id).statut == "traite"                          # une réponse clôt le courrier d'origine
    assert den.post(f"/courrier/{first.id}/suivi", data={"statut": "archive"}).status_code == 303
    assert den.post(f"/courrier/{first.id}/suivi", data={"statut": "n'importe quoi"}).status_code == 400
    assert den.get(f"/courrier/{first.id}").status_code == 200
    com = client_for("com@psie.ci")
    assert "Invitation" in com.get("/courrier").text                                      # lecture seule
    assert com.post(f"/courrier/{first.id}/suivi", data={"statut": "recu"}).status_code == 403


def test_agreement_circuit_follows_the_statutes(db, staff, monkeypatch):
    den, ca, sec, com = client_for("den@psie.ci"), client_for("ca@psie.ci"), client_for("sec@psie.ci"), client_for("com@psie.ci")
    assert upload(den, "/conventions", titre="Convention Waqf", partenaire="Fondation X", montant="500000").status_code == 303
    c = db.query(models.Convention).one()
    act = lambda who, a, **k: who.post(f"/conventions/{c.id}/action", data={"action": a, **k})
    assert den.post(f"/signatures/convention/{c.id}/code").status_code == 403                    # pas avant l'avis du CA
    assert act(ca, "avis_favorable").status_code == 400                                          # pas encore soumise
    assert act(com, "soumettre").status_code == 403                                              # lecture seule
    assert act(sec, "soumettre").status_code == 303
    assert act(den, "avis_favorable").status_code == 403                                         # l'avis est celui du CA
    assert act(ca, "avis_defavorable").status_code == 400                                        # motif obligatoire
    assert act(ca, "avis_defavorable", commentaire="Montant trop élevé").status_code == 303
    db.expire_all()
    assert db.get(models.Convention, c.id).statut == "rejetee"
    assert act(den, "soumettre").status_code == 303                                              # reprise après rejet
    assert act(ca, "avis_favorable").status_code == 303
    assert sec.post(f"/signatures/convention/{c.id}/code").status_code == 403                    # la signature est celle du DEN
    codes = []
    import app.signatures as sg
    monkeypatch.setattr(sg, "send_email", lambda to, subject, body: codes.append(body.split(": ")[1][:6]) or True)
    assert den.post(f"/signatures/convention/{c.id}/code").status_code == 303
    assert den.post(f"/signatures/convention/{c.id}/confirmer", data={"code": codes[0]}).status_code == 303
    db.expire_all()
    assert db.get(models.Convention, c.id).statut == "signee"
    assert act(den, "soumettre").status_code == 400                                              # figée une fois signée
    page = den.get(f"/conventions/{c.id}").text
    assert "Montant trop élevé" in page and "Signée" in page and "500 000 FCFA" in page
    assert [e.action for e in db.get(models.Convention, c.id).etapes] == ["creation", "soumettre", "avis_defavorable", "soumettre", "avis_favorable", "signer"]



def test_access_grid_controls_the_module(db, staff):
    com = client_for("com@psie.ci")
    assert com.get("/documents").status_code == 200
    page = com.get("/admin").text
    assert "/documents" in page
    cc = client_for("cc@psie.ci")
    assert cc.get("/courrier").status_code == 200 and cc.post("/courrier", data={"sens": "arrivee", "correspondant": "x", "objet": "y"}).status_code == 403
    adm = client_for("adm@psie.ci")
    assert adm.post("/acces", data={"n__commissaire__documents": "0"}).status_code in (200, 303)
    assert cc.get("/documents").status_code == 403
