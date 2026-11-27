"""Accès par rubrique : chaque secrétariat ne voit que ce qui le concerne ; l'administrateur règle qui voit quoi."""
import datetime
import re

import pytest

from app import acces, models

from .conftest import client_for, make_faitiere, make_user

ROLES = ("den", "secretaire", "finances", "communication", "formation", "examens", "ressources", "administrateur_ca", "commissaire")
# une adresse typique de chaque rubrique
URLS = {"membres": "/faitieres", "adhesions": "/adhesions", "formation": "/formations", "documents": "/documents",
        "finances": "/cotisations", "contenu": "/gestion/contenu"}


@pytest.fixture
def people(db):
    make_faitiere(db, "LECIM")
    make_user(db, "admin@psie.ci", "admin")
    for r in ROLES:
        make_user(db, f"{r}@psie.ci", r)
    return None


def status(email, url):
    return client_for(email).get(url).status_code


# ---------------------------------------------------------------- valeurs par défaut

@pytest.mark.parametrize("role", ROLES)
def test_each_role_sees_exactly_its_own_sections_by_default(people, role):
    for section, url in URLS.items():
        expected = 200 if acces.DEFAULTS[role].get(section, 0) >= acces.LECTURE else 403
        assert status(f"{role}@psie.ci", url) == expected, (role, section)
    assert status(f"{role}@psie.ci", "/admin") == 200                                  # tableau de bord : toujours


def test_admin_has_no_finance_access_by_default_and_keeps_the_admin_pages(people):
    assert status("admin@psie.ci", "/cotisations") == 403 and status("admin@psie.ci", "/finances") == 403
    for url in ("/users", "/audit", "/acces", "/faitieres", "/gestion/contenu"):
        assert status("admin@psie.ci", url) == 200, url


def test_admin_pages_are_reserved_to_the_admin(people):
    for role in ROLES:
        for url in ("/users", "/audit", "/acces"):
            assert status(f"{role}@psie.ci", url) == 403, (role, url)


def test_a_section_cannot_be_reached_by_typing_the_address(people):
    c = client_for("communication@psie.ci")
    for url in ("/faitieres/1", "/faitieres/1/edit", "/mandats", "/adhesions/1",
                "/depenses", "/etat-financier.pdf", "/paiements/1/recu.pdf", "/appels/1", "/registre-membres.pdf", "/pieces/1",
                "/faitieres/1/releve.pdf", "/faitieres/1/attestation.pdf", "/cotisations/export.csv"):
        assert c.get(url).status_code == 403, url
    assert c.post("/faitieres/new", data={"nom": "X", "sigle": "X"}).status_code == 403


def test_a_refused_section_shows_a_clear_message(people):
    page = client_for("communication@psie.ci").get("/faitieres")
    assert page.status_code == 403 and "ne fait pas partie de votre espace" in page.text


def test_federation_accounts_are_not_affected_by_the_sections(db, people):
    f = db.query(models.Faitiere).one()
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    c = client_for("rep@psie.ci")
    assert c.get(f"/faitieres/{f.id}").status_code == 200 and c.get("/formations").status_code == 200
    assert c.get(f"/faitieres/{f.id}/releve.pdf").status_code == 200
    assert c.get("/cotisations").status_code == 403 and c.get("/users").status_code == 403


def test_public_pages_stay_open(anon):
    for url in ("/login", "/adhesion", "/apropos", "/membres", "/actualites", "/health"):
        assert anon.get(url).status_code == 200, url


# ---------------------------------------------------------------- réglage par l'administrateur

def matrix_form(db, **overrides):
    """Formulaire complet de la grille : valeurs actuelles (par défaut), avec les changements demandés."""
    data = {}
    for role in [r for r in models.ROLES if r != "faitiere"]:
        levels = acces.role_defaults_with_overrides(db, role)
        for section in acces.SECTIONS:
            data[f"n__{role}__{section}"] = str(levels.get(section, 0))
    data.update({k.replace("__", "__", 1): str(v) for k, v in overrides.items()})
    return data


def test_the_matrix_page_lists_every_role_and_section(db, people):
    page = client_for("admin@psie.ci").get("/acces").text
    for label in ("Membres et mandats", "Finances et cotisations", "Contenu du site", "Secrétariat Examens", "Commissaire aux comptes"):
        assert label in page, label
    assert page.count("<select") == len(acces.SECTIONS) * len([r for r in models.ROLES if r != "faitiere"])
    assert "n__faitiere__" not in page                                                      # pas de colonne pour les faîtières


def test_extending_a_secretariat_takes_effect_immediately(db, people):
    assert status("examens@psie.ci", "/faitieres") == 403
    r = client_for("admin@psie.ci").post("/acces", data=matrix_form(db, **{"n__examens__membres": 1}))
    assert r.status_code == 303 and r.headers["location"] == "/acces?ok=1"
    assert status("examens@psie.ci", "/faitieres") == 200                                   # lecture accordée
    assert client_for("examens@psie.ci").post("/faitieres/new", data={"nom": "X", "sigle": "X"}).status_code == 403   # pas d'écriture
    assert "Membres et mandats" not in client_for("formation@psie.ci").get("/admin").text   # les autres rôles ne changent pas


def test_granting_write_lets_the_role_change_things(db, people):
    client_for("admin@psie.ci").post("/acces", data=matrix_form(db, **{"n__examens__membres": 2}))
    r = client_for("examens@psie.ci").post("/faitieres/new", data={"nom": "Nouvelle", "sigle": "NOUV", "categorie": "ordinaire", "statut": "actif"})
    assert r.status_code == 303 and db.query(models.Faitiere).filter_by(sigle="NOUV").count() == 1


def test_restricting_a_role_hides_what_it_saw_before(db, people):
    assert status("secretaire@psie.ci", "/formations") == 200
    client_for("admin@psie.ci").post("/acces", data=matrix_form(db, **{"n__secretaire__formation": 0}))
    assert status("secretaire@psie.ci", "/formations") == 403
    assert status("secretaire@psie.ci", "/adhesions") == 200


def test_only_differences_are_stored_and_defaults_can_be_restored(db, people):
    admin = client_for("admin@psie.ci")
    admin.post("/acces", data=matrix_form(db))                                              # rien ne change
    assert db.query(models.AccesRole).count() == 0
    admin.post("/acces", data=matrix_form(db, **{"n__examens__membres": 1, "n__den__finances": 2}))
    assert {(r.role, r.section, r.niveau) for r in db.query(models.AccesRole)} == {("examens", "membres", 1), ("den", "finances", 2)}
    admin.post("/acces", data=matrix_form(db, **{"n__examens__membres": 0, "n__den__finances": 1}))   # retour aux valeurs par défaut
    assert db.query(models.AccesRole).count() == 0
    admin.post("/acces", data=matrix_form(db, **{"n__examens__membres": 2}))
    assert admin.post("/acces/reinitialiser").status_code == 303 and db.query(models.AccesRole).count() == 0
    assert status("examens@psie.ci", "/faitieres") == 403


def test_invalid_values_are_ignored(db, people):
    data = matrix_form(db, **{"n__examens__membres": "9"})
    data["n__examens__inconnue"] = "2"
    data["n__fantome__membres"] = "2"
    client_for("admin@psie.ci").post("/acces", data=data)
    assert db.query(models.AccesRole).count() == 0


def test_only_the_admin_can_change_the_matrix(db, people):
    for role in ROLES:
        c = client_for(f"{role}@psie.ci")
        assert c.post("/acces", data=matrix_form(db, **{"n__examens__membres": 2})).status_code == 403, role
        assert c.post("/acces/reinitialiser").status_code == 403
    assert db.query(models.AccesRole).count() == 0


def test_every_change_is_written_to_the_audit_log(db, people):
    client_for("admin@psie.ci").post("/acces", data=matrix_form(db, **{"n__examens__membres": 1}))
    entry = db.query(models.AuditLog).filter_by(action="acces_roles").one()
    assert "examens/membres=1" in entry.detail and entry.user_email == "admin@psie.ci"


def test_the_admin_cannot_lock_himself_out_of_the_admin_pages(db, people):
    data = matrix_form(db, **{f"n__admin__{s}": 0 for s in acces.SECTIONS})
    client_for("admin@psie.ci").post("/acces", data=data)
    assert status("admin@psie.ci", "/acces") == 200 and status("admin@psie.ci", "/users") == 200
    assert status("admin@psie.ci", "/faitieres") == 403


# ---------------------------------------------------------------- exceptions personnelles

def test_a_personal_exception_beats_the_role(db, people):
    exam = db.query(models.User).filter_by(email="examens@psie.ci").one()
    admin = client_for("admin@psie.ci")
    page = admin.get(f"/users/{exam.id}/acces").text
    assert "Comme son rôle" in page and "Secrétariat Examens" in page
    r = admin.post(f"/users/{exam.id}/acces", data={"n__adhesions": "1", "n__membres": "", "n__finances": ""})
    assert r.status_code == 303
    assert status("examens@psie.ci", "/adhesions") == 200                                   # lui seul
    assert status("formation@psie.ci", "/adhesions") == 403                                 # pas son collègue
    assert {(r.section, r.niveau) for r in db.query(models.AccesUtilisateur)} == {("adhesions", 1)}
    admin.post(f"/users/{exam.id}/acces", data={"n__adhesions": ""})                       # « comme son rôle » retire l'exception
    assert db.query(models.AccesUtilisateur).count() == 0 and status("examens@psie.ci", "/adhesions") == 403


def test_a_personal_exception_can_also_remove_an_access(db, people):
    sec = db.query(models.User).filter_by(email="secretaire@psie.ci").one()
    client_for("admin@psie.ci").post(f"/users/{sec.id}/acces", data={"n__formation": "0"})
    assert status("secretaire@psie.ci", "/formations") == 403 and status("secretaire@psie.ci", "/adhesions") == 200
    assert status("den@psie.ci", "/formations") == 200


def test_exception_equal_to_the_role_level_is_not_stored(db, people):
    sec = db.query(models.User).filter_by(email="secretaire@psie.ci").one()
    client_for("admin@psie.ci").post(f"/users/{sec.id}/acces", data={"n__formation": "2"})       # déjà le niveau de son rôle
    assert db.query(models.AccesUtilisateur).count() == 0


def test_exceptions_follow_a_change_of_the_role_matrix(db, people):
    exam = db.query(models.User).filter_by(email="examens@psie.ci").one()
    admin = client_for("admin@psie.ci")
    admin.post(f"/users/{exam.id}/acces", data={"n__membres": "1"})
    assert status("examens@psie.ci", "/faitieres") == 200
    admin.post("/acces", data=matrix_form(db, **{"n__examens__membres": 2}))
    assert db.query(models.AccesUtilisateur).count() == 1                                   # l'exception reste, la grille a changé
    assert status("examens@psie.ci", "/faitieres") == 200


def test_exception_pages_are_admin_only_and_not_for_federations(db, people):
    f = db.query(models.Faitiere).one()
    rep = make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    exam = db.query(models.User).filter_by(email="examens@psie.ci").one()
    assert client_for("den@psie.ci").get(f"/users/{exam.id}/acces").status_code == 403
    assert client_for("den@psie.ci").post(f"/users/{exam.id}/acces", data={"n__membres": "2"}).status_code == 403
    assert client_for("admin@psie.ci").get(f"/users/{rep.id}/acces").status_code == 404
    assert client_for("admin@psie.ci").get("/users/9999/acces").status_code == 404
    assert "/users/%d/acces" % exam.id in client_for("admin@psie.ci").get("/users").text
    assert "/users/%d/acces" % rep.id not in client_for("admin@psie.ci").get("/users").text


# ---------------------------------------------------------------- pouvoirs liés à la fonction

def test_statutory_powers_do_not_travel_with_a_section(db, people):
    """Donner l'écriture sur les finances à un secrétariat ne lui permet pas de signer une dépense (art. 38)."""
    admin = client_for("admin@psie.ci")
    admin.post("/acces", data=matrix_form(db, **{"n__communication__finances": 2}))
    c = client_for("communication@psie.ci")
    assert c.get("/depenses").status_code == 200
    dep = models.Depense(libelle="Test", montant=1000, categorie="autre", date_depense=datetime.date.today(), statut="a_valider")
    db.add(dep)
    db.commit()
    assert c.post(f"/depenses/{dep.id}/signer").status_code in (400, 403, 404, 409)
    db.refresh(dep)
    assert dep.statut == "a_valider"
    # et un avis du CA reste réservé aux fonctions prévues par les Statuts
    admin.post("/acces", data=matrix_form(db, **{"n__communication__adhesions": 2}))
    assert client_for("communication@psie.ci").post("/adhesions/1/avis", data={"avis": "favorable"}).status_code == 403


# ---------------------------------------------------------------- menu et tableau de bord

def menu_of(email):
    page = client_for(email).get("/admin").text
    return set(re.findall(r'<a href="(/[a-z/-]*)"', page.split('class="nav"')[1].split("</aside>")[0] if 'class="nav"' in page else ""))


def test_the_menu_only_lists_allowed_sections(people):
    com = menu_of("communication@psie.ci")
    assert "/gestion/contenu" in com and "/documents" in com and "/admin" in com
    assert not ({"/faitieres", "/adhesions", "/cotisations", "/users", "/acces", "/audit"} & com)
    fin = menu_of("finances@psie.ci")
    assert {"/cotisations", "/appels", "/finances", "/faitieres", "/documents"} <= fin and "/adhesions" not in fin and "/users" not in fin
    adm = menu_of("admin@psie.ci")
    assert {"/users", "/acces", "/audit", "/faitieres", "/gestion/contenu"} <= adm and "/cotisations" not in adm


def test_an_extended_secretariat_gets_the_menu_entry(db, people):
    assert "/faitieres" not in menu_of("examens@psie.ci")
    client_for("admin@psie.ci").post("/acces", data=matrix_form(db, **{"n__examens__membres": 1}))
    assert "/faitieres" in menu_of("examens@psie.ci")


def test_the_dashboard_only_shows_what_the_user_may_see(db, people):
    com = client_for("communication@psie.ci").get("/admin").text
    for hidden in ("Membres actifs", "Composition des organes", "Mandats arrivant à échéance", "Appels exceptionnels en cours"):
        assert hidden not in com, hidden
    assert "Contenu du site" in com
    den = client_for("den@psie.ci").get("/admin").text
    assert "Membres actifs" in den and "Composition des organes" in den and "Appels exceptionnels en cours" in den
    fin = client_for("finances@psie.ci").get("/admin").text
    assert "Appels exceptionnels en cours" in fin and "Composition des organes" in fin       # les finances lisent aussi les membres
    exam = client_for("examens@psie.ci").get("/admin").text
    assert "Composition des organes" not in exam and "Appels exceptionnels en cours" not in exam
    assert "Documents et courrier" in exam and "Formation" in exam and "Adhésions" not in exam
