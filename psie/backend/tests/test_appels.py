import datetime

import pytest

from app import finance, models

from .conftest import client_for, make_faitiere, make_user

TODAY = datetime.date.today()


@pytest.fixture
def setup(db):
    f = {s: make_faitiere(db, s) for s in ("LECIM", "IQRA", "OEECI")}
    hon = make_faitiere(db, "HON", categorie="honneur")
    make_user(db, "fin@psie.local", "finances")
    return f, hon


def create(client, **extra):
    data = {"intitule": "Soutien examens 2026", "reference_decision": "PV DEN du 12/03", "motif": "Frais d'examens"}
    data.update(extra)
    return client.post("/appels", data=data)


def test_equal_amount_for_selected_members(db, setup):
    f, _ = setup
    client = client_for("fin@psie.local")
    r = create(client, montant_commun="100000", **{f"inclure_{f['LECIM'].id}": "on", f"inclure_{f['IQRA'].id}": "on"})
    assert r.status_code == 303
    appel = db.query(models.AppelExceptionnel).one()
    assert sorted((e.faitiere.sigle, e.montant_du) for e in appel.echeances) == [("IQRA", 100000), ("LECIM", 100000)]
    assert all(e.type == "exceptionnelle" and e.appel_id == appel.id for e in appel.echeances)
    assert appel.total_du == 200000


def test_amounts_can_differ_per_member(db, setup):
    f, _ = setup
    client = client_for("fin@psie.local")
    create(client, montant_commun="100000",
           **{f"inclure_{f['LECIM'].id}": "on", f"montant_{f['LECIM'].id}": "250000",
              f"inclure_{f['IQRA'].id}": "on"})
    montants = {e.faitiere.sigle: e.montant_du for e in db.query(models.Echeance).all()}
    assert montants == {"LECIM": 250000, "IQRA": 100000}  # le montant propre l'emporte


def test_creation_validation(db, setup):
    f, hon = setup
    client = client_for("fin@psie.local")
    inc = {f"inclure_{f['LECIM'].id}": "on"}
    assert create(client, **inc).status_code == 400                                     # aucun montant
    assert create(client, montant_commun="abc", **inc).status_code == 400               # montant invalide
    assert create(client, montant_commun="1000").status_code == 400                     # aucune faîtière
    assert create(client, montant_commun="1000", intitule=" ", **inc).status_code == 400
    assert create(client, montant_commun="1000", **{f"inclure_{hon.id}": "on"}).status_code == 400  # honneur
    assert db.query(models.AppelExceptionnel).count() == 0 and db.query(models.Echeance).count() == 0


def test_payment_receipt_and_totals_for_exceptional_due(db, setup):
    f, _ = setup
    client = client_for("fin@psie.local")
    create(client, montant_commun="100000", date_limite=(TODAY + datetime.timedelta(days=30)).isoformat(),
           **{f"inclure_{f['LECIM'].id}": "on", f"inclure_{f['IQRA'].id}": "on"})
    e = db.query(models.Echeance).filter_by(faitiere_id=f["LECIM"].id).one()
    r = client.post(f"/echeances/{e.id}/paiements",
                    data={"montant": "100000", "date_paiement": TODAY.isoformat(), "mode": "virement"})
    assert r.status_code == 303
    pdf = client.get(f"/paiements/{db.query(models.Paiement).one().id}/recu.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    appel = db.query(models.AppelExceptionnel).one()
    assert (appel.total_paye, appel.reste, appel.taux, appel.is_solde) == (100000, 100000, 50, False)
    assert client.get("/appels").status_code == 200 and client.get(f"/appels/{appel.id}").status_code == 200


def test_exceptional_due_does_not_affect_annual_attestation_or_year_totals(db, setup):
    f, _ = setup
    client = client_for("fin@psie.local")
    create(client, montant_commun="100000", **{f"inclure_{f['LECIM'].id}": "on"})
    assert finance.situation(db, TODAY.year)["total_du"] == 0  # la situation annuelle ne compte que l'annuelle


def test_exemption_zeroes_balance_and_blocks_payment(db, setup):
    f, _ = setup
    client = client_for("fin@psie.local")
    create(client, montant_commun="100000", **{f"inclure_{f['LECIM'].id}": "on"})
    e = db.query(models.Echeance).one()
    assert client.post(f"/echeances/{e.id}/exonerer", data={"motif": ""}).status_code == 400
    assert client.post(f"/echeances/{e.id}/exonerer", data={"motif": "Difficulté financière reconnue"}).status_code == 303
    db.refresh(e)
    assert (e.solde, e.statut) == (0, "exonere")
    pay = {"montant": "1000", "date_paiement": TODAY.isoformat(), "mode": "virement"}
    assert client.post(f"/echeances/{e.id}/paiements", data=pay).status_code == 400
    assert db.query(models.Echeance).one().appel.total_du == 0
    assert client.post(f"/echeances/{e.id}/exonerer", data={"motif": "encore"}).status_code == 409
    client.post(f"/echeances/{e.id}/retablir")
    db.refresh(e)
    assert (e.solde, e.statut) == (100000, "impaye")
    assert {a.action for a in db.query(models.AuditLog)} >= {"exoneration", "retablissement"}


def test_exempted_due_gets_no_reminder(db, setup):
    f, _ = setup
    f["LECIM"].email = "lecim@psie.local"
    db.commit()
    client = client_for("fin@psie.local")
    create(client, montant_commun="100000", date_limite=TODAY.isoformat(), **{f"inclure_{f['LECIM'].id}": "on"})
    e = db.query(models.Echeance).one()
    client.post(f"/echeances/{e.id}/exonerer", data={"motif": "Décision du bureau"})
    db.expire_all()  # la session de test a gardé l'ancienne version de l'échéance
    mails = []
    assert finance.send_reminders(db, TODAY, lambda *a: mails.append(a) or True) == 0 and mails == []


def test_postpone_resets_reminders_and_validates(db, setup):
    f, _ = setup
    f["LECIM"].email = "lecim@psie.local"
    db.commit()
    client = client_for("fin@psie.local")
    limite = TODAY + datetime.timedelta(days=5)
    create(client, montant_commun="100000", date_limite=limite.isoformat(), **{f"inclure_{f['LECIM'].id}": "on"})
    e = db.query(models.Echeance).one()
    assert finance.send_reminders(db, TODAY, lambda *a: True) == 1               # J-7 envoyé
    assert db.query(models.RelanceLog).count() == 1
    new = (limite + datetime.timedelta(days=60)).isoformat()
    assert client.post(f"/echeances/{e.id}/reporter", data={"nouvelle_date": new, "motif": ""}).status_code == 400
    earlier = (limite - datetime.timedelta(days=1)).isoformat()
    assert client.post(f"/echeances/{e.id}/reporter", data={"nouvelle_date": earlier, "motif": "x"}).status_code == 400
    assert client.post(f"/echeances/{e.id}/reporter", data={"nouvelle_date": new, "motif": "Accord du bureau"}).status_code == 303
    db.refresh(e)
    assert e.date_limite.isoformat() == new and db.query(models.RelanceLog).count() == 0


def test_amount_correction_rules(db, setup):
    f, _ = setup
    client = client_for("fin@psie.local")
    create(client, montant_commun="100000", **{f"inclure_{f['LECIM'].id}": "on"})
    e = db.query(models.Echeance).one()
    client.post(f"/echeances/{e.id}/paiements",
                data={"montant": "60000", "date_paiement": TODAY.isoformat(), "mode": "especes"})
    assert client.post(f"/echeances/{e.id}/montant", data={"montant": "50000", "motif": "erreur"}).status_code == 400
    assert client.post(f"/echeances/{e.id}/montant", data={"montant": "70000", "motif": ""}).status_code == 400
    assert client.post(f"/echeances/{e.id}/montant", data={"montant": "70000", "motif": "Montant corrigé"}).status_code == 303
    db.refresh(e)
    assert (e.montant_du, e.solde) == (70000, 10000)


def test_permissions(db, setup):
    f, _ = setup
    fin = client_for("fin@psie.local")
    create(fin, montant_commun="100000", **{f"inclure_{f['LECIM'].id}": "on"})
    e = db.query(models.Echeance).one()
    appel = db.query(models.AppelExceptionnel).one()
    for role in ("admin", "den", "secretaire", "administrateur_ca", "commissaire"):
        make_user(db, f"{role}@psie.local", role)
        c = client_for(f"{role}@psie.local")
        assert c.post("/appels", data={"intitule": "X", "montant_commun": "1"}).status_code == 403, role
        for action in ("exonerer", "reporter", "montant", "retablir"):
            assert c.post(f"/echeances/{e.id}/{action}", data={"motif": "x", "montant": "5", "nouvelle_date": "2099-01-01"}).status_code == 403, (role, action)
        expected = 200 if role in ("den", "administrateur_ca", "commissaire") else 403
        assert c.get(f"/appels/{appel.id}").status_code == expected, role
    # Un représentant ne voit ni les appels ni l'échéance d'une autre faîtière
    other = make_faitiere(db, "ZZZ")
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=other.id)
    rep = client_for("rep@psie.local")
    assert rep.get("/appels").status_code == 403 and rep.get(f"/echeances/{e.id}").status_code == 404
    assert rep.post(f"/echeances/{e.id}/exonerer", data={"motif": "x"}).status_code == 403


def test_representative_sees_own_exceptional_due(db, setup):
    f, _ = setup
    fin = client_for("fin@psie.local")
    create(fin, montant_commun="100000", **{f"inclure_{f['LECIM'].id}": "on", f"inclure_{f['IQRA'].id}": "on"})
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=f["LECIM"].id)
    page = client_for("rep@psie.local").get(f"/faitieres/{f['LECIM'].id}").text
    assert "Soutien examens 2026" in page
