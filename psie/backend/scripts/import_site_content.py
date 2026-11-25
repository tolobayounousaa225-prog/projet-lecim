"""Importe le contenu actuel du site vitrine (dossier data/ et fichiers assets/) dans l'application.

Usage :
    python -m scripts.import_site_content /chemin/vers/le/depot/PSIE [--remplacer]

À lancer une fois, pour que l'équipe de communication reprenne en main un contenu déjà saisi.
Sans --remplacer, une rubrique qui contient déjà des éléments est laissée intacte (aucun doublon).
Les fichiers (logos, photos, PDF) passent par le même nettoyage que les envois depuis l'application.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import media, models, site_content as sc
from app.database import SessionLocal


def to_form_data(col: sc.Collection, raw: dict | list) -> dict:
    """Format des fichiers data/*.json -> forme enregistrée par l'application."""
    if col.key == "annonce":
        raw = {"actif": raw.get("actif"), "texte": {"fr": raw.get("fr", ""), "ar": raw.get("ar", "")}, "lien": raw.get("lien", "")}
    return raw


def import_file(db, root: Path, rel: str, kind: str):
    """Dépose un fichier du site dans la base et retourne son identifiant (ou None s'il est absent)."""
    if not rel:
        return None
    path = (root / rel).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        print(f"  ! fichier introuvable, ignoré : {rel}")
        return None
    try:
        data, mime, ext, digest = media.process(path.read_bytes(), kind)
    except media.MediaError as e:
        print(f"  ! {rel} refusé : {e}")
        return None
    m = db.query(models.MediaSite).filter_by(sha256=digest).first()
    if not m:
        m = models.MediaSite(nom=media.safe_name(path.name), mime=mime, extension=ext, taille=len(data), sha256=digest, contenu=data)
        db.add(m)
        db.flush()
    return m.id


def run(root: Path, replace: bool) -> int:
    db = SessionLocal()
    problems = 0
    try:
        for key, col in sc.COLLECTIONS.items():
            path = root / "data" / f"{key}.json"
            if not path.exists():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            items = [raw] if col.singleton else raw
            existing = db.query(models.ContenuSite).filter_by(collection=key)
            if existing.count() and not replace:
                print(f"{col.titre} : déjà renseigné, laissé tel quel")
                continue
            if replace:
                existing.delete()
            taken: set[str] = set()
            made = 0
            for position, entry in enumerate(items):
                entry = to_form_data(col, entry)
                if col.singleton and not any(v for v in entry.values() if v):
                    continue
                for f in col.fields:
                    if f.kind == "media":
                        entry[f.name] = import_file(db, root, entry.get(f.name, ""), f.media)
                values = sc.flatten(col, entry)
                data, errors = sc.parse(col, values, lambda i: db.get(models.MediaSite, i))
                errors += sc.check_collection_rules(col, data) if not errors else []
                if not errors:
                    try:
                        cle = sc.make_key(col, {**data, "slug": entry.get("slug", "")}, taken)
                    except sc.FormError as e:
                        errors.append(str(e))
                if errors:
                    problems += 1
                    print(f"  ! {col.titre} n°{position + 1} ignoré : " + " ; ".join(errors))
                    continue
                if cle:
                    taken.add(cle)
                    if "slug" in data:
                        data["slug"] = cle
                db.add(models.ContenuSite(collection=key, cle=cle, position=position, data=json.dumps(data, ensure_ascii=False)))
                made += 1
            print(f"{col.titre} : {made} élément(s) importé(s)")
        db.commit()
    finally:
        db.close()
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("depot", type=Path, help="dossier du dépôt du site vitrine (celui qui contient data/ et assets/)")
    parser.add_argument("--remplacer", action="store_true", help="remplace les rubriques déjà renseignées")
    args = parser.parse_args()
    sys.exit(1 if run(args.depot, args.remplacer) else 0)
