"""Signature électronique : demande de code, confirmation, certificat PDF, vérification publique par QR."""

import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import models, notifier, pdfs, signatures
from ..audit import log_action
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_internal
from ..rate_limit import rate_limiter
from ..web import render

router = APIRouter()
confirm_limit = rate_limiter("signature-confirm", 20, 600)
verify_limit = rate_limiter("signature-verify", 60, 600)


def _read(user: models.User = Depends(require_internal)) -> models.User:
    if not user.can("documents"):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")
    return user


def _target(doc_type: str, doc_id: int, db: Session) -> str:
    if doc_type not in models.SIGNABLE:
        raise HTTPException(status_code=404, detail="Document introuvable")
    try:
        return signatures.document_fingerprint(db, doc_type, doc_id)[0]
    except signatures.SignatureError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _back(doc_type: str, doc_id: int, db: Session) -> str:
    if doc_type == "convention":
        return f"/conventions/{doc_id}"
    if doc_type == "registre":
        e = db.get(models.RegistreEntree, doc_id)
        return f"/registres/{e.registre}" if e else "/registres"
    return "/documents"


@router.get("/signatures/{sig_id:int}/certificat.pdf")
def signature_certificate(sig_id: int, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    sig = db.get(models.Signature, sig_id)
    if not sig:
        raise HTTPException(status_code=404, detail="Signature introuvable")
    url = f"{settings.public_base_url.rstrip('/')}/verifier/signature/{sig.token}"
    return Response(pdfs.signature_certificate_pdf(sig, url), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="signature-{sig.id}.pdf"', "Cache-Control": "private, no-store"})


@router.get("/signatures/{doc_type}/{doc_id}")
def signature_page(doc_type: str, doc_id: int, request: Request, sent: str = "", error: str = "", user: models.User = Depends(_read),
                   db: Session = Depends(get_db)):
    title = _target(doc_type, doc_id, db)
    existing = db.query(models.Signature).filter_by(doc_type=doc_type, doc_id=doc_id).order_by(models.Signature.id).all()
    return render(request, "signature.html", user, doc_type=doc_type, doc_id=doc_id, title=title, existing=existing,
                  refusal=signatures.can_sign(user, db, doc_type, doc_id), sent=bool(sent), error=error,
                  back=_back(doc_type, doc_id, db), kind=models.SIGNABLE[doc_type])


@router.post("/signatures/{doc_type}/{doc_id}/code")
def signature_code(doc_type: str, doc_id: int, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    _target(doc_type, doc_id, db)
    reason = signatures.can_sign(user, db, doc_type, doc_id)
    if reason:
        raise HTTPException(status_code=403, detail=reason)
    ok = signatures.request_code(db, user, doc_type, doc_id)
    db.commit()
    return RedirectResponse(f"/signatures/{doc_type}/{doc_id}?" + ("sent=1" if ok else "error=wait"), status_code=303)


@router.post("/signatures/{doc_type}/{doc_id}/confirmer", dependencies=[Depends(confirm_limit)])
def signature_confirm(doc_type: str, doc_id: int, code: str = Form(""), user: models.User = Depends(_read), db: Session = Depends(get_db)):
    _target(doc_type, doc_id, db)
    reason = signatures.can_sign(user, db, doc_type, doc_id)
    if reason:
        raise HTTPException(status_code=403, detail=reason)
    try:
        sig = signatures.confirm(db, user, doc_type, doc_id, code)
    except signatures.SignatureError as e:
        db.commit()                                              # le compteur d'essais doit être conservé
        return RedirectResponse(f"/signatures/{doc_type}/{doc_id}?error=" + ("wrong" if "incorrect" in str(e) else "code"), status_code=303)
    if doc_type == "convention":                                 # la signature clôt le circuit d'approbation
        c = db.get(models.Convention, doc_id)
        c.statut = "signee"
        db.add(models.ConventionEtape(convention_id=c.id, action="signer", par=user.full_name, role=user.role, commentaire=f"Signature électronique {sig.token[:8]}"))
        notifier.notify(db, [db.get(models.User, c.created_by_id)] if c.created_by_id else [], f"Convention signée : {c.titre}",
                        lien=f"/conventions/{c.id}", kind="convention", exclude_id=user.id)
    log_action(db, user, "signature", doc_type, doc_id, f"{sig.doc_titre} — {sig.doc_sha256[:12]}")
    db.commit()
    return RedirectResponse(f"/signatures/{doc_type}/{doc_id}", status_code=303)


@router.get("/verifier/signature/{token}", dependencies=[Depends(verify_limit)])
def signature_verify(token: str, request: Request, db: Session = Depends(get_db)):
    found = signatures.verify(db, token)
    if not found:
        raise HTTPException(status_code=404, detail="Signature non reconnue")
    sig, intact = found
    return render(request, "verifier_signature.html", None, sig=sig, intact=intact, kind=models.SIGNABLE.get(sig.doc_type, sig.doc_type))
