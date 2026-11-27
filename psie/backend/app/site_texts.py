"""Textes des pages de la vitrine modifiables depuis l'application (rubrique « Pages et textes »).

Chaque rubrique correspond à une clé du dictionnaire de textes du site (`content.T`) :
  - un « bloc de textes » : plusieurs champs bilingues, un par clé de texte du site ;
  - une « liste » : une suite d'éléments (questions de la FAQ, entrées du glossaire…).
Ce qui n'est pas renseigné garde le texte d'origine du site : on ne casse jamais une page en vidant un champ.
Les textes d'origine sont fournis dans site_defaults.json (généré par scripts/gen_site_defaults.py) pour pré-remplir
les formulaires : l'éditeur corrige l'existant au lieu de tout réécrire."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BLOC = "textes"          # clé de l'export JSON qui contient toutes ces rubriques

# clé de rubrique -> (titre, aide, [(clé de texte du site, libellé, « bi » court ou « bilong » long, aide)])
BLOCS = {
    "txt_accueil": ("Accueil : textes principaux", "Le grand titre, l'introduction et l'appel à adhérer de la page d'accueil.", [
        ("hero_kicker", "Petite ligne au-dessus du titre", "bi", ""),
        ("hero_title_a", "Titre (début)", "bi", ""),
        ("hero_title_hl", "Titre (partie mise en valeur)", "bi", ""),
        ("hero_intro", "Introduction", "bilong", ""),
        ("cta_title", "Appel à adhérer : titre", "bi", ""),
        ("cta_text", "Appel à adhérer : texte", "bilong", ""),
        ("footer_tag", "Devise du pied de page", "bi", ""),
    ]),
    "txt_apropos": ("À propos : textes", "Présentation de la PSIE, histoire et objet.", [
        ("about_lead", "Introduction", "bilong", ""),
        ("story", "Notre histoire", "bilong", "Un retour à la ligne = un nouveau paragraphe."),
        ("object", "Notre objet", "bilong", ""),
        ("timeline_lead", "Introduction de la chronologie", "bi", ""),
    ]),
    "txt_gouvernance": ("Gouvernance : textes", "Introduction de la page et présentation du réseau régional.", [
        ("gov_lead", "Introduction", "bilong", ""),
        ("regional", "Réseau régional", "bilong", ""),
    ]),
    "txt_adhesion": ("Adhésion : textes", "Les explications de la page « Adhérer ».", [
        ("join_lead", "Introduction", "bilong", ""),
        ("conditions_intro", "Introduction des conditions", "bilong", ""),
        ("process_note", "Note sur les montants et les délais", "bilong", ""),
    ]),
    "txt_contact": ("Contact : textes et coordonnées du siège", "Adresse et téléphones du siège, textes de la page Contact.", [
        ("contact_lead", "Introduction", "bilong", ""),
        ("contact_note", "Note", "bilong", ""),
        ("address", "Adresse du siège", "bi", ""),
        ("phone1", "Téléphone 1", "tel", "Tel qu'il doit s'afficher, par exemple +225 07 07 83 63 73."),
        ("phone2", "Téléphone 2", "tel", ""),
    ]),
    "txt_statuts": ("Statuts et droits : textes", "Introductions et notes des pages « Les statuts en bref » et « Droits et devoirs ».", [
        ("rules_lead", "Statuts : introduction", "bilong", ""),
        ("rules_note", "Statuts : note", "bilong", ""),
        ("rights_lead", "Droits et devoirs : introduction", "bilong", ""),
        ("rights_note", "Droits et devoirs : note", "bilong", ""),
    ]),
    "txt_guide": ("Guide et connexion : textes", "Introductions du guide de l'espace membre et de la page de connexion.", [
        ("guide_lead", "Guide : introduction", "bilong", ""),
        ("login_lead", "Connexion : introduction", "bilong", ""),
        ("login_help", "Connexion : aide", "bilong", ""),
    ]),
    "txt_legal": ("Confidentialité : introduction", "Phrase d'introduction de la page Confidentialité.", [
        ("privacy_lead", "Introduction", "bilong", ""),
    ]),
}

# clé de rubrique -> (titre, aide, clé de la liste dans le site, [(clé d'un élément, libellé, genre)], champ du titre)
LISTES = {
    "faq": ("FAQ : questions fréquentes", "Les questions et réponses de la page FAQ. Les premières s'affichent en premier.",
            "faq", [("q", "Question", "bi"), ("a", "Réponse", "bilong")], "q"),
    "guide_faq": ("Guide : questions fréquentes", "Les questions du guide de l'espace membre.",
                  "guide_faq", [("q", "Question", "bi"), ("a", "Réponse", "bilong")], "q"),
    "glossaire": ("Glossaire", "Les sigles et mots clés expliqués.",
                  "glossary", [("term", "Terme ou sigle", "bi"), ("full", "Forme complète (facultatif)", "bi"),
                               ("d", "Explication", "bilong")], "term"),
    "missions": ("Nos missions", "Les missions présentées sur l'accueil et la page À propos.",
                 "missions", [("t", "Titre", "bi"), ("d", "Description", "bilong")], "t"),
    "chronologie": ("Chronologie (À propos)", "Les grandes étapes de l'histoire.",
                    "timeline", [("date", "Date (texte libre)", "bi"), ("t", "Titre", "bi"), ("d", "Description", "bilong")], "t"),
    "statuts_points": ("Les statuts en 10 points", "Résumé pédagogique des statuts (le texte officiel reste celui des statuts).",
                       "rules", [("t", "Titre", "bi"), ("d", "Explication", "bilong")], "t"),
    "droits": ("Droits des membres", "La liste des droits.", "rights", [("t", "Titre", "bi"), ("d", "Explication", "bilong")], "t"),
    "devoirs": ("Devoirs des membres", "La liste des devoirs.", "duties", [("t", "Titre", "bi"), ("d", "Explication", "bilong")], "t"),
    "mentions": ("Mentions légales", "Les blocs de la page Mentions légales.",
                 "legal", [("t", "Titre du bloc", "bi"), ("p", "Texte", "bilong")], "t"),
    "confidentialite": ("Confidentialité : blocs", "Les blocs de la page Confidentialité.",
                        "privacy", [("t", "Titre du bloc", "bi"), ("p", "Texte", "bilong")], "t"),
}

PARAGRAPH_KEYS = {"story", "p"}      # textes que le site garde en liste de paragraphes


@lru_cache(maxsize=1)
def defaults() -> dict:
    p = Path(__file__).with_name("site_defaults.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
