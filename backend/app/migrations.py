"""Migrations idempotentes exécutées à chaque démarrage de l'application — sans
dépendance à un outil de migration externe. Chaque étape se protège elle-même par
une vérification d'état avant d'agir, donc elle n'a plus aucun effet après son
premier passage réussi."""

import random

from sqlalchemy import inspect, text

from .database import Base, SessionLocal, engine

# Coordonnées approximatives (chef-lieu) des localités de Côte d'Ivoire utilisées
# comme "bureau local" dans les fiches établissement importées. Sert uniquement à
# positionner les écoles sur la carte publique au niveau de la ville/commune —
# une précision au mètre près n'est ni disponible ni nécessaire pour cet usage.
LOCALITE_COORDS: dict[str, tuple[float, float]] = {
    "ABENGOUROU": (6.7297, -3.4964),
    "ABIDJAN/ABOBO": (5.4297, -4.0447),
    "ABOBO": (5.4297, -4.0447),
    "ABOISSO": (5.4703, -3.2058),
    "ADJAME": (5.3599, -4.0247),
    "ADZOPE": (6.1042, -3.8628),
    "ANYAMA": (5.4949, -4.0511),
    "BONDOUKOU": (8.0402, -2.8000),
    "BOUAKE": (7.6906, -5.0300),
    "BOUNA": (9.2667, -3.0000),
    "DABOU": (5.3197, -4.3775),
    "DIANRA": (8.3500, -6.2000),
    "DIVO": (5.8372, -5.3572),
    "FERKE": (9.6000, -5.2000),
    "GBELEBAN": (9.7500, -7.4500),
    "GRAND LAHOU": (5.1414, -5.0197),
    "ISSIA": (6.4886, -6.5850),
    "KORHOGO": (9.4580, -5.6296),
    "KOUMASSI": (5.2939, -3.9569),
    "LAKOTA": (5.8500, -5.6833),
    "MAN": (7.4125, -7.5533),
    "MANKONO": (8.0575, -6.1875),
    "ODIENNE": (9.5062, -7.5654),
    "SAN PEDRO": (4.7485, -6.6363),
    "SEGUELA": (7.9614, -6.6731),
    "SINFRA": (6.6167, -5.9167),
    "SOUBRE": (5.7846, -6.5926),
    "VAVOUA": (7.3833, -6.4667),
    "YAMOUSSOUKRO": (6.8276, -5.2893),
    "YOPOUGON": (5.3453, -4.0725),
    "ZOUKOUGBEU": (6.9667, -6.0500),
}


# Découpage administratif officiel de Côte d'Ivoire : 14 districts au total — 2
# districts autonomes (Abidjan, Yamoussoukro), sans région propre — et 12 districts
# « ordinaires », eux-mêmes subdivisés en 31 régions au total. Chaque région
# appartient à exactement un des 12 districts ordinaires.
REGION_TO_DISTRICT: dict[str, str] = {
    "Agnéby-Tiassa": "District des Lagunes",
    "Grands-Ponts": "District des Lagunes",
    "La Mé": "District des Lagunes",
    "Gbôklé": "District du Bas-Sassandra",
    "Nawa": "District du Bas-Sassandra",
    "San-Pédro": "District du Bas-Sassandra",
    "Indénié-Djuablin": "District de la Comoé",
    "Sud-Comoé": "District de la Comoé",
    "Folon": "District du Denguélé",
    "Kabadougou": "District du Denguélé",
    "Gôh": "District du Gôh-Djiboua",
    "Lôh-Djiboua": "District du Gôh-Djiboua",
    "Bélier": "District des Lacs",
    "Iffou": "District des Lacs",
    "Moronou": "District des Lacs",
    "N'Zi": "District des Lacs",
    "Cavally": "District des Montagnes",
    "Guémon": "District des Montagnes",
    "Tonkpi": "District des Montagnes",
    "Haut-Sassandra": "District du Sassandra-Marahoué",
    "Marahoué": "District du Sassandra-Marahoué",
    "Gbêkê": "District de la Vallée du Bandama",
    "Hambol": "District de la Vallée du Bandama",
    "Bafing": "District du Woroba",
    "Béré": "District du Woroba",
    "Worodougou": "District du Woroba",
    "Bounkani": "District du Zanzan",
    "Gontougo": "District du Zanzan",
    "Bagoué": "District des Savanes",
    "Poro": "District des Savanes",
    "Tchologo": "District des Savanes",
}

# Correspondance commune/ville (valeur de bureau_local) -> (district, region). Les
# communes des 2 districts autonomes n'ont pas de région ; toutes les autres ont
# à la fois leur région et le district ordinaire dont elle dépend (via
# REGION_TO_DISTRICT ci-dessus). Sert uniquement de pré-remplissage au démarrage
# pour les communes reconnues ; toute commune absente de cette table laisse
# district/région vides, à compléter manuellement par l'admin.
COMMUNE_DISTRICT_REGION: dict[str, tuple[str | None, str | None]] = {
    "ABIDJAN/ABOBO": ("District Autonome d'Abidjan", None),
    "ABOBO": ("District Autonome d'Abidjan", None),
    "ADJAME": ("District Autonome d'Abidjan", None),
    "ANYAMA": ("District Autonome d'Abidjan", None),
    "KOUMASSI": ("District Autonome d'Abidjan", None),
    "YOPOUGON": ("District Autonome d'Abidjan", None),
    "YAMOUSSOUKRO": ("District Autonome de Yamoussoukro", None),
    "ABENGOUROU": (REGION_TO_DISTRICT["Indénié-Djuablin"], "Indénié-Djuablin"),
    "ABOISSO": (REGION_TO_DISTRICT["Sud-Comoé"], "Sud-Comoé"),
    "ADZOPE": (REGION_TO_DISTRICT["La Mé"], "La Mé"),
    "BONDOUKOU": (REGION_TO_DISTRICT["Gontougo"], "Gontougo"),
    "BOUAKE": (REGION_TO_DISTRICT["Gbêkê"], "Gbêkê"),
    "BOUNA": (REGION_TO_DISTRICT["Bounkani"], "Bounkani"),
    "DABOU": (REGION_TO_DISTRICT["Grands-Ponts"], "Grands-Ponts"),
    "DIANRA": (REGION_TO_DISTRICT["Worodougou"], "Worodougou"),
    "DIVO": (REGION_TO_DISTRICT["Lôh-Djiboua"], "Lôh-Djiboua"),
    "FERKE": (REGION_TO_DISTRICT["Tchologo"], "Tchologo"),
    "GBELEBAN": (REGION_TO_DISTRICT["Folon"], "Folon"),
    "GRAND LAHOU": (REGION_TO_DISTRICT["Grands-Ponts"], "Grands-Ponts"),
    "ISSIA": (REGION_TO_DISTRICT["Haut-Sassandra"], "Haut-Sassandra"),
    "KORHOGO": (REGION_TO_DISTRICT["Poro"], "Poro"),
    "LAKOTA": (REGION_TO_DISTRICT["Lôh-Djiboua"], "Lôh-Djiboua"),
    "MAN": (REGION_TO_DISTRICT["Tonkpi"], "Tonkpi"),
    "MANKONO": (REGION_TO_DISTRICT["Béré"], "Béré"),
    "ODIENNE": (REGION_TO_DISTRICT["Kabadougou"], "Kabadougou"),
    "SAN PEDRO": (REGION_TO_DISTRICT["San-Pédro"], "San-Pédro"),
    "SEGUELA": (REGION_TO_DISTRICT["Worodougou"], "Worodougou"),
    "SINFRA": (REGION_TO_DISTRICT["Marahoué"], "Marahoué"),
    "SOUBRE": (REGION_TO_DISTRICT["Nawa"], "Nawa"),
    "VAVOUA": (REGION_TO_DISTRICT["Haut-Sassandra"], "Haut-Sassandra"),
    "ZOUKOUGBEU": (REGION_TO_DISTRICT["Haut-Sassandra"], "Haut-Sassandra"),
}


def _deduire_district_region_depuis_commune() -> None:
    """Pré-remplit district/région à partir de la commune (bureau_local) pour les
    établissements qui n'ont ni l'un ni l'autre — ne touche jamais un
    établissement où l'un des deux est déjà renseigné (saisie manuelle admin
    prioritaire), et laisse vide si la commune n'est pas dans la table de
    correspondance ci-dessus."""
    from . import models

    db = SessionLocal()
    try:
        etablissements = (
            db.query(models.Etablissement)
            .filter(models.Etablissement.district.is_(None), models.Etablissement.region.is_(None))
            .all()
        )
        changed = False
        for e in etablissements:
            match = COMMUNE_DISTRICT_REGION.get((e.bureau_local or "").strip().upper())
            if not match:
                continue
            e.district, e.region = match
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _deduire_district_depuis_region() -> None:
    """Complète le district (l'un des 12 districts ordinaires) pour les
    établissements qui ont déjà une région renseignée mais pas de district —
    nécessaire car le découpage comporte en réalité 12 districts ordinaires (en
    plus des 2 districts autonomes), chaque région dépendant de l'un d'eux. Ne
    touche jamais un district déjà renseigné (saisie manuelle admin prioritaire)."""
    from . import models

    db = SessionLocal()
    try:
        etablissements = (
            db.query(models.Etablissement)
            .filter(models.Etablissement.district.is_(None), models.Etablissement.region.isnot(None))
            .all()
        )
        changed = False
        for e in etablissements:
            district = REGION_TO_DISTRICT.get((e.region or "").strip())
            if not district:
                continue
            e.district = district
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _geocode_etablissements_sans_coordonnees() -> None:
    """Positionne sur la carte les établissements dont la localité est reconnue
    mais qui n'ont pas encore de coordonnées précises — ne touche jamais un
    établissement ayant déjà une latitude/longitude (renseignée manuellement ou
    plus précisément par la suite)."""
    from . import models

    db = SessionLocal()
    try:
        etablissements = (
            db.query(models.Etablissement)
            .filter(models.Etablissement.latitude.is_(None), models.Etablissement.bureau_local.isnot(None))
            .all()
        )
        changed = False
        for e in etablissements:
            coords = LOCALITE_COORDS.get((e.bureau_local or "").strip().upper())
            if not coords:
                continue
            # Dispersion legere et deterministe (memes ecarts a chaque execution)
            # pour eviter que toutes les ecoles d'une meme ville se superposent.
            rng = random.Random(e.id)
            jitter_lat = (rng.random() - 0.5) * 0.06
            jitter_lon = (rng.random() - 0.5) * 0.06
            e.latitude = coords[0] + jitter_lat
            e.longitude = coords[1] + jitter_lon
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def run_startup_migrations() -> None:
    inspector = inspect(engine)

    if inspector.has_table("adhesion_requests"):
        columns = {c["name"] for c in inspector.get_columns("adhesion_requests")}
        if "code_demande" not in columns:
            # Ancien schéma (fonctionnalité introduite juste avant ce circuit complet,
            # sans donnée réelle en production) — recréée avec le nouveau schéma.
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE adhesion_requests CASCADE"))

    if inspector.has_table("partenaires"):
        columns = {c["name"] for c in inspector.get_columns("partenaires")}
        if "logo_path" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE partenaires ADD COLUMN logo_path VARCHAR(500)"))
        if "projet_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE partenaires ADD COLUMN projet_id INTEGER"))

    if inspector.has_table("photos"):
        columns = {c["name"] for c in inspector.get_columns("photos")}
        if "is_public" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE photos ADD COLUMN is_public BOOLEAN DEFAULT FALSE"))

    if inspector.has_table("etablissements"):
        columns = {c["name"] for c in inspector.get_columns("etablissements")}
        if "statut_agrement" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE etablissements ADD COLUMN statut_agrement VARCHAR(20) DEFAULT 'en_cours'"))
        if "date_expiration_agrement" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE etablissements ADD COLUMN date_expiration_agrement DATE"))
        if "is_ecole_modele" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE etablissements ADD COLUMN is_ecole_modele BOOLEAN DEFAULT FALSE"))
        if "categorie" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE etablissements ADD COLUMN categorie VARCHAR(20) DEFAULT 'membre'"))
        if "district" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE etablissements ADD COLUMN district VARCHAR(255)"))
        if "region" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE etablissements ADD COLUMN region VARCHAR(255)"))

    if inspector.has_table("news_posts"):
        columns = {c["name"] for c in inspector.get_columns("news_posts")}
        if "is_urgent" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE news_posts ADD COLUMN is_urgent BOOLEAN DEFAULT FALSE"))
        if "push_sent_at" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE news_posts ADD COLUMN push_sent_at TIMESTAMP"))

    if inspector.has_table("resultats_examens"):
        columns = {c["name"] for c in inspector.get_columns("resultats_examens")}
        if "nombre_admis_garcons" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE resultats_examens ADD COLUMN nombre_admis_garcons INTEGER DEFAULT 0"))
        if "nombre_admis_filles" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE resultats_examens ADD COLUMN nombre_admis_filles INTEGER DEFAULT 0"))

    if inspector.has_table("gouvernance_membres"):
        columns = {c["name"] for c in inspector.get_columns("gouvernance_membres")}
        if "niveau" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE gouvernance_membres ADD COLUMN niveau VARCHAR(20) DEFAULT 'autre'"))
        if "parent_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE gouvernance_membres ADD COLUMN parent_id INTEGER "
                    "REFERENCES gouvernance_membres(id) ON DELETE SET NULL"
                ))

    Base.metadata.create_all(bind=engine)

    if inspector.has_table("etablissements"):
        _geocode_etablissements_sans_coordonnees()
        _deduire_district_region_depuis_commune()
        _deduire_district_depuis_region()
