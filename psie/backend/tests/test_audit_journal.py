import datetime

from app import audit, models, rappels

from .conftest import client_for, make_user


def seed(db):
    adm = make_user(db, "adm@psie.ci", "admin")
    for i, (action, entity) in enumerate([("creation", "faitiere"), ("suppression", "documents"), ("creation", "user"),
                                          ("acces_roles", "acces"), ("modification", "ecoles")]):
        audit.log_action(db, adm, action, entity, i + 1, f"détail {i}")
    audit.log_action(db, None, "decision", "adhesion", 9, "=HYPERLINK(\"x\")")
    db.commit()
    return adm


def test_filters_pagination_and_sensitive_flag(db):
    seed(db)
    c = client_for("adm@psie.ci")
    assert "détail 1" in c.get("/audit?action=suppression").text and "détail 0" not in c.get("/audit?action=suppression").text
    page = c.get("/audit?sensibles=1").text
    assert "détail 1" in page and "détail 3" in page and "détail 2" in page and "détail 0" not in page and "détail 4" not in page
    assert "adm@psie.ci" in c.get("/audit?personne=ADM@").text and "détail" not in c.get("/audit?personne=inconnu").text
    assert "détail 3" in c.get("/audit?q=acces").text
    assert c.get("/audit?debut=pas-une-date&page=999").status_code == 200           # saisie invalide : ignorée, jamais d'erreur
    future = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
    assert "détail" not in c.get(f"/audit?debut={future}").text


def test_csv_export_respects_filters_neutralises_formulas_and_is_audited(db):
    seed(db)
    c = client_for("adm@psie.ci")
    full = c.get("/audit.csv")
    assert full.status_code == 200 and "attachment" in full.headers["content-disposition"] and "'=HYPERLINK" in full.text
    assert "\n=HYPERLINK" not in full.text
    only = c.get("/audit.csv?action=suppression").text
    assert "documents" in only and "faitiere" not in only
    db.expire_all()
    assert db.query(models.AuditLog).filter_by(action="export").count() == 2


def test_only_the_admin_can_read_the_journal(db):
    seed(db)
    make_user(db, "den@psie.ci", "den")
    den = client_for("den@psie.ci")
    assert den.get("/audit").status_code == 403 and den.get("/audit.csv").status_code == 403


def test_daily_digest_reports_yesterdays_sensitive_actions_once(db):
    adm = seed(db)
    yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    for a in db.query(models.AuditLog):
        a.created_at = yesterday
    db.commit()
    sent = []
    today = datetime.date.today()
    assert rappels.audit_sensible(db, today, lambda to, s, b: sent.append((to, b)) or True) == 1
    to, body = sent[0]
    assert to == adm.email and "suppression documents" in body and "detail 4" not in body and "modification" not in body
    assert rappels.audit_sensible(db, today, lambda *a: True) == 0                  # une seule fois par jour
