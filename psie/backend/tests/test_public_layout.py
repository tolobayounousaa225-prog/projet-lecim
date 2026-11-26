"""Les pages ouvertes aux visiteurs (dépôt de demande, suivi, vérification, erreurs) n'affichent que leur contenu :
pas de faux menu « À propos / Membres / Actualités » : le site public, c'est la vitrine."""
import pytest

from app.config import settings

MENU = ('class="topbar"', 'href="/apropos"', 'href="/membres"', 'href="/actualites"')


@pytest.fixture
def vitrine(monkeypatch):
    monkeypatch.setattr(settings, "vitrine_url", "https://vitrine.example.org/PSIE/")


@pytest.mark.parametrize("url", ["/adhesion", "/adhesion/suivi", "/page-inexistante"])
def test_visitor_pages_show_only_their_content_and_a_way_back(anon, vitrine, url):
    page = anon.get(url, headers={"accept": "text/html"}).text
    for fragment in MENU:
        assert fragment not in page, (url, fragment)
    assert 'href="https://vitrine.example.org/PSIE/"' in page            # retour au site vitrine
    assert 'href="/lang/ar"' in page                                     # le choix de langue reste disponible


def test_application_form_is_the_wide_focused_variant(anon, vitrine):
    page = anon.get("/adhesion").text
    assert 'class="bare wide"' in page and 'name="statuts_file"' in page and 'name="nom"' in page


def test_no_back_link_when_there_is_no_vitrine(anon):
    assert "vitrine.example.org" not in anon.get("/adhesion").text


@pytest.mark.parametrize("path,target", [("/apropos", "apropos.html"), ("/membres", "membres.html"), ("/actualites", "actualites.html"),
                                         ("/actualites/7", "actualite.html?id=7")])
def test_duplicated_public_pages_send_visitors_to_the_vitrine(anon, vitrine, path, target):
    r = anon.get(path)
    assert r.status_code == 302 and r.headers["location"] == f"https://vitrine.example.org/PSIE/{target}"


def test_the_legacy_news_menu_entry_is_gone_but_content_editing_stays(db):
    from .conftest import client_for, make_user
    make_user(db, "com@psie.ci", "communication")
    menu = client_for("com@psie.ci").get("/admin").text
    assert "/gestion/contenu" in menu and 'href="/gestion/actualites"' not in menu
