"""Petits utilitaires de défense en profondeur réutilisés par plusieurs routers :
échappement anti-injection pour les cellules CSV et les en-têtes HTTP construits à
partir de texte saisi par un utilisateur (formulaire public ou back-office)."""

_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    """Neutralise l'injection de formule dans les exports CSV (CWE-1236) : si la
    cellule ouverte dans Excel/LibreOffice/Sheets commence par un caractère qui y
    déclenche l'évaluation d'une formule (=, +, -, @, tabulation), elle est préfixée
    d'une apostrophe pour forcer une interprétation en texte brut. Nécessaire dès
    qu'une valeur exportée peut provenir d'une saisie non fiable (formulaire public,
    ou simple copier-coller d'un membre) plutôt que d'une donnée générée par le serveur."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_TRIGGERS):
        return "'" + text
    return text


def safe_content_disposition(filename: str | None, fallback: str = "fichier") -> str:
    """Construit une valeur d'en-tête Content-Disposition sûre à partir d'un nom de
    fichier potentiellement fourni par l'utilisateur (nom original d'un upload, titre
    saisi...) : retire les caractères de contrôle (retour à la ligne — injection
    d'en-tête HTTP) et échappe les guillemets pour ne pas rompre la chaîne
    "filename=\"...\"" du header."""
    text = (filename or "").strip()
    text = "".join(ch for ch in text if ch not in "\r\n\t" and ord(ch) >= 32)
    text = text.replace('"', "'")
    return text or fallback
