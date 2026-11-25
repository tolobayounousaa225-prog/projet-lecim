import datetime

import pytest

from app import finance, models

from .conftest import client_for, make_faitiere, make_user

YEAR = datetime.date.today().year
TODAY = datetime.date.today()


@pytest.fixture
def setup(db):
    """4 membres (dont un honneur et un suspendu), un secrétaire aux finances, un barème."""
    f1 = make_faitiere(db, "LECIM")
    f2 = make_faitiere(db, "IQRA")
    make_faitiere(db, "HON", categorie="honneur")
    susp = make_faitiere(db, "SUSP", categorie="ordinaire")
    susp.statut = "suspendu"
    db.commit()
    make_user(db, "fin@psie.local", "finances")
    return f1, f2


def open_year(db, montant=500000, limite=None):
    client = client_for("fin@psie.local")
    data = {"annee": str(YEAR), "montant": str(montant)}
    if limite:
        data["date_limite"] = limite.isoformat()
    assert client.post("/cotisations/bareme", data=data).status_code == 303
    assert client.post("/cotisations/ouvrir", data={"annee": str(YEAR)}).status_code == 303
    return client


def test_year_generation_only_for_active_paying_members(db, setup):
    open_year(db)
    sigles = sorted(e.faitiere.sigle for e in db.query(models.Echeance).all())
    assert sigles == ["IQRA", "LECIM"]  # ni membre d'honneur, ni membre suspendu
    assert all(e.montant_du == 500000 for e in db.query(models.Echeance).all())


def test_generation_is_idempotent_and_keeps_existing_amounts(db, setup):
    client = open_year(db)
    client.post("/cotisations/bareme", data={"annee": str(YEAR), "montant": "600000"})
    client.post("/cotisations/ouvrir", data={"annee": str(YEAR)})
    echeances = db.query(models.Echeance).all()
    assert len(echeances) == 2 and {e.montant_du for e in echeances} == {500000}


def test_generation_requires_amount(db, setup):
    client = client_for("fin@psie.local")
    assert client.post("/cotisations/ouvrir", data={"annee": str(YEAR)}).status_code == 400


def test_partial_then_full_payment_and_status(db, setup):
    f1, _ = setup
    client = open_year(db, limite=TODAY + datetime.timedelta(days=60))
    e = db.query(models.Echeance).filter_by(faitiere_id=f1.id).one()
    assert e.statut == "impaye"
    r = client.post(f"/echeances/{e.id}/paiements",
                    data={"montant": "200000", "date_paiement": TODAY.isoformat(), "mode": "virement", "reference": "V1"})
    assert r.status_code == 303
    db.refresh(e)
    assert (e.montant_paye, e.solde, e.statut) == (200000, 300000, "partiel")
    client.post(f"/echeances/{e.id}/paiements",
                data={"montant": "300000", "date_paiement": TODAY.isoformat(), "mode": "especes"})
    db.refresh(e)
    assert (e.solde, e.statut) == (0, "paye")
    numeros = [p.recu_numero for p in e.paiements]
    assert numeros == [f"PSIE-REC-{TODAY.year}-0001", f"PSIE-REC-{TODAY.year}-0002"]


def test_payment_validation(db, setup):
    f1, _ = setup
    client = open_year(db)
    e = db.query(models.Echeance).filter_by(faitiere_id=f1.id).one()
    base = {"date_paiement": TODAY.isoformat(), "mode": "virement"}
    assert client.post(f"/echeances/{e.id}/paiements", data={**base, "montant": "500001"}).status_code == 400
    assert client.post(f"/echeances/{e.id}/paiements", data={**base, "montant": "0"}).status_code == 400
    assert client.post(f"/echeances/{e.id}/paiements", data={**base, "montant": "-5"}).status_code == 400
    assert client.post(f"/echeances/{e.id}/paiements", data={**base, "montant": "100", "mode": "troc"}).status_code == 400
    future = (TODAY + datetime.timedelta(days=3)).isoformat()
    assert client.post(f"/echeances/{e.id}/paiements",
                       data={"montant": "100", "date_paiement": future, "mode": "virement"}).status_code == 400
    assert db.query(models.Paiement).count() == 0


def test_cancellation_keeps_trace_and_restores_balance(db, setup):
    f1, _ = setup
    client = open_year(db)
    e = db.query(models.Echeance).filter_by(faitiere_id=f1.id).one()
    client.post(f"/echeances/{e.id}/paiements",
                data={"montant": "500000", "date_paiement": TODAY.isoformat(), "mode": "virement"})
    p = db.query(models.Paiement).one()
    assert client.post(f"/paiements/{p.id}/annuler", data={"motif": ""}).status_code == 400
    assert client.post(f"/paiements/{p.id}/annuler", data={"motif": "Erreur de saisie"}).status_code == 303
    db.refresh(e)
    db.refresh(p)
    assert p.annule and e.solde == 500000 and db.query(models.Paiement).count() == 1  # pas supprimé
    assert client.post(f"/paiements/{p.id}/annuler", data={"motif": "encore"}).status_code == 409
    assert db.query(models.AuditLog).filter_by(action="annulation").count() == 1


def test_late_status_and_totals(db, setup):
    f1, f2 = setup
    client = open_year(db, limite=TODAY - datetime.timedelta(days=1))
    e1 = db.query(models.Echeance).filter_by(faitiere_id=f1.id).one()
    client.post(f"/echeances/{e1.id}/paiements",
                data={"montant": "500000", "date_paiement": TODAY.isoformat(), "mode": "virement"})
    data = finance.situation(db, YEAR)
    assert (data["total_du"], data["total_paye"], data["taux"]) == (1000000, 500000, 50)
    assert (data["nb_a_jour"], data["nb_retard"]) == (1, 1)


def test_only_finance_secretary_writes(db, setup):
    f1, _ = setup
    open_year(db)
    e = db.query(models.Echeance).filter_by(faitiere_id=f1.id).first()
    pay = {"montant": "1000", "date_paiement": TODAY.isoformat(), "mode": "virement"}
    for role in ("admin", "den", "secretaire", "administrateur_ca", "commissaire"):
        make_user(db, f"{role}@psie.local", role)
        client = client_for(f"{role}@psie.local")
        assert client.post(f"/echeances/{e.id}/paiements", data=pay).status_code == 403, role
        assert client.post("/cotisations/bareme", data={"annee": "2030", "montant": "1"}).status_code == 403, role
        assert client.post("/cotisations/ouvrir", data={"annee": str(YEAR)}).status_code == 403, role
    assert db.query(models.Paiement).count() == 0


def test_read_access_matrix(db, setup):
    open_year(db)
    for role, expected in [("den", 200), ("commissaire", 200), ("administrateur_ca", 200),
                           ("admin", 403), ("secretaire", 403)]:
        make_user(db, f"{role}@psie.local", role)
        assert client_for(f"{role}@psie.local").get("/cotisations").status_code == expected, role


def test_representative_sees_only_own_dues_and_receipts(db, setup):
    f1, f2 = setup
    client = open_year(db)
    e1 = db.query(models.Echeance).filter_by(faitiere_id=f1.id).one()
    e2 = db.query(models.Echeance).filter_by(faitiere_id=f2.id).one()
    for e in (e1, e2):
        client.post(f"/echeances/{e.id}/paiements",
                    data={"montant": "500000", "date_paiement": TODAY.isoformat(), "mode": "virement"})
    p1 = db.query(models.Paiement).filter_by(echeance_id=e1.id).one()
    p2 = db.query(models.Paiement).filter_by(echeance_id=e2.id).one()
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=f1.id)
    rep = client_for("rep@psie.local")
    assert rep.get(f"/echeances/{e1.id}").status_code == 200
    assert rep.get(f"/echeances/{e2.id}").status_code == 404
    assert rep.get(f"/paiements/{p1.id}/recu.pdf").status_code == 200
    assert rep.get(f"/paiements/{p2.id}/recu.pdf").status_code == 404
    assert rep.get(f"/faitieres/{f1.id}/attestation.pdf").status_code == 200
    assert rep.get(f"/faitieres/{f2.id}/attestation.pdf").status_code == 404
    assert rep.get("/cotisations").status_code == 403
    assert rep.post(f"/echeances/{e1.id}/paiements",
                    data={"montant": "1", "date_paiement": TODAY.isoformat(), "mode": "virement"}).status_code == 403
    assert "LECIM" in rep.get(f"/faitieres/{f1.id}").text and "IQRA" not in rep.get(f"/faitieres/{f1.id}").text


def test_receipt_and_attestation_pdfs(db, setup):
    f1, _ = setup
    client = open_year(db)
    e = db.query(models.Echeance).filter_by(faitiere_id=f1.id).one()
    # Pas à jour : pas d'attestation
    assert client.get(f"/faitieres/{f1.id}/attestation.pdf").status_code == 409
    client.post(f"/echeances/{e.id}/paiements",
                data={"montant": "500000", "date_paiement": TODAY.isoformat(), "mode": "virement"})
    p = db.query(models.Paiement).one()
    receipt = client.get(f"/paiements/{p.id}/recu.pdf")
    assert receipt.status_code == 200 and receipt.content.startswith(b"%PDF") and len(receipt.content) > 5000
    att = client.get(f"/faitieres/{f1.id}/attestation.pdf")
    assert att.status_code == 200 and att.content.startswith(b"%PDF")


def test_public_verification(db, setup, anon):
    f1, _ = setup
    client = open_year(db)
    e = db.query(models.Echeance).filter_by(faitiere_id=f1.id).one()
    client.post(f"/echeances/{e.id}/paiements",
                data={"montant": "500000", "date_paiement": TODAY.isoformat(), "mode": "virement"})
    p = db.query(models.Paiement).one()
    page = anon.get(f"/verifier/{p.verify_token}")
    assert page.status_code == 200 and p.recu_numero in page.text and "LECIM" in page.text
    assert anon.get("/verifier/jetoinexistant").status_code == 404
    sig = finance.attestation_signature(f1.id, YEAR)
    assert anon.get(f"/verifier/attestation/{f1.id}/{YEAR}/{sig}").status_code == 200
    assert anon.get(f"/verifier/attestation/{f1.id}/{YEAR}/{'0' * 24}").status_code == 404
    # Une attestation d'une autre faîtière ne se déduit pas de la signature d'une autre
    assert anon.get(f"/verifier/attestation/999/{YEAR}/{sig}").status_code == 404
    # Reçu annulé : signalé
    client.post(f"/paiements/{p.id}/annuler", data={"motif": "erreur"})
    assert "annulé" in anon.get(f"/verifier/{p.verify_token}").text.lower()


def test_csv_export(db, setup):
    open_year(db)
    client = client_for("fin@psie.local")
    r = client.get(f"/cotisations/export.csv?annee={YEAR}")
    assert r.status_code == 200 and "LECIM" in r.text and "TOTAL" in r.text


def test_adhesion_fee_once_per_member(db, setup):
    f1, _ = setup
    client = client_for("fin@psie.local")
    r = client.post("/echeances/adhesion", data={"faitiere_id": str(f1.id), "montant": "100000"})
    assert r.status_code == 303
    assert client.post("/echeances/adhesion", data={"faitiere_id": str(f1.id), "montant": "100000"}).status_code == 409
    assert db.query(models.Echeance).filter_by(type="adhesion").count() == 1
