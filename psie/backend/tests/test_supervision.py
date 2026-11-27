import pytest

from app import models

from .conftest import client_for, make_faitiere, make_user


@pytest.fixture
def world(db):
    f = make_faitiere(db, "LECIM")
    for email, role, kw in (("adm@psie.ci", "admin", {}), ("den@psie.ci", "den", {}), ("fin@psie.ci", "finances", {}), ("com@psie.ci", "communication", {}),
                            ("rep@psie.ci", "faitiere", {"faitiere_id": f.id})):
        make_user(db, email, role, **kw)
    return f


def test_den_sees_accounts_and_what_each_one_did(db, world):
    fin = client_for("fin@psie.ci")
    fin.post("/cotisations/bareme", data={"annee": "2026", "montant": "500000"})
    den = client_for("den@psie.ci")
    page = den.get("/supervision").text
    assert "fin@psie.ci" in page and "com@psie.ci" in page and "Dernière connexion" in page
    uid = db.query(models.User).filter_by(email="fin@psie.ci").one().id
    act = den.get(f"/supervision/{uid}/activite").text
    assert "connexion" in act and "bareme" in act.lower() or "cotisation" in act.lower()
    assert "fin@psie.ci" in den.get("/supervision?q=fin").text and "com@psie.ci" not in den.get("/supervision?q=fin").text
    assert client_for("com@psie.ci").get("/supervision").status_code == 403            # Communication : pas dans la rubrique
    assert client_for("rep@psie.ci").get("/supervision").status_code == 403


def test_view_the_finance_space_read_only_with_banner_and_audit(db, world):
    fin_id = db.query(models.User).filter_by(email="fin@psie.ci").one().id
    den = client_for("den@psie.ci")
    r = den.post(f"/supervision/{fin_id}/voir")
    assert r.status_code == 303 and "view_as" in r.headers.get("set-cookie", "")
    page = den.get("/cotisations").text                                                # l'espace Finances, vu par le DEN
    import html
    assert "Vous consultez l'espace de" in html.unescape(page) and "lecture seule" in page and "den@psie.ci" in page   # le superviseur est nommé
    assert den.get("/supervision").status_code == 403                                   # il voit ce que voit le compte : pas la supervision
    assert den.get("/audit").status_code == 403                                         # ... et l'administration reste fermée
    # aucune écriture possible
    w = den.post("/cotisations/bareme", data={"annee": "2027", "montant": "1"})
    assert w.status_code == 403 and "lecture seule" in w.text.lower()
    assert db.query(models.BaremeCotisation).count() == 0
    assert den.post("/mot-de-passe", data={"current": "x", "new": "y", "confirm": "y"}).status_code == 403
    entry = db.query(models.AuditLog).filter_by(action="consultation_compte").one()
    assert entry.user_email == "den@psie.ci" and "fin@psie.ci" in entry.detail
    out = den.post("/supervision/quitter")
    assert out.status_code == 303 and out.headers["location"] == "/supervision"
    den.cookies.delete("view_as")
    assert "Vous consultez" not in den.get("/admin").text and den.get("/supervision").status_code == 200


def test_actions_during_a_consultation_are_attributed_to_the_supervisor(db, world):
    fin_id = db.query(models.User).filter_by(email="fin@psie.ci").one().id
    den = client_for("den@psie.ci")
    den.post(f"/supervision/{fin_id}/voir")
    den.get("/registre-membres.pdf")                                                    # l'édition d'un PDF est tracée
    logged = db.query(models.AuditLog).filter(models.AuditLog.action == "edition").all()
    for e in logged:
        assert e.user_email == "den@psie.ci" and "[consultation de fin@psie.ci]" in (e.detail or "")


def test_permissions_of_the_consultation_and_who_may_be_viewed(db, world):
    ids = {u.email: u.id for u in db.query(models.User)}
    den, adm, com = client_for("den@psie.ci"), client_for("adm@psie.ci"), client_for("com@psie.ci")
    assert com.post(f"/supervision/{ids['fin@psie.ci']}/voir").status_code == 403
    assert den.post(f"/supervision/{ids['adm@psie.ci']}/voir").status_code == 403         # le DEN ne consulte pas l'administrateur
    assert den.post(f"/supervision/{ids['den@psie.ci']}/voir").status_code == 403         # pas soi-même
    assert adm.post(f"/supervision/{ids['den@psie.ci']}/voir").status_code == 303         # l'administrateur peut consulter tout le monde
    adm.post("/supervision/quitter")
    assert adm.post(f"/supervision/{ids['rep@psie.ci']}/voir").status_code == 303          # y compris l'espace d'une faîtière
    assert "LECIM" in adm.get("/portail", follow_redirects=True).text
    assert adm.post("/annonces", data={"titre": "x", "texte": "y"}).status_code == 403


def test_view_as_cookie_cannot_be_forged_or_borrowed(db, world):
    from app.security import create_view_as_token
    ids = {u.email: u.id for u in db.query(models.User)}
    com = client_for("com@psie.ci")
    com.cookies.set("view_as", create_view_as_token("com@psie.ci", ids["fin@psie.ci"]))      # signé, mais com n'a pas le droit
    assert "Vous consultez" not in com.get("/admin").text
    den = client_for("den@psie.ci")
    den.cookies.set("view_as", create_view_as_token("adm@psie.ci", ids["fin@psie.ci"]))     # jeton d'une autre personne
    assert "Vous consultez" not in den.get("/admin").text
    den.cookies.set("view_as", "n-importe-quoi")
    assert den.get("/admin").status_code == 200 and "Vous consultez" not in den.get("/admin").text
    from app.security import create_access_token
    den.cookies.set("access_token", create_view_as_token("den@psie.ci", ids["fin@psie.ci"]))   # un jeton de consultation n'ouvre jamais une session
    assert den.get("/admin").status_code in (303, 401)


def test_notifications_of_the_viewed_account_stay_unread(db, world):
    from app import notifier
    fin = db.query(models.User).filter_by(email="fin@psie.ci").one()
    notifier.notify(db, fin, "Pour la finance", lien="/cotisations", email=False)
    db.commit()
    n = db.query(models.Notification).one()
    den = client_for("den@psie.ci")
    den.post(f"/supervision/{fin.id}/voir")
    den.get(f"/notifications/{n.id}/ouvrir")
    db.expire_all()
    assert db.get(models.Notification, n.id).lue_at is None


def test_portals_of_every_role_can_be_previewed_without_any_account(db, world):
    """L'administrateur voit le portail de chaque secrétariat même si aucun compte n'existe pour ce rôle."""
    import html
    adm = client_for("adm@psie.ci")
    page = adm.get("/supervision").text
    for role in ("Secrétariat Formation", "Secrétariat Examens", "Commissaire aux comptes", "Directeur Exécutif National"):
        assert role in html.unescape(page)
    assert "/supervision/apercu/formation" in page and f"/supervision/apercu/faitiere/{world.id}" in page
    r = adm.post("/supervision/apercu/formation")                                          # aucun compte « formation » n'existe
    assert r.status_code == 303 and "view_as" in r.headers.get("set-cookie", "")
    home = html.unescape(adm.get("/admin").text)
    assert "Aperçu : Secrétariat Formation" in home and "/formations" in home and "/cotisations" not in home
    assert adm.get("/formations").status_code == 200 and adm.get("/cotisations").status_code == 403   # exactement les droits du rôle
    assert adm.post("/formations", data={"titre": "x"}).status_code in (303, 403)                # l'écriture dépend du rôle ...
    w = adm.post("/cotisations/bareme", data={"annee": "2027", "montant": "1"})
    assert w.status_code == 403 and db.query(models.BaremeCotisation).count() == 0
    assert db.query(models.Formation).count() == 0                                           # ... mais aucune modification en aperçu
    entry = db.query(models.AuditLog).filter_by(action="consultation_compte").one()
    assert entry.user_email == "adm@psie.ci" and "formation" in entry.detail
    assert db.query(models.User).filter(models.User.email.like("apercu-%")).count() == 0         # la personne virtuelle n'est jamais enregistrée
    adm.post("/supervision/quitter")
    adm.cookies.delete("view_as")


def test_federation_portal_preview_and_who_may_use_it(db, world):
    adm = client_for("adm@psie.ci")
    assert adm.post(f"/supervision/apercu/faitiere/{world.id}").status_code == 303
    assert adm.get("/portail", follow_redirects=False).status_code in (200, 303)
    adm.cookies.delete("view_as")
    assert adm.post("/supervision/apercu/admin").status_code == 404 and adm.post("/supervision/apercu/inconnu").status_code == 404
    assert adm.post("/supervision/apercu/faitiere/9999").status_code == 404
    assert client_for("com@psie.ci").post("/supervision/apercu/formation").status_code == 403
    assert client_for("rep@psie.ci").post("/supervision/apercu/formation").status_code == 403
    assert client_for("com@psie.ci").get("/supervision").status_code == 403
