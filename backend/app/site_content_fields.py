"""Registre des blocs de texte du site vitrine modifiables depuis l'espace admin,
sans intervention d'un développeur. Chaque clé correspond à un élément marqué
`data-content-key="..."` dans les pages HTML publiques (voir assets/js/script.js,
fonction loadSiteContent). Une valeur vide en base = le texte par défaut de la
page reste affiché.
"""

SITE_CONTENT_FIELDS: dict[str, dict] = {
    "hero_badge": {
        "group": "Accueil — Bannière principale",
        "label": "Bandeau au-dessus du titre",
        "type": "text",
        "default": "Ligue des Établissements Confessionnels et Madrassas en Côte d'Ivoire",
    },
    "hero_title": {
        "group": "Accueil — Bannière principale",
        "label": "Titre principal",
        "type": "textarea",
        "default": "Bâtir une éducation islamique de qualité, unie et apolitique",
    },
    "hero_subtitle": {
        "group": "Accueil — Bannière principale",
        "label": "Texte sous le titre",
        "type": "textarea",
        "default": (
            "La LECIM fédère les écoles confessionnelles et madrassas de Côte d'Ivoire autour "
            "d'une même exigence : instruire, renforcer la foi et outiller chaque établissement "
            "pour la réussite de ses élèves."
        ),
    },
    "exam_title": {
        "group": "Accueil — Bandeau Examens",
        "label": "Titre du bandeau",
        "type": "text",
        "default": "Pour tous concernant les examens cliquer ici",
    },
    "exam_subtitle": {
        "group": "Accueil — Bandeau Examens",
        "label": "Sous-titre du bandeau",
        "type": "text",
        "default": "Inscriptions, résultats et informations sur les examens scolaires islamiques",
    },
    "missions_title": {
        "group": "Accueil — Section Missions",
        "label": "Titre de la section",
        "type": "text",
        "default": "Une action au service de l'éducation confessionnelle",
    },
    "missions_subtitle": {
        "group": "Accueil — Section Missions",
        "label": "Sous-titre de la section",
        "type": "textarea",
        "default": "Quatre grands axes structurent l'engagement de la LECIM auprès des établissements membres.",
    },
    "cta_title": {
        "group": "Accueil — Bandeau d'appel à l'action (bas de page)",
        "label": "Titre",
        "type": "text",
        "default": "Votre établissement souhaite rejoindre la LECIM ?",
    },
    "cta_subtitle": {
        "group": "Accueil — Bandeau d'appel à l'action (bas de page)",
        "label": "Sous-titre",
        "type": "textarea",
        "default": "Bénéficiez de l'accompagnement, des ressources et de la plateforme de gestion de la Ligue.",
    },
    "about_title": {
        "group": "À propos — Notre identité",
        "label": "Titre",
        "type": "text",
        "default": "Qui sommes-nous ?",
    },
    "about_p1": {
        "group": "À propos — Notre identité",
        "label": "Premier paragraphe",
        "type": "textarea",
        "default": (
            "La LECIM — Ligue des Établissements Confessionnels et Madrassas en Côte d'Ivoire — "
            "est une organisation fédérant les écoles confessionnelles islamiques et madrassas du pays."
        ),
    },
    "about_p2": {
        "group": "À propos — Notre identité",
        "label": "Deuxième paragraphe",
        "type": "textarea",
        "default": (
            "Elle se consacre à la promotion d'une éducation islamique de qualité, apolitique, "
            "et accompagne ses établissements membres dans leur gestion quotidienne comme dans "
            "leurs examens officiels."
        ),
    },
    "about_p3": {
        "group": "À propos — Notre identité",
        "label": "Troisième paragraphe",
        "type": "textarea",
        "default": (
            "À travers sa plateforme numérique de gestion scolaire, la LECIM modernise "
            "l'administration des écoles membres : préinscription, inscription, comptabilité, "
            "relances, notes, gestion des enseignants et impression des bulletins en français "
            "et en arabe."
        ),
    },
    "footer_description": {
        "group": "Pied de page (toutes les pages)",
        "label": "Texte de présentation",
        "type": "textarea",
        "default": "Ligue des Établissements Confessionnels et Madrassas en Côte d'Ivoire. Éducation islamique, unie et de qualité.",
    },
    "footer_copyright": {
        "group": "Pied de page (toutes les pages)",
        "label": "Mention de copyright",
        "type": "text",
        "default": "© 2026 LECIM — Tous droits réservés.",
    },
}
