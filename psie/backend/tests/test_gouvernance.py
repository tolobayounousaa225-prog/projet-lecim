import datetime

import pytest

from app import finance, gouvernance, models

from .conftest import client_for, make_faitiere, make_user

TODAY = datetime.date.today()
SIGLES = ["OEECI", "LECIM", "IQRA", "CHERIFLA", "HIKMA", "HINNEH"]


def make_mandat(db, organe, nom, faitiere=None, email=None, debut=None, fin=None):
    m = models.Mandat(organe=organe, full_name=nom, faitiere_id=faitiere.id if faitiere else None, email=email,
                      date_debut=debut or TODAY - datetime.timedelta(days=100),
                      date_fin=fin or TODAY + datetime.timedelta(days=900))
    db.add(m)
    db.commit()
    return m


@pytest.fixture
def world(db):
    """6 organisations membres, 2 délégués chacune, un utilisateur par rôle utile."""
    orgs = {}
    for s in SIGLES:
        f = make_faitiere(db, s)
        f.email = f"{s.lower()}@psie.local"
        db.commit()
        orgs[s] = f
        for i in (1, 2):
            make_mandat(db, "AG", f"Délégué {s} {i}", f)
    for role in ("den", "administrateur_ca", "secretaire", "finances", "commissaire"):
        make_user(db, f"{role}@psie.local", role)
    return orgs


def create(client, type_="AGA", days=20, **extra):
    data = {"type": type_, "date_assemblee": (TODAY + datetime.timedelta(days=days)).isoformat(), "heure": "09:00",
            "lieu": "Bouaké", "ordre_du_jour": "1. Rapports\n2. Budget", "mode_vote": "organisation"}
    data.update(extra)
    return client.post("/assemblees", data=data)


def assembly(db, client, type_="AGA", mode="organisation", **extra):
    """Crée une assemblée prête à siéger : convoquée, date ramenée à aujourd'hui, séance ouverte."""
    extra.setdefault("demande_age", "Demande conjointe DEN et CA" if type_ == "AGE" else "")
    create(client, type_=type_, mode_vote=mode, **extra)
    a = db.query(models.Assemblee).order_by(models.Assemblee.id.desc()).first()
    if type_ != "AGE":
        client.post(f"/assemblees/{a.id}/avis-ca", data={"reference": "Avis CA n°1"})
    assert client.post(f"/assemblees/{a.id}/convoquer").status_code == 303
    a.date_assemblee = TODAY
    db.commit()
    assert client.post(f"/assemblees/{a.id}/ouvrir").status_code == 303
    db.refresh(a)
    return a


def mark_present(client, db, a, sigles=None, per_org=1):
    ids = []
    for p in a.presences:
        if p.organe == "AG" and p.faitiere.sigle in (sigles or SIGLES):
            same = [x for x in ids if db.get(models.PresenceAG, x).faitiere_id == p.faitiere_id]
            if len(same) < per_org:
                ids.append(p.id)
    response = client.post(f"/assemblees/{a.id}/emargement", data={"present": [str(i) for i in ids]})
    db.expire_all()  # la session de test ne doit pas garder l'ancien émargement
    return response


def units(a, db):
    return gouvernance.voting_base(db, a)["units"]


def vote_all(client, db, a, r, choix):
    """choix : liste de choix appliquée dans l'ordre aux unités présentes."""
    db.refresh(a)
    data = {f"vote_{k}": c for k, c in zip(units(a, db), choix)}
    return client.post(f"/assemblees/{a.id}/resolutions/{r.id}/votes", data=data)


def resolution(db, client, a, regle="majorite"):
    client.post(f"/assemblees/{a.id}/resolutions", data={"intitule": "Adopter le rapport", "regle": regle})
    return db.query(models.Resolution).order_by(models.Resolution.id.desc()).first()


# ---------- Convocation ----------

def test_ordinary_assembly_needs_15_days_and_ca_opinion(db, world):
    den = client_for("den@psie.local")
    create(den, days=10)
    a = db.query(models.Assemblee).one()
    den.post(f"/assemblees/{a.id}/avis-ca", data={"reference": "Avis CA"})
    assert den.post(f"/assemblees/{a.id}/convoquer").status_code == 400          # 10 jours < 15
    a.date_assemblee = TODAY + datetime.timedelta(days=15)
    db.commit()
    assert den.post(f"/assemblees/{a.id}/convoquer").status_code == 303          # 15 jours : accepté
    db.refresh(a)
    assert a.statut == "convoquee" and a.convocation_at


def test_convocation_requires_ca_opinion(db, world):
    den = client_for("den@psie.local")
    create(den, days=30)
    a = db.query(models.Assemblee).one()
    assert den.post(f"/assemblees/{a.id}/convoquer").status_code == 400          # pas d'avis du CA
    assert den.post(f"/assemblees/{a.id}/avis-ca", data={"reference": " "}).status_code == 400
    assert client_for("finances@psie.local").post(f"/assemblees/{a.id}/avis-ca", data={"reference": "x"}).status_code == 403
    assert client_for("administrateur_ca@psie.local").post(
        f"/assemblees/{a.id}/avis-ca", data={"reference": "Avis CA du 3/5"}).status_code == 303
    assert den.post(f"/assemblees/{a.id}/convoquer").status_code == 303
    assert den.post(f"/assemblees/{a.id}/convoquer").status_code == 409          # déjà convoquée


def test_extraordinary_assembly_rules(db, world):
    den = client_for("den@psie.local")
    assert create(den, "AGE", days=3).status_code == 400                         # demande conjointe obligatoire
    assert create(den, "AGE", days=3, demande_age="DEN et CA").status_code == 303
    a = db.query(models.Assemblee).one()
    assert den.post(f"/assemblees/{a.id}/avis-ca", data={"reference": "x"}).status_code == 400   # pas d'avis requis
    assert den.post(f"/assemblees/{a.id}/convoquer").status_code == 303          # ni 15 jours ni avis du CA
    create(den, "AGE", days=-2, demande_age="DEN et CA")
    past = db.query(models.Assemblee).order_by(models.Assemblee.id.desc()).first()
    assert den.post(f"/assemblees/{past.id}/convoquer").status_code == 400


def test_convocation_emails_reach_members_and_organs(db, world):
    make_mandat(db, "CA", "Admin Un", world["LECIM"], email="admin1@psie.local")
    make_mandat(db, "CC", "Commissaire", None, email="cc@psie.local")
    make_mandat(db, "DEN", "Expiré", None, email="vieux@psie.local",
                debut=TODAY - datetime.timedelta(days=900), fin=TODAY - datetime.timedelta(days=10))
    susp = world["IQRA"]
    susp.statut = "suspendu"
    db.commit()
    den = client_for("den@psie.local")
    create(den, days=20)
    a = db.query(models.Assemblee).one()
    a.avis_ca_reference = "Avis"
    db.commit()
    to = gouvernance.convocation_recipients(db, a)
    assert "oeeci@psie.local" in to and "admin1@psie.local" in to and "cc@psie.local" in to
    assert "iqra@psie.local" not in to and "vieux@psie.local" not in to
    sent = []
    n = gouvernance.send_convocation(db, client_user(db, "den@psie.local"), a, sender=lambda *x: sent.append(x) or True)
    assert n == len(to) == len(sent) and "Bouaké" in sent[0][2] and "Rapports" in sent[0][2]


def client_user(db, email):
    return db.query(models.User).filter_by(email=email).one()


# ---------- Séance, émargement, quorum ----------

def test_opening_builds_attendance_list(db, world):
    make_mandat(db, "CA", "Admin Un", world["LECIM"])
    make_mandat(db, "AG", "Ancien délégué", world["LECIM"], fin=TODAY - datetime.timedelta(days=5))
    world["HINNEH"].statut = "suspendu"
    db.commit()
    den = client_for("den@psie.local")
    a = assembly(db, den)
    noms = {p.nom for p in a.presences}
    assert "Délégué OEECI 1" in noms and "Admin Un" in noms
    assert "Ancien délégué" not in noms                    # mandat expiré
    assert not any(n.startswith("Délégué HINNEH") for n in noms)   # organisation suspendue : ne siège pas


def test_session_cannot_open_before_date_or_before_convocation(db, world):
    den = client_for("den@psie.local")
    create(den, days=20)
    a = db.query(models.Assemblee).one()
    assert den.post(f"/assemblees/{a.id}/ouvrir").status_code == 409             # pas convoquée
    den.post(f"/assemblees/{a.id}/avis-ca", data={"reference": "Avis"})
    den.post(f"/assemblees/{a.id}/convoquer")
    assert den.post(f"/assemblees/{a.id}/ouvrir").status_code == 400             # avant la date


def test_quorum_by_organisation_is_two_thirds(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a, SIGLES[:3])
    db.refresh(a)
    assert gouvernance.voting_base(db, a)["quorum"] is False                     # 3/6
    mark_present(den, db, a, SIGLES[:4])
    assert gouvernance.voting_base(db, a)["quorum"] is True                      # 4/6 = 2/3 exactement
    r = resolution(db, den, a)
    assert vote_all(den, db, a, r, ["pour"] * 4).status_code == 303


def test_quorum_by_delegate_counts_individuals(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den, mode="delegue")
    mark_present(den, db, a, SIGLES, per_org=1)                                  # 6 délégués sur 12
    db.refresh(a)
    base = gouvernance.voting_base(db, a)
    assert (base["presents"], base["base"], base["quorum"]) == (6, 12, False)
    mark_present(den, db, a, SIGLES[:4], per_org=2)                              # 8 / 12
    assert gouvernance.voting_base(db, a)["quorum"] is True


def test_no_deliberation_without_quorum(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a, SIGLES[:2])
    r = resolution(db, den, a)
    assert den.post(f"/assemblees/{a.id}/resolutions/{r.id}/cloturer", data={"consensus": "1"}).status_code == 400
    assert den.post(f"/assemblees/{a.id}/resolutions/{r.id}/votes", data={}).status_code == 400


def test_unpaid_dues_do_not_block_attendance(db, world):
    f = world["OEECI"]
    db.add(models.Echeance(faitiere_id=f.id, type="annuelle", annee=TODAY.year, libelle="Cotisation",
                           montant_du=500000, date_limite=TODAY - datetime.timedelta(days=30)))
    db.commit()
    den = client_for("den@psie.local")
    a = assembly(db, den)
    assert mark_present(den, db, a, ["OEECI"]).status_code == 303
    db.refresh(a)
    assert any(p.present and p.faitiere_id == f.id for p in a.presences)
    page = client_for("finances@psie.local").get(f"/assemblees/{a.id}").text
    assert "En retard" in page                                                    # information seulement


# ---------- Résolutions et scrutins ----------

def test_majority_of_present_members(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a, SIGLES[:4])
    r = resolution(db, den, a)
    vote_all(den, db, a, r, ["pour", "pour", "contre", "abstention"])           # 2 pour sur 4 présents : pas > moitié
    den.post(f"/assemblees/{a.id}/resolutions/{r.id}/cloturer")
    db.refresh(r)
    assert (r.pour, r.contre, r.abstention, r.presents, r.adoptee) == (2, 1, 1, 4, False)
    r2 = resolution(db, den, a)
    vote_all(den, db, a, r2, ["pour", "pour", "pour", "abstention"])            # 3 sur 4 : adoptée
    den.post(f"/assemblees/{a.id}/resolutions/{r2.id}/cloturer")
    db.refresh(r2)
    assert r2.adoptee is True and r2.mode_adoption == "vote" and r2.numero == 2


def test_consensus_adoption(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a, SIGLES[:5])
    r = resolution(db, den, a)
    den.post(f"/assemblees/{a.id}/resolutions/{r.id}/cloturer", data={"consensus": "1"})
    db.refresh(r)
    assert (r.adoptee, r.mode_adoption, r.pour) == (True, "consensus", 5)


def test_close_without_votes_rejected(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a)
    r = resolution(db, den, a)
    assert den.post(f"/assemblees/{a.id}/resolutions/{r.id}/cloturer").status_code == 400


def test_dissolution_requires_age_and_four_fifths(db, world):
    den = client_for("den@psie.local")
    aga = assembly(db, den)
    assert den.post(f"/assemblees/{aga.id}/resolutions",
                    data={"intitule": "Dissoudre", "regle": "dissolution"}).status_code == 400
    age = assembly(db, den, "AGE")
    mark_present(den, db, age)
    r = resolution(db, den, age, "dissolution")
    assert den.post(f"/assemblees/{age.id}/resolutions/{r.id}/cloturer", data={"consensus": "1"}).status_code == 400
    vote_all(den, db, age, r, ["pour"] * 4 + ["contre"] * 2)                     # 4/6 < 4/5
    den.post(f"/assemblees/{age.id}/resolutions/{r.id}/cloturer")
    db.refresh(r)
    assert r.adoptee is False
    r2 = resolution(db, den, age, "dissolution")
    vote_all(den, db, age, r2, ["pour"] * 5 + ["contre"])                        # 5/6 >= 4/5
    den.post(f"/assemblees/{age.id}/resolutions/{r2.id}/cloturer")
    db.refresh(r2)
    assert r2.adoptee is True


def test_vote_validation_and_freeze(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a, SIGLES[:4])
    r = resolution(db, den, a)
    absent = f"o:{world['HINNEH'].id}"
    assert den.post(f"/assemblees/{a.id}/resolutions/{r.id}/votes", data={f"vote_{absent}": "pour"}).status_code == 400
    first = next(iter(units(a, db)))
    assert den.post(f"/assemblees/{a.id}/resolutions/{r.id}/votes", data={f"vote_{first}": "peut-etre"}).status_code == 400
    vote_all(den, db, a, r, ["pour"] * 4)
    den.post(f"/assemblees/{a.id}/resolutions/{r.id}/cloturer")
    assert vote_all(den, db, a, r, ["contre"] * 4).status_code == 409           # scrutin clos : voix figées
    assert mark_present(den, db, a, SIGLES).status_code == 409                   # émargement figé
    assert db.query(models.Vote).filter_by(choix="pour").count() == 4


def test_revoting_replaces_previous_voices(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a, SIGLES[:4])
    r = resolution(db, den, a)
    vote_all(den, db, a, r, ["pour"] * 4)
    vote_all(den, db, a, r, ["contre"] * 4)
    assert db.query(models.Vote).count() == 4 and db.query(models.Vote).filter_by(choix="contre").count() == 4


def test_closing_assembly_and_minutes(db, world):
    den = client_for("den@psie.local")
    a = assembly(db, den)
    mark_present(den, db, a, SIGLES[:5])
    r = resolution(db, den, a)
    assert den.post(f"/assemblees/{a.id}/cloturer",
                    data={"president": "Imam K.", "assesseur1": "A", "assesseur2": "B"}).status_code == 400  # scrutin ouvert
    assert den.get(f"/assemblees/{a.id}/pv.pdf").status_code == 409
    den.post(f"/assemblees/{a.id}/resolutions/{r.id}/cloturer", data={"consensus": "1"})
    assert den.post(f"/assemblees/{a.id}/cloturer", data={"president": "Imam K.", "assesseur1": "A"}).status_code == 400
    assert den.post(f"/assemblees/{a.id}/cloturer",
                    data={"president": "Imam K.", "assesseur1": "A", "assesseur2": "B"}).status_code == 303
    pv = den.get(f"/assemblees/{a.id}/pv.pdf")
    assert pv.status_code == 200 and pv.content.startswith(b"%PDF")
    assert den.post(f"/assemblees/{a.id}/resolutions", data={"intitule": "Trop tard"}).status_code == 409
    assert den.get(f"/assemblees/{a.id}/convocation.pdf").content.startswith(b"%PDF")


# ---------- Permissions ----------

def test_assembly_permissions(db, world):
    den = client_for("den@psie.local")
    create(den)
    a = db.query(models.Assemblee).one()
    for email in ("finances@psie.local", "commissaire@psie.local", "administrateur_ca@psie.local"):
        c = client_for(email)
        assert c.get(f"/assemblees/{a.id}").status_code == 200
        assert create(c).status_code == 403
        for action in ("convoquer", "ouvrir", "emargement", "cloturer", "resolutions"):
            assert c.post(f"/assemblees/{a.id}/{action}", data={"intitule": "x"}).status_code == 403, (email, action)


def test_representative_sees_only_convocation(db, world):
    den = client_for("den@psie.local")
    create(den)
    a = db.query(models.Assemblee).one()
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=world["LECIM"].id)
    rep = client_for("rep@psie.local")
    assert rep.get(f"/assemblees/{a.id}").status_code == 404                     # en préparation : invisible
    assert "Bouaké" not in rep.get("/assemblees").text
    den.post(f"/assemblees/{a.id}/avis-ca", data={"reference": "Avis"})
    den.post(f"/assemblees/{a.id}/convoquer")
    page = rep.get(f"/assemblees/{a.id}")
    assert page.status_code == 200 and "Bouaké" in page.text and "Délégué" not in page.text
    for url in (f"/assemblees/{a.id}/pv.pdf", f"/assemblees/{a.id}/convocation.pdf"):
        assert rep.get(url).status_code == 403
    assert rep.post(f"/assemblees/{a.id}/ouvrir").status_code == 403


# ---------- Sanctions ----------

def sanction(client, faitiere, type_="avertissement", **extra):
    data = {"faitiere_id": str(faitiere.id), "type": type_, "motif": "Absences répétées", "reference": "Avis CA n°4"}
    data.update(extra)
    return client.post("/sanctions", data=data)


def test_warning_and_blame_keep_member_active(db, world):
    den = client_for("den@psie.local")
    for t in ("avertissement", "blame"):
        assert sanction(den, world["IQRA"], t).status_code == 303
    db.refresh(world["IQRA"])
    assert world["IQRA"].statut == "actif" and db.query(models.Sanction).count() == 2


def test_suspension_removes_member_from_dues_and_vitrine_then_lift(db, world, anon):
    den, fin = client_for("den@psie.local"), client_for("finances@psie.local")
    assert sanction(den, world["IQRA"], "suspension").status_code == 303
    db.refresh(world["IQRA"])
    assert world["IQRA"].statut == "suspendu" and not world["IQRA"].is_membre_actif
    assert "IQRA" not in anon.get("/membres").text
    fin.post("/cotisations/bareme", data={"annee": str(TODAY.year), "montant": "500000"})
    fin.post("/cotisations/ouvrir", data={"annee": str(TODAY.year)})
    assert {e.faitiere.sigle for e in db.query(models.Echeance)} == set(SIGLES) - {"IQRA"}
    s = db.query(models.Sanction).one()
    assert den.post(f"/sanctions/{s.id}/lever", data={"motif": ""}).status_code == 400
    assert den.post(f"/sanctions/{s.id}/lever", data={"motif": "Situation régularisée"}).status_code == 303
    db.refresh(world["IQRA"])
    assert world["IQRA"].statut == "actif"
    assert den.post(f"/sanctions/{s.id}/lever", data={"motif": "encore"}).status_code == 409


def test_two_suspensions_member_stays_suspended_until_both_lifted(db, world):
    den = client_for("den@psie.local")
    sanction(den, world["IQRA"], "suspension")
    sanction(den, world["IQRA"], "suspension", reference="Avis CA n°5")
    s1, s2 = db.query(models.Sanction).order_by(models.Sanction.id).all()
    den.post(f"/sanctions/{s1.id}/lever", data={"motif": "levée"})
    db.refresh(world["IQRA"])
    assert world["IQRA"].statut == "suspendu"
    den.post(f"/sanctions/{s2.id}/lever", data={"motif": "levée"})
    db.refresh(world["IQRA"])
    assert world["IQRA"].statut == "actif"


def test_radiation_is_final_and_sanction_rules(db, world):
    den = client_for("den@psie.local")
    assert sanction(den, world["IQRA"], "radiation", reference="").status_code == 400      # référence obligatoire
    assert sanction(den, world["IQRA"], "avertissement", motif="").status_code == 400
    assert sanction(den, world["IQRA"], "inconnue").status_code == 400
    future = (TODAY + datetime.timedelta(days=2)).isoformat()
    assert sanction(den, world["IQRA"], "blame", date_decision=future).status_code == 400
    assert sanction(den, world["IQRA"], "radiation", reference="Résolution AGO n°7").status_code == 303
    db.refresh(world["IQRA"])
    assert world["IQRA"].statut == "radie"
    assert sanction(den, world["IQRA"], "avertissement").status_code == 409                # déjà radiée
    hon = make_faitiere(db, "HONNEUR", categorie="honneur")
    assert sanction(den, hon, "avertissement").status_code == 400                          # membres d'honneur exclus


def test_sanction_notification_and_permissions(db, world):
    den = client_for("den@psie.local")
    sanction(den, world["IQRA"], "blame")
    s = db.query(models.Sanction).one()
    assert den.get(f"/sanctions/{s.id}/notification.pdf").content.startswith(b"%PDF")
    den.post(f"/sanctions/{s.id}/notifier")
    db.refresh(s)
    assert s.notifiee_le == TODAY
    for email in ("finances@psie.local", "commissaire@psie.local", "administrateur_ca@psie.local"):
        c = client_for(email)
        assert c.get("/sanctions").status_code == 200
        assert sanction(c, world["LECIM"]).status_code == 403
        assert c.post(f"/sanctions/{s.id}/notifier").status_code == 403
    make_user(db, "rep@psie.local", "faitiere", faitiere_id=world["LECIM"].id)
    assert client_for("rep@psie.local").get("/sanctions").status_code == 403
    assert {a.action for a in db.query(models.AuditLog)} >= {"sanction", "notification"}


def test_composition_of_organs(db, world):
    for i in range(10):
        make_mandat(db, "CA", f"Administrateur {i}", world[SIGLES[i % 6]])
    make_mandat(db, "CC", "Commissaire 1")
    comp = {c["organe"]: (c["reel"], c["attendu"]) for c in gouvernance.composition_organes(db)}
    assert comp == {"CA": (10, 13), "DEN": (0, 13), "CC": (1, 2), "AG": (12, 12)}
    page = client_for("den@psie.local").get("/admin").text
    assert "10 / 13" in page and "12 / 12" in page
