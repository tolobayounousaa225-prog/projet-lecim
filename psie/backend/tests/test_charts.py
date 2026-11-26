import datetime

from app import charts, models

from .conftest import client_for, make_faitiere, make_user


def test_bars_escape_text_scale_and_describe():
    svg = str(charts.bars([("<script>alert(1)</script>", 10), ("B", 5), ("C", 0)], "Élèves"))
    assert "<script>" not in svg and "&lt;script&gt;" in svg
    assert 'role="img"' in svg and "<title>Élèves</title>" in svg and "<desc>" in svg
    assert svg.count("<rect") == 2                                       # une valeur nulle ne dessine pas de barre
    assert charts.bars([], "x") == ""


def test_stacked_and_line_degrade_gracefully():
    assert "c2" in str(charts.stacked([("A", [3, 7])], ["Fr", "Ar"], "Personnel"))
    assert charts.line([("2025", 10)], "x") == ""                        # une seule année : pas de courbe
    assert charts.line([("2025", None), ("2026", None)], "x") == ""
    svg = str(charts.line([("2024", 100), ("2025", 150.5), ("2026", 120)], "Élèves"))
    assert "<path" in svg and "150.5" in svg and svg.count("<circle") == 3


def test_statistics_pages_embed_the_charts_without_any_script(db):
    a, b = make_faitiere(db, "LECIM"), make_faitiere(db, "IQRA")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=a.id)
    make_user(db, "den@psie.ci", "den")
    rep = client_for("rep@psie.ci")
    year = datetime.date.today().year
    rep.post(f"/faitieres/{a.id}/ecoles", data={"nom": "École A"})
    e = db.query(models.Ecole).one()
    for y in (year - 1, year):
        rep.post(f"/faitieres/{a.id}/ecoles/{e.id}/recensement", data={"annee": str(y), "eleves": str(100 + y % 7), "ens_francophone": "3", "ens_arabisant": "2"})
    rep.post(f"/faitieres/{a.id}/ecoles/{e.id}/examens", data={"annee": str(year), "examen": "cepe", "inscrits": "20", "admis": "15"})
    for page in (rep.get(f"/faitieres/{a.id}/statistiques").text, client_for("den@psie.ci").get("/statistiques").text):
        assert "<svg" in page and 'role="img"' in page and page.count("<script") == 1 and "psie.js" in page
    assert "75 %" in rep.get(f"/faitieres/{a.id}/statistiques").text
