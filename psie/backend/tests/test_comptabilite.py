import datetime

import pytest

from app import comptabilite, finance, models

from .conftest import client_for, make_faitiere, make_user

TODAY = datetime.date.today()
PDF = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n" + b"x" * 600
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def world(db):
    lecim = make_faitiere(db, "LECIM")
    iqra = make_faitiere(db, "IQRA")
    make_user(db, "den@psie.local", "den", name="Le DEN", origine_id=lecim.id)
    make_user(db, "fin@psie.local", "finances", name="Le Trésorier", origine_id=iqra.id)
    for role in ("admin", "administrateur_ca", "commissaire", "secretaire"):
        make_user(db, f"{role}@psie.local", role, name=role)
    return {"LECIM": lecim, "IQRA": iqra}


def new_depense(client, **extra):
    data = {"libelle": "Location de salle", "categorie": "fonctionnement", "montant": "150000",
            "date_depense": TODAY.isoformat()}
    data.update(extra)
    return client.post("/depenses", data=data)


def upload(client, depense_id, content=PDF, name="facture.pdf"):
    return client.post(f"/depenses/{depense_id}/justificatifs", files={"fichier": (name, content, "application/pdf")})


def depense(db):
    db.expire_all()
    return db.query(models.Depense).order_by(models.Depense.id.desc()).first()


# ---------- Dépenses : cycle complet et double signature ----------

def test_expense_lifecycle_with_two_signatures(db, world):
    fin, den = client_for("fin@psie.local"), client_for("den@psie.local")
    assert new_depense(fin).status_code == 303
    d = depense(db)
    assert d.statut == "a_valider"
    assert upload(fin, d.id).status_code == 303
    assert den.post(f"/depenses/{d.id}/signer").status_code == 303
    assert depense(db).statut == "a_valider"                       # une seule signature : pas encore payable
    assert fin.post(f"/depenses/{d.id}/payer", data={"date_paiement": TODAY.isoformat(), "mode": "virement"}).status_code == 409
    assert fin.post(f"/depenses/{d.id}/signer").status_code == 303
    d = depense(db)
    assert d.statut == "validee" and {v.role for v in d.validations} == {"den", "finances"}
    assert fin.post(f"/depenses/{d.id}/payer",
                    data={"date_paiement": TODAY.isoformat(), "mode": "virement", "reference": "VIR-9"}).status_code == 303
    d = depense(db)
    assert (d.statut, d.payee_le, d.reference_paiement) == ("payee", TODAY, "VIR-9")
    assert {a.action for a in db.query(models.AuditLog)} >= {"creation", "justificatif", "signature", "paiement"}


def test_signatories_must_come_from_different_organisations(db, world):
    make_user(db, "den2@psie.local", "den", origine_id=world["IQRA"].id)   # même organisation que le trésorier
    fin = client_for("fin@psie.local")
    new_depense(fin)
    d = depense(db)
    upload(fin, d.id)
    assert fin.post(f"/depenses/{d.id}/signer").status_code == 303
    same_org = client_for("den2@psie.local")
    assert same_org.post(f"/depenses/{d.id}/signer").status_code == 400       # Statuts art. 38
    assert depense(db).statut == "a_valider"
    assert client_for("den@psie.local").post(f"/depenses/{d.id}/signer").status_code == 303
    assert depense(db).statut == "validee"


def test_signature_requires_known_origin(db, world):
    make_user(db, "den3@psie.local", "den", origine_id=None)
    fin = client_for("fin@psie.local")
    new_depense(fin)
    d = depense(db)
    upload(fin, d.id)
    assert client_for("den3@psie.local").post(f"/depenses/{d.id}/signer").status_code == 400


def test_signature_requires_receipt_or_ca_exception(db, world):
    fin, den = client_for("fin@psie.local"), client_for("den@psie.local")
    new_depense(fin)
    d = depense(db)
    assert den.post(f"/depenses/{d.id}/signer").status_code == 400            # ni pièce ni décision du CA
    assert fin.post(f"/depenses/{d.id}/derogation", data={"reference": ""}).status_code == 400
    assert fin.post(f"/depenses/{d.id}/derogation", data={"reference": "Décision CA n°7"}).status_code == 303
    assert den.post(f"/depenses/{d.id}/signer").status_code == 303


def test_only_den_and_finance_secretary_sign(db, world):
    fin = client_for("fin@psie.local")
    new_depense(fin)
    d = depense(db)
    upload(fin, d.id)
    for role in ("admin", "administrateur_ca", "commissaire", "secretaire"):
        assert client_for(f"{role}@psie.local").post(f"/depenses/{d.id}/signer").status_code == 403, role
    client_for("den@psie.local").post(f"/depenses/{d.id}/signer")
    assert client_for("den@psie.local").post(f"/depenses/{d.id}/signer").status_code == 409   # déjà signée


def test_expense_creation_rules(db, world):
    fin = client_for("fin@psie.local")
    assert new_depense(fin, montant="0").status_code == 400
    assert new_depense(fin, montant="-5").status_code == 400
    assert new_depense(fin, categorie="cadeaux").status_code == 400
    assert new_depense(fin, libelle=" ").status_code == 400
    assert new_depense(fin, date_depense=(TODAY + datetime.timedelta(days=2)).isoformat()).status_code == 400
    assert new_depense(fin, categorie="mission").status_code == 400                      # ordre de mission requis
    assert new_depense(fin, categorie="mission", ordre_mission="OM-2026-12").status_code == 303
    assert db.query(models.Depense).count() == 1


def test_cancel_and_payment_rules(db, world):
    fin, den = client_for("fin@psie.local"), client_for("den@psie.local")
    new_depense(fin)
    d = depense(db)
    pay = {"date_paiement": TODAY.isoformat(), "mode": "virement"}
    assert fin.post(f"/depenses/{d.id}/payer", data=pay).status_code == 409              # pas validée
    assert fin.post(f"/depenses/{d.id}/annuler", data={"motif": ""}).status_code == 400
    assert fin.post(f"/depenses/{d.id}/annuler", data={"motif": "Doublon"}).status_code == 303
    assert depense(db).statut == "annulee" and db.query(models.Depense).count() == 1     # jamais supprimée
    assert den.post(f"/depenses/{d.id}/signer").status_code == 409                       # plus signable
    # dépense payée : non annulable
    new_depense(fin)
    d2 = depense(db)
    upload(fin, d2.id)
    den.post(f"/depenses/{d2.id}/signer")
    fin.post(f"/depenses/{d2.id}/signer")
    assert fin.post(f"/depenses/{d2.id}/payer", data={**pay, "mode": "troc"}).status_code == 400
    fin.post(f"/depenses/{d2.id}/payer", data=pay)
    assert fin.post(f"/depenses/{d2.id}/annuler", data={"motif": "Erreur"}).status_code == 409
    assert fin.post(f"/depenses/{d2.id}/payer", data=pay).status_code == 409             # pas deux fois


def test_only_finance_secretary_writes_expenses(db, world):
    for role in ("admin", "den", "administrateur_ca", "commissaire", "secretaire"):
        c = client_for(f"{role}@psie.local")
        assert new_depense(c).status_code == 403, role
    assert db.query(models.Depense).count() == 0
    new_depense(client_for("fin@psie.local"))
    d = depense(db)
    for role in ("den", "administrateur_ca", "commissaire"):
        c = client_for(f"{role}@psie.local")
        assert c.get(f"/depenses/{d.id}").status_code == 200                              # lecture
        assert c.post(f"/depenses/{d.id}/annuler", data={"motif": "x"}).status_code == 403
        assert upload(c, d.id).status_code == 403
    assert client_for("admin@psie.local").get("/depenses").status_code == 403            # administrateur technique : rien


# ---------- Justificatifs ----------

def test_receipt_upload_validation(db, world):
    fin = client_for("fin@psie.local")
    new_depense(fin)
    d = depense(db)
    # Un fichier qui se dit PDF mais n'en est pas un est refusé : on regarde le contenu
    assert upload(fin, d.id, b"<html><script>alert(1)</script></html>", "x.pdf").status_code == 400
    assert upload(fin, d.id, b"MZ\x90\x00 programme", "virus.pdf").status_code == 400
    assert upload(fin, d.id, b"").status_code == 400
    assert upload(fin, d.id, PDF + b"x" * (models.JUSTIFICATIF_MAX_BYTES + 10)).status_code == 413
    assert upload(fin, d.id, PNG, "scan.png").status_code == 303
    assert upload(fin, d.id, PDF, "../../etc/passwd.pdf").status_code == 303
    d = depense(db)
    assert [j.content_type for j in d.justificatifs] == ["image/png", "application/pdf"]
    assert d.justificatifs[1].nom == "passwd.pdf"                                        # chemin neutralisé
    assert len(d.justificatifs[0].sha256) == 64


def test_receipt_download_is_sandboxed_and_restricted(db, world, anon):
    fin = client_for("fin@psie.local")
    new_depense(fin)
    d = depense(db)
    upload(fin, d.id)
    j = depense(db).justificatifs[0]
    r = client_for("commissaire@psie.local").get(f"/justificatifs/{j.id}")
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    assert "sandbox" in r.headers["content-security-policy"]
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=world["LECIM"].id)
    assert client_for("rep@psie.local").get(f"/justificatifs/{j.id}").status_code == 403
    assert client_for("admin@psie.local").get(f"/justificatifs/{j.id}").status_code == 403
    assert anon.get(f"/justificatifs/{j.id}").status_code == 303
    assert fin.get("/justificatifs/9999").status_code == 404


def test_cannot_attach_to_closed_expense(db, world):
    fin = client_for("fin@psie.local")
    new_depense(fin)
    d = depense(db)
    fin.post(f"/depenses/{d.id}/annuler", data={"motif": "Erreur"})
    assert upload(fin, d.id).status_code == 409


# ---------- Dons ----------

DON = {"donateur_nom": "Moussa Traoré", "adresse": "Bouaké, quartier Commerce", "nature": "numeraire",
       "valeur": "50000", "date_don": TODAY.isoformat()}


def test_donation_register_mandatory_fields(db, world):
    fin = client_for("fin@psie.local")
    assert fin.post("/dons", data=DON).status_code == 303
    assert fin.post("/dons", data={**DON, "donateur_nom": " "}).status_code == 400
    assert fin.post("/dons", data={**DON, "adresse": ""}).status_code == 422                # champ vide : refusé
    page = fin.post("/dons", data={**DON, "adresse": ""}, headers={"accept": "text/html"})
    assert "adresse" in page.text and "<h1>" in page.text                                  # message lisible
    assert fin.post("/dons", data={**DON, "valeur": "0"}).status_code == 400
    assert fin.post("/dons", data={**DON, "nature": "bijoux"}).status_code == 400
    assert fin.post("/dons", data={**DON, "date_don": (TODAY + datetime.timedelta(days=1)).isoformat()}).status_code == 400
    assert db.query(models.Don).count() == 1


def test_enhanced_verification_above_threshold(db, world):
    fin = client_for("fin@psie.local")
    assert fin.post("/dons/seuil", data={"seuil": "abc"}).status_code == 400
    assert fin.post("/dons/seuil", data={"seuil": "1 000 000"}).status_code == 303
    assert comptabilite.seuil_don(db) == 1000000
    big = {**DON, "valeur": "1000000"}
    assert fin.post("/dons", data=big).status_code == 400                               # pièce et origine manquantes
    assert fin.post("/dons", data={**big, "piece_type": "cni", "piece_numero": "C0123"}).status_code == 400
    assert fin.post("/dons", data={**big, "piece_type": "cni", "piece_numero": "C0123",
                                   "origine_fonds": "Vente de récolte"}).status_code == 303
    assert fin.post("/dons", data={**DON, "valeur": "999999"}).status_code == 303        # sous le seuil
    flags = {d.valeur: d.verification_renforcee for d in db.query(models.Don)}
    assert flags == {1000000: True, 999999: False}
    fin.post("/dons/seuil", data={"seuil": ""})                                         # seuil retiré
    assert comptabilite.seuil_don(db) is None
    assert fin.post("/dons", data={**DON, "valeur": "9000000"}).status_code == 303


def test_threshold_and_donations_permissions(db, world):
    for role in ("den", "administrateur_ca", "commissaire"):
        c = client_for(f"{role}@psie.local")
        assert c.get("/dons").status_code == 200
        assert c.post("/dons/seuil", data={"seuil": "5"}).status_code == 403
        assert c.post("/dons", data=DON).status_code == 403
    assert client_for("admin@psie.local").get("/dons").status_code == 403


# ---------- Recettes et budget ----------

def test_other_receipts(db, world):
    fin = client_for("fin@psie.local")
    base = {"categorie": "subvention", "libelle": "Subvention ministère", "montant": "2000000",
            "date_recette": TODAY.isoformat()}
    assert fin.post("/recettes", data=base).status_code == 303
    assert fin.post("/recettes", data={**base, "categorie": "cotisation"}).status_code == 400   # compté automatiquement
    assert fin.post("/recettes", data={**base, "montant": "-1"}).status_code == 400
    assert client_for("den@psie.local").post("/recettes", data=base).status_code == 403


def test_budget_workflow(db, world):
    fin, den, ca = client_for("fin@psie.local"), client_for("den@psie.local"), client_for("administrateur_ca@psie.local")
    year = TODAY.year
    form = {"annee": str(year), "l_recette_cotisations": "3000000", "l_depense_fonctionnement": "1500000",
            "l_depense_mission": "800000"}
    assert ca.post("/budget/lignes", data=form).status_code == 403
    assert den.post("/budget/lignes", data=form).status_code == 303                      # le DEN élabore le budget
    assert fin.post("/budget/lignes", data={"annee": str(year), "l_depense_mission": "900000"}).status_code == 303
    assert fin.post("/budget/lignes", data={"annee": str(year), "l_depense_inconnue": "1"}).status_code == 400
    b = db.query(models.BudgetAnnee).one()
    assert {(l.sens, l.categorie): l.montant_prevu for l in b.lignes}[("depense", "mission")] == 900000
    assert fin.post("/budget/valider", data={"annee": str(year), "reference": ""}).status_code == 400
    assert ca.post("/budget/valider", data={"annee": str(year), "reference": "AGA"}).status_code == 403
    assert fin.post("/budget/valider", data={"annee": str(year), "reference": "Résolution AGA n°2"}).status_code == 303
    assert fin.post("/budget/lignes", data={"annee": str(year), "l_depense_mission": "1"}).status_code == 409   # figé
    assert fin.post("/budget/valider", data={"annee": str(year), "reference": "x"}).status_code == 409
    assert fin.post("/budget/valider", data={"annee": "2099", "reference": "x"}).status_code == 400


# ---------- États financiers ----------

def paid_expense(db, fin, den, montant, when, categorie="fonctionnement"):
    new_depense(fin, montant=str(montant), categorie=categorie, date_depense=when.isoformat())
    d = depense(db)
    upload(fin, d.id)
    den.post(f"/depenses/{d.id}/signer")
    fin.post(f"/depenses/{d.id}/signer")
    fin.post(f"/depenses/{d.id}/payer", data={"date_paiement": when.isoformat(), "mode": "virement"})


def test_financial_statement_totals_and_periods(db, world):
    fin, den = client_for("fin@psie.local"), client_for("den@psie.local")
    y = TODAY.year if TODAY.month > 6 else TODAY.year - 1       # année dont le 1er semestre est entièrement passé
    jan, aug = datetime.date(y, 1, 15), datetime.date(y, 8, 20)
    if aug > TODAY:
        aug = TODAY
    e = models.Echeance(faitiere_id=world["LECIM"].id, type="annuelle", annee=y, libelle="Cotisation", montant_du=500000)
    db.add(e)
    db.commit()
    db.add_all([
        models.Paiement(echeance_id=e.id, montant=300000, date_paiement=jan, mode="virement", recu_numero="R1", verify_token="t1"),
        models.Paiement(echeance_id=e.id, montant=100000, date_paiement=aug, mode="virement", recu_numero="R2", verify_token="t2"),
        models.Paiement(echeance_id=e.id, montant=50000, date_paiement=jan, mode="virement", recu_numero="R3",
                        verify_token="t3", annule=True),                                  # annulé : exclu
        models.Don(donateur_nom="X", adresse="Y", nature="numeraire", valeur=70000, date_don=jan),
        models.Don(donateur_nom="Z", adresse="Y", nature="nature", valeur=999000, date_don=jan),
        models.Recette(categorie="subvention", libelle="Subv", montant=1000000, date_recette=aug),
    ])
    db.commit()
    paid_expense(db, fin, den, 40000, jan)
    paid_expense(db, fin, den, 25000, aug, "formation")
    db.expire_all()
    full = comptabilite.etat_financier(db, y)
    assert full["recettes"]["Cotisations annuelles"] == 400000 and full["recettes"]["Dons en numéraire"] == 70000
    assert full["total_recettes"] == 400000 + 70000 + 1000000
    assert full["total_depenses"] == 65000 and full["solde"] == 1470000 - 65000
    assert full["dons_en_nature"] == 999000                                                 # hors caisse
    s1, s2 = comptabilite.etat_financier(db, y, "s1"), comptabilite.etat_financier(db, y, "s2")
    assert (s1["total_recettes"], s1["total_depenses"]) == (370000, 40000)
    assert (s2["total_recettes"], s2["total_depenses"]) == (1100000, 25000)
    assert s1["total_recettes"] + s2["total_recettes"] == full["total_recettes"]
    for url in (f"/etat-financier?annee={y}", f"/etat-financier.csv?annee={y}", f"/finances?annee={y}"):
        assert fin.get(url).status_code == 200, url
    assert fin.get(f"/etat-financier?annee={y}&periode=hiver").status_code == 400
    pdf = client_for("commissaire@psie.local").get(f"/etat-financier.pdf?annee={y}&periode=s1")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "Total recettes" in fin.get(f"/etat-financier.csv?annee={y}").text


def test_statement_budget_comparison_and_commitments(db, world):
    fin, den = client_for("fin@psie.local"), client_for("den@psie.local")
    y = TODAY.year
    den.post("/budget/lignes", data={"annee": str(y), "l_depense_fonctionnement": "100000", "l_recette_dons": "50000"})
    new_depense(fin, montant="30000")                                                       # engagée, non payée
    paid_expense(db, fin, den, 60000, TODAY)
    db.add(models.Don(donateur_nom="X", adresse="Y", nature="numeraire", valeur=20000, date_don=TODAY))
    db.commit()
    e = comptabilite.etat_financier(db, y)
    assert e["engagements_non_payes"] == 30000
    cmp = {(c["sens"], c["categorie"]): c for c in e["comparaison"]}
    dep = cmp[("depense", "Fonctionnement")]
    assert (dep["prevu"], dep["reel"], dep["ecart"]) == (100000, 60000, -40000)
    assert cmp[("recette", "Dons et legs")]["reel"] == 20000


def test_finance_pages_closed_to_representatives_and_anonymous(db, world, anon):
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=world["LECIM"].id)
    rep = client_for("rep@psie.local")
    urls = ["/finances", "/depenses", "/recettes", "/dons", "/budget", "/etat-financier", "/etat-financier.pdf",
            "/etat-financier.csv", "/rapports-cc", "/interets"]
    for url in urls:
        assert rep.get(url).status_code == 403, url
        assert anon.get(url).status_code == 303, url


# ---------- Contrôle ----------

def test_auditor_reports(db, world):
    co = client_for("commissaire@psie.local")
    data = {"annee": "2026", "titre": "Contrôle de caisse", "texte": "Caisse conforme au registre."}
    assert co.post("/rapports-cc", data=data).status_code == 303
    assert co.post("/rapports-cc", data={**data, "texte": " "}).status_code == 400
    emails = {"den": "den", "finances": "fin", "administrateur_ca": "administrateur_ca", "secretaire": "secretaire",
              "admin": "admin"}
    for role in emails:
        assert client_for(f"{emails[role]}@psie.local").post("/rapports-cc", data=data).status_code == 403, role
    for role in ("den", "finances", "administrateur_ca"):
        assert "Contrôle de caisse" in client_for(f"{emails[role]}@psie.local").get("/rapports-cc").text


def test_conflict_of_interest_declarations(db, world):
    den = client_for("den@psie.local")
    assert den.post("/interets", data={"objet": "Mon cousin loue la salle de réunion"}).status_code == 303
    assert den.post("/interets", data={"objet": " "}).status_code == 400
    assert "cousin" in client_for("commissaire@psie.local").get("/interets").text
    assert "cousin" not in client_for("secretaire@psie.local").get("/interets").text   # non lisible par tous
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=world["LECIM"].id)
    assert client_for("rep@psie.local").post("/interets", data={"objet": "x"}).status_code == 403


# ---------- Organisation d'origine ----------

def test_admin_sets_origin_for_signatories_only(db, world):
    adm = client_for("admin@psie.local")
    den2 = make_user(db, "den4@psie.local", "den")
    assert adm.post(f"/users/{den2.id}/origine", data={"origine_id": str(world["IQRA"].id)}).status_code == 303
    db.refresh(den2)
    assert den2.faitiere_origine_id == world["IQRA"].id
    ca = db.query(models.User).filter_by(role="administrateur_ca").one()
    assert adm.post(f"/users/{ca.id}/origine", data={"origine_id": str(world["IQRA"].id)}).status_code == 400
    assert adm.post(f"/users/{den2.id}/origine", data={"origine_id": "9999"}).status_code == 400
    assert client_for("den@psie.local").post(f"/users/{den2.id}/origine", data={"origine_id": ""}).status_code == 403
    r = adm.post("/users", data={"email": "nouveau@psie.local", "full_name": "N", "role": "finances",
                                 "password": "Motdepasse1", "origine_id": str(world["LECIM"].id)})
    assert r.status_code == 303
    assert db.query(models.User).filter_by(email="nouveau@psie.local").one().faitiere_origine_id == world["LECIM"].id
