"""Pagination simple et réutilisable pour les listes admin volumineuses — évite de
charger des centaines/milliers de lignes d'un coup sur les tableaux qui grossissent
avec le temps (établissements, courrier...). Les exports (CSV/Excel) ne doivent
jamais passer par ici : ils restent volontairement sur la liste complète."""

from sqlalchemy.orm import Query

PAGE_SIZE = 50


def paginate(query: Query, page: int, page_size: int = PAGE_SIZE):
    """Retourne (items_de_la_page, total, nombre_de_pages, page_effective).
    Une page hors bornes (trop petite ou trop grande que le nombre de pages
    réellement disponible) est ramenée dans l'intervalle valide plutôt que de
    renvoyer une page vide ou de lever une erreur."""
    total = query.order_by(None).count()
    total_pages = max(1, -(-total // page_size))  # division entière arrondie au-dessus
    page = max(1, min(page, total_pages))
    items = query.limit(page_size).offset((page - 1) * page_size).all()
    return items, total, total_pages, page
