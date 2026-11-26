"""Contenu du site vitrine : description des champs, validation et export.

Chaque « collection » correspond à un fichier du dossier data/ du site vitrine (actualites.json,
equipe.json…). L'export produit exactement la même forme, plus la liste des fichiers à récupérer :
le site se reconstruit donc à l'identique, que son contenu vienne de fichiers ou de cette application.
Les règles de validation reprennent celles de la construction du site (qui les revérifie).
"""

import datetime
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from . import models

SLUG_RE = re.compile(r"[a-z0-9-]{2,60}")
LINK_RE = re.compile(r"https://[^\s\"'<>]+")
SITE_RE = re.compile(r"https?://[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(:\d{1,5})?([/?#][^\s\"'<>]*)?")
DATE_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])")
PHONE_RE = re.compile(r"\d{8,15}")
LANGS = ("fr", "ar")

ORGANES = {"den": "Direction Exécutive Nationale", "ca": "Conseil d'Administration", "cc": "Commissariat aux Comptes"}
PARTENAIRE_TYPES = {"etat": "État", "technique": "Partenaire technique", "financier": "Partenaire financier"}
TRANSPARENCE_KINDS = {
    "rapport_activite": "Rapport d'activité", "etats_financiers": "États financiers", "budget": "Budget",
    "proces_verbal": "Procès-verbal", "rapport_cc": "Rapport des commissaires aux comptes", "autre": "Autre",
}


@dataclass
class Field:
    name: str
    label: str
    kind: str = "text"        # text long bi bilong date int float url site phone choice bool media
    required: bool = False
    choices: dict | None = None
    help: str = ""
    media: str = "image"      # pour kind == "media" : « image » ou « pdf »
    placeholder: str = ""


@dataclass
class Collection:
    key: str
    titre: str
    aide: str
    fields: list[Field]
    singleton: bool = False
    slug_from: str | None = None      # champ dont on tire l'identifiant si l'éditeur n'en donne pas
    slug_max: int = 60
    sort: str = "position"            # « position » (ordre choisi) ou « date »
    title: tuple[str, ...] = ()       # champs affichés dans la liste (le premier non vide)


def _bi(name, label, **kw):
    return Field(name, label, "bi", **kw)


COLLECTIONS: dict[str, Collection] = {c.key: c for c in [
    Collection("annonce", "Bandeau d'annonce", "Message affiché en haut de toutes les pages.", singleton=True, fields=[
        Field("actif", "Afficher le bandeau", "bool"),
        _bi("texte", "Texte"),
        Field("lien", "Lien (facultatif)", "url", help="Doit commencer par https://"),
    ], title=("texte",)),
    Collection("president", "Mot du Président", "Nom, photo et message du Président.", singleton=True, fields=[
        Field("nom", "Nom"),
        _bi("fonction", "Fonction"),
        Field("photo", "Photo", "media"),
        Field("message", "Message", "bilong"),
    ], title=("nom",)),
    Collection("contact", "Contact et réseaux sociaux", "WhatsApp, messages pré-remplis, liens des réseaux.", singleton=True, fields=[
        Field("whatsapp", "Numéro WhatsApp", "phone", help="Avec l'indicatif, sans + ni espaces. Exemple : 22507XXXXXXXX"),
        _bi("message", "Message WhatsApp (page Contact)"),
        _bi("message_partenariat", "Message WhatsApp (page Devenir partenaire)"),
        Field("facebook", "Facebook", "url", help="Lien https://"),
        Field("youtube", "YouTube", "url", help="Lien https://"),
        Field("instagram", "Instagram", "url", help="Lien https://"),
    ], title=("whatsapp",)),
    Collection("actualites", "Actualités", "Les nouvelles de la PSIE. Les plus récentes passent en premier.", slug_from="titre",
               sort="date", fields=[
        Field("date", "Date", "date", required=True),
        _bi("titre", "Titre", required=True),
        _bi("resume", "Résumé (une phrase)"),
        Field("contenu", "Contenu", "bilong", help="Un retour à la ligne = un nouveau paragraphe."),
        Field("image", "Image (facultative)", "media"),
        Field("slug", "Adresse de la page (facultatif)", help="Lettres minuscules, chiffres et tirets. Laissez vide : elle sera créée à partir du titre."),
    ], title=("titre",)),
    Collection("equipe", "Équipe (bureau exécutif)", "Les responsables présentés sur la page Équipe.", fields=[
        Field("nom", "Nom et prénoms", required=True),
        _bi("fonction", "Fonction"),
        Field("organisation", "Organisation d'origine"),
        Field("organe", "Organe", "choice", required=True, choices=ORGANES),
        Field("photo", "Photo", "media"),
    ], title=("nom",)),
    Collection("partenaires", "Partenaires", "L'État, les partenaires techniques et financiers.", fields=[
        Field("nom", "Nom", required=True),
        Field("type", "Type", "choice", required=True, choices=PARTENAIRE_TYPES),
        Field("logo", "Logo", "media"),
        Field("site_web", "Site web", "site"),
        _bi("description", "Description"),
    ], title=("nom",)),
    Collection("documents", "Documents à télécharger", "Statuts, règlement intérieur, formulaires… (PDF).", fields=[
        _bi("titre", "Titre", required=True),
        _bi("description", "Description"),
        Field("fichier", "Fichier PDF", "media", required=True, media="pdf"),
        Field("categorie", "Catégorie (facultatif)"),
    ], title=("titre",)),
    Collection("transparence", "Centre de transparence", "Rapports et états financiers publiés (PDF).", fields=[
        _bi("titre", "Titre", required=True),
        _bi("description", "Description"),
        Field("categorie", "Catégorie", "choice", required=True, choices=TRANSPARENCE_KINDS),
        Field("annee", "Année", "int", required=True),
        Field("fichier", "Fichier PDF", "media", required=True, media="pdf"),
    ], title=("titre",)),
    Collection("galerie", "Galerie photos", "Les photos de la page Galerie.", fields=[
        Field("image", "Photo", "media", required=True),
        _bi("legende", "Légende"),
        Field("date", "Date", "date"),
    ], title=("legende",)),
    Collection("faitieres", "Fiches des faîtières", "Présentation de chaque faîtière (page Membres).", slug_from="sigle",
               slug_max=40, fields=[
        Field("sigle", "Sigle", required=True),
        _bi("nom", "Nom complet"),
        Field("presentation", "Présentation", "bilong"),
        Field("logo", "Logo", "media"),
        Field("annee_creation", "Année de création"),
        Field("nombre_ecoles", "Nombre d'écoles", help="Exemple : 430+ (un nombre en tête permet le graphique de l'accueil)."),
        Field("telephone", "Téléphone"),
        Field("email", "E-mail"),
        Field("adresse", "Adresse"),
        Field("site_web", "Site web", "site"),
        Field("slug", "Adresse de la page (facultatif)", help="Laissez vide : elle sera créée à partir du sigle."),
    ], title=("sigle",)),
    Collection("regions", "DRENA et délégués régionaux", "Les 41 directions régionales : délégué, téléphone, position sur la carte.", fields=[
        Field("drena", "DRENA", required=True),
        Field("region", "Région"),
        Field("delegue", "Délégué"),
        Field("telephone", "Téléphone"),
        Field("lat", "Latitude", "float", help="Entre 3,5 et 11,5 (Côte d'Ivoire)."),
        Field("lon", "Longitude", "float", help="Entre -9,5 et -2,0."),
    ], title=("drena",)),
]}


class FormError(ValueError):
    pass


def collection(key: str) -> Collection | None:
    return COLLECTIONS.get(key)


# ---------------------------------------------------------------- lecture du formulaire

def form_name(f: Field, lang: str | None = None) -> str:
    return f"{f.name}__{lang}" if lang else f.name


def _text(value) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()


def slugify(text: str, maxlen: int = 60) -> str:
    base = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:maxlen].strip("-")


def parse(col: Collection, values: dict, media_lookup) -> tuple[dict, list[str]]:
    """Valide les valeurs du formulaire. Retourne (données, messages d'erreur).
    media_lookup(id) -> MediaSite | None."""
    data, errors = {}, []
    for f in col.fields:
        try:
            data[f.name] = _parse_field(f, values, media_lookup)
        except FormError as e:
            errors.append(f"{f.label} : {e}")
    return data, errors


def _parse_field(f: Field, v: dict, media_lookup):
    k = f.kind
    if k in ("bi", "bilong"):
        out = {lang: _text(v.get(form_name(f, lang))) for lang in LANGS}
        if f.required and not (out["fr"] or out["ar"]):
            raise FormError("renseignez au moins le français ou l'arabe")
        return out
    if k == "bool":
        return v.get(f.name) in ("on", "true", "1", True)
    if k == "media":
        raw = _text(v.get(form_name(f, "id")))
        if not raw:
            if f.required:
                raise FormError("un fichier est obligatoire")
            return None
        if not raw.isdigit() or not (m := media_lookup(int(raw))):
            raise FormError("fichier introuvable")
        if (m.extension == "pdf") != (f.media == "pdf"):
            raise FormError("type de fichier incorrect (PDF attendu)" if f.media == "pdf" else "une image est attendue")
        return int(raw)
    raw = _text(v.get(f.name))
    if not raw:
        if f.required:
            raise FormError("ce champ est obligatoire")
        return None if k in ("int", "float") else ""
    if k == "choice":
        if raw not in (f.choices or {}):
            raise FormError("choix invalide")
        return raw
    if k == "date":
        if not DATE_RE.fullmatch(raw) or not _real_date(raw):
            raise FormError("date invalide (format AAAA-MM-JJ)")
        return raw
    if k == "int":
        if not re.fullmatch(r"\d{1,6}", raw):
            raise FormError("un nombre entier est attendu")
        n = int(raw)
        if f.name == "annee" and not 2000 <= n <= 2100:
            raise FormError("l'année doit être comprise entre 2000 et 2100")
        return n
    if k == "float":
        try:
            n = float(raw.replace(",", "."))
        except ValueError:
            raise FormError("un nombre est attendu")
        if n != n or abs(n) > 1000:
            raise FormError("nombre invalide")
        return n
    if k == "phone":
        digits = re.sub(r"[\s+().-]", "", raw)
        if not PHONE_RE.fullmatch(digits):
            raise FormError("chiffres uniquement, avec l'indicatif (exemple : 22507XXXXXXXX)")
        return digits
    if k == "url":
        if not LINK_RE.fullmatch(raw):
            raise FormError("le lien doit commencer par https:// et ne pas contenir d'espace")
        return raw
    if k == "site":
        if "://" not in raw:
            raw = "https://" + raw
        if not SITE_RE.fullmatch(raw):
            raise FormError("adresse de site invalide")
        return raw
    if len(raw) > (20000 if k == "long" else 300):
        raise FormError("texte trop long")
    return raw


def _real_date(iso: str) -> bool:
    try:
        datetime.date.fromisoformat(iso)
    except ValueError:
        return False
    return True


def flatten(col: Collection, data: dict) -> dict:
    """Données enregistrées -> valeurs de formulaire (pour préremplir ou revalider)."""
    out = {}
    for f in col.fields:
        v = data.get(f.name)
        if f.kind in ("bi", "bilong"):
            v = v or {}
            for lang in LANGS:
                out[form_name(f, lang)] = v.get(lang, "")
        elif f.kind == "media":
            out[form_name(f, "id")] = "" if v is None else str(v)
        elif f.kind == "bool":
            out[f.name] = "on" if v else ""
        else:
            out[f.name] = "" if v is None else str(v)
    return out


def check_collection_rules(col: Collection, data: dict) -> list[str]:
    """Règles qui lient plusieurs champs."""
    errors = []
    if col.key == "regions":
        lat, lon = data.get("lat"), data.get("lon")
        if (lat is None) != (lon is None):
            errors.append("Position : renseignez la latitude ET la longitude, ou aucune des deux")
        elif lat is not None and not (3.5 <= lat <= 11.5 and -9.5 <= lon <= -2.0):
            errors.append("Position : coordonnées hors de la Côte d'Ivoire")
    if col.key == "contact" and data.get("whatsapp") and not (data["message"]["fr"] or data["message"]["ar"]):
        errors.append("Message WhatsApp (page Contact) : écrivez le message pré-rempli")
    return errors


def make_key(col: Collection, data: dict, taken: set[str]) -> str | None:
    """Identifiant (slug) d'un élément : celui saisi, sinon dérivé du titre/sigle ; rendu unique."""
    if col.singleton:
        return "main"
    if not col.slug_from:
        return None
    wanted = _text(data.get("slug"))
    if wanted:
        if not re.fullmatch(r"[a-z0-9-]{2,%d}" % col.slug_max, wanted):
            raise FormError(f"Adresse de la page : lettres minuscules, chiffres et tirets, {col.slug_max} caractères au plus")
        if wanted in taken:
            raise FormError("Adresse de la page : déjà utilisée par un autre élément")
        return wanted
    src = data.get(col.slug_from)
    text = (src.get("fr") or src.get("ar")) if isinstance(src, dict) else src
    base = slugify(text or "", col.slug_max - 5) or col.key[:6]
    if len(base) < 2:
        base += "-1"
    slug, n = base, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    return slug


# ---------------------------------------------------------------- lecture / export

def load(item: models.ContenuSite) -> dict:
    return json.loads(item.data)


MEDIA_GRACE_SECONDS = 60      # un fichier tout juste déposé n'est jamais supprimé (il peut être en cours d'enregistrement)


def referenced_media_ids(db) -> set[int]:
    """Identifiants des fichiers encore utilisés par un élément du site."""
    ids: set[int] = set()
    for row in db.query(models.ContenuSite):
        col = COLLECTIONS.get(row.collection)
        if not col:
            continue
        data = load(row)
        for f in col.fields:
            v = data.get(f.name)
            if f.kind == "media" and isinstance(v, int):
                ids.add(v)
    return ids


def purge_unused_media(db, grace_seconds: int | None = None) -> int:
    """Supprime de la base (et donc du site) les fichiers que plus aucun élément n'utilise : une photo supprimée par
    l'éditeur ne reste ni publiée, ni téléchargeable à son ancienne adresse. Retourne le nombre de fichiers supprimés."""
    import datetime

    grace = MEDIA_GRACE_SECONDS if grace_seconds is None else grace_seconds
    limit = datetime.datetime.utcnow() - datetime.timedelta(seconds=grace)
    db.flush()
    used = referenced_media_ids(db)
    removed = 0
    for m in db.query(models.MediaSite).filter(models.MediaSite.created_at < limit):
        if m.id not in used:
            db.delete(m)
            removed += 1
    return removed


def title_of(col: Collection, data: dict) -> str:
    for name in col.title:
        value = data.get(name)
        if isinstance(value, dict):
            value = value.get("fr") or value.get("ar")
        if value:
            return str(value)
    return "(sans titre)"


def items_of(db: Session, key: str) -> list[models.ContenuSite]:
    rows = (db.query(models.ContenuSite).filter_by(collection=key)
            .order_by(models.ContenuSite.position, models.ContenuSite.id).all())
    col = COLLECTIONS[key]
    if col.sort == "date":
        rows.sort(key=lambda r: load(r).get("date") or "", reverse=True)
    return rows


def media_path(m: models.MediaSite) -> str:
    return f"assets/media/{m.id}.{m.extension}"


def export_site(db: Session) -> dict:
    """Contenu complet au format des fichiers data/*.json du site vitrine.
    « media » liste les fichiers à récupérer (chemin dans le site, adresse, empreinte)."""
    medias = {m.id: m for m in db.query(models.MediaSite).all()}
    used: dict[int, models.MediaSite] = {}

    def resolve(data: dict, col: Collection) -> dict:
        out = dict(data)
        for f in col.fields:
            if f.kind == "media":
                m = medias.get(data.get(f.name) or 0)
                out[f.name] = media_path(m) if m else ""
                if m:
                    used[m.id] = m
        return out

    result: dict = {}
    for key, col in COLLECTIONS.items():
        rows = items_of(db, key)
        if col.singleton:
            result[key] = resolve(load(rows[0]), col) if rows else {}
            if key == "contact" and rows and not any(result[key]["message_partenariat"].values()):
                del result[key]["message_partenariat"]       # le site reprend alors le message général
            if key == "annonce" and rows:                  # forme attendue par le site : fr / ar à plat
                a = result[key]
                result[key] = {"actif": a["actif"], "fr": a["texte"]["fr"], "ar": a["texte"]["ar"], "lien": a["lien"]}
            continue
        items = []
        for r in rows:
            item = resolve(load(r), col)
            if col.slug_from:
                item["slug"] = r.cle
            items.append(item)
        result[key] = items
    result["media"] = [{"path": media_path(m), "url": f"/medias/{m.id}.{m.extension}", "sha256": m.sha256,
                        "taille": m.taille} for m in sorted(used.values(), key=lambda m: m.id)]
    body = json.dumps({k: v for k, v in result.items()}, sort_keys=True, ensure_ascii=False)
    result["version"] = hashlib.sha256(body.encode()).hexdigest()[:16]
    return result
