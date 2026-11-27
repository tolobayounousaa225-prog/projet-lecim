import pytest

from app import models, notifier
from app.main import app

from .conftest import client_for, make_faitiere, make_user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(notifier, "send_email", lambda to, subject, body: out.append((to, subject, body)) or True)
    return out


@pytest.fixture
def world(db, sent):
    a, b = make_faitiere(db, "LECIM"), make_faitiere(db, "IQRA")
    for email, role, kw in (("den@psie.ci", "den", {}), ("sec@psie.ci", "secretaire", {}), ("ca@psie.ci", "administrateur_ca", {}),
                            ("form@psie.ci", "formation", {}), ("rep-a@psie.ci", "faitiere", {"faitiere_id": a.id}),
                            ("rep-b@psie.ci", "faitiere", {"faitiere_id": b.id})):
        make_user(db, email, role, **kw)
    return a, b


def titles(db, email):
    u = db.query(models.User).filter_by(email=email).one()
    return [n.titre for n in db.query(models.Notification).filter_by(user_id=u.id).order_by(models.Notification.id)]


def test_new_membership_request_notifies_den_and_secretary_not_others(db, world, sent):
    from fastapi.testclient import TestClient
    c = TestClient(app, follow_redirects=False)
    r = c.post("/adhesion", data={"nom": "Union Nour", "sigle": "NOUR", "representant_nom": "Moussa Traoré", "email": "a@exemple.org",
                                  "telephone": "+225 07 00 00 00 00", "siege": "Bouaké", "statut_juridique": "Association",
                                  "date_creation": "2015-04-01", "nb_structures": "12", "accepte_statuts": "on", "accepte_cotisations": "on"})
    assert r.status_code == 200
    assert any("NOUR" in t for t in titles(db, "den@psie.ci")) and any("NOUR" in t for t in titles(db, "sec@psie.ci"))
    assert titles(db, "ca@psie.ci") == [] and titles(db, "rep-a@psie.ci") == []
    assert {to for to, _, _ in sent} >= {"den@psie.ci", "sec@psie.ci"}


def test_bell_counter_page_open_and_read_state(db, world):
    den = db.query(models.User).filter_by(email="den@psie.ci").one()
    notifier.notify(db, den, "Titre A", texte="Détail", lien="/faitieres", email=False)
    notifier.notify(db, den, "Titre B", lien="//evil.example", email=False)
    db.commit()
    c = client_for("den@psie.ci")
    page = c.get("/admin").text
    assert 'class="bell-count">2<' in page
    listing = c.get("/notifications").text
    assert "Titre A" in listing and "Titre B" in listing
    n = db.query(models.Notification).filter_by(titre="Titre A").one()
    r = c.get(f"/notifications/{n.id}/ouvrir")
    assert r.status_code == 303 and r.headers["location"] == "/faitieres"
    bad = db.query(models.Notification).filter_by(titre="Titre B").one()
    assert c.get(f"/notifications/{bad.id}/ouvrir").headers["location"] == "/notifications"       # lien externe refusé
    assert 'bell-count' not in c.get("/admin").text
    notifier.notify(db, den, "Titre C", email=False); db.commit()
    assert c.post("/notifications/tout-lire").status_code == 303
    assert 'bell-count' not in c.get("/admin").text


def test_nobody_reads_someone_elses_notifications(db, world):
    den = db.query(models.User).filter_by(email="den@psie.ci").one()
    notifier.notify(db, den, "Confidentiel", email=False); db.commit()
    n = db.query(models.Notification).one()
    other = client_for("rep-a@psie.ci")
    assert other.get(f"/notifications/{n.id}/ouvrir").status_code == 404
    assert "Confidentiel" not in other.get("/notifications").text


def test_email_preference_is_respected_and_failures_never_block(db, world, sent, monkeypatch):
    den = db.query(models.User).filter_by(email="den@psie.ci").one()
    c = client_for("den@psie.ci")
    c.post("/notifications/preferences", data={})                          # décoché
    db.expire_all()
    assert db.query(models.User).filter_by(email="den@psie.ci").one().notif_email is False
    notifier.notify(db, db.query(models.User).filter_by(email="den@psie.ci").one(), "Sans e-mail"); db.commit()
    assert not any(to == "den@psie.ci" for to, _, _ in sent) and "Sans e-mail" in titles(db, "den@psie.ci")
    c.post("/notifications/preferences", data={"email": "1"})
    monkeypatch.setattr(notifier, "send_email", lambda *a: (_ for _ in ()).throw(RuntimeError("smtp down")))
    notifier.notify(db, db.query(models.User).filter_by(email="den@psie.ci").one(), "Malgré la panne"); db.commit()
    assert "Malgré la panne" in titles(db, "den@psie.ci")


def test_workflow_events_notify_the_right_people(db, world):
    a, b = world
    ra, rb, den, ca, form = (client_for(x) for x in ("rep-a@psie.ci", "rep-b@psie.ci", "den@psie.ci", "ca@psie.ci", "form@psie.ci"))
    # convention : DEN soumet -> le CA est prévenu -> avis -> le DEN est prévenu
    den.post("/conventions", data={"titre": "Convention Waqf", "partenaire": "Fondation X"}, files={"fichier": ("a.pdf", PDF, "application/pdf")})
    c = db.query(models.Convention).one()
    den.post(f"/conventions/{c.id}/action", data={"action": "soumettre"})
    assert any("Convention à examiner" in t for t in titles(db, "ca@psie.ci"))
    ca.post(f"/conventions/{c.id}/action", data={"action": "avis_favorable"})
    assert any("Avis du CA" in t for t in titles(db, "den@psie.ci"))
    # annonce ciblée : seule la faîtière visée est prévenue
    den.post("/annonces", data={"titre": "Pour IQRA", "texte": "x", "cible": str(b.id)})
    assert any("Pour IQRA" in t for t in titles(db, "rep-b@psie.ci")) and not any("Pour IQRA" in t for t in titles(db, "rep-a@psie.ci"))
    den.post("/annonces", data={"titre": "Pour tous", "texte": "x", "cible": ""})
    assert any("Pour tous" in t for t in titles(db, "rep-a@psie.ci")) and any("Pour tous" in t for t in titles(db, "rep-b@psie.ci"))
    # demande -> PSIE prévenue ; réponse -> la faîtière prévenue
    ra.post("/demandes", data={"type": "attestation", "objet": "Attestation 2026"})
    assert any("Attestation 2026" in t for t in titles(db, "den@psie.ci"))
    d = db.query(models.DemandeFaitiere).one()
    den.post(f"/demandes/{d.id}/traiter", data={"statut": "traitee", "reponse": "Prête"})
    assert any("Réponse à votre demande" in t for t in titles(db, "rep-a@psie.ci")) and not titles(db, "rep-b@psie.ci")[-1:] == ["Réponse à votre demande : Attestation 2026"]
    # bilan -> secrétariats ; décision -> faîtière
    ra.post(f"/faitieres/{a.id}/ecoles", data={"nom": "École Nour"})
    e = db.query(models.Ecole).one()
    ra.post(f"/faitieres/{a.id}/ecoles/{e.id}/bilans", data={"annee": "2025", "resume": "Bien", "action": "soumettre"})
    assert any("Bilan à examiner" in t for t in titles(db, "form@psie.ci"))
    bil = db.query(models.BilanEcole).one()
    form.post(f"/faitieres/{a.id}/ecoles/{e.id}/bilans/{bil.id}/decision", data={"decision": "valider"})
    assert any("Bilan validé" in t for t in titles(db, "rep-a@psie.ci"))


def test_extra_channels_can_be_plugged_and_failures_are_contained(db, world):
    got = []
    notifier.register_channel(lambda user, titre, texte, lien: got.append((user.email, titre)))
    notifier.register_channel(lambda *a: 1 / 0)
    try:
        den = db.query(models.User).filter_by(email="den@psie.ci").one()
        assert notifier.notify(db, den, "Canal", email=False) == 1
        assert got == [("den@psie.ci", "Canal")]
    finally:
        notifier.CHANNELS.clear()
