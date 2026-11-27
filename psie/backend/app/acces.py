"""Accès par rubrique : qui voit quoi, et qui peut modifier quoi.

Chaque rubrique (SECTIONS) a trois niveaux : 0 = invisible, 1 = lecture, 2 = écriture. Les valeurs par défaut
(DEFAULTS) donnent à chaque secrétariat ce qui le concerne ; l'administrateur les ajuste par rôle (AccesRole) et
peut faire une exception pour une personne (AccesUtilisateur). La rubrique est vérifiée sur le serveur pour chaque
adresse (jamais seulement masquée dans le menu).

Les pouvoirs que les Statuts attachent à une fonction (avis écrit du CA, double signature des dépenses par le DEN et
le secrétaire aux finances, rapports des commissaires aux comptes) restent liés au rôle : ils ne se délèguent pas ici.
"""

import re

AUCUN, LECTURE, ECRITURE = 0, 1, 2
LEVELS = {AUCUN: "Aucun accès", LECTURE: "Lecture", ECRITURE: "Lecture et modification"}

# clé : (libellé FR, libellé AR, explication)
SECTIONS = {
    "membres": ("Membres et mandats", "الأعضاء والانتدابات", "Fiches des faîtières, représentants, mandats, registre des membres, pièces justificatives."),
    "adhesions": ("Adhésions", "طلبات الانخراط", "Demandes d'adhésion, avis du CA, décision de l'AG, certificats."),
    "assemblees": ("Assemblées", "الجمعيات", "Convocations, émargement, résolutions, votes, procès-verbaux, documents."),
    "sanctions": ("Sanctions", "العقوبات", "Dossiers disciplinaires et notifications."),
    "finances": ("Finances et cotisations", "المالية والاشتراكات", "Cotisations, paiements, reçus, appels exceptionnels, dépenses, recettes, dons, budget, états financiers."),
    "ecoles": ("Écoles et suivi des faîtières", "المدارس ومتابعة المنظمات", "Écoles affiliées, recensement du personnel, résultats d'examens, bilans, statistiques par faîtière."),
    "documents": ("Documents, courrier et registres", "الوثائق والمراسلات والسجلات", "Documents de la PSIE, courrier arrivée et départ, conventions (circuit d'approbation), registres légaux des délibérations."),
    "formation": ("Formation", "التكوين", "Formations et sessions, inscriptions du personnel des faîtières, présence, certificats."),
    "supervision": ("Supervision des comptes", "متابعة الحسابات", "Lecture : voir l'activité de chaque compte. Modification : en plus, consulter l'espace d'un compte en lecture seule (voir ce qu'il voit)."),
    "interets": ("Déclarations d'intérêts", "تصريحات المصالح", "Conflits d'intérêts déclarés par les membres des organes."),
    "contenu": ("Contenu du site", "محتوى الموقع", "Actualités, équipe, partenaires, documents publics du site vitrine."),
}
SECTION_KEYS = tuple(SECTIONS)

# Rubriques d'administration : réservées à l'administrateur, hors de cette grille.
ADMIN_ONLY_PREFIXES = ("/users", "/audit", "/acces")

# Valeurs par défaut : chaque secrétariat ne voit que ce qui le concerne.
DEFAULTS: dict[str, dict[str, int]] = {
    # L'administrateur technique n'a pas accès aux finances par défaut (principe de séparation des fonctions).
    "admin": {"supervision": 2, "formation": 1, "documents": 2, "ecoles": 1, "membres": 2, "adhesions": 2, "assemblees": 2, "sanctions": 2, "interets": 2, "contenu": 2},
    "den": {"supervision": 2, "formation": 2, "documents": 2, "ecoles": 2, "membres": 2, "adhesions": 2, "assemblees": 2, "sanctions": 2, "finances": 1, "interets": 2},
    "secretaire": {"formation": 2, "documents": 2, "ecoles": 2, "membres": 2, "adhesions": 2, "assemblees": 2, "sanctions": 2, "interets": 2},
    "finances": {"documents": 1, "ecoles": 1, "finances": 2, "membres": 1, "assemblees": 1, "interets": 2},
    "communication": {"documents": 1, "contenu": 2, "interets": 2},
    "formation": {"formation": 2, "documents": 1, "ecoles": 2, "interets": 2},
    "examens": {"formation": 1, "documents": 1, "ecoles": 2, "interets": 2},
    "ressources": {"documents": 1, "ecoles": 1, "interets": 2},
    "administrateur_ca": {"formation": 1, "documents": 1, "ecoles": 1, "membres": 1, "adhesions": 1, "assemblees": 1, "sanctions": 1, "finances": 1, "interets": 2},
    "commissaire": {"documents": 1, "finances": 1, "interets": 2},
}

# Début de chemin -> rubrique. Une adresse hors de cette liste est accessible à tout compte connecté.
_PREFIXES = (
    ("/faitieres", "membres"), ("/registre-membres.pdf", "membres"), ("/pieces", "membres"), ("/mandats", "membres"),
    ("/adhesions", "adhesions"),
    ("/assemblees", "assemblees"), ("/annexes", "assemblees"),
    ("/sanctions", "sanctions"),
    ("/cotisations", "finances"), ("/echeances", "finances"), ("/paiements", "finances"), ("/appels", "finances"),
    ("/finances", "finances"), ("/depenses", "finances"), ("/justificatifs", "finances"), ("/recettes", "finances"),
    ("/dons", "finances"), ("/budget", "finances"), ("/etat-financier", "finances"), ("/rapports-cc", "finances"),
    ("/statistiques", "ecoles"), ("/ecoles", "ecoles"), ("/bilans", "ecoles"),
    ("/documents", "documents"), ("/courrier", "documents"), ("/conventions", "documents"), ("/registres", "documents"), ("/signatures", "documents"), ("/formations", "formation"), ("/supervision", "supervision"),
    ("/annonces", "membres"), ("/demandes", "membres"),
    ("/interets", "interets"),
    ("/gestion", "contenu"),
)
_ECOLES_PATH = re.compile(r"/faitieres/\d+/(ecoles|statistiques|export-ecoles\.csv)(/.*)?")
_FINANCE_DOCS = re.compile(r"/faitieres/\d+/(attestation|releve)\.pdf")


def section_for_path(path: str) -> str | None:
    if _FINANCE_DOCS.fullmatch(path):
        return "finances"
    if _ECOLES_PATH.fullmatch(path):
        return "ecoles"
    for prefix, section in _PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return section
    return None


def is_admin_only(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in ADMIN_ONLY_PREFIXES)


def defaults_for(role: str) -> dict[str, int]:
    return dict(DEFAULTS.get(role, {}))


def role_defaults_with_overrides(db, role: str) -> dict[str, int]:
    from . import models

    perms = defaults_for(role)
    for row in db.query(models.AccesRole).filter_by(role=role):
        if row.section in SECTIONS and row.niveau in LEVELS:
            perms[row.section] = row.niveau
    return perms


def effective(db, user) -> dict[str, int]:
    """Niveau de chaque rubrique pour cette personne : valeurs du rôle, puis exception personnelle."""
    from . import models

    perms = role_defaults_with_overrides(db, user.role)
    for row in db.query(models.AccesUtilisateur).filter_by(user_id=user.id):
        if row.section in SECTIONS and row.niveau in LEVELS:
            perms[row.section] = row.niveau
    return perms
