"""Correspondance approximative de texte, réutilisée par la recherche globale
(search_public.py) et l'assistant de réponse aux questions fréquentes
(assistant_public.py). Pas d'IA générative ni de dépendance externe — juste
difflib (bibliothèque standard) pour tolérer les fautes de frappe."""

import difflib


def score_text(term: str, *fields: str | None) -> float:
    """Score de pertinence d'un terme de recherche contre un ou plusieurs
    champs : 1.0 si un champ commence par le terme, un peu moins s'il le
    contient, sinon un score de similarité approximative (tolère les fautes
    de frappe) via difflib. On garde le meilleur score parmi les champs."""
    term_l = term.lower().strip()
    best = 0.0
    for field in fields:
        if not field:
            continue
        field_l = field.lower()
        if field_l.startswith(term_l):
            score = 1.0
        elif term_l in field_l:
            score = 0.75
        else:
            # Compare le terme à chaque mot du champ, pas au champ entier,
            # pour ne pas diluer la similarité dans un long texte.
            score = max(
                (difflib.SequenceMatcher(None, term_l, word).ratio() for word in field_l.split()),
                default=0.0,
            )
        best = max(best, score)
    return best
