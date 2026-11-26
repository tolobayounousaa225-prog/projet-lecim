import datetime

import pytest

from app import models

from .conftest import client_for, make_faitiere, make_user

YEAR = datetime.date.today().year


@pytest.fixture
def two(db):
    a, b = make_faitiere(db, "LECIM"), make_faitiere(db, "IQRA")
    make_user(db, "rep-a@psie.ci", "faitiere", faitiere_id=a.id)
    make_user(db, "rep-b@psie.ci", "faitiere", faitiere_id=b.id)
    return a, b


def school(client, f, nom="École Al Amine", **extra):
    return client.post(f"/faitieres/{f.id}/ecoles", data={"nom": nom, "niveau": "primaire", "directeur": "M. Koné", **extra})


def census(client, f, e, **extra):
    data = {"annee": str(YEAR), "eleves": "300", "admin_francophone": "2", "admin_arabisant": "1",
            "ens_francophone": "10", "ens_arabisant": "7"}
    data.update(extra)
    return client.post(f"/faitieres/{f.id}/ecoles/{e.id}/recensement", data=data)


def test_federation_registers_school_and_census_with_automatic_total(db, two):
    a, _ = two
    rep = client_for("rep-a@psie.ci")
    assert school(rep, a).status_code == 303
    e = db.query(models.Ecole).one()
    assert census(rep, a, e).status_code == 303
    r = db.query(models.RecensementEcole).one()
    assert r.personnel_total == 20
    assert "École Al Amine" in rep.get(f"/faitieres/{a.id}/ecoles").text
    page = rep.get(f"/faitieres/{a.id}/ecoles/{e.id}")
    assert page.status_code == 200 and "300" in page.text
    census(rep, a, e, eleves="350")                                        # même année : remplacée, pas dupliquée
    db.expire_all()
    assert db.query(models.RecensementEcole).count() == 1 and db.query(models.RecensementEcole).one().eleves == 350
    assert census(rep, a, e, eleves="-4").status_code == 400
    assert census(rep, a, e, annee="1800").status_code == 400


def test_exam_results_validate_and_compute_rate(db, two):
    a, _ = two
    rep = client_for("rep-a@psie.ci")
    school(rep, a)
    e = db.query(models.Ecole).one()
    url = f"/faitieres/{a.id}/ecoles/{e.id}/examens"
    assert rep.post(url, data={"annee": str(YEAR), "examen": "cepe", "inscrits": "40", "admis": "30"}).status_code == 303
    assert db.query(models.ResultatExamen).one().taux == 75.0
    assert rep.post(url, data={"annee": str(YEAR), "examen": "cepe", "inscrits": "10", "admis": "11"}).status_code == 400
    assert rep.post(url, data={"annee": str(YEAR), "examen": "inconnu", "inscrits": "10", "admis": "5"}).status_code == 400
    res = db.query(models.ResultatExamen).one()
    assert rep.post(f"{url}/{res.id}/supprimer").status_code == 303 and db.query(models.ResultatExamen).count() == 0


def test_a_federation_never_reaches_another_federations_schools(db, two):
    a, b = two
    school(client_for("rep-a@psie.ci"), a)
    e = db.query(models.Ecole).one()
    rep_b = client_for("rep-b@psie.ci")
    assert rep_b.get(f"/faitieres/{a.id}/ecoles/{e.id}").status_code == 404
    assert census(rep_b, a, e).status_code == 404
    assert census(rep_b, b, e).status_code == 404                           # l'identifiant d'une autre école dans sa propre adresse
    assert rep_b.get(f"/faitieres/{a.id}/statistiques").status_code == 404
    assert rep_b.get(f"/faitieres/{a.id}/export-ecoles.csv").status_code == 404
    assert db.query(models.RecensementEcole).count() == 0


def test_report_workflow_propose_then_validate_or_fix(db, two):
    a, _ = two
    rep = client_for("rep-a@psie.ci")
    school(rep, a)
    e = db.query(models.Ecole).one()
    base = f"/faitieres/{a.id}/ecoles/{e.id}/bilans"
    assert rep.post(base, data={"annee": str(YEAR), "resume": "Bonne année", "action": "soumettre"}).status_code == 303
    b = db.query(models.BilanEcole).one()
    assert b.statut == "soumis"
    assert rep.post(f"{base}/{b.id}/decision", data={"decision": "valider"}).status_code == 403   # pas à la faîtière de se valider
    make_user(db, "form@psie.ci", "formation")
    form = client_for("form@psie.ci")
    assert form.post(f"{base}/{b.id}/decision", data={"decision": "a_corriger"}).status_code == 400   # motif obligatoire
    assert form.post(f"{base}/{b.id}/decision", data={"decision": "a_corriger", "avis": "Précisez les effectifs"}).status_code == 303
    db.refresh(b)
    assert b.statut == "a_corriger" and b.avis == "Précisez les effectifs"
    rep.post(base, data={"annee": str(YEAR), "resume": "Corrigé", "action": "soumettre"})
    db.refresh(b)
    assert b.statut == "soumis" and b.resume == "Corrigé"
    form.post(f"{base}/{b.id}/decision", data={"decision": "valider"})
    db.refresh(b)
    assert b.statut == "valide"
    assert rep.post(base, data={"annee": str(YEAR), "resume": "Retouche", "action": "soumettre"}).status_code == 400   # figé une fois validé


def test_secretariats_follow_the_access_grid(db, two):
    a, _ = two
    school(client_for("rep-a@psie.ci"), a)
    e = db.query(models.Ecole).one()
    make_user(db, "exam@psie.ci", "examens")
    make_user(db, "com@psie.ci", "communication")
    make_user(db, "fin@psie.ci", "finances")
    exam, com, fin = client_for("exam@psie.ci"), client_for("com@psie.ci"), client_for("fin@psie.ci")
    assert exam.get(f"/faitieres/{a.id}/ecoles/{e.id}").status_code == 200                # Examens : écoles en écriture
    assert census(exam, a, e).status_code == 303
    assert com.get(f"/faitieres/{a.id}/ecoles").status_code == 403                         # Communication : rien
    assert com.get("/statistiques").status_code == 403
    assert fin.get("/statistiques").status_code == 200                                     # Finances : lecture
    assert census(fin, a, e).status_code == 403
    assert "/statistiques" in exam.get("/admin").text and "/statistiques" not in com.get("/admin").text


def test_statistics_per_federation_and_privacy(db, two):
    a, b = two
    ra, rb = client_for("rep-a@psie.ci"), client_for("rep-b@psie.ci")
    school(ra, a, "École A1")
    school(rb, b, "École B1")
    ea, eb = db.query(models.Ecole).filter_by(nom="École A1").one(), db.query(models.Ecole).filter_by(nom="École B1").one()
    census(ra, a, ea, eleves="300")
    census(rb, b, eb, eleves="100", admin_francophone="0", admin_arabisant="0", ens_francophone="3", ens_arabisant="2")
    ra.post(f"/faitieres/{a.id}/ecoles/{ea.id}/examens", data={"annee": str(YEAR), "examen": "bepc", "inscrits": "20", "admis": "10"})
    make_user(db, "den@psie.ci", "den")
    den = client_for("den@psie.ci")
    page = den.get("/statistiques").text
    assert "LECIM" in page and "IQRA" in page and "50.0 %" in page
    csv = den.get(f"/statistiques.csv?annee={YEAR}")
    assert csv.status_code == 200 and "LECIM" in csv.text and "IQRA" in csv.text
    own = ra.get(f"/faitieres/{a.id}/statistiques").text
    assert "300" in own and "École B1" not in own and "IQRA" not in own        # sa position par rapport à la moyenne, sans nommer les autres
    assert ra.get("/statistiques").status_code == 303 and ra.get("/statistiques").headers["location"] == f"/faitieres/{a.id}/statistiques"
    assert ra.get("/statistiques.csv").status_code == 403


def test_csv_export_and_import(db, two):
    a, _ = two
    rep = client_for("rep-a@psie.ci")
    data = "nom;localité;DRENA;téléphone;niveau;directeur\nÉcole Nour;Bouaké;Bouaké 1;0707;primaire;M. Diallo\n=cmd();X;;;;\n".encode()
    r = rep.post(f"/faitieres/{a.id}/ecoles/import", files={"fichier": ("ecoles.csv", data, "text/csv")})
    assert r.status_code == 303 and db.query(models.Ecole).count() == 2
    rep.post(f"/faitieres/{a.id}/ecoles/import", files={"fichier": ("ecoles.csv", data, "text/csv")})
    assert db.query(models.Ecole).count() == 2                                              # pas de doublons
    out = rep.get(f"/faitieres/{a.id}/export-ecoles.csv").text
    assert "École Nour" in out and "'=cmd()" in out and "\n=cmd" not in out                  # formule neutralisée
    assert rep.post(f"/faitieres/{a.id}/ecoles/import", files={"fichier": ("x.csv", b"", "text/csv")}).status_code == 400


def test_dashboard_progress_and_announcements_and_requests(db, two):
    a, b = two
    rep = client_for("rep-a@psie.ci")
    page = rep.get(f"/faitieres/{a.id}").text
    assert "Dossier à compléter" in page and "<progress" in page
    make_user(db, "sec@psie.ci", "secretaire")
    make_user(db, "com@psie.ci", "communication")
    sec = client_for("sec@psie.ci")
    assert sec.post("/annonces", data={"titre": "Assemblée", "texte": "Date à venir", "cible": ""}).status_code == 303
    assert sec.post("/annonces", data={"titre": "Pour IQRA", "texte": "Privé", "cible": str(b.id)}).status_code == 303
    assert "Assemblée" in rep.get("/annonces").text and "Pour IQRA" not in rep.get("/annonces").text
    assert "Pour IQRA" in client_for("rep-b@psie.ci").get("/annonces").text
    assert rep.post("/annonces", data={"titre": "x", "texte": "y"}).status_code == 403
    assert rep.post("/demandes", data={"type": "attestation", "objet": "Attestation 2026", "message": "Merci"}).status_code == 303
    d = db.query(models.DemandeFaitiere).one()
    assert "Attestation 2026" in sec.get("/demandes").text and "Attestation 2026" not in client_for("rep-b@psie.ci").get("/demandes").text
    assert sec.post("/demandes", data={"type": "autre", "objet": "x"}).status_code == 403   # seule une faîtière écrit à la PSIE
    assert rep.post(f"/demandes/{d.id}/traiter", data={"statut": "traitee", "reponse": "ok"}).status_code == 403
    assert sec.post(f"/demandes/{d.id}/traiter", data={"statut": "traitee", "reponse": "Prête"}).status_code == 303
    assert "Prête" in rep.get("/demandes").text
    assert client_for("com@psie.ci").get("/demandes").status_code == 403
