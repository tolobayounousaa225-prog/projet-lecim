"""Finances : dépenses (double signature), justificatifs, recettes, dons, budget, états, contrôle."""

import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import comptabilite, models, pdfs
from ..audit import log_action
from ..database import get_db
from ..deps import get_current_user, require_internal
from ..finance import fcfa
from ..web import clean, parse_date, render
from .cotisations import require_finance_read, require_finance_write

router = APIRouter()
BUDGET_WRITE_ROLES = {"finances", "den"}


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _depense(db: Session, depense_id: int) -> models.Depense:
    d = db.get(models.Depense, depense_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dépense introuvable")
    return d


def _annee(annee: int | None) -> int:
    return annee or datetime.date.today().year


# ---------- Tableau des finances ----------

@router.get("/finances")
def finances_hub(request: Request, annee: int | None = None, user: models.User = Depends(require_finance_read),
                 db: Session = Depends(get_db)):
    annee = _annee(annee)
    return render(request, "finances.html", user, annee=annee, e=comptabilite.etat_financier(db, annee), fcfa=fcfa,
                  a_signer=[d for d in db.query(models.Depense).filter_by(statut="a_valider")
                            if user.role in models.SIGNATAIRE_ROLES and not d.validation_de(user.role)],
                  a_payer=db.query(models.Depense).filter_by(statut="validee").count())


# ---------- Dépenses ----------

@router.get("/depenses")
def depenses_list(request: Request, user: models.User = Depends(require_finance_read), db: Session = Depends(get_db)):
    items = db.query(models.Depense).order_by(models.Depense.id.desc()).all()
    return render(request, "depenses.html", user, items=items, fcfa=fcfa, categories=models.DEPENSE_CATEGORIES,
                  today=datetime.date.today())


@router.post("/depenses")
def depense_create(libelle: str = Form(...), categorie: str = Form(...), montant: int = Form(...),
                   date_depense: str = Form(...), beneficiaire: str = Form(""), ordre_mission: str = Form(""),
                   derogation: str = Form(""), user: models.User = Depends(require_finance_write),
                   db: Session = Depends(get_db)):
    when = parse_date(date_depense)
    if not when:
        raise HTTPException(status_code=400, detail="Date obligatoire")
    d = comptabilite.create_depense(db, user, libelle=libelle, categorie=categorie, montant=montant,
                                    date_depense=when, beneficiaire=beneficiaire, ordre_mission=ordre_mission,
                                    derogation=derogation)
    db.commit()
    return _redirect(f"/depenses/{d.id}")


@router.get("/depenses/{depense_id}")
def depense_detail(depense_id: int, request: Request, user: models.User = Depends(require_finance_read),
                   db: Session = Depends(get_db)):
    return render(request, "depense_detail.html", user, d=_depense(db, depense_id), fcfa=fcfa,
                  modes=models.MODES_PAIEMENT, today=datetime.date.today())


@router.post("/depenses/{depense_id}/justificatifs")
async def depense_justificatif(depense_id: int, fichier: UploadFile = File(...),
                               user: models.User = Depends(require_finance_write), db: Session = Depends(get_db)):
    d = _depense(db, depense_id)
    data = await fichier.read(models.JUSTIFICATIF_MAX_BYTES + 1)  # jamais plus que la limite en mémoire
    comptabilite.add_justificatif(db, user, d, fichier.filename or "piece", data)
    db.commit()
    return _redirect(f"/depenses/{d.id}")


@router.get("/justificatifs/{justificatif_id}")
def justificatif_download(justificatif_id: int, user: models.User = Depends(require_finance_read),
                          db: Session = Depends(get_db)):
    j = db.get(models.Justificatif, justificatif_id)
    if not j:
        raise HTTPException(status_code=404, detail="Pièce introuvable")
    ext = models.JUSTIFICATIF_TYPES.get(j.content_type, "bin")
    return Response(j.contenu, media_type=j.content_type, headers={
        "Content-Disposition": f'inline; filename="justificatif-{j.id}.{ext}"',
        # Document utilisateur : aucun script ni ressource externe, quoi qu'il contienne
        "Content-Security-Policy": "sandbox; default-src 'none'",
    })


@router.post("/depenses/{depense_id}/derogation")
def depense_derogation(depense_id: int, reference: str = Form(""), user: models.User = Depends(require_finance_write),
                       db: Session = Depends(get_db)):
    d = _depense(db, depense_id)
    if d.statut != "a_valider":
        raise HTTPException(status_code=409, detail="Cette dépense n'est plus à valider")
    if not reference.strip():
        raise HTTPException(status_code=400, detail="La référence de la décision du CA est obligatoire")
    d.derogation_ca_reference = reference.strip()
    log_action(db, user, "derogation_ca", "depense", d.id, reference.strip())
    db.commit()
    return _redirect(f"/depenses/{d.id}")


@router.post("/depenses/{depense_id}/signer")
def depense_sign(depense_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _depense(db, depense_id)
    comptabilite.sign_depense(db, user, d)
    db.commit()
    return _redirect(f"/depenses/{d.id}")


@router.post("/depenses/{depense_id}/payer")
def depense_pay(depense_id: int, date_paiement: str = Form(...), mode: str = Form(...), reference: str = Form(""),
                user: models.User = Depends(require_finance_write), db: Session = Depends(get_db)):
    d = _depense(db, depense_id)
    when = parse_date(date_paiement)
    if not when:
        raise HTTPException(status_code=400, detail="Date obligatoire")
    comptabilite.pay_depense(db, user, d, when, mode, reference)
    db.commit()
    return _redirect(f"/depenses/{d.id}")


@router.post("/depenses/{depense_id}/annuler")
def depense_cancel(depense_id: int, motif: str = Form(""), user: models.User = Depends(require_finance_write),
                   db: Session = Depends(get_db)):
    d = _depense(db, depense_id)
    comptabilite.cancel_depense(db, user, d, motif)
    db.commit()
    return _redirect(f"/depenses/{d.id}")


# ---------- Recettes ----------

@router.get("/recettes")
def recettes_list(request: Request, user: models.User = Depends(require_finance_read), db: Session = Depends(get_db)):
    items = db.query(models.Recette).order_by(models.Recette.date_recette.desc(), models.Recette.id.desc()).all()
    return render(request, "recettes.html", user, items=items, fcfa=fcfa, categories=models.RECETTE_CATEGORIES)


@router.post("/recettes")
def recette_create(categorie: str = Form(...), libelle: str = Form(...), source: str = Form(""),
                   montant: int = Form(...), date_recette: str = Form(...), reference: str = Form(""),
                   user: models.User = Depends(require_finance_write), db: Session = Depends(get_db)):
    when = parse_date(date_recette)
    if not when:
        raise HTTPException(status_code=400, detail="Date obligatoire")
    comptabilite.create_recette(db, user, categorie=categorie, libelle=libelle, source=source, montant=montant,
                                date_recette=when, reference=reference)
    db.commit()
    return _redirect("/recettes")


# ---------- Registre des dons ----------

@router.get("/dons")
def dons_list(request: Request, user: models.User = Depends(require_finance_read), db: Session = Depends(get_db)):
    items = db.query(models.Don).order_by(models.Don.date_don.desc(), models.Don.id.desc()).all()
    return render(request, "dons.html", user, items=items, fcfa=fcfa, seuil=comptabilite.seuil_don(db),
                  natures=models.DON_NATURES, pieces=models.PIECE_TYPES)


@router.post("/dons")
def don_create(donateur_nom: str = Form(...), adresse: str = Form(...), telephone: str = Form(""),
               piece_type: str = Form(""), piece_numero: str = Form(""), nature: str = Form("numeraire"),
               description: str = Form(""), valeur: int = Form(...), date_don: str = Form(...),
               origine_fonds: str = Form(""), user: models.User = Depends(require_finance_write),
               db: Session = Depends(get_db)):
    when = parse_date(date_don)
    if not when:
        raise HTTPException(status_code=400, detail="Date obligatoire")
    comptabilite.record_don(db, user, donateur_nom=donateur_nom, adresse=adresse, telephone=telephone,
                            piece_type=piece_type, piece_numero=piece_numero, nature=nature,
                            description=description, valeur=valeur, date_don=when, origine_fonds=origine_fonds)
    db.commit()
    return _redirect("/dons")


@router.post("/dons/seuil")
def don_seuil(seuil: str = Form(""), user: models.User = Depends(require_finance_write), db: Session = Depends(get_db)):
    seuil = seuil.strip().replace(" ", "")
    if seuil and not seuil.isdigit():
        raise HTTPException(status_code=400, detail="Seuil invalide")
    comptabilite.set_seuil_don(db, user, int(seuil) if seuil else None)
    db.commit()
    return _redirect("/dons")


# ---------- Budget ----------

@router.get("/budget")
def budget_page(request: Request, annee: int | None = None, user: models.User = Depends(require_finance_read),
                db: Session = Depends(get_db)):
    annee = _annee(annee)
    b = db.query(models.BudgetAnnee).filter_by(annee=annee).first()
    prevu = {(l.sens, l.categorie): l.montant_prevu for l in b.lignes} if b else {}
    return render(request, "budget.html", user, annee=annee, b=b, prevu=prevu, fcfa=fcfa,
                  rec_cats=models.BUDGET_RECETTE_CATEGORIES, dep_cats=models.DEPENSE_CATEGORIES,
                  can_write=user.role in BUDGET_WRITE_ROLES)


@router.post("/budget/lignes")
async def budget_lines(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in BUDGET_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Le budget est élaboré par la DEN et le secrétaire aux finances")
    form = await request.form()
    annee = int(form.get("annee", 0) or 0)
    for key, value in form.items():
        if key.startswith("l_") and str(value).strip():
            _, sens, categorie = key.split("_", 2)
            v = str(value).replace(" ", "")
            if not v.isdigit():
                raise HTTPException(status_code=400, detail=f"Montant invalide : {value}")
            comptabilite.set_budget_line(db, user, annee, sens, categorie, int(v))
    db.commit()
    return _redirect(f"/budget?annee={annee}")


@router.post("/budget/valider")
def budget_validate(annee: int = Form(...), reference: str = Form(""), user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if user.role not in BUDGET_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Action réservée à la DEN et au secrétaire aux finances")
    comptabilite.validate_budget(db, user, annee, reference)
    db.commit()
    return _redirect(f"/budget?annee={annee}")


# ---------- États financiers ----------

@router.get("/etat-financier")
def etat_page(request: Request, annee: int | None = None, periode: str = "annee",
              user: models.User = Depends(require_finance_read), db: Session = Depends(get_db)):
    annee = _annee(annee)
    return render(request, "etat_financier.html", user, annee=annee, periode=periode, periodes=comptabilite.PERIODES,
                  e=comptabilite.etat_financier(db, annee, periode), fcfa=fcfa)


@router.get("/etat-financier.csv")
def etat_csv(annee: int | None = None, periode: str = "annee", user: models.User = Depends(require_finance_read),
             db: Session = Depends(get_db)):
    annee = _annee(annee)
    content = comptabilite.etat_csv(comptabilite.etat_financier(db, annee, periode))
    return Response("﻿" + content, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="etat-financier-{annee}-{periode}.csv"'})


@router.get("/etat-financier.pdf")
def etat_pdf(annee: int | None = None, periode: str = "annee", user: models.User = Depends(require_finance_read),
             db: Session = Depends(get_db)):
    annee = _annee(annee)
    pdf = pdfs.etat_financier_pdf(comptabilite.etat_financier(db, annee, periode))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="etat-financier-{annee}-{periode}.pdf"'})


# ---------- Contrôle ----------

@router.get("/rapports-cc")
def rapports_list(request: Request, user: models.User = Depends(require_finance_read), db: Session = Depends(get_db)):
    items = db.query(models.RapportCC).order_by(models.RapportCC.id.desc()).all()
    return render(request, "rapports_cc.html", user, items=items, annee=datetime.date.today().year)


@router.post("/rapports-cc")
def rapport_create(annee: int = Form(...), titre: str = Form(""), texte: str = Form(""),
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "commissaire":
        raise HTTPException(status_code=403, detail="Seuls les commissaires aux comptes rédigent ces rapports")
    comptabilite.add_rapport_cc(db, user, annee, titre, texte)
    db.commit()
    return _redirect("/rapports-cc")


@router.get("/interets")
def interets_list(request: Request, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    items = db.query(models.DeclarationInteret).order_by(models.DeclarationInteret.id.desc()).all() \
        if user.can_view_finances else []
    return render(request, "interets.html", user, items=items)


@router.post("/interets")
def interet_create(objet: str = Form(""), user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    comptabilite.declare_interet(db, user, objet)
    db.commit()
    return _redirect("/interets")
