import pytest

from app import models

from .conftest import client_for, make_faitiere, make_user

YEAR = 2025


@pytest.fixture
def setup(db):
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    other = make_faitiere(db, "IQRA")
    make_user(db, "rep2@psie.ci", "faitiere", faitiere_id=other.id)
    rep = client_for("rep@psie.ci")
    for nom in ("École Al Amine", "École Nour"):
        rep.post(f"/faitieres/{f.id}/ecoles", data={"nom": nom})
    return f, rep


def post(client, f, kind, text, simuler=""):
    return client.post(f"/faitieres/{f.id}/import-{kind}", data={"simuler": simuler},
                       files={"fichier": ("x.csv", text.encode(), "text/csv")})


def test_census_import_simulation_then_apply_with_tolerant_headers(db, setup):
    f, rep = setup
    csv = ("École;Année;Élèves;Administratifs francophones;Administratifs arabisants;Enseignants francophones;Enseignants arabisants\n"
           f"école al amine;{YEAR};300;2;1;10;7\nÉcole Nour;{YEAR};150;1;0;5;3\n")
    sim = post(rep, f, "recensement", csv, simuler="1")
    assert sim.status_code == 200 and "Simulation réussie" in sim.text
    assert db.query(models.RecensementEcole).count() == 0                       # la simulation n'écrit rien
    real = post(rep, f, "recensement", csv)
    assert real.status_code == 200 and "Import terminé" in real.text
    db.expire_all()
    assert db.query(models.RecensementEcole).count() == 2
    first = db.query(models.RecensementEcole).filter_by(eleves=300).one()
    assert first.personnel_total == 20
    post(rep, f, "recensement", csv.replace("300", "310"))                     # même année : remplacée, pas dupliquée
    db.expire_all()
    assert db.query(models.RecensementEcole).count() == 2 and db.query(models.RecensementEcole).filter_by(eleves=310).count() == 1


def test_any_error_blocks_the_whole_file_with_a_line_report(db, setup):
    f, rep = setup
    csv = f"école;année;élèves\nÉcole Nour;{YEAR};100\nInconnue;{YEAR};50\nÉcole Nour;1800;10\nÉcole Nour;{YEAR};-3\n"
    r = post(rep, f, "recensement", csv)
    assert r.status_code == 400 and "ligne 3" in r.text and "ligne 4" in r.text and "ligne 5" in r.text and "ligne 2" not in r.text
    assert db.query(models.RecensementEcole).count() == 0                       # rien d'enregistré, même la ligne valide


def test_exam_results_import(db, setup):
    f, rep = setup
    ok = post(rep, f, "examens", f"école;année;examen;candidats;admis\nÉcole Nour;{YEAR};CEPE;40;30\nÉcole Nour;{YEAR};Baccalauréat;20;10\n")
    assert ok.status_code == 200 and db.query(models.ResultatExamen).count() == 2
    bad = post(rep, f, "examens", f"école;année;examen;candidats;admis\nÉcole Nour;{YEAR};CEPE;10;11\nÉcole Nour;{YEAR};Truc;10;5\n")
    assert bad.status_code == 400 and "dépasser" in bad.text and "examen inconnu" in bad.text


def test_files_and_isolation(db, setup):
    f, rep = setup
    assert post(rep, f, "recensement", "").status_code == 400                     # vide
    assert post(rep, f, "recensement", "école;élèves\nA;1\n").status_code == 400
    assert post(rep, f, "inconnu", "x").status_code == 404
    other = client_for("rep2@psie.ci")
    assert post(other, f, "recensement", f"école;année\nÉcole Nour;{YEAR}\n").status_code == 404   # pas la faîtière d'un autre
    # une école d'une autre faîtière n'est jamais touchée
    iqra = db.query(models.Faitiere).filter_by(sigle="IQRA").one()
    other.post(f"/faitieres/{iqra.id}/ecoles", data={"nom": "École Iqra"})
    bad = post(rep, f, "recensement", f"école;année\nÉcole Iqra;{YEAR}\n")
    assert bad.status_code == 400 and "école inconnue" in bad.text


def test_members_import_by_den_only(db):
    make_user(db, "den@psie.ci", "den")
    make_user(db, "com@psie.ci", "communication")
    make_faitiere(db, "LECIM")
    text = "sigle;nom;catégorie;e-mail\nNOUR;Union Nour;ordinaire;nour@exemple.org\nSAFA;Réseau Safa;honneur;\n"
    den, com = client_for("den@psie.ci"), client_for("com@psie.ci")
    files = {"fichier": ("m.csv", text.encode(), "text/csv")}
    assert com.post("/faitieres/import", data={}, files=files).status_code == 403
    assert den.post("/faitieres/import", data={"simuler": "1"}, files=files).status_code == 200
    assert db.query(models.Faitiere).count() == 1
    assert den.post("/faitieres/import", data={}, files=files).status_code == 200
    assert {f.sigle for f in db.query(models.Faitiere)} == {"LECIM", "NOUR", "SAFA"}
    dup = den.post("/faitieres/import", data={}, files={"fichier": ("m.csv", b"sigle;nom\nlecim;Doublon\nNEW;x\nNEW;y\n", "text/csv")})
    assert dup.status_code == 400 and "existe déjà" in dup.text and "en double" in dup.text
    assert db.query(models.Faitiere).count() == 3
