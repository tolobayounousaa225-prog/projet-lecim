"""Module « membres, mandats et comptes » : pièces justificatives, registre légal, historique des mandats, comptes."""
import datetime
import io
import re

import pytest
from PIL import Image

from app import models
from app.security import verify_password

from .conftest import PASSWORD, client_for, make_faitiere, make_user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (30, 20), (20, 120, 60)).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def setup(db):
    a, b = make_faitiere(db, "LECIM", "fondateur"), make_faitiere(db, "IQRA", "fondateur")
    make_user(db, "den@psie.ci", "den")
    make_user(db, "sec@psie.ci", "secretaire")
    make_user(db, "exam@psie.ci", "examens")
    make_user(db, "rep-a@psie.ci", "faitiere", faitiere_id=a.id)
    make_user(db, "rep-b@psie.ci", "faitiere", faitiere_id=b.id)
    make_user(db, "admin@psie.ci", "admin")
    return a, b


def upload(client, f, kind="statuts", name="statuts.pdf", content=PDF, ctype="application/pdf"):
    return client.post(f"/faitieres/{f.id}/pieces", data={"type": kind}, files={"fichier": (name, content, ctype)})


# ---------------------------------------------------------------- pièces justificatives

def test_den_and_secretariat_attach_and_remove_supporting_documents(db, setup):
    a, _ = setup
    for who in ("den@psie.ci", "sec@psie.ci"):
        assert upload(client_for(who), a).status_code == 303, who
    page = client_for("den@psie.ci").get(f"/faitieres/{a.id}").text
    assert "Pièces justificatives" in page and "Statuts de l&#39;organisation" in page and "statuts.pdf" in page
    piece = db.query(models.PieceFaitiere).first()
    assert client_for("den@psie.ci").post(f"/pieces/{piece.id}/supprimer").status_code == 303
    assert db.query(models.PieceFaitiere).count() == 1
    assert db.query(models.AuditLog).filter_by(entity="piece").count() == 3                # 2 ajouts + 1 suppression


def test_images_are_accepted_and_cleaned(db, setup):
    a, _ = setup
    raw = png()
    assert upload(client_for("den@psie.ci"), a, "recepisse", "scan.png", raw, "image/png").status_code == 303
    piece = db.query(models.PieceFaitiere).one()
    assert piece.extension == "png" and Image.open(io.BytesIO(piece.contenu)).size == (30, 20)


@pytest.mark.parametrize("kind,name,content,ctype", [
    ("inconnu", "a.pdf", PDF, "application/pdf"),
    ("statuts", "faux.pdf", b"MZ ce n'est pas un pdf", "application/pdf"),
    ("statuts", "x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/svg+xml"),
    ("statuts", "vide.pdf", b"", "application/pdf"),
])
def test_bad_supporting_documents_are_refused(db, setup, kind, name, content, ctype):
    a, _ = setup
    assert upload(client_for("den@psie.ci"), a, kind, name, content, ctype).status_code == 400
    assert db.query(models.PieceFaitiere).count() == 0


def test_only_managers_can_add_or_delete_pieces(db, setup):
    a, _ = setup
    assert upload(client_for("exam@psie.ci"), a).status_code == 403
    assert upload(client_for("rep-a@psie.ci"), a).status_code == 403                       # pas même sa propre faîtière
    upload(client_for("den@psie.ci"), a)
    piece = db.query(models.PieceFaitiere).one()
    assert client_for("rep-a@psie.ci").post(f"/pieces/{piece.id}/supprimer").status_code == 403
    assert db.query(models.PieceFaitiere).count() == 1


def test_documents_are_cloistered_by_federation(db, setup, anon):
    a, _ = setup
    upload(client_for("den@psie.ci"), a)
    piece = db.query(models.PieceFaitiere).one()
    own = client_for("rep-a@psie.ci").get(f"/pieces/{piece.id}")
    assert own.status_code == 200 and own.content == PDF and "attachment" in own.headers["content-disposition"]
    assert own.headers["cache-control"] == "private, no-store"
    assert client_for("exam@psie.ci").get(f"/pieces/{piece.id}").status_code == 200        # organes de la PSIE
    assert client_for("rep-b@psie.ci").get(f"/pieces/{piece.id}").status_code == 404       # autre faîtière
    assert anon.get(f"/pieces/{piece.id}").status_code == 303
    assert client_for("den@psie.ci").get("/pieces/9999").status_code == 404


def test_pieces_follow_their_federation_when_it_is_deleted(db, setup):
    a, _ = setup
    upload(client_for("den@psie.ci"), a)
    assert db.query(models.PieceFaitiere).filter_by(faitiere_id=a.id).count() == 1


# ---------------------------------------------------------------- registre des membres

def test_member_register_pdf_for_the_bodies_of_the_psie(db, setup):
    a, _ = setup
    db.add(models.Mandat(faitiere_id=a.id, organe="AG", full_name="Koné Ali", date_debut=datetime.date.today(),
                         date_fin=datetime.date.today() + datetime.timedelta(days=900)))
    db.add(models.Mandat(faitiere_id=a.id, organe="AG", full_name="Ancien Délégué", date_debut=datetime.date(2015, 1, 1),
                         date_fin=datetime.date(2018, 1, 1)))
    db.commit()
    for who in ("den@psie.ci", "exam@psie.ci", "sec@psie.ci"):
        r = client_for(who).get("/registre-membres.pdf")
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF-"), who
    assert client_for("rep-a@psie.ci").get("/registre-membres.pdf").status_code == 403
    assert db.query(models.AuditLog).filter_by(entity="registre_membres").count() == 3


def test_register_lists_members_and_only_current_representatives(db, setup, tmp_path):
    import shutil
    import subprocess
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext absent")
    a, _ = setup
    db.add(models.Mandat(faitiere_id=a.id, organe="AG", full_name="Koné Ali", date_debut=datetime.date.today(),
                         date_fin=datetime.date.today() + datetime.timedelta(days=900)))
    db.add(models.Mandat(faitiere_id=a.id, organe="AG", full_name="Ancien Délégué", date_fin=datetime.date(2018, 1, 1)))
    db.commit()
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(client_for("den@psie.ci").get("/registre-membres.pdf").content)
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    assert "REGISTRE DES MEMBRES" in text and "LECIM" in text and "IQRA" in text and "Koné Ali" in text
    assert "Ancien Délégué" not in text


# ---------------------------------------------------------------- mandats

def mandat(db, f, **kw):
    m = models.Mandat(faitiere_id=f.id, organe="AG", full_name="Koné Ali", date_debut=datetime.date(2024, 1, 1),
                      date_fin=datetime.date.today() + datetime.timedelta(days=400), **kw)
    db.add(m)
    db.commit()
    return m


def test_ending_a_mandate_keeps_its_history(db, setup):
    a, _ = setup
    m = mandat(db, a)
    r = client_for("den@psie.ci").post(f"/mandats/{m.id}/terminer", data={"date_fin": "2026-01-31", "next": f"/faitieres/{a.id}"})
    assert r.status_code == 303 and r.headers["location"] == f"/faitieres/{a.id}"
    db.expire_all()
    assert db.get(models.Mandat, m.id).date_fin == datetime.date(2026, 1, 31)
    page = client_for("den@psie.ci").get(f"/faitieres/{a.id}").text
    assert "Historique des mandats terminés" in page and "Koné Ali" in page
    assert db.query(models.AuditLog).filter_by(action="fin_mandat").count() == 1


def test_ending_a_mandate_defaults_to_today_and_refuses_a_date_before_the_start(db, setup):
    a, _ = setup
    m = mandat(db, a)
    c = client_for("den@psie.ci")
    assert c.post(f"/mandats/{m.id}/terminer", data={"date_fin": "2020-01-01"}).status_code == 400
    assert c.post(f"/mandats/{m.id}/terminer", data={}).status_code == 303
    db.expire_all()
    assert db.get(models.Mandat, m.id).date_fin == datetime.date.today()
    assert c.post("/mandats/9999/terminer", data={}).status_code == 404


def test_mandate_can_be_corrected(db, setup):
    a, b = setup
    m = mandat(db, a)
    c = client_for("sec@psie.ci")
    assert "Koné Ali" in c.get(f"/mandats/{m.id}/edit").text
    r = c.post(f"/mandats/{m.id}/edit", data={"full_name": "Koné Aly", "organe": "AG", "fonction": "Délégué",
                                              "faitiere_id": str(b.id), "date_debut": "2024-01-01", "date_fin": "2027-01-01",
                                              "email": "k@x.org", "telephone": "0707"})
    assert r.status_code == 303 and r.headers["location"] == f"/faitieres/{b.id}"
    db.expire_all()
    got = db.get(models.Mandat, m.id)
    assert (got.full_name, got.faitiere_id, got.fonction, got.email) == ("Koné Aly", b.id, "Délégué", "k@x.org")
    assert c.post(f"/mandats/{m.id}/edit", data={"full_name": "", "organe": "AG"}).status_code in (400, 422)
    assert c.post(f"/mandats/{m.id}/edit", data={"full_name": "X", "organe": "AG", "date_debut": "2026-01-01",
                                                 "date_fin": "2025-01-01"}).status_code == 400


def test_other_roles_cannot_change_mandates(db, setup):
    a, _ = setup
    m = mandat(db, a)
    for who in ("exam@psie.ci", "rep-a@psie.ci"):
        c = client_for(who)
        assert c.post(f"/mandats/{m.id}/terminer", data={}).status_code == 403
        assert c.get(f"/mandats/{m.id}/edit").status_code == 403
        assert c.post(f"/mandats/{m.id}/edit", data={"full_name": "X", "organe": "AG"}).status_code == 403


def test_deleting_a_mandate_still_works_for_mistakes(db, setup):
    a, _ = setup
    m = mandat(db, a)
    assert client_for("den@psie.ci").post(f"/mandats/{m.id}/delete", data={}).status_code == 303
    assert db.query(models.Mandat).count() == 0


# ---------------------------------------------------------------- comptes

def test_admin_edits_a_name_and_email(db, setup):
    c = client_for("admin@psie.ci")
    target = db.query(models.User).filter_by(email="exam@psie.ci").one()
    assert "exam@psie.ci" in c.get(f"/users/{target.id}/edit").text
    assert c.post(f"/users/{target.id}/edit", data={"full_name": "Chef Examens", "email": " EXAM2@psie.ci "}).status_code == 303
    db.expire_all()
    got = db.get(models.User, target.id)
    assert (got.full_name, got.email) == ("Chef Examens", "exam2@psie.ci")
    assert c.post(f"/users/{target.id}/edit", data={"full_name": "X", "email": "den@psie.ci"}).status_code == 409
    assert c.post(f"/users/{target.id}/edit", data={"full_name": "X", "email": "pas un mail"}).status_code == 400
    assert c.post(f"/users/{target.id}/edit", data={"full_name": " ", "email": "a@b.ci"}).status_code == 400
    assert client_for("den@psie.ci").get(f"/users/{target.id}/edit").status_code == 403


def test_admin_sends_a_reset_link_instead_of_choosing_the_password(db, setup, monkeypatch, anon):
    sent = []
    monkeypatch.setattr("app.routers.membres.send_email", lambda to, subject, body: sent.append((to, body)) or True)
    target = db.query(models.User).filter_by(email="exam@psie.ci").one()
    c = client_for("admin@psie.ci")
    assert c.post(f"/users/{target.id}/lien-mdp").status_code == 303
    assert len(sent) == 1 and sent[0][0] == "exam@psie.ci"
    link = re.search(r"https?://\S+/mot-de-passe-oublie/[\w-]+", sent[0][1]).group(0)
    path = "/" + link.split("/", 3)[3]
    assert anon.post(path, data={"new": "Nouveau-mdp-2026", "confirm": "Nouveau-mdp-2026"}).status_code == 303
    db.expire_all()
    assert verify_password("Nouveau-mdp-2026", db.get(models.User, target.id).hashed_password)
    assert c.post(f"/users/{target.id}/lien-mdp").status_code == 429                      # délai entre deux messages
    assert "Lien envoyé" in c.get("/users?lien=1").text


def test_reset_link_rules(db, setup, monkeypatch):
    monkeypatch.setattr("app.routers.membres.send_email", lambda *a, **k: True)
    admin = client_for("admin@psie.ci")
    target = db.query(models.User).filter_by(email="exam@psie.ci").one()
    assert client_for("den@psie.ci").post(f"/users/{target.id}/lien-mdp").status_code == 403
    target.is_active = False
    db.commit()
    assert admin.post(f"/users/{target.id}/lien-mdp").status_code == 404
    assert admin.post("/users/9999/lien-mdp").status_code == 404
    monkeypatch.setattr("app.routers.membres.send_email", lambda *a, **k: False)
    target.is_active = True
    db.commit()
    assert admin.post(f"/users/{target.id}/lien-mdp").status_code == 503                  # e-mail indisponible : message clair


def test_users_page_shows_last_login_and_secretariat_labels(db, setup):
    admin = client_for("admin@psie.ci")
    client_for("exam@psie.ci")                                                            # une connexion de plus au journal
    page = admin.get("/users").text
    assert "Dernière connexion" in page and "Secrétariat Examens" in page
    row = next(r for r in page.split("<tr>") if "exam@psie.ci" in r)
    assert re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", row)
    never = next(r for r in page.split("<tr>") if "rep-b@psie.ci" in r)
    assert not re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", never)


def test_register_link_is_on_the_members_page(db, setup):
    assert "/registre-membres.pdf" in client_for("den@psie.ci").get("/faitieres").text
