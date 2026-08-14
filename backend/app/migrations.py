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

    Base.metadata.create_all(bind=engine)

    if inspector.has_table("etablissements"):
        _geocode_etablissements_sans_coordonnees()
