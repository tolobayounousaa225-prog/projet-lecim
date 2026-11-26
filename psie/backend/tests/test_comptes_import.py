import pytest

from app import comptes_import as ci
from app import models, password_reset

from .conftest import client_for, make_faitiere, make_user

HEAD = "nom;email;role;faitiere;origine\n"


@pytest.fixture
def lecim(db):
    return make_faitiere(db, "LECIM")


def run(db, text, **kw):
    rows = ci.parse(text, db)
    sent = []
    done = ci.apply(db, rows, send=lambda to, subject, body: sent.append((to, body)) or True, **kw)
    return rows, done, sent


def test_creates_secretariats_and_federation_accounts_with_invitations(db, lecim):
    text = HEAD + "A Examens;exam@exemple.org;examens;;\nB Rep;rep@exemple.org;faitiere;lecim;\nC Fin;fin@exemple.org;Secrétaire chargé des finances (ou adjoint);;LECIM\n"
    rows, done, sent = run(db, text)
    assert [r.errors for r in rows] == [[], [], []] and len(done) == 3
    users = {u.email: u for u in db.query(models.User)}
    assert users["exam@exemple.org"].role == "examens"
    assert users["rep@exemple.org"].role == "faitiere" and users["rep@exemple.org"].faitiere_id == lecim.id
    assert users["fin@exemple.org"].role == "finances" and users["fin@exemple.org"].faitiere_origine_id == lecim.id
    for to, body in sent:
        assert "/mot-de-passe-oublie/" in body and "mot de passe" in body.lower()      # un lien, jamais un mot de passe
    token = done[0][1].rsplit("/", 1)[1]
    assert password_reset.find_valid(db, token) is not None


def test_invitation_link_lets_the_person_choose_a_password_and_log_in(db, lecim):
    _, done, _ = run(db, HEAD + "A Com;com@exemple.org;communication;;\n")
    token = done[0][1].rsplit("/", 1)[1]
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app, follow_redirects=False)
    r = c.post(f"/mot-de-passe-oublie/{token}", data={"new": "MotDePasse-Solide-2026", "confirm": "MotDePasse-Solide-2026"})
    assert r.status_code in (200, 303), r.text
    assert db.query(models.User).filter_by(email="com@exemple.org").one().role == "communication"
    assert c.post("/login", data={"email": "com@exemple.org", "password": "MotDePasse-Solide-2026"}).status_code == 303
    assert c.post(f"/mot-de-passe-oublie/{token}", data={"new": "Autre-Mot-De-Passe-2026", "confirm": "Autre-Mot-De-Passe-2026"}).status_code == 400   # lien à usage unique


def test_errors_block_everything_and_nothing_is_created(db, lecim):
    text = HEAD + "A;a@exemple.org;examens;;\n;b@exemple.org;examens;;\nC;pas-un-mail;examens;;\nD;d@exemple.org;chef;;\nE;e@exemple.org;faitiere;INCONNUE;\nF;a@exemple.org;examens;;\n"
    rows = ci.parse(text, db)
    errors = [r.errors for r in rows]
    assert errors[0] == [] and "nom manquant" in errors[1][0] and "e-mail invalide" in errors[2][0]
    assert "rôle inconnu" in errors[3][0] and "faîtière inconnue" in errors[4][0] and "en double" in errors[5][0]
    assert db.query(models.User).count() == 0                                        # parse ne crée rien


def test_existing_accounts_are_left_untouched(db, lecim):
    make_user(db, "deja@exemple.org", "den", name="Déjà là")
    rows, done, _ = run(db, HEAD + "Nouveau Nom;DEJA@exemple.org;examens;;\nAutre;autre@exemple.org;examens;;\n")
    assert rows[0].skip and len(done) == 1
    old = db.query(models.User).filter_by(email="deja@exemple.org").one()
    assert old.role == "den" and old.full_name == "Déjà là"


def test_rows_limit_and_empty_file(db):
    with pytest.raises(ValueError):
        ci.parse("", db)
    with pytest.raises(ValueError):
        ci.parse(HEAD + "".join(f"N{i};n{i}@exemple.org;examens;;\n" for i in range(ci.MAX_ROWS + 1)), db)


def test_comma_separated_and_excel_bom_files_are_accepted(db):
    rows = ci.parse("﻿nom,email,role\nA,a@exemple.org,examens\n", db)
    assert rows[0].errors == [] and rows[0].role == "examens"
