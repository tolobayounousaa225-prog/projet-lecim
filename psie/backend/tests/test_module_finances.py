"""Module 2 : reçu par e-mail à chaque paiement, relevé de compte, rappels réglementaires, tableau de bord."""
import datetime
import email
import shutil
import subprocess

import pytest

from app import finance, models, rappels
from app.emailing import send_email

from .conftest import client_for, make_faitiere, make_user

TODAY = datetime.date.today()


@pytest.fixture
def setup(db):
    lecim = make_faitiere(db, "LECIM", "fondateur")
    lecim.email = "contact@lecim.ci"
    iqra = make_faitiere(db, "IQRA", "fondateur")
    for who, role, fid in (("fin", "finances", None), ("den", "den", None), ("sec", "secretaire", None), ("exam", "examens", None),
                           ("rep-a", "faitiere", lecim.id), ("rep-b", "faitiere", iqra.id), ("cc", "commissaire", None)):
        make_user(db, f"{who}@psie.ci", role, faitiere_id=fid)
    db.commit()
    return lecim, iqra


def echeance(db, f, montant=500000, limite=None):
    e = models.Echeance(faitiere_id=f.id, type="annuelle", annee=TODAY.year, libelle=f"Cotisation {TODAY.year}",
                        montant_du=montant, date_limite=limite)
    db.add(e)
    db.commit()
    return e


def pay(client, e, montant=200000, **over):
    return client.post(f"/echeances/{e.id}/paiements", data={"montant": str(montant), "date_paiement": TODAY.isoformat(),
                                                             "mode": "virement", **over})


@pytest.fixture
def mails(monkeypatch):
    sent = []

    def fake(to, subject, body, attachments=None):
        sent.append({"to": to, "subject": subject, "body": body, "attachments": attachments or []})
        return True

    monkeypatch.setattr("app.finance.send_email", fake)
    monkeypatch.setattr("app.rappels.send_email", fake)
    return sent


# ---------------------------------------------------------------- pièces jointes des e-mails

def test_emails_can_carry_attachments(monkeypatch):
    from app.config import settings
    captured = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, message): captured["message"] = message

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.org")
    monkeypatch.setattr("app.emailing.smtplib.SMTP", FakeSMTP)
    assert send_email("a@b.ci", "Sujet", "Texte", attachments=[("recu.pdf", b"%PDF-1.4 x", "application/pdf")])
    parts = list(captured["message"].iter_attachments())
    assert len(parts) == 1 and parts[0].get_filename() == "recu.pdf" and parts[0].get_content_type() == "application/pdf"
    assert send_email("a@b.ci", "Sujet", "Sans pièce jointe")


# ---------------------------------------------------------------- reçu envoyé à chaque paiement

def test_receipt_is_emailed_to_the_federation_with_the_pdf(db, setup, mails):
    lecim, _ = setup
    e = echeance(db, lecim)
    r = pay(client_for("fin@psie.ci"), e)
    assert r.status_code == 303 and r.headers["location"].endswith("?recu=envoye")
    assert len(mails) == 1 and mails[0]["to"] == "contact@lecim.ci" and "Reçu PSIE-REC-" in mails[0]["subject"]
    name, data, mime = mails[0]["attachments"][0]
    assert name.endswith(".pdf") and data.startswith(b"%PDF-") and mime == "application/pdf"
    assert "300" in mails[0]["body"].replace(" ", "").replace(" ", "")                    # solde restant 300 000 FCFA


def test_payment_is_recorded_even_without_an_address_or_when_email_fails(db, setup, mails, monkeypatch):
    _, iqra = setup                                                                      # IQRA : aucune adresse sur la fiche
    e = echeance(db, iqra)
    r = pay(client_for("fin@psie.ci"), e)
    assert r.status_code == 303 and r.headers["location"].endswith("?recu=non") and mails == []
    assert db.query(models.Paiement).count() == 1
    lecim, _ = setup
    e2 = echeance(db, lecim)

    def boom(*a, **k):
        raise RuntimeError("SMTP en panne")

    monkeypatch.setattr("app.finance.send_email", boom)
    assert pay(client_for("fin@psie.ci"), e2).status_code == 303
    assert db.query(models.Paiement).count() == 2


def test_notice_is_shown_and_receipt_can_be_resent(db, setup, mails):
    lecim, _ = setup
    e = echeance(db, lecim)
    c = client_for("fin@psie.ci")
    pay(c, e)
    assert "Reçu envoyé par e-mail" in c.get(f"/echeances/{e.id}?recu=envoye").text
    assert "n&#39;a pas pu être envoyé" in c.get(f"/echeances/{e.id}?recu=non").text
    p = db.query(models.Paiement).one()
    assert "Renvoyer par e-mail" in c.get(f"/echeances/{e.id}").text
    assert c.post(f"/paiements/{p.id}/renvoyer-recu").status_code == 303 and len(mails) == 2
    assert client_for("den@psie.ci").post(f"/paiements/{p.id}/renvoyer-recu").status_code == 403
    c.post(f"/paiements/{p.id}/annuler", data={"motif": "erreur de saisie"})
    assert c.post(f"/paiements/{p.id}/renvoyer-recu").status_code == 404                  # jamais un reçu annulé
    assert pay(c, e, 100000).status_code == 303 and len(mails) == 3


# ---------------------------------------------------------------- relevé de compte

def statement_text(client, f, tmp_path):
    r = client.get(f"/faitieres/{f.id}/releve.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    if not shutil.which("pdftotext"):
        return ""
    pdf = tmp_path / "releve.pdf"
    pdf.write_bytes(r.content)
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout


def test_account_statement_lists_dues_payments_and_flags_cancelled_receipts(db, setup, mails, tmp_path):
    lecim, _ = setup
    e = echeance(db, lecim)
    c = client_for("fin@psie.ci")
    pay(c, e, 200000)
    pay(c, e, 100000, reference="VIR-42")
    p2 = db.query(models.Paiement).order_by(models.Paiement.id.desc()).first()
    c.post(f"/paiements/{p2.id}/annuler", data={"motif": "doublon"})
    text = statement_text(c, lecim, tmp_path)
    if text:
        assert "RELEVÉ DE COMPTE" in text and "LECIM" in text and f"Cotisation {TODAY.year}" in text
        assert "ANNULÉ : doublon" in text and "TOTAL" in text
        flat = text.replace(" ", " ").replace("\xa0", " ")
        assert "500 000" in flat and "200 000" in flat                                   # dû et payé (le payé exclut l'annulé)


def test_account_statement_access_rules(db, setup, anon):
    lecim, iqra = setup
    echeance(db, lecim)
    for who in ("fin", "den", "cc"):
        assert client_for(f"{who}@psie.ci").get(f"/faitieres/{lecim.id}/releve.pdf").status_code == 200, who
    assert client_for("rep-a@psie.ci").get(f"/faitieres/{lecim.id}/releve.pdf").status_code == 200       # sa propre faîtière
    assert client_for("rep-b@psie.ci").get(f"/faitieres/{lecim.id}/releve.pdf").status_code == 404       # jamais une autre
    for who in ("sec", "exam"):                                                         # organes sans accès aux finances
        assert client_for(f"{who}@psie.ci").get(f"/faitieres/{lecim.id}/releve.pdf").status_code == 404, who
    assert anon.get(f"/faitieres/{lecim.id}/releve.pdf").status_code == 303
    assert client_for("fin@psie.ci").get("/faitieres/9999/releve.pdf").status_code == 404
    assert "releve.pdf" in client_for("fin@psie.ci").get(f"/faitieres/{lecim.id}").text


# ---------------------------------------------------------------- rappels réglementaires

def mandat(db, f, days, name="Koné Ali"):
    m = models.Mandat(faitiere_id=f.id, organe="AG", full_name=name, date_debut=TODAY - datetime.timedelta(days=1000),
                      date_fin=TODAY + datetime.timedelta(days=days))
    db.add(m)
    db.commit()
    return m


def test_expiring_mandates_are_reported_once_per_threshold_to_den_and_secretariat(db, setup, mails):
    lecim, _ = setup
    mandat(db, lecim, 60)                                           # franchit le seuil de 90 jours
    mandat(db, lecim, 400, "Loin")                                  # pas concerné
    mandat(db, lecim, -100, "Très ancien")                          # expiré depuis longtemps : ignoré
    assert rappels.send_regulatory_reminders(db, TODAY) == 2
    assert sorted(m["to"] for m in mails) == ["den@psie.ci", "sec@psie.ci"]
    body = mails[0]["body"]
    assert "Koné Ali" in body and "expire dans 60 jour(s)" in body and "Loin" not in body and "Très ancien" not in body
    assert rappels.send_regulatory_reminders(db, TODAY) == 0 and len(mails) == 2                # une seule fois
    later = TODAY + datetime.timedelta(days=40)                                                  # reste 20 jours : seuil 30
    assert rappels.send_regulatory_reminders(db, later) == 2 and "expire dans 20 jour(s)" in mails[-1]["body"]
    assert rappels.send_regulatory_reminders(db, later) == 0


def test_a_mandate_ending_today_or_just_expired_is_flagged(db, setup, mails):
    lecim, _ = setup
    mandat(db, lecim, 0, "Aujourd'hui")
    mandat(db, lecim, -3, "Hier")
    rappels.send_regulatory_reminders(db, TODAY)
    text = mails[0]["body"]
    assert "expire aujourd'hui" in text and "expiré" in text


@pytest.mark.parametrize("day,expected", [
    (datetime.date(2026, 6, 1), 0), (datetime.date(2026, 6, 14), 0), (datetime.date(2026, 6, 15), 1), (datetime.date(2026, 6, 30), 1),
    (datetime.date(2026, 7, 2), 0), (datetime.date(2026, 12, 20), 1), (datetime.date(2026, 3, 10), 0),
])
def test_half_yearly_report_reminder_goes_to_the_den_only(db, setup, mails, day, expected):
    assert rappels.send_regulatory_reminders(db, day) == expected
    assert [m["to"] for m in mails] == (["den@psie.ci"] if expected else [])
    if expected:
        assert "rapport semestriel" in mails[0]["body"] and "art. 18" in mails[0]["body"]
        assert rappels.send_regulatory_reminders(db, day) == 0


def assembly(db, type_, days, statut="convoquee"):
    a = models.Assemblee(type=type_, date_assemblee=TODAY + datetime.timedelta(days=days), lieu="Siège",
                         ordre_du_jour="Rapports", statut=statut)
    db.add(a)
    db.commit()
    return a


def test_financial_statements_reminder_before_an_ordinary_assembly(db, setup, mails):
    assembly(db, "AGA", 18)
    assembly(db, "AGE", 10)                                          # une AGE n'a pas d'états financiers à fournir
    assembly(db, "AGO", 60)                                          # trop loin
    assembly(db, "AGA", 5, statut="close")                           # déjà tenue
    sent = rappels.send_regulatory_reminders(db, TODAY)
    states = [m for m in mails if "États financiers" in m["subject"]]
    assert sent == 2 and sorted(m["to"] for m in states) == ["den@psie.ci", "fin@psie.ci"]
    limite = (TODAY + datetime.timedelta(days=3)).strftime("%d/%m/%Y")                   # AG - 15 jours
    assert limite in states[0]["body"] and "art. 36" in states[0]["body"]
    assert rappels.send_regulatory_reminders(db, TODAY) == 0


def test_inactive_users_never_receive_reminders(db, setup, mails):
    lecim, _ = setup
    mandat(db, lecim, 10)
    for u in db.query(models.User).filter(models.User.role.in_(("den", "secretaire"))):
        u.is_active = False
    db.commit()
    assert rappels.send_regulatory_reminders(db, TODAY) == 0 and mails == []


def test_failed_sends_are_not_retried_forever_per_recipient(db, setup, monkeypatch):
    lecim, _ = setup
    mandat(db, lecim, 10)
    monkeypatch.setattr("app.rappels.send_email", lambda *a, **k: False)
    assert rappels.send_regulatory_reminders(db, TODAY) == 0                  # rien envoyé ; le rappel reste marqué (pas de spam)


def test_daily_job_runs_the_regulatory_reminders(db, setup, mails, monkeypatch):
    from app import scheduler
    lecim, _ = setup
    mandat(db, lecim, 5)
    monkeypatch.setattr("app.scheduler.SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    scheduler.job_daily()
    assert any("Mandats arrivant à échéance" in m["subject"] for m in mails)


# ---------------------------------------------------------------- tableau de bord

def test_dashboard_shows_open_calls_assemblies_and_expenses_to_sign(db, setup, mails):
    lecim, iqra = setup
    fin = client_for("fin@psie.ci")
    finance.create_appel(db, db.query(models.User).filter_by(email="fin@psie.ci").one(), "Appel test", None, None, None,
                         [(lecim, 100000), (iqra, 100000)])
    db.commit()
    assembly(db, "AGO", 30, statut="preparation")
    page = fin.get("/admin").text
    assert "Appels exceptionnels en cours" in page and "Dépenses à signer" in page and "Prochaines assemblées" in page
    assert "Assemblée Générale Ordinaire" in page
    secretary = client_for("sec@psie.ci").get("/admin").text
    assert "Appels exceptionnels en cours" not in secretary and "Dépenses à signer" not in secretary
    assert "Prochaines assemblées" in secretary
