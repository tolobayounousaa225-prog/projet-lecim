import datetime

from app import finance, models

from .conftest import make_faitiere, make_user

D = datetime.date(2026, 3, 1)


def make_echeance(db, email="lecim@psie.local", limite=D, montant=500000, **kw):
    f = make_faitiere(db, kw.pop("sigle", "LECIM"))
    f.email = email
    e = models.Echeance(faitiere_id=f.id, type="annuelle", annee=2026, libelle="Cotisation annuelle 2026",
                        montant_du=montant, date_limite=limite)
    db.add(e)
    db.commit()
    return e


class Outbox:
    def __init__(self, ok=True):
        self.mails, self.ok = [], ok

    def __call__(self, to, subject, body):
        self.mails.append((to, subject, body))
        return self.ok


def test_reminder_thresholds_send_once_each(db):
    make_echeance(db)
    box = Outbox()
    assert finance.send_reminders(db, D - datetime.timedelta(days=45), box) == 0   # trop tôt
    assert finance.send_reminders(db, D - datetime.timedelta(days=30), box) == 1   # J-30
    assert finance.send_reminders(db, D - datetime.timedelta(days=29), box) == 0   # déjà envoyé
    assert finance.send_reminders(db, D - datetime.timedelta(days=7), box) == 1    # J-7
    assert finance.send_reminders(db, D, box) == 1                                  # jour J
    assert finance.send_reminders(db, D + datetime.timedelta(days=3), box) == 0
    assert finance.send_reminders(db, D + datetime.timedelta(days=7), box) == 1    # 1re relance de retard
    assert finance.send_reminders(db, D + datetime.timedelta(days=14), box) == 1   # 2e
    assert len(box.mails) == 5


def test_missed_days_do_not_skip_reminder(db):
    make_echeance(db)
    box = Outbox()
    # Le planificateur n'a pas tourné entre J-10 et J-3 : le rappel J-7 part quand même
    assert finance.send_reminders(db, D - datetime.timedelta(days=3), box) == 1
    assert "J7" in {r.kind for r in db.query(models.RelanceLog)}


def test_no_reminder_when_paid_or_no_email_or_inactive(db):
    e = make_echeance(db)
    db.add(models.Paiement(echeance_id=e.id, montant=500000, date_paiement=D, mode="virement",
                           recu_numero="PSIE-REC-2026-0001", verify_token="t1"))
    db.commit()
    box = Outbox()
    assert finance.send_reminders(db, D, box) == 0
    e2 = make_echeance(db, email="", sigle="IQRA")
    assert finance.send_reminders(db, D, box) == 0
    e3 = make_echeance(db, sigle="HINNEH")
    e3.faitiere.statut = "suspendu"
    db.commit()
    assert finance.send_reminders(db, D, box) == 0 and box.mails == []


def test_failed_send_is_retried_later(db):
    make_echeance(db)
    assert finance.send_reminders(db, D, Outbox(ok=False)) == 0
    assert db.query(models.RelanceLog).count() == 0
    assert finance.send_reminders(db, D, Outbox(ok=True)) == 1


def test_reminder_is_bilingual(db):
    make_echeance(db)
    box = Outbox()
    finance.send_reminders(db, D, box)
    _, subject, body = box.mails[0]
    assert "LECIM" in subject and "500 000 FCFA" in body and "تأخر" in body or "تذكير" in body


def test_weekly_digest_goes_to_finance_only(db):
    make_echeance(db)
    make_user(db, "fin@psie.local", "finances")
    make_user(db, "den@psie.local", "den")
    box = Outbox()
    assert finance.send_weekly_digest(db, D + datetime.timedelta(days=10), box) == 1
    assert box.mails[0][0] == "fin@psie.local" and "LECIM" in box.mails[0][2]
    # Rien en retard (échéance pas encore échue) : aucun envoi
    assert finance.send_weekly_digest(db, D - datetime.timedelta(days=10), Outbox()) == 0
