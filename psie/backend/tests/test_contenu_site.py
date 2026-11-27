import io
import json

import pytest
from PIL import Image

from app import models, publish
from app import site_content as sc
from app.config import settings

from .conftest import client_for, make_faitiere, make_user


@pytest.fixture
def editor(db):
    make_user(db, "com@psie.ci", "communication")
    return client_for("com@psie.ci")


def png(size=(40, 30), color=(10, 120, 60)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


def jpeg_with_gps() -> bytes:
    img = Image.new("RGB", (60, 40), (200, 30, 30))
    exif = Image.Exif()
    exif[0x010F] = "MarqueSecrete"                  # fabricant de l'appareil
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif)
    return out.getvalue()


def news_form(**over):
    data = {"date": "2026-03-04", "titre__fr": "Assemblée générale annuelle", "titre__ar": "",
            "resume__fr": "Résumé", "resume__ar": "", "contenu__fr": "Ligne 1\nLigne 2", "contenu__ar": "", "slug": ""}
    data.update(over)
    return data


# ---------------------------------------------------------------- droits d'accès

def test_only_communication_and_admin_can_edit_site_content(db, anon):
    for role in ("secretaire", "den", "finances", "commissaire"):
        make_user(db, f"{role}@psie.ci", role)
        assert client_for(f"{role}@psie.ci").get("/gestion/contenu").status_code == 403, role
    f = make_faitiere(db, "LECIM")
    make_user(db, "rep@psie.ci", "faitiere", faitiere_id=f.id)
    assert client_for("rep@psie.ci").get("/gestion/contenu").status_code == 403
    assert anon.get("/gestion/contenu").status_code == 303                      # renvoyé vers la connexion
    for role in ("communication", "admin"):
        make_user(db, f"{role}@psie.ci", role)
        assert client_for(f"{role}@psie.ci").get("/gestion/contenu").status_code == 200, role


def test_communication_role_has_a_label_and_requires_two_factor(db):
    user = make_user(db, "com@psie.ci", "communication")
    assert user.role_label == "Secrétariat Information et Communication"
    assert user.requires_two_factor and user.is_internal and not user.is_admin
    assert not user.can_manage_members and not user.can_view_finances      # aucun autre pouvoir


def test_editor_cannot_reach_other_areas(db, editor):
    for url in ("/users", "/audit", "/finances"):
        assert editor.get(url).status_code in (403, 303), url


# ---------------------------------------------------------------- création et validation

def test_create_news_generates_unique_slug_and_publishes(db, editor, monkeypatch):
    calls = []
    monkeypatch.setattr(publish, "trigger_rebuild", lambda: calls.append(1))
    for _ in range(2):
        r = editor.post("/gestion/contenu/actualites/nouveau", data=news_form())
        assert r.status_code == 303, r.text
    slugs = sorted(row.cle for row in db.query(models.ContenuSite).filter_by(collection="actualites"))
    assert slugs == ["assemblee-generale-annuelle", "assemblee-generale-annuelle-2"]
    assert len(calls) == 2                                                      # reconstruction demandée à chaque enregistrement
    audit = db.query(models.AuditLog).filter(models.AuditLog.entity == "contenu:actualites").count()
    assert audit == 2


def test_explicit_slug_must_be_valid_and_unique(db, editor):
    assert editor.post("/gestion/contenu/actualites/nouveau", data=news_form(slug="ag-2026")).status_code == 303
    again = editor.post("/gestion/contenu/actualites/nouveau", data=news_form(slug="ag-2026"))
    assert again.status_code == 400 and "déjà utilisée" in again.text
    bad = editor.post("/gestion/contenu/actualites/nouveau", data=news_form(slug="Pas Valide!"))
    assert bad.status_code == 400 and "minuscules" in bad.text


@pytest.mark.parametrize("collection,form,message", [
    ("actualites", news_form(date="12/03/2026"), "date invalide"),
    ("actualites", news_form(date="2026-02-31"), "date invalide"),
    ("actualites", news_form(**{"titre__fr": "", "titre__ar": ""}), "au moins le français"),
    ("annonce", {"actif": "on", "texte__fr": "x", "texte__ar": "", "lien": "http://pas-https.org"}, "https://"),
    ("contact", {"whatsapp": "0707", "message__fr": "Bonjour", "message__ar": "", "message_partenariat__fr": "",
                 "message_partenariat__ar": ""}, "indicatif"),
    ("contact", {"whatsapp": "22507070707", "message__fr": "", "message__ar": "", "message_partenariat__fr": "",
                 "message_partenariat__ar": ""}, "message pré-rempli"),
    ("regions", {"drena": "Abidjan 1", "region": "Abidjan", "lat": "5.3", "lon": ""}, "latitude ET la longitude"),
    ("regions", {"drena": "Paris", "region": "IDF", "lat": "48.8", "lon": "2.3"}, "hors de la Côte d"),
    ("equipe", {"nom": "A B", "organe": "xx", "fonction__fr": "", "fonction__ar": ""}, "choix invalide"),
    ("partenaires", {"nom": "UNICEF", "type": "etat", "site_web": "javascript:alert(1)", "description__fr": "",
                     "description__ar": ""}, "adresse de site invalide"),
])
def test_invalid_content_is_refused_with_a_clear_message(editor, db, collection, form, message):
    url = f"/gestion/contenu/{collection}/" + ("unique" if collection in ("annonce", "contact") else "nouveau")
    r = editor.post(url, data=form)
    assert r.status_code == 400 and message in r.text
    assert db.query(models.ContenuSite).count() == 0                            # rien n'est enregistré


def test_form_keeps_what_was_typed_when_there_is_an_error(editor):
    r = editor.post("/gestion/contenu/actualites/nouveau", data=news_form(date="n'importe quoi", **{"titre__fr": "Mon titre"}))
    assert r.status_code == 400 and 'value="Mon titre"' in r.text


def test_html_is_escaped_everywhere(editor, db):
    editor.post("/gestion/contenu/actualites/nouveau", data=news_form(**{"titre__fr": "<script>alert(1)</script>"}))
    page = editor.get("/gestion/contenu/actualites")
    assert "<script>alert(1)</script>" not in page.text and "&lt;script&gt;" in page.text


# ---------------------------------------------------------------- contenus uniques, ordre, suppression

def test_single_items_are_saved_in_place(db, editor):
    data = {"actif": "on", "texte__fr": "Assemblée le 12", "texte__ar": "", "lien": "https://exemple.org/ag"}
    assert editor.post("/gestion/contenu/annonce/unique", data=data).status_code == 303
    assert editor.post("/gestion/contenu/annonce/unique", data={**data, "texte__fr": "Modifié"}).status_code == 303
    rows = db.query(models.ContenuSite).filter_by(collection="annonce").all()
    assert len(rows) == 1 and rows[0].cle == "main" and json.loads(rows[0].data)["texte"]["fr"] == "Modifié"
    assert "Modifié" in editor.get("/gestion/contenu/annonce").text
    assert editor.get("/gestion/contenu/annonce/nouveau").status_code == 303


def test_order_can_be_changed_and_items_deleted(db, editor):
    for name in ("Alpha", "Bravo", "Charlie"):
        editor.post("/gestion/contenu/partenaires/nouveau", data={"nom": name, "type": "etat", "site_web": "",
                                                                  "description__fr": "", "description__ar": ""})

    def names():
        return [json.loads(r.data)["nom"] for r in db.query(models.ContenuSite).filter_by(collection="partenaires")
                .order_by(models.ContenuSite.position)]

    db.expire_all()
    ids = {json.loads(r.data)["nom"]: r.id for r in db.query(models.ContenuSite).filter_by(collection="partenaires")}
    assert editor.post(f"/gestion/contenu/partenaires/{ids['Charlie']}/haut").status_code == 303
    db.expire_all()
    assert names() == ["Alpha", "Charlie", "Bravo"]
    editor.post(f"/gestion/contenu/partenaires/{ids['Alpha']}/haut")              # déjà premier : sans effet
    editor.post(f"/gestion/contenu/partenaires/{ids['Alpha']}/bas")
    db.expire_all()
    assert names() == ["Charlie", "Alpha", "Bravo"]
    editor.post(f"/gestion/contenu/partenaires/{ids['Bravo']}/supprimer")
    db.expire_all()
    assert names() == ["Charlie", "Alpha"]
    assert editor.post(f"/gestion/contenu/partenaires/{ids['Alpha']}/diagonale").status_code == 404


def test_an_item_cannot_be_reached_through_another_collection(db, editor):
    editor.post("/gestion/contenu/partenaires/nouveau", data={"nom": "X", "type": "etat", "site_web": "",
                                                              "description__fr": "", "description__ar": ""})
    item = db.query(models.ContenuSite).one()
    assert editor.get(f"/gestion/contenu/equipe/{item.id}/modifier").status_code == 404
    assert editor.post(f"/gestion/contenu/equipe/{item.id}/supprimer").status_code == 404
    assert editor.get("/gestion/contenu/inconnu").status_code == 404


# ---------------------------------------------------------------- fichiers

def upload(editor, name, content, ctype, **fields):
    return editor.post("/gestion/contenu/president/unique", data={
        "nom": "Président", "fonction__fr": "", "fonction__ar": "", "message__fr": "", "message__ar": "", **fields},
        files={"photo__file": (name, content, ctype)})


def test_image_upload_is_reencoded_without_metadata(db, editor):
    raw = jpeg_with_gps()
    assert b"MarqueSecrete" in raw
    assert upload(editor, "../../etc/passwd.jpg", raw, "image/jpeg").status_code == 303
    m = db.query(models.MediaSite).one()
    assert b"MarqueSecrete" not in m.contenu and m.extension == "jpg" and "/" not in m.nom and ".." not in m.nom
    assert Image.open(io.BytesIO(m.contenu)).size == (60, 40)


def test_big_images_are_reduced(db, editor):
    assert upload(editor, "grande.png", png((3000, 2000)), "image/png").status_code == 303
    assert max(Image.open(io.BytesIO(db.query(models.MediaSite).one().contenu)).size) == 2400


@pytest.mark.parametrize("name,content,ctype", [
    ("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/svg+xml"),
    ("faux.png", b"<html><script>alert(1)</script></html>", "image/png"),
    ("vide.png", b"", "image/png"),
    ("doc.pdf", b"%PDF-1.4 pas une image", "image/png"),
    ("gif.gif", (lambda o: (Image.new("RGB", (5, 5)).save(o, "GIF"), o.getvalue())[1])(io.BytesIO()), "image/gif"),
])
def test_dangerous_or_wrong_files_are_refused(db, editor, name, content, ctype):
    r = upload(editor, name, content, ctype)
    assert r.status_code == 400 and db.query(models.MediaSite).count() == 0


def test_a_failed_save_does_not_keep_the_uploaded_file(db, editor):
    r = editor.post("/gestion/contenu/equipe/nouveau", data={"nom": "", "organe": "den", "fonction__fr": "",
                                                              "fonction__ar": "", "organisation": ""},
                    files={"photo__file": ("p.png", png(), "image/png")})
    assert r.status_code == 400 and db.query(models.MediaSite).count() == 0


def test_pdf_fields_accept_pdf_only(db, editor):
    base = {"titre__fr": "Statuts", "titre__ar": "", "description__fr": "", "description__ar": "", "categorie": ""}
    bad = editor.post("/gestion/contenu/documents/nouveau", data=base, files={"fichier__file": ("s.pdf", b"MZ pas un pdf", "application/pdf")})
    assert bad.status_code == 400 and "PDF valide" in bad.text
    img = editor.post("/gestion/contenu/documents/nouveau", data=base, files={"fichier__file": ("s.png", png(), "image/png")})
    assert img.status_code == 400
    ok = editor.post("/gestion/contenu/documents/nouveau", data=base,
                     files={"fichier__file": ("s.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")})
    assert ok.status_code == 303 and db.query(models.MediaSite).one().extension == "pdf"
    required = editor.post("/gestion/contenu/documents/nouveau", data=base)
    assert required.status_code == 400 and "obligatoire" in required.text


def test_same_file_is_stored_once_and_can_be_kept_or_removed(db, editor):
    for _ in range(2):
        upload(editor, "a.png", png(), "image/png")
    assert db.query(models.MediaSite).count() == 1
    m = db.query(models.MediaSite).one()
    keep = editor.post("/gestion/contenu/president/unique", data={"nom": "Nouveau nom", "fonction__fr": "", "fonction__ar": "",
                                                                  "message__fr": "", "message__ar": "", "photo__id": str(m.id)})
    assert keep.status_code == 303
    assert json.loads(db.query(models.ContenuSite).one().data)["photo"] == m.id
    editor.post("/gestion/contenu/president/unique", data={"nom": "N", "fonction__fr": "", "fonction__ar": "", "message__fr": "",
                                                           "message__ar": "", "photo__id": str(m.id), "photo__clear": "1"})
    db.expire_all()
    assert json.loads(db.query(models.ContenuSite).one().data)["photo"] is None


def test_media_is_served_with_safe_headers(db, editor, anon):
    upload(editor, "p.png", png(), "image/png")
    m = db.query(models.MediaSite).one()
    r = anon.get(f"/medias/{m.id}.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff" and "immutable" in r.headers["cache-control"]
    assert anon.get(f"/medias/{m.id}.png", headers={"if-none-match": r.headers["etag"]}).status_code == 304
    assert anon.get(f"/medias/{m.id}.pdf").status_code == 404 and anon.get("/medias/abc.png").status_code == 404
    assert anon.get("/medias/9999.png").status_code == 404


# ---------------------------------------------------------------- export public

def test_export_has_the_site_data_shape_and_lists_files(db, editor, anon):
    upload(editor, "p.png", png(), "image/png", nom="Dr Président")
    editor.post("/gestion/contenu/actualites/nouveau", data=news_form(date="2026-01-10", slug="ancienne"))
    editor.post("/gestion/contenu/actualites/nouveau", data=news_form(date="2026-06-10", slug="recente"))
    editor.post("/gestion/contenu/annonce/unique", data={"actif": "on", "texte__fr": "Bonjour", "texte__ar": "مرحبا", "lien": ""})
    editor.post("/gestion/contenu/contact/unique", data={"whatsapp": "+225 07 07 07 07 07", "message__fr": "Salut", "message__ar": "",
                                                         "message_partenariat__fr": "", "message_partenariat__ar": "",
                                                         "facebook": "https://facebook.com/psie", "youtube": "", "instagram": ""})
    r = anon.get("/api/public/site.json")
    assert r.status_code == 200 and "max-age=60" in r.headers["cache-control"]
    d = r.json()
    assert [n["slug"] for n in d["actualites"]] == ["recente", "ancienne"]       # plus récentes d'abord
    assert d["actualites"][0]["titre"] == {"fr": "Assemblée générale annuelle", "ar": ""}
    assert d["annonce"] == {"actif": True, "fr": "Bonjour", "ar": "مرحبا", "lien": ""}
    assert d["contact"]["whatsapp"] == "2250707070707" and "message_partenariat" not in d["contact"]
    media_id = db.query(models.MediaSite).one().id
    assert d["president"]["nom"] == "Dr Président" and d["president"]["photo"] == f"assets/media/{media_id}.png"
    assert d["media"] == [{"path": f"assets/media/{media_id}.png", "url": f"/medias/{media_id}.png",
                           "sha256": d["media"][0]["sha256"], "taille": d["media"][0]["taille"]}]
    for name in ("documents", "galerie", "regions", "faitieres", "equipe", "partenaires", "transparence"):
        assert d[name] == []
    assert len(d["version"]) == 16


def test_export_version_changes_only_when_content_changes(db, editor, anon):
    editor.post("/gestion/contenu/annonce/unique", data={"actif": "on", "texte__fr": "A", "texte__ar": "", "lien": ""})
    first = anon.get("/api/public/site.json").json()["version"]
    assert anon.get("/api/public/site.json").json()["version"] == first
    editor.post("/gestion/contenu/annonce/unique", data={"actif": "on", "texte__fr": "B", "texte__ar": "", "lien": ""})
    assert anon.get("/api/public/site.json").json()["version"] != first


def test_export_never_leaks_internal_data(db, editor, anon):
    lecim = make_faitiere(db, "LECIM")
    lecim.email = "prive@lecim.ci"
    db.commit()
    editor.post("/gestion/contenu/annonce/unique", data={"actif": "on", "texte__fr": "A", "texte__ar": "", "lien": ""})
    raw = anon.get("/api/public/site.json").text
    for secret in ("prive@lecim.ci", "com@psie.ci", "hashed_password", "updated_by"):
        assert secret not in raw


# ---------------------------------------------------------------- reconstruction du site

def test_rebuild_is_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "github_dispatch_repo", "")
    monkeypatch.setattr(settings, "github_dispatch_token", "")
    assert not publish.rebuild_configured() and publish.trigger_rebuild() is False


def test_rebuild_calls_github_with_a_minimal_request(monkeypatch):
    monkeypatch.setattr(settings, "github_dispatch_repo", "org/PSIE")
    monkeypatch.setattr(settings, "github_dispatch_token", "ghp_test")
    sent = {}

    class Response:
        status = 204
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(request, timeout):
        sent.update(url=request.full_url, body=json.loads(request.data), auth=request.get_header("Authorization"), timeout=timeout)
        return Response()

    monkeypatch.setattr(publish.urllib.request, "urlopen", fake_urlopen)
    assert publish.trigger_rebuild() is True
    assert sent == {"url": "https://api.github.com/repos/org/PSIE/dispatches", "body": {"event_type": "contenu-modifie"},
                    "auth": "Bearer ghp_test", "timeout": 15}


def test_rebuild_failure_never_blocks_saving(db, editor, monkeypatch):
    import urllib.error
    monkeypatch.setattr(settings, "github_dispatch_repo", "org/PSIE")
    monkeypatch.setattr(settings, "github_dispatch_token", "ghp_test")

    def boom(request, timeout):
        raise urllib.error.URLError("pas de réseau")

    monkeypatch.setattr(publish.urllib.request, "urlopen", boom)
    assert editor.post("/gestion/contenu/actualites/nouveau", data=news_form()).status_code == 303
    assert db.query(models.ContenuSite).count() == 1


def test_a_malformed_repository_name_disables_rebuild(monkeypatch):
    monkeypatch.setattr(settings, "github_dispatch_repo", "https://evil.example/x")
    monkeypatch.setattr(settings, "github_dispatch_token", "ghp_test")
    assert not publish.rebuild_configured()


@pytest.mark.parametrize("role,label", [
    ("communication", "Secrétariat Information et Communication"), ("formation", "Secrétariat Formation"),
    ("examens", "Secrétariat Examens"), ("ressources", "Secrétariat Mobilisation des ressources"),
])
def test_each_secretariat_has_its_own_account_and_space(db, role, label):
    user = make_user(db, f"{role}@psie.ci", role)
    assert user.role_label == label and user.is_internal
    client = client_for(f"{role}@psie.ci")
    assert client.get("/admin").status_code == 200                             # tableau de bord de la PSIE
    assert client.get("/faitieres").status_code == 403                         # rubrique « membres » hors de leur secrétariat
    assert client.get("/documents").status_code == 200
    assert client.get("/finances").status_code == 403                          # pas d'accès aux finances
    assert client.get("/users").status_code == 403                             # ni à l'administration des comptes
    assert (client.get("/gestion/contenu").status_code == 200) == (role == "communication")


def test_admin_can_create_an_account_for_each_secretariat(db):
    make_user(db, "admin@psie.ci", "admin")
    admin = client_for("admin@psie.ci")
    for role in ("communication", "formation", "examens", "ressources"):
        r = admin.post("/users", data={"email": f"{role}@psie.ci", "full_name": f"Resp {role}", "role": role,
                                       "password": "Motdepasse1"})
        assert r.status_code == 303, (role, r.text)
        assert db.query(models.User).filter_by(email=f"{role}@psie.ci").one().role == role


def test_a_removed_photo_is_deleted_from_the_database_and_no_longer_downloadable(db, editor, anon, monkeypatch):
    """Une photo supprimée ne doit rester ni publiée ni téléchargeable à son ancienne adresse."""
    monkeypatch.setattr(sc, "MEDIA_GRACE_SECONDS", 0)
    upload(editor, "a.png", png(), "image/png")
    m = db.query(models.MediaSite).one()
    url = f"/medias/{m.id}.{m.extension}"
    assert anon.get(url).status_code == 200
    editor.post("/gestion/contenu/president/unique", data={"nom": "N", "fonction__fr": "", "fonction__ar": "", "message__fr": "",
                                                           "message__ar": "", "photo__id": str(m.id), "photo__clear": "1"})
    db.expire_all()
    assert db.query(models.MediaSite).count() == 0
    assert anon.get(url).status_code == 404


def test_a_file_still_in_use_or_just_uploaded_is_never_purged(db, editor, monkeypatch):
    upload(editor, "a.png", png(), "image/png")                      # utilisé par le président
    monkeypatch.setattr(sc, "MEDIA_GRACE_SECONDS", 0)
    editor.post("/gestion/contenu/president/unique", data={"nom": "Autre", "fonction__fr": "", "fonction__ar": "", "message__fr": "",
                                                           "message__ar": "", "photo__id": str(db.query(models.MediaSite).one().id)})
    assert db.query(models.MediaSite).count() == 1                    # toujours référencé : conservé
    monkeypatch.setattr(sc, "MEDIA_GRACE_SECONDS", 3600)
    upload(editor, "b.png", png(color=(1, 2, 3)), "image/png")        # remplace la photo, mais l'ancienne est trop récente
    assert db.query(models.MediaSite).count() == 2


# ---------------------------------------------------------------- Pages et textes

def test_page_texts_are_prefilled_saved_and_exported(db, editor, monkeypatch):
    monkeypatch.setattr(publish, "trigger_rebuild", lambda: None)
    index = editor.get("/gestion/contenu")
    assert index.status_code == 200 and "Pages et textes" in index.text and "txt_accueil" in index.text
    page = editor.get("/gestion/contenu/txt_accueil")                          # première ouverture : textes d'origine déjà dans le formulaire
    assert page.status_code == 200 and "Ensemble pour une éducation islamique" in page.text
    assert sc.export_site(db)["textes"]["txt_accueil"] == {}                   # tant qu'on n'enregistre pas : rien n'est exporté
    values = sc.flatten(sc.COLLECTIONS["txt_accueil"], sc.default_values(sc.COLLECTIONS["txt_accueil"]))
    values["hero_title_a__fr"] = "Un titre corrigé"
    assert editor.post("/gestion/contenu/txt_accueil/unique", data=values).status_code in (200, 303)
    assert sc.export_site(db)["textes"]["txt_accueil"]["hero_title_a"]["fr"] == "Un titre corrigé"
    assert sc.export_site(db)["version"]


def test_text_lists_import_the_current_texts_then_can_be_edited(db, editor, monkeypatch):
    monkeypatch.setattr(publish, "trigger_rebuild", lambda: None)
    assert "Importer les textes actuels" in editor.get("/gestion/contenu/faq").text
    assert editor.post("/gestion/contenu/faq/importer").status_code in (200, 303)
    faq = sc.export_site(db)["textes"]["faq"]
    assert len(faq) >= 5 and faq[0]["q"]["fr"] and faq[0]["q"]["ar"]
    assert "Importer les textes actuels" not in editor.get("/gestion/contenu/faq").text
    assert editor.post("/gestion/contenu/faq/importer").status_code == 404      # on n'importe qu'une fois
    r = editor.post("/gestion/contenu/faq/nouveau", data={"q__fr": "Nouvelle ?", "q__ar": "", "a__fr": "Oui.", "a__ar": ""})
    assert r.status_code in (200, 303)
    assert sc.export_site(db)["textes"]["faq"][-1]["q"]["fr"] == "Nouvelle ?"


def test_every_default_text_matches_its_collection(db):
    from app import site_texts as st
    for key, (_t, _a, fields) in st.BLOCS.items():
        assert set(st.defaults()[key]) == {n for n, *_ in fields}, key
    for key, (_t, _a, _tk, fields, _ti) in st.LISTES.items():
        assert st.defaults()[key] and all(set(row) == {n for n, *_ in fields} for row in st.defaults()[key]), key
