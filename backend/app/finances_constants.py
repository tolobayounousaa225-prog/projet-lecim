"""Barème statutaire des ressources de la LECIM (montants fixés par les textes)."""

ADHESION_MONTANT = 12000

# Montant total annuel et part reversée au bureau local, selon le statut de l'établissement.
# Valeurs statutaires exactes — ne pas recalculer par simple division, les montants
# indiqués dans les textes de la LECIM font foi tels quels.
COTISATION_RULES = {
    "non_subventionne": {"label": "Non subventionné", "montant_du": 7500, "part_bureau_local": 2500},
    "subventionne": {"label": "Subventionné", "montant_du": 20000, "part_bureau_local": 5000},
}

RECETTE_CATEGORIES = {
    "subvention": "Subvention",
    "don_legs": "Don ou legs",
    "vente_produit": "Vente de produits (cartes, gadgets...)",
    "produit_activite": "Produit des activités",
    "autre": "Autre ressource",
}
# Les ventes de livres et les droits d'examens ont leur propre section dédiée
# (modèles VenteLivre et DroitExamen) pour une meilleure clarté comptable —
# ils ne figurent plus dans les catégories de "Autres recettes" ci-dessus.


def cotisation_rule(statut: str) -> dict:
    return COTISATION_RULES.get(statut, COTISATION_RULES["non_subventionne"])
