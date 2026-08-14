"""Postes du Bureau Exécutif National (BEN) de la LECIM.

Chaque poste porte ses attributions statutaires, affichées dans l'espace personnel
du titulaire une fois connecté. Un même poste peut être occupé par un titulaire et,
le cas échéant, son adjoint (voir champ `is_adjoint` sur le modèle User).
"""

POSTES: dict[str, dict] = {
    "president": {
        "label": "Président",
        "attributions": [
            "Premier responsable de la LECIM",
            "Veille à l'application des décisions prises par le BEN",
            "Représente la LECIM devant les autorités religieuses, politiques, administratives et judiciaires",
            "Nomme et révoque librement les membres de son bureau",
            "Ordonne le budget et est cosignataire des comptes de la LECIM avec le chargé des finances",
            "Responsable devant le congrès et l'Assemblée Générale",
            "Consulte le CSC avant toute déclaration engageant la LECIM sur le plan national et international",
            "Convoque et préside toutes les réunions et manifestations de la LECIM",
            "Peut créer des structures et/ou des commissions spécialisées",
            "Coordonne les activités de tous les départements du BEN",
            "Prépare l'ordre du jour des réunions avec le secrétaire administratif",
        ],
    },
    "vp1_education": {
        "label": "1er Vice-Président — Éducation et Formation",
        "attributions": [
            "Assiste le président dans l'accomplissement de ses fonctions",
            "Assure l'intérim du président en cas d'absence, d'empêchement, de démission ou de décès",
            "Reçoit délégation de pouvoirs du président pour agir en son nom",
            "Fait appliquer le programme d'enseignement islamique",
            "Initie toute activité contribuant à la morale et à l'éducation islamique dans les établissements membres",
        ],
    },
    "vp2_interieur": {
        "label": "2e Vice-Président — Intérieur",
        "attributions": [
            "Assiste le président dans l'accomplissement de ses fonctions",
            "Assure l'intérim du président ou du 1er vice-président en cas d'absence, d'empêchement, de démission ou de décès",
            "Reçoit délégation de pouvoirs du président pour agir en son nom",
            "Assure la mise en place de la politique d'implantation de la LECIM",
            "Coordonne les activités des Comités Locaux et veille à leur bon fonctionnement",
            "S'occupe des documents liés à l'adhésion à la LECIM",
            "Supervise les activités de tous les secrétariats sous sa tutelle",
        ],
    },
    "sec_relations_exterieures": {
        "label": "Secrétaire chargé des Relations Extérieures",
        "attributions": [
            "Assure les relations avec les partenaires extérieurs (ONG, institutions, pays frères)",
            "Représente la LECIM auprès des réseaux internationaux de l'éducation islamique",
            "Identifie les opportunités de coopération et de financement à l'international",
        ],
    },
    "sec_administratif": {
        "label": "Secrétaire National Administratif",
        "attributions": [
            "Organe d'information de la LECIM",
            "Convoque les réunions, rédige et distribue les PV, comptes rendus et rapports",
            "Assure la tutelle du secrétariat permanent",
            "Gère les archives de la LECIM",
            "Reçoit et enregistre toutes les correspondances de la LECIM",
        ],
    },
    "sec_education_formation": {
        "label": "Secrétaire chargé de l'Éducation et de la Formation",
        "attributions": [
            "Met en œuvre les plans de formation au sein de la LECIM",
            "Suit l'application des programmes d'éducation et de renforcement des capacités",
            "Organise les sessions de formation pour les organes",
            "Sous la tutelle du 1er vice-président",
        ],
    },
    "sec_pedagogie_vie_scolaire": {
        "label": "Secrétaire chargé de la Pédagogie et des Activités de Vie Scolaire",
        "attributions": [
            "Développe les programmes pédagogiques harmonisés pour les madrassas et écoles affiliées",
            "Organise les formations pédagogiques pour les enseignants",
            "Suit l'implémentation des référentiels dans les établissements",
            "Organise les concours (Coran, arabe, culture islamique), colonies, voyages éducatifs",
            "Développe un calendrier national d'activités parascolaires",
            "Sous la tutelle du 1er vice-président",
        ],
    },
    "sec_interieur": {
        "label": "Secrétaire chargé de l'Intérieur",
        "attributions": [
            "Anime les antennes régionales, suit leurs activités, besoins et plans d'action",
            "Gère l'implantation et l'adhésion",
            "Représente le lien entre la coordination centrale et les structures locales",
            "Facilite la remontée des rapports locaux et la communication avec les délégués",
            "Sous la tutelle du 2e vice-président",
        ],
    },
    "sec_finances": {
        "label": "Secrétaire National chargé des Finances",
        "attributions": [
            "Gère les fonds de la LECIM",
            "Recouvre les droits d'adhésion et les cotisations",
            "Élabore le projet de budget",
            "Prépare et présente les rapports financiers du BEN",
            "Cosignataire avec le président des comptes de la LECIM",
            "Produit les pièces justificatives des dépenses et des recettes",
            "Présente un rapport financier au BEN tous les quatre mois",
        ],
    },
    "sec_communication_tic": {
        "label": "Secrétaire National chargé de la Communication et des TIC",
        "attributions": [
            "Met en œuvre la stratégie de communication de la LECIM (interne et externe)",
            "Gère les canaux numériques : site web, réseaux sociaux, bulletins",
            "Définit et applique la politique de communication entre les secrétariats et les organes",
            "Assure la promotion de l'image de marque et les relations avec la presse",
            "Assure l'animation des cérémonies du BEN",
        ],
    },
    "sec_affaires_sociales": {
        "label": "Secrétaire National chargé des Affaires Sociales et de la Solidarité",
        "attributions": [
            "Définit et applique la politique sociale de la LECIM",
            "Veille à la bonne entente, à la solidarité et à la fraternité entre les membres",
            "Apporte assistance aux membres en difficulté",
        ],
    },
    "sec_projets_patrimoine": {
        "label": "Secrétaire National chargé des Projets, de l'Équipement et du Patrimoine",
        "attributions": [
            "Gère l'équipement et le patrimoine de la LECIM",
            "Veille à la bonne utilisation et à la préservation des biens matériels",
            "Assure l'étude, le suivi et l'évaluation des différents projets du BEN",
        ],
    },
    "directeur_enseignement": {
        "label": "Directeur Général chargé de l'Enseignement Islamique",
        "attributions": [
            "Sous la tutelle du 1er vice-président chargé de l'éducation et de la formation",
            "Œuvre pour l'obtention de l'agrément des Structures Islamiques d'Éducation et la reconnaissance des diplômes",
            "Assure l'inspection générale des écoles affiliées à la LECIM",
            "Accomplit les missions confiées par le Président de la LECIM",
        ],
    },
    "secretariat_permanent": {
        "label": "Secrétariat Permanent",
        "attributions": [
            "Sous l'autorité du secrétaire national administratif",
            "Assiste à la rédaction des PV et autres documents administratifs",
            "Gère les archives de la LECIM",
            "Assure le fonctionnement des services administratifs et financiers",
        ],
    },
}

# ---------- Modules de la plateforme ----------
# Liste complète des fonctionnalités que l'administrateur peut activer/désactiver,
# individuellement, pour chaque compte. Rien n'est partagé par défaut : chaque
# secrétaire ne voit que ce que l'administrateur lui a explicitement accordé.
MODULES: dict[str, str] = {
    "reunions": "Réunions (ordre du jour, présence)",
    "membres": "Répertoire des membres",
    "documents": "Documents & PV",
    "photos": "Galerie photo",
    "news": "Actualités du site",
    "activities": "Activités du site",
    "contact": "Messages de contact",
    "finances": "Finances (établissements, adhésions, cotisations, recettes, dépenses, rapports)",
    "cartes_gestion": "Gestion des cartes de membres (validation, impression)",
    "partenaires": "Relations extérieures (annuaire des partenaires)",
    "projets_patrimoine": "Projets, équipement et patrimoine",
    "affaires_sociales": "Affaires sociales et solidarité",
    "publications": "Publications publiques du site (Règlement, Statuts, résultats aux examens...)",
    "executif": "Tableau de bord exécutif (vue d'ensemble de tous les domaines)",
    "delegations": "Délégations régionales (supervision des comités locaux)",
    "historique": "Historique des anciens présidents (photo, mandat, mot)",
    "gouvernance": "Gouvernance publique (photos des membres du BEN et de leurs adjoints)",
    "site_content": "Contenu du site (textes modifiables de la vitrine)",
    "enseignants": "Répertoire des enseignants des écoles membres",
    "resultats_examens": "Résultats aux examens scolaires islamiques (par établissement)",
    "sondages": "Gestion des sondages et votes électroniques (création, dépouillement)",
    "effectifs": "Effectifs des élèves des écoles membres (primaire/secondaire)",
    "cartes_scolaires": "Cartes scolaires des élèves (validation, impression)",
    "messagerie": "Messagerie avec les établissements membres",
    "adhesion_examen": "Examen et validation des demandes d'adhésion",
}

# Suggestion de cases pré-cochées lorsqu'un poste est sélectionné à la création
# d'un compte — un simple point de départ, modifiable librement par l'administrateur
# avant l'enregistrement. Un poste non listé ici démarre sans aucun module coché.
DEFAULT_MODULES_BY_POSTE: dict[str, list[str]] = {
    "president": ["reunions", "membres", "documents", "photos", "executif", "historique", "gouvernance", "site_content", "sondages", "adhesion_examen"],
    "vp1_education": ["reunions", "membres"],
    "vp2_interieur": ["reunions", "membres", "delegations", "adhesion_examen"],
    "sec_relations_exterieures": ["reunions", "partenaires"],
    "sec_administratif": ["reunions", "membres", "documents", "photos", "contact", "cartes_gestion", "sondages", "messagerie"],
    "sec_education_formation": ["reunions", "activities", "enseignants", "resultats_examens", "effectifs"],
    "sec_pedagogie_vie_scolaire": ["reunions", "activities", "enseignants", "resultats_examens", "effectifs", "cartes_scolaires"],
    "sec_interieur": ["reunions", "membres", "delegations", "adhesion_examen"],
    "sec_finances": ["finances"],
    "sec_communication_tic": ["reunions", "news", "photos", "publications", "historique", "gouvernance", "site_content"],
    "sec_affaires_sociales": ["reunions", "membres", "affaires_sociales"],
    "sec_projets_patrimoine": ["reunions", "documents", "projets_patrimoine"],
    "directeur_enseignement": ["reunions", "documents", "resultats_examens", "effectifs"],
    "secretariat_permanent": ["reunions", "membres", "documents", "photos", "contact", "cartes_gestion"],
}


# ---------- Rubriques de l'espace établissement ----------
# L'administrateur crée un compte "titulaire" (accès complet à son espace) et peut
# en plus autoriser un ou plusieurs comptes "secrétaire", chacun limité aux rubriques
# explicitement cochées ci-dessous.
ETAB_MODULES: dict[str, str] = {
    "cotisation": "Suivi de la cotisation",
    "resultats": "Résultats aux examens (CEPE, BEPC, BAC...)",
    "enseignants": "Gestion des enseignants",
    "effectifs": "Effectifs des élèves (primaire/secondaire)",
    "cartes_scolaires": "Demandes de cartes scolaires des élèves",
    "demandes": "Demandes administratives auprès du BEN",
    "annonces": "Annonces de la délégation régionale",
    "messagerie": "Messagerie avec le BEN",
    "ressources": "Bibliothèque pédagogique",
}


def default_modules_for_poste(key: str | None) -> list[str]:
    return DEFAULT_MODULES_BY_POSTE.get(key, [])


def poste_label(key: str | None) -> str:
    if not key:
        return "Administrateur"
    return POSTES.get(key, {}).get("label", key)


def poste_attributions(key: str | None) -> list[str]:
    if not key:
        return []
    return POSTES.get(key, {}).get("attributions", [])
