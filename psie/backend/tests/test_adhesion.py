import datetime

import pytest

from app import models

from .conftest import client_for, make_faitiere, make_user

FORM = {
    "nom": "Association Al Nour", "sigle": "alnour", "representant_nom": "Moussa Traoré",
    "representant_fonction": "Président", "email": "contact@alnour.ci", "telephone": "+225 07 00 00 00 00",
    "siege": "Bouaké", "statut_juridique": "Association", "date_creation": "2015-04-01", "nb_structures": "12",
    "message": "Nous souhaitons adhérer.", "accepte_statuts": "on", "accepte_cotisations": "on",
}


def submit(anon, **override):
    data = {**FORM, **override}
    return anon.post("/adhesion", data={k: v for k, v in data.items() if v is not None})


def test_public_submission_creates_request_with_code(db, anon):
    r = submit(anon)
    assert r.status_code == 200
    d = db.query(models.DemandeAdhesion).one()
    assert d.code.startswith("ADH-") and d.code in r.text
    assert (d.sigle, d.etat, d.email) == ("ALNOUR", "nouvelle", "contact@alnour.ci")
    assert db.query(models.AuditLog).filter_by(action="depot").count() == 1


@pytest.mark.parametrize("override", [
    {"nom": " "}, {"email": "pas-un-email"}, {"telephone": "abc"}, {"accepte_statuts": None},
    {"accepte_cotisations": None}, {"nb_structures": "-3"}, {"nb_structures": "beaucoup"},
    {"date_creation": (datetime.date.today() + datetime.timedelta(days=5)).isoformat()},
    {"date_creation": "31/02/2020"}, {"sigle": "X" * 60},
])
def test_invalid_submissions_rejected(db, anon, override):
    assert submit(anon, **override).status_code == 400
    assert db.query(models.DemandeAdhesion).count() == 0


def test_existing_member_acronym_rejected(db, anon):
    make_faitiere(db, "ALNOUR")
    assert submit(anon).status_code == 409


def test_honeypot_silently_ignored(db, anon):
    r = anon.post("/adhesion", data={**FORM, "website": "http://spam.example"})
    assert r.status_code == 200 and db.query(models.DemandeAdhesion).count() == 0


def test_submission_rate_limited(db, anon):
    for i in range(5):
        assert submit(anon, sigle=f"ORG{i}").status_code == 200
    assert submit(anon, sigle="ORG9").status_code == 429


def test_xss_in_submission_is_escaped(db, anon):
    submit(anon, nom='<script>alert(1)</script>')
    make_user(db, "den@psie.local", "den")
    page = client_for("den@psie.local").get(f"/adhesions/{db.query(models.DemandeAdhesion).one().id}").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_tracking_shows_only_status(db, anon):
    submit(anon)
    d = db.query(models.DemandeAdhesion).one()
    r = anon.post("/adhesion/suivi", data={"code": d.code.lower()})
    assert r.status_code == 200 and "Demande reçue" in r.text
    assert "alnour" not in r.text.lower() and "Traoré" not in r.text
    assert anon.post("/adhesion/suivi", data={"code": "ADH-INCONNU1"}).status_code == 404


def test_tracking_rate_limited(anon):
    for _ in range(30):
        anon.post("/adhesion/suivi", data={"code": "ADH-INCONNU1"})
    assert anon.post("/adhesion/suivi", data={"code": "ADH-INCONNU1"}).status_code == 429


# ---------- Instruction ----------

@pytest.fixture
def demande(db, anon):
    submit(anon)
    make_user(db, "den@psie.local", "den")
    make_user(db, "ca@psie.local", "administrateur_ca")
    make_user(db, "fin@psie.local", "finances")
    return db.query(models.DemandeAdhesion).one()


def test_full_circuit_acceptance_creates_member_and_certificate(db, demande, anon):
    den, ca = client_for("den@psie.local"), client_for("ca@psie.local")
    assert den.post(f"/adhesions/{demande.id}/examen", data={"notes": "Dossier complet"}).status_code == 303
    assert ca.post(f"/adhesions/{demande.id}/avis", data={"avis": "favorable"}).status_code == 303
    r = den.post(f"/adhesions/{demande.id}/decision", data={
        "decision": "accepter", "reference": "Résolution AGO n°3", "date_decision": "2026-05-03",
        "droit_adhesion": "100000"})
    assert r.status_code == 303
    db.refresh(demande)
    f = db.get(models.Faitiere, demande.faitiere_id)
    assert (demande.etat, f.categorie, f.statut, f.sigle) == ("acceptee", "ordinaire", "actif", "ALNOUR")
    assert f.date_adhesion == datetime.date(2026, 5, 3) and f.is_membre_actif
    due = db.query(models.Echeance).filter_by(faitiere_id=f.id, type="adhesion").one()
    assert due.montant_du == 100000
    pdf = den.get(f"/adhesions/{demande.id}/certificat.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    page = anon.get(f"/verifier/adhesion/{demande.cert_token}")
    assert page.status_code == 200 and "ALNOUR" in page.text
    assert "Adhésion acceptée" in anon.post("/adhesion/suivi", data={"code": demande.code}).text
    assert f.sigle in anon.get("/membres").text  # visible sur la vitrine


def test_acceptance_requires_favorable_ca_opinion(db, demande):
    den, ca = client_for("den@psie.local"), client_for("ca@psie.local")
    data = {"decision": "accepter", "reference": "Résolution 1"}
    assert den.post(f"/adhesions/{demande.id}/decision", data=data).status_code == 400   # aucun avis
    assert ca.post(f"/adhesions/{demande.id}/avis", data={"avis": "defavorable", "motif": ""}).status_code == 400
    ca.post(f"/adhesions/{demande.id}/avis", data={"avis": "defavorable", "motif": "Dossier incomplet"})
    assert den.post(f"/adhesions/{demande.id}/decision", data=data).status_code == 400   # avis défavorable
    db.refresh(demande)
    assert demande.etat == "en_examen" and db.query(models.Faitiere).count() == 0


def test_refusal_needs_reference_and_is_final(db, demande, anon):
    den = client_for("den@psie.local")
    assert den.post(f"/adhesions/{demande.id}/decision", data={"decision": "refuser", "reference": ""}).status_code == 400
    assert den.post(f"/adhesions/{demande.id}/decision",
                    data={"decision": "refuser", "reference": "AGA 2026", "motif": "Hors périmètre"}).status_code == 303
    db.refresh(demande)
    assert demande.etat == "refusee" and demande.cert_token is None
    assert den.post(f"/adhesions/{demande.id}/decision",
                    data={"decision": "refuser", "reference": "AGA 2026"}).status_code == 409
    assert den.get(f"/adhesions/{demande.id}/certificat.pdf").status_code == 404
    assert "Demande refusée" in anon.post("/adhesion/suivi", data={"code": demande.code}).text


def test_permissions_on_instruction(db, demande, anon):
    fin = client_for("fin@psie.local")
    assert fin.get("/adhesions").status_code == 200          # lecture
    assert fin.post(f"/adhesions/{demande.id}/decision", data={"decision": "refuser", "reference": "x"}).status_code == 403
    assert fin.post(f"/adhesions/{demande.id}/avis", data={"avis": "favorable"}).status_code == 403
    assert fin.post(f"/adhesions/{demande.id}/examen", data={}).status_code == 403
    assert anon.get("/adhesions").status_code == 303          # public : renvoyé vers la connexion
    assert anon.post(f"/adhesions/{demande.id}/decision", data={"decision": "refuser", "reference": "x"}).status_code == 303
    f = make_faitiere(db, "ZZZ")
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=f.id)
    rep = client_for("rep@psie.local")
    assert rep.get("/adhesions").status_code == 403 and rep.get(f"/adhesions/{demande.id}").status_code == 403


def test_certificate_only_for_own_member(db, demande):
    den, ca = client_for("den@psie.local"), client_for("ca@psie.local")
    ca.post(f"/adhesions/{demande.id}/avis", data={"avis": "favorable"})
    den.post(f"/adhesions/{demande.id}/decision", data={"decision": "accepter", "reference": "AGO 2026"})
    db.refresh(demande)
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=demande.faitiere_id)
    other = make_faitiere(db, "AUTRE")
    make_user(db, "autre@psie.local", "faitiere", faitiere_id=other.id)
    assert client_for("rep@psie.local").get(f"/adhesions/{demande.id}/certificat.pdf").status_code == 200
    assert client_for("autre@psie.local").get(f"/adhesions/{demande.id}/certificat.pdf").status_code == 404
    assert client_for("ca@psie.local").get(f"/adhesions/{demande.id}/certificat.pdf").status_code == 404


def test_unknown_certificate_token(anon):
    assert anon.get("/verifier/adhesion/inconnu").status_code == 404


# ---------- Vitrine ----------

def test_public_pages_are_open_and_bilingual(db, anon):
    make_faitiere(db, "LECIM")
    for url in ("/", "/apropos", "/membres", "/actualites", "/adhesion", "/adhesion/suivi", "/login"):
        assert anon.get(url).status_code == 200, url
    assert "Nos missions" in anon.get("/").text
    anon.cookies.set("lang", "ar")
    home = anon.get("/").text
    assert 'dir="rtl"' in home and "مهامنا" in home and "Nos missions" not in home


def test_public_members_show_only_active_members(db, anon):
    make_faitiere(db, "LECIM")
    susp = make_faitiere(db, "SUSPENDUE")
    susp.statut = "suspendu"
    db.commit()
    page = anon.get("/membres").text
    assert "LECIM" in page and "SUSPENDUE" not in page


def test_news_publication_and_language_fallback(db, anon):
    make_user(db, "sec@psie.local", "secretaire")
    c = client_for("sec@psie.local")
    assert c.post("/gestion/actualites", data={"titre_fr": "Assemblée annuelle", "contenu_fr": "Elle se tiendra à Bouaké.",
                                                "publie": "on"}).status_code == 303
    assert c.post("/gestion/actualites", data={"titre_fr": "Brouillon secret", "contenu_fr": "x"}).status_code == 303
    assert c.post("/gestion/actualites", data={"contenu_fr": "pas de titre"}).status_code == 400
    published, draft = db.query(models.Actualite).order_by(models.Actualite.id).all()
    page = anon.get("/actualites").text
    assert "Assemblée annuelle" in page and "Brouillon secret" not in page
    assert anon.get(f"/actualites/{draft.id}").status_code == 404
    anon.cookies.set("lang", "ar")  # pas de version arabe : on retombe sur le français
    assert "Assemblée annuelle" in anon.get(f"/actualites/{published.id}").text
    c.post(f"/gestion/actualites/{published.id}/delete")
    assert db.query(models.Actualite).count() == 1


def test_news_content_is_escaped_and_admin_restricted(db, anon):
    make_user(db, "sec@psie.local", "secretaire")
    make_user(db, "ca@psie.local", "administrateur_ca")
    client_for("sec@psie.local").post("/gestion/actualites", data={
        "titre_fr": "<b>gras</b>", "contenu_fr": "<img src=x onerror=alert(1)>", "publie": "on"})
    item = db.query(models.Actualite).one()
    page = anon.get(f"/actualites/{item.id}").text
    assert "<img src=x" not in page and "&lt;img" in page
    ca = client_for("ca@psie.local")
    assert ca.get("/gestion/actualites").status_code == 403
    assert ca.post("/gestion/actualites", data={"titre_fr": "x"}).status_code == 403
    assert anon.get("/gestion/actualites").status_code == 303
