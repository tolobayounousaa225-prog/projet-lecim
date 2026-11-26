"""Crée plusieurs comptes d'un coup à partir d'un fichier CSV.

Usage :
    python -m scripts.creer_comptes FICHIER.csv                 # simulation : montre ce qui serait créé, ne crée rien
    python -m scripts.creer_comptes FICHIER.csv --appliquer     # crée les comptes et envoie les invitations par e-mail
    python -m scripts.creer_comptes FICHIER.csv --appliquer --afficher-liens   # affiche aussi les liens (si l'e-mail ne part pas)
"""
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import comptes_import as ci
from app.database import SessionLocal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fichier")
    ap.add_argument("--appliquer", action="store_true")
    ap.add_argument("--afficher-liens", action="store_true")
    args = ap.parse_args()
    try:
        raw = Path(args.fichier).read_bytes()
        text = raw.decode("utf-8-sig") if raw else ""
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    except OSError as e:
        print(f"ERREUR : fichier illisible ({e})")
        return 2
    db = SessionLocal()
    try:
        rows = ci.parse(text, db)
        bad = [r for r in rows if r.errors]
        print(f"{len(rows)} ligne(s) lue(s)")
        for r in rows:
            state = "ERREUR : " + " ; ".join(r.errors) if r.errors else (f"ignorée : {r.skip}" if r.skip else "à créer")
            print(f"  ligne {r.line} : {r.nom} <{r.email}> — {r.role} — {state}")
        if bad:
            print(f"\n{len(bad)} ligne(s) en erreur : corrigez le fichier, rien n'a été créé.")
            return 1
        todo = [r for r in rows if not r.skip]
        if not args.appliquer:
            print(f"\nSimulation : {len(todo)} compte(s) seraient créés. Relancez avec --appliquer pour les créer.")
            return 0
        done = ci.apply(db, rows)
        print()
        for row, link, sent in done:
            print(f"✓ {row.email} : compte créé, invitation {'envoyée par e-mail' if sent else 'NON ENVOYÉE (e-mail non configuré ou refusé)'}")
            if args.afficher_liens or not sent:
                print(f"    lien (valable 7 jours, à transmettre en privé) : {link}")
        print(f"\n{len(done)} compte(s) créé(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
