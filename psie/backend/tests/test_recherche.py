import pytest

from app import models

from .conftest import client_for, make_faitiere, make_user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def world(db):
    a, b = make_faitiere(db, "LECIM"), make_faitiere(db, "IQRA")
    make_user(db, "rep-a@psie.ci", "faitiere", faitiere_id=a.id)
    make_user(db, "den@psie.ci", "den")
    make_user(db, "com@psie.ci", "communication")
    make_user(db, "fin@psie.ci", "finances")
    make_user(db, "adm@psie.ci", "admin", name="Admin Spécial")
    ra, rb = client_for("rep-a@psie.ci"), None
    ra.post(f"/faitieres/{a.id}/ecoles", data={"nom": "École Al Amine", "localite": "Yopougon"})
    make_user(db, "rep-b@psie.ci", "faitiere", faitiere_id=b.id)
    client_for("rep-b@psie.ci").post(f"/faitieres/{b.id}/ecoles", data={"nom": "École Secrète Iqra"})
    den = client_for("den@psie.ci")
    den.post("/documents", data={"titre": "Statuts Amine 2026", "categorie": "statuts"}, files={"fichier": ("s.pdf", PDF, "application/pdf")})
    den.post("/documents", data={"titre": "Note Amine confidentielle", "categorie": "decision", "restreint": "1"},
             files={"fichier": ("s.pdf", PDF, "application/pdf")})
    den.post("/courrier", data={"sens": "arrivee", "correspondant": "Ministère Amine", "objet": "Invitation"})
    return a, b


def test_den_finds_everything_he_may_see(world):
    page = client_for("den@psie.ci").get("/recherche?q=amine").text
    assert "École Al Amine" in page and "Statuts Amine 2026" in page and "Note Amine confidentielle" in page and "Ministère Amine" in page


def test_results_follow_the_access_grid(world):
    com = client_for("com@psie.ci").get("/recherche?q=amine").text              # lecture des documents, pas des écoles
    assert "Statuts Amine 2026" in com and "Note Amine confidentielle" not in com and "École Al Amine" not in com
    fin = client_for("fin@psie.ci").get("/recherche?q=amine").text
    assert "École Al Amine" in fin
    assert "Admin Spécial" not in client_for("den@psie.ci").get("/recherche?q=sp%C3%A9cial").text          # comptes : administrateur seulement
    assert "Admin Spécial" in client_for("adm@psie.ci").get("/recherche?q=sp%C3%A9cial").text


def test_a_federation_only_searches_its_own_data(world):
    ra = client_for("rep-a@psie.ci")
    assert "École Al Amine" in ra.get("/recherche?q=amine").text
    other = ra.get("/recherche?q=iqra").text
    assert "École Secrète Iqra" not in other and "Statuts" not in ra.get("/recherche?q=statuts").text


def test_short_or_wild_queries_are_harmless(world):
    den = client_for("den@psie.ci")
    assert "2 caractères" in den.get("/recherche?q=a").text
    assert den.get("/recherche?q=%25%25").status_code == 200 and "Statuts" not in den.get("/recherche?q=%25%25").text   # « % » n'est pas un joker
    assert den.get("/recherche?q=" + "x" * 500).status_code == 200


def test_application_pages_load_only_our_own_script_and_no_inline_script(world):
    page = client_for("den@psie.ci").get("/faitieres").text
    assert '<script src="/static/psie.js" defer></script>' in page and page.count("<script") == 1
    assert 'id="global-search"' in page and "data-filterable" in page
    from fastapi.testclient import TestClient
    from app.main import app
    anon_page = TestClient(app).get("/login").text
    assert "<script" not in anon_page                                          # la connexion n'en charge aucun
    js = TestClient(app).get("/static/psie.js")
    assert js.status_code == 200 and "eval(" not in js.text and "innerHTML" not in js.text
