"""Signature électronique simple (conventions, documents, entrées de registre).

Règle : la personne est connectée, elle demande un code, le reçoit par e-mail, le saisit. Le serveur enregistre alors qui
a signé, quand, et l'EMPREINTE du document à cet instant. Si le document change ensuite, la vérification publique le dit.
Ce n'est pas une signature qualifiée au sens juridique strict : c'est une preuve d'approbation interne, traçable."""

import datetime
import hashlib
import hmac
import json
import secrets

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .emailing import send_email

CODE_MINUTES = 10
MAX_ATTEMPTS = 5
COOLDOWN_SECONDS = 60


class SignatureError(ValueError):
    """Message lisible, affiché tel quel."""


def document_fingerprint(db: Session, doc_type: str, doc_id: int) -> tuple[str, str]:
    """(titre, empreinte SHA-256) de l'état actuel du document ; lève SignatureError s'il n'existe pas."""
    if doc_type == "convention":
        c = db.get(models.Convention, doc_id)
        if not c:
            raise SignatureError("Convention introuvable")
        body = json.dumps([c.titre, c.partenaire, c.objet, c.montant, str(c.date_debut), str(c.date_fin),
                           hashlib.sha256(c.contenu).hexdigest() if c.nom else ""], ensure_ascii=False, sort_keys=True)
        return c.titre, hashlib.sha256(body.encode()).hexdigest()
    if doc_type == "document":
        d = db.get(models.Document, doc_id)
        if not d:
            raise SignatureError("Document introuvable")
        return d.titre, d.sha256
    if doc_type == "registre":
        e = db.get(models.RegistreEntree, doc_id)
        if not e:
            raise SignatureError("Entrée introuvable")
        return f"{e.registre} n°{e.numero} — {e.titre}", e.empreinte
    raise SignatureError("Type de document inconnu")


def _hash_code(user_id: int, doc_type: str, doc_id: int, code: str) -> str:
    key = settings.secret_key.encode()
    return hmac.new(key, f"{user_id}:{doc_type}:{doc_id}:{code}".encode(), hashlib.sha256).hexdigest()


def request_code(db: Session, user: models.User, doc_type: str, doc_id: int, sender=None) -> bool:
    """Envoie un code. False si un code vient d'être envoyé (délai d'une minute) ou si l'e-mail n'a pas pu partir."""
    document_fingerprint(db, doc_type, doc_id)
    sender = sender or send_email
    now = datetime.datetime.utcnow()
    last = db.query(models.CodeSignature).filter_by(user_id=user.id, doc_type=doc_type, doc_id=doc_id).order_by(models.CodeSignature.id.desc()).first()
    if last and last.created_at > now - datetime.timedelta(seconds=COOLDOWN_SECONDS):
        return False
    db.query(models.CodeSignature).filter_by(user_id=user.id, doc_type=doc_type, doc_id=doc_id).delete()
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(models.CodeSignature(user_id=user.id, doc_type=doc_type, doc_id=doc_id, code_hash=_hash_code(user.id, doc_type, doc_id, code),
                                expires_at=now + datetime.timedelta(minutes=CODE_MINUTES)))
    db.flush()
    title, _ = document_fingerprint(db, doc_type, doc_id)
    return bool(sender(user.email, "PSIE — Code de signature",
                       f"Votre code pour signer « {title} » : {code}\n\nIl est valable {CODE_MINUTES} minutes et ne sert qu'une fois. "
                       "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message et prévenez l'administrateur.\n"))


def confirm(db: Session, user: models.User, doc_type: str, doc_id: int, code: str) -> models.Signature:
    row = db.query(models.CodeSignature).filter_by(user_id=user.id, doc_type=doc_type, doc_id=doc_id).first()
    now = datetime.datetime.utcnow()
    if not row or row.expires_at < now:
        raise SignatureError("Aucun code valide : demandez-en un nouveau.")
    if row.attempts >= MAX_ATTEMPTS:
        db.delete(row)
        raise SignatureError("Trop d'essais : demandez un nouveau code.")
    row.attempts += 1
    if not hmac.compare_digest(row.code_hash, _hash_code(user.id, doc_type, doc_id, (code or "").strip())):
        db.flush()
        raise SignatureError("Code incorrect.")
    title, sha = document_fingerprint(db, doc_type, doc_id)
    db.delete(row)                                        # un code ne sert qu'une fois
    sig = models.Signature(doc_type=doc_type, doc_id=doc_id, doc_titre=title[:255], doc_sha256=sha, signer_id=user.id,
                           signer_nom=user.full_name, signer_role=user.role, token=secrets.token_urlsafe(24))
    db.add(sig)
    db.flush()
    return sig


def verify(db: Session, token: str) -> tuple[models.Signature, bool] | None:
    """(signature, document inchangé depuis la signature ?) ou None si le jeton est inconnu."""
    sig = db.query(models.Signature).filter_by(token=token).first()
    if not sig:
        return None
    try:
        _, sha = document_fingerprint(db, sig.doc_type, sig.doc_id)
    except SignatureError:
        return sig, False                                 # document supprimé depuis
    return sig, hmac.compare_digest(sha, sig.doc_sha256)


def can_sign(user: models.User, db: Session, doc_type: str, doc_id: int) -> str | None:
    """None si la personne peut signer ce document, sinon la raison du refus."""
    if not user.is_internal:
        return "Réservé aux organes de la PSIE"
    if doc_type == "convention":
        c = db.get(models.Convention, doc_id)
        if not c:
            return "Convention introuvable"
        if user.role != "den":
            return "La signature des conventions est réservée au Directeur Exécutif National (Statuts)"
        if c.statut != "approuvee":
            return "La convention doit d'abord recevoir l'avis favorable du Conseil d'Administration"
        return None
    if not user.can("documents", True):
        return "Action non autorisée pour votre rôle"
    if doc_type == "document":
        d = db.get(models.Document, doc_id)
        return None if d else "Document introuvable"
    return None if db.get(models.RegistreEntree, doc_id) else "Entrée introuvable"
