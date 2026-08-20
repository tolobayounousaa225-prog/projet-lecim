"""Correspondance approximative de texte, réutilisée par la recherche globale
(search_public.py) et l'assistant de réponse aux questions fréquentes
(assistant_public.py). Pas d'IA générative ni de dépendance externe — juste
difflib (bibliothèque standard) pour tolérer les fautes de frappe."""

import difflib


def score_text(term: str, *fields: str | None) -> float:
    """Score de pertinence d'un terme de recherche contre un ou plusieurs
    champs : 1.0 si un champ commence par le terme, un peu moins s'il le
    contient, sinon le meilleur de trois signaux de similarité approximative :
    - comparaison mot à mot (bon pour un terme court contre un champ long) ;
    - comparaison des deux chaînes entières (bon pour une faute de frappe
      répartie sur toute la phrase) ;
    - recouvrement de mots communs (bon pour une question reformulée avec
      les mêmes mots dans un ordre différent, cas fréquent d'une question
      posée en langage naturel à l'assistant).
    On garde le meilleur score parmi les champs."""
    term_l = term.lower().strip()
    term_words = set(term_l.split())
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
            word_ratio = max(
                (difflib.SequenceMatcher(None, term_l, word).ratio() for word in field_l.split()),
                default=0.0,
            )
            whole_ratio = difflib.SequenceMatcher(None, term_l, field_l).ratio()
            field_words = set(field_l.split())
            overlap_ratio = (
                0.9 * len(term_words & field_words) / len(term_words) if term_words else 0.0
            )
            score = max(word_ratio, whole_ratio, overlap_ratio)
        best = max(best, score)
    return best
