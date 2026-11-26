"""Création de plusieurs comptes d'un coup à partir d'une liste (CSV exporté d'Excel).

Colonnes : nom ; e-mail ; rôle ; faîtière (sigle, seulement pour le rôle « faitiere ») ; organisation d'origine
(sigle, facultatif, pour le DEN et le secrétaire aux finances : contrôle de la double signature).
Aucun mot de passe n'est jamais choisi ni transmis : chaque personne reçoit un lien personnel (valable 7 jours)
pour choisir le sien. Un compte déjà existant n'est jamais modifié."""

import csv
import io
import re
import secrets
import unicodedata

from sqlalchemy.orm import Session

from . import models, password_reset
from .audit import log_action
from .config import settings
from .emailing import send_email
from .security import hash_password

MAX_ROWS = 200
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode())


# « Examens », « Secrétariat Examens », « examens »… : la clé du rôle, son libellé ou le mot principal sont acceptés
ROLE_ALIASES = {_norm(k): k for k in models.ROLES}
ROLE_ALIASES.update({_norm(v): k for k, v in models.ROLES.items()})
ROLE_ALIASES.update({"faitiere": "faitiere", "representant": "faitiere", "directeurexecutifnational": "den",
                     "administrateur": "admin", "financesecretaire": "finances", "secretairefinances": "finances",
                     "secretariatfinances": "finances", "secretariatcommunication": "communication",
                     "secretariatformation": "formation", "secretariatexamens": "examens", "secretariatressources": "ressources",
                     "commissairesauxcomptes": "commissaire", "ca": "administrateur_ca"})


class Row:
    def __init__(self, line: int, nom: str, email: str, role: str, faitiere: str, origine: str):
        self.line, self.nom, self.email, self.role, self.faitiere, self.origine = line, nom, email, role, faitiere, origine
        self.errors: list[str] = []
        self.skip: str | None = None          # raison pour laquelle la ligne est ignorée sans être une erreur


def parse(text: str, db: Session) -> list[Row]:
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    reader = [r for r in csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter) if any(c.strip() for c in r)]
    if reader and _norm(reader[0][0]) in ("nom", "nomcomplet", "name"):
        reader = reader[1:]
    if not reader:
        raise ValueError("Le fichier est vide.")
    if len(reader) > MAX_ROWS:
        raise ValueError(f"Trop de lignes ({len(reader)}) : {MAX_ROWS} comptes au maximum par fichier.")
    sigles = {_norm(f.sigle): f for f in db.query(models.Faitiere)}
    existing = {u.email for u in db.query(models.User)}
    seen: set[str] = set()
    rows: list[Row] = []
    for i, cells in enumerate(reader, start=2):
        cells = (cells + [""] * 5)[:5]
        row = Row(i, cells[0].strip(), cells[1].strip().lower(), cells[2].strip(), cells[3].strip(), cells[4].strip())
        if not row.nom:
            row.errors.append("nom manquant")
        if not EMAIL_RE.match(row.email):
            row.errors.append("adresse e-mail invalide")
        role = ROLE_ALIASES.get(_norm(row.role))
        if not role:
            row.errors.append(f"rôle inconnu « {row.role} » (rôles possibles : {', '.join(models.ROLES)})")
        row.role = role or row.role
        if role == "faitiere":
            if _norm(row.faitiere) not in sigles:
                row.errors.append(f"faîtière inconnue « {row.faitiere} »")
        elif row.faitiere:
            row.errors.append("une faîtière n'est indiquée que pour le rôle « faitiere »")
        if row.origine and _norm(row.origine) not in sigles:
            row.errors.append(f"organisation d'origine inconnue « {row.origine} »")
        if row.email in seen:
            row.errors.append("adresse e-mail en double dans le fichier")
        seen.add(row.email)
        if not row.errors and row.email in existing:
            row.skip = "un compte existe déjà avec cette adresse (laissé tel quel)"
        rows.append(row)
    return rows


def apply(db: Session, rows: list[Row], actor_label: str = "script", send=send_email) -> list[tuple[Row, str, bool]]:
    """Crée les comptes valides et envoie les invitations. Retourne (ligne, lien, e-mail envoyé)."""
    sigles = {_norm(f.sigle): f for f in db.query(models.Faitiere)}
    done = []
    for row in rows:
        if row.errors or row.skip:
            continue
        f = sigles.get(_norm(row.faitiere)) if row.role == "faitiere" else None
        o = sigles.get(_norm(row.origine)) if row.origine and row.role in models.SIGNATAIRE_ROLES else None
        user = models.User(email=row.email, full_name=row.nom, role=row.role, faitiere_id=f.id if f else None,
                           faitiere_origine_id=o.id if o else None, hashed_password=hash_password(secrets.token_urlsafe(32)))
        db.add(user)
        db.flush()
        token = password_reset.issue(db, user, minutes=password_reset.INVITATION_MINUTES)
        link = f"{settings.public_base_url.rstrip('/')}/mot-de-passe-oublie/{token}"
        log_action(db, None, "creation", "user", user.id, f"{user.email} ({row.role}, import par {actor_label})")
        role_label = models.ROLES.get(row.role, row.role)
        sent = send(user.email, "PSIE — Votre espace est prêt",
                    f"Bonjour {user.full_name},\n\nUn compte « {role_label} » vient d'être créé pour vous sur la plateforme de la PSIE.\n"
                    f"Choisissez votre mot de passe avec ce lien personnel (valable 7 jours, à usage unique) :\n{link}\n\n"
                    f"Ensuite, connectez-vous sur : {settings.public_base_url.rstrip('/')}/login\n\n"
                    f"مرحبا {user.full_name}،\nتم إنشاء حساب لكم على منصة PSIE. اختاروا كلمة مروركم عبر الرابط الشخصي أعلاه (صالح لمدة 7 أيام).\n\n"
                    "Plateforme des Structures Islamiques d'Éducation (PSIE)\n")
        done.append((row, link, bool(sent)))
    db.commit()
    return done
