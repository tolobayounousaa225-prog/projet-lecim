import pytest

from app import models

from .conftest import client_for, make_faitiere, make_user


@pytest.fixture
def two(db):
    a, b = make_faitiere(db, "LECIM"), make_faitiere(db, "IQRA")
    make_user(db, "rep-a@psie.ci", "faitiere", faitiere_id=a.id)
    make_user(db, "rep-b@psie.ci", "faitiere", faitiere_id=b.id)
    return a, b


def add(client, f, kind, **data):
    return client.post(f"/faitieres/{f.id}/{kind}", data=data)


def test_a_federation_manages_its_own_delegates_and_schools(db, two):
    a, _ = two
    rep = client_for("rep-a@psie.ci")
    assert add(rep, a, "delegues", nom="Koné Ali", drena="Abidjan 1", telephone="0707070707").status_code == 303
    assert add(rep, a, "ecoles", nom="École Al Amine", localite="Yopougon", drena="Abidjan 3").status_code == 303
    page = rep.get(f"/faitieres/{a.id}/delegues")
    assert "Koné Ali" in page.text and "Abidjan 1" in page.text
    assert "École Al Amine" in rep.get(f"/faitieres/{a.id}/ecoles").text
    assert "Espace de la faîtière" in rep.get(f"/faitieres/{a.id}").text
    item = db.query(models.Ecole).one()
    assert rep.post(f"/faitieres/{a.id}/ecoles/{item.id}/supprimer").status_code == 303
    assert db.query(models.Ecole).count() == 0


def test_a_federation_never_sees_or_touches_another(db, two):
    a, b = two
    add(client_for("rep-a@psie.ci"), a, "ecoles", nom="École A")
    rep_b = client_for("rep-b@psie.ci")
    assert rep_b.get(f"/faitieres/{a.id}/ecoles").status_code == 404
    assert add(rep_b, a, "ecoles", nom="Intrus").status_code == 404
    school = db.query(models.Ecole).one()
    assert rep_b.post(f"/faitieres/{a.id}/ecoles/{school.id}/supprimer").status_code == 404
    # un identifiant d'une autre faîtière glissé dans sa propre adresse ne marche pas non plus
    assert rep_b.post(f"/faitieres/{b.id}/ecoles/{school.id}/supprimer").status_code == 404
    assert db.query(models.Ecole).count() == 1 and db.query(models.Ecole).one().nom == "École A"


def test_internal_bodies_can_read_and_only_den_and_secretariat_can_correct(db, two):
    a, _ = two
    add(client_for("rep-a@psie.ci"), a, "delegues", nom="Koné Ali", drena="Abidjan 1")
    make_user(db, "exam@psie.ci", "examens")
    make_user(db, "fin@psie.ci", "finances")
    make_user(db, "den@psie.ci", "den")
    exam, fin, den = client_for("exam@psie.ci"), client_for("fin@psie.ci"), client_for("den@psie.ci")
    assert exam.get(f"/faitieres/{a.id}/delegues").status_code == 403                    # hors de son secrétariat
    assert "Koné Ali" in fin.get(f"/faitieres/{a.id}/delegues").text                     # lecture seule pour les finances
    assert add(fin, a, "delegues", nom="X", drena="Y").status_code == 403
    assert add(den, a, "delegues", nom="Corrigé", drena="Bouaké").status_code == 303


def test_required_fields_and_unknown_kinds(db, two):
    a, _ = two
    rep = client_for("rep-a@psie.ci")
    assert add(rep, a, "ecoles", nom="").status_code == 400
    assert add(rep, a, "delegues", nom="Sans DRENA").status_code == 400
    assert add(rep, a, "ecoles", nom="x" * 300).status_code == 400
    assert rep.get(f"/faitieres/{a.id}/secrets").status_code == 404
    assert db.query(models.Ecole).count() == 0 and db.query(models.DelegueRegional).count() == 0


def test_anonymous_visitors_are_sent_to_login(db, two, anon):
    a, _ = two
    assert anon.get(f"/faitieres/{a.id}/ecoles").status_code == 303
    assert anon.post(f"/faitieres/{a.id}/ecoles", data={"nom": "x"}).status_code == 303


def test_html_in_names_is_escaped(db, two):
    a, _ = two
    rep = client_for("rep-a@psie.ci")
    add(rep, a, "ecoles", nom="<img src=x onerror=alert(1)>")
    assert "<img src=x" not in rep.get(f"/faitieres/{a.id}/ecoles").text
