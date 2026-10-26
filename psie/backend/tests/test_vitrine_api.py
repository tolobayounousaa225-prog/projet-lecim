import datetime
import importlib

from fastapi.testclient import TestClient

from app import models
from app.config import Settings, production_problems, settings

from .conftest import make_faitiere


def test_public_json_exposes_only_public_data(db, anon):
    lecim = make_faitiere(db, "LECIM")
    lecim.email, lecim.telephone, lecim.siege = "secret@lecim.ci", "+225 00 00 00 00", "Adresse privée"
    susp = make_faitiere(db, "SUSP")
    susp.statut = "suspendu"
    db.add_all([
        models.Actualite(titre_fr="Publiée", contenu_fr="Texte", titre_ar="منشور", publie=True,
                         date_publication=datetime.date(2026, 5, 3)),
        models.Actualite(titre_fr="Brouillon", contenu_fr="Secret", publie=False),
    ])
    db.commit()
    r = anon.get("/api/public/vitrine.json")
    assert r.status_code == 200 and "max-age=300" in r.headers["cache-control"]
    data = r.json()
    assert [m["sigle"] for m in data["membres"]] == ["LECIM"]                  # membre suspendu exclu
    assert set(data["membres"][0]) == {"sigle", "nom", "categorie"}
    assert [n["titre"]["fr"] for n in data["actualites"]] == ["Publiée"]        # brouillon exclu
    assert data["actualites"][0]["titre"]["ar"] == "منشور" and data["actualites"][0]["date"] == "2026-05-03"
    raw = r.text
    for leak in ("secret@lecim.ci", "+225 00 00 00 00", "Adresse privée", "Brouillon", "Secret"):
        assert leak not in raw, leak


def test_root_redirects_to_external_site_when_configured(monkeypatch, anon):
    assert anon.get("/").status_code == 200                                     # sans vitrine externe : page locale
    monkeypatch.setattr(settings, "vitrine_url", "https://psie.example.org")
    r = anon.get("/")
    assert r.status_code == 302 and r.headers["location"] == "https://psie.example.org"
    assert anon.get("/adhesion").status_code == 200                              # l'application garde ses pages


def test_cors_allows_only_configured_origin_and_never_credentials(monkeypatch):
    monkeypatch.setattr(settings, "vitrine_origins", "https://site.example.org, https://autre.example.org/")
    import app.main as main
    reloaded = importlib.reload(main)
    try:
        client = TestClient(reloaded.app)
        ok = client.get("/api/public/vitrine.json", headers={"Origin": "https://site.example.org"})
        assert ok.headers["access-control-allow-origin"] == "https://site.example.org"
        assert "access-control-allow-credentials" not in ok.headers
        other = client.get("/api/public/vitrine.json", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in other.headers
        pre = client.options("/api/public/vitrine.json", headers={
            "Origin": "https://site.example.org", "Access-Control-Request-Method": "POST"})
        assert pre.status_code == 400                                            # POST interdit depuis l'extérieur
    finally:
        monkeypatch.setattr(settings, "vitrine_origins", "")
        importlib.reload(main)


def test_cross_origin_post_still_blocked_by_csrf_guard(anon):
    r = anon.post("/login", data={"email": "a@b.c", "password": "x"}, headers={"Origin": "https://site.example.org"})
    assert r.status_code == 403


def test_production_requires_https_for_vitrine():
    good = dict(cookie_secure=True, secret_key="x" * 40, debug=False, two_factor_enabled=True,
                smtp_host="smtp.example.org", public_base_url="https://app.example.org")
    assert production_problems(Settings(**good, vitrine_url="https://psie.example.org",
                                        vitrine_origins="https://psie.example.org")) == []
    assert any("VITRINE" in p for p in production_problems(Settings(**good, vitrine_url="http://psie.example.org")))
    assert any("VITRINE" in p for p in production_problems(Settings(**good, vitrine_origins="http://x.org")))
