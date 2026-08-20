import datetime

from sqlalchemy import Boolean, DateTime, Date, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .finances_constants import cotisation_rule
from .postes import poste_attributions, poste_label


class StoredFile(Base):
    """Fichier uploadé (photo, document, logo...) stocké en base de données
    plutôt que sur le disque du conteneur — le disque de Railway est éphémère
    et se réinitialise à chaque déploiement, ce qui faisait perdre tous les
    fichiers uploadés (incident du 2026-08-20). `path` sert de clé logique
    (ex. "documents/<uuid>.pdf"), exactement comme l'ancien chemin relatif
    sur disque, pour que les tables qui référencent un fichier n'aient pas eu
    besoin de changer de schéma."""

    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(300), unique=True, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Au plus un compte titulaire par établissement — un index unique partiel
        # plutôt qu'une simple vérification applicative, pour empêcher deux
        # créations concurrentes de laisser deux titulaires pour la même école.
        Index(
            "uq_user_etablissement_titulaire", "etablissement_id", unique=True,
            postgresql_where=text("is_etablissement_titulaire = true AND etablissement_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_level: Mapped[str] = mapped_column(String(20), default="bureau")  # "admin" | "bureau"
    poste: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_adjoint: Mapped[bool] = mapped_column(Boolean, default=False)
    # Liste de clés de modules séparées par des virgules (ex: "reunions,documents").
    # Source de vérité unique pour ce à quoi ce compte a accès — définie
    # explicitement par l'administrateur, aucun module n'est accordé par défaut.
    allowed_modules: Mapped[str] = mapped_column(Text, default="")
    # Si renseigné, ce compte est un compte "délégation régionale" (portail séparé),
    # distinct des comptes du Bureau Exécutif National (qui ont un `poste` à la place.)
    delegation_id: Mapped[int | None] = mapped_column(ForeignKey("delegations.id"), nullable=True)
    role_local: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Si renseigné, ce compte est un compte "établissement" (portail séparé, en lecture
    # quasi totale) rattaché à un établissement affilié précis.
    etablissement_id: Mapped[int | None] = mapped_column(ForeignKey("etablissements.id"), nullable=True)
    # Pour un compte établissement : le titulaire (créé en premier, en général le
    # directeur/directrice) a accès à tout son espace ; un compte secrétaire n'a
    # accès qu'aux rubriques explicitement cochées par l'administrateur (allowed_modules).
    is_etablissement_titulaire: Mapped[bool] = mapped_column(Boolean, default=True)
    # Verrouillage temporaire après plusieurs échecs de connexion consécutifs.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    delegation: Mapped["Delegation | None"] = relationship(foreign_keys=[delegation_id])
    etablissement: Mapped["Etablissement | None"] = relationship(foreign_keys=[etablissement_id])

    @property
    def poste_label(self) -> str:
        if self.delegation_id:
            base = self.role_local or "Compte délégation"
            return f"{base} — {self.delegation.nom}" if self.delegation else base
        if self.etablissement_id:
            return f"Compte établissement — {self.etablissement.nom}" if self.etablissement else "Compte établissement"
        label = poste_label(self.poste)
        return f"{label} (adjoint)" if self.is_adjoint and self.poste else label

    @property
    def attributions(self) -> list[str]:
        return poste_attributions(self.poste)

    @property
    def is_admin(self) -> bool:
        return self.access_level == "admin"

    @property
    def is_observer(self) -> bool:
        return self.access_level == "observateur"

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > datetime.datetime.utcnow())

    @property
    def allowed_modules_list(self) -> list[str]:
        return [m for m in (self.allowed_modules or "").split(",") if m]

    def has_module(self, key: str) -> bool:
        return self.is_admin or key in self.allowed_modules_list

    def has_etab_module(self, key: str) -> bool:
        """Pour les comptes établissement : le titulaire voit tout, un compte
        secrétaire ne voit que les rubriques cochées par l'administrateur."""
        if not self.is_etablissement_account:
            return False
        return self.is_etablissement_titulaire or key in self.allowed_modules_list

    @property
    def can_manage_reunions(self) -> bool:
        return self.has_module("reunions")

    @property
    def can_manage_membres(self) -> bool:
        return self.has_module("membres")

    @property
    def can_manage_documents(self) -> bool:
        return self.has_module("documents")

    @property
    def can_manage_photos(self) -> bool:
        return self.has_module("photos")

    @property
    def can_manage_news(self) -> bool:
        return self.has_module("news")

    @property
    def can_manage_activities(self) -> bool:
        return self.has_module("activities")

    @property
    def can_manage_contact(self) -> bool:
        return self.has_module("contact")

    @property
    def can_examine_adhesions(self) -> bool:
        return self.has_module("adhesion_examen")

    @property
    def can_manage_finances(self) -> bool:
        return self.has_module("finances")

    @property
    def can_manage_cartes(self) -> bool:
        return self.has_module("cartes_gestion")

    @property
    def can_manage_partenaires(self) -> bool:
        return self.has_module("partenaires")

    @property
    def can_manage_projets_patrimoine(self) -> bool:
        return self.has_module("projets_patrimoine")

    @property
    def can_manage_affaires_sociales(self) -> bool:
        return self.has_module("affaires_sociales")

    @property
    def can_manage_publications(self) -> bool:
        return self.has_module("publications")

    @property
    def can_manage_executif(self) -> bool:
        return self.has_module("executif")

    @property
    def can_manage_delegations(self) -> bool:
        return self.has_module("delegations")

    @property
    def can_manage_historique(self) -> bool:
        return self.has_module("historique")

    @property
    def can_manage_fondateurs(self) -> bool:
        return self.has_module("fondateurs")

    @property
    def can_manage_gouvernance(self) -> bool:
        return self.has_module("gouvernance")

    @property
    def can_manage_site_content(self) -> bool:
        return self.has_module("site_content")

    @property
    def can_manage_enseignants(self) -> bool:
        return self.has_module("enseignants")

    @property
    def can_manage_resultats_examens(self) -> bool:
        return self.has_module("resultats_examens")

    @property
    def can_manage_sondages(self) -> bool:
        return self.has_module("sondages")

    @property
    def can_manage_effectifs(self) -> bool:
        return self.has_module("effectifs")

    @property
    def can_manage_cartes_scolaires(self) -> bool:
        return self.has_module("cartes_scolaires")

    @property
    def can_manage_messagerie(self) -> bool:
        return self.has_module("messagerie")

    def pending_action_counts(self) -> dict[str, int]:
        """Nombre d'éléments en attente d'action par rubrique de la barre latérale
        admin (ex : ressources non publiées, dons non confirmés...) — calculé via
        la session déjà ouverte qui a chargé ce compte, sans dépendance
        supplémentaire à passer depuis chaque route. Ne renvoie que les clés dont
        le compte a le module correspondant, avec un compte strictement positif."""
        from sqlalchemy.orm import object_session

        db = object_session(self)
        if db is None:
            return {}

        counts: dict[str, int] = {}
        if self.can_manage_publications:
            counts["ressources"] = (
                db.query(RessourcePedagogique).filter(RessourcePedagogique.is_published.is_(False)).count()
            )
        if self.can_manage_finances:
            counts["dons"] = db.query(DonDeclare).filter(DonDeclare.is_confirme.is_(False)).count()
            counts["demandes_etablissements"] = (
                db.query(DemandeEtablissement).filter(DemandeEtablissement.statut == "nouvelle").count()
            )
        if self.can_examine_adhesions:
            counts["adhesion_requests"] = (
                db.query(AdhesionRequest).filter(AdhesionRequest.etat_demande == "nouvelle").count()
            )
        if self.can_manage_cartes_scolaires:
            counts["cartes_scolaires"] = db.query(CarteScolaire).filter(CarteScolaire.status == "soumise").count()
        if self.can_manage_cartes:
            counts["cartes"] = db.query(CarteMembre).filter(CarteMembre.status == "soumise").count()
        if self.can_manage_messagerie:
            counts["messagerie"] = (
                db.query(MessageEtablissement)
                .filter(MessageEtablissement.is_from_ben.is_(False), MessageEtablissement.is_read_by_ben.is_(False))
                .count()
            )
        return {k: v for k, v in counts.items() if v}

    @property
    def unread_messages_count(self) -> int:
        """Pour un compte établissement : nombre de messages du BEN pas encore lus
        — pour un badge dans la barre latérale de son espace personnel."""
        from sqlalchemy.orm import object_session

        if not self.is_etablissement_account:
            return 0
        db = object_session(self)
        if db is None:
            return 0
        return (
            db.query(MessageEtablissement)
            .filter(
                MessageEtablissement.etablissement_id == self.etablissement_id,
                MessageEtablissement.is_from_ben.is_(True),
                MessageEtablissement.is_read_by_etablissement.is_(False),
            )
            .count()
        )

    @property
    def is_delegation_account(self) -> bool:
        return self.delegation_id is not None

    @property
    def is_etablissement_account(self) -> bool:
        return self.etablissement_id is not None


class NewsPost(Base):
    __tablename__ = "news_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    # Déclenche une notification push aux visiteurs abonnés dès la publication —
    # push_sent_at évite un second envoi si l'actualité est modifiée ensuite.
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    push_sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    @property
    def image_url(self) -> str | None:
        return f"/api/news/{self.id}/image" if self.image_path else None


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    @property
    def status(self) -> str:
        return "upcoming" if self.event_date >= datetime.date.today() else "past"


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    establishment: Mapped[str] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class AdhesionRequest(Base):
    """Demande d'adhésion soumise depuis la vitrine par une école ou madrassa
    qui n'est pas encore membre de la LECIM. Circuit complet : soumission en ligne
    (récépissé avec code de suivi) -> entretien physique au siège -> examen et
    validation par le secrétariat chargé de l'intérieur -> certificat signé."""

    __tablename__ = "adhesion_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code_demande: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)

    # --- Renseignés par le demandeur, lors de la soumission en ligne ---
    nom_etablissement: Mapped[str] = mapped_column(String(255), nullable=False)
    nom_directeur: Mapped[str] = mapped_column(String(255), nullable=False)
    cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)  # maternelle | primaire | secondaire
    type_enseignement: Mapped[str] = mapped_column(String(30), nullable=False)
    telephone: Mapped[str] = mapped_column(String(50), nullable=False)
    telephone_fixe: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    localite: Mapped[str] = mapped_column(String(255), nullable=False)
    boite_postale: Mapped[str | None] = mapped_column(String(100), nullable=True)
    propriete_terrain: Mapped[str | None] = mapped_column(String(20), nullable=True)  # location | proprietaire
    superficie_m2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nombre_classes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nombre_garcons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nombre_filles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=True)

    # --- Renseignés par le secrétariat lors de l'examen / entretien ---
    etat_demande: Mapped[str] = mapped_column(String(20), default="nouvelle")  # nouvelle | en_cours | validee | rejetee
    agree: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    numero_agrement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_adhesion: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    notes_examen: Mapped[str | None] = mapped_column(Text, nullable=True)
    examinee_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    examinee_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    valide_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    valide_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    examinee_par: Mapped["User | None"] = relationship(foreign_keys=[examinee_par_id])
    valide_par: Mapped["User | None"] = relationship(foreign_keys=[valide_par_id])

    @property
    def etat_label(self) -> str:
        return ADHESION_ETATS.get(self.etat_demande, self.etat_demande)


ADHESION_ETATS = {
    "nouvelle": "Nouvelle demande",
    "en_cours": "Entretien en cours",
    "validee": "Validée",
    "rejetee": "Rejetée",
}
ADHESION_CYCLES = {
    "maternelle": "Maternelle",
    "primaire": "Primaire",
    "secondaire": "Secondaire",
}
ADHESION_PROPRIETES = {
    "location": "Location",
    "proprietaire": "Propriétaire",
}


class Membre(Base):
    """Répertoire permanent des membres du BEN : personnes physiques occupant un poste,
    utilisé pour le suivi de présence aux réunions (avec ou sans compte de connexion)."""

    __tablename__ = "membres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    poste: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_adjoint: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    # NULL = membre du répertoire national du BEN ; renseigné = membre local d'une délégation.
    delegation_id: Mapped[int | None] = mapped_column(ForeignKey("delegations.id"), nullable=True)
    mandat_debut: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    mandat_fin: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    mandat_alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    @property
    def poste_label(self) -> str:
        label = poste_label(self.poste)
        if not self.poste:
            return "—"
        return f"{label} (adjoint)" if self.is_adjoint else label

    @property
    def mandat_status(self) -> str | None:
        if not self.mandat_fin:
            return None
        today = datetime.date.today()
        if self.mandat_fin < today:
            return "expire"
        if self.mandat_fin <= today + datetime.timedelta(days=60):
            return "bientot"
        return "en_cours"


class Reunion(Base):
    __tablename__ = "reunions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    lieu: Mapped[str] = mapped_column(String(255), nullable=True)
    ordre_du_jour: Mapped[str] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # NULL = réunion nationale du BEN ; renseigné = réunion locale d'une délégation.
    delegation_id: Mapped[int | None] = mapped_column(ForeignKey("delegations.id"), nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    created_by: Mapped["User | None"] = relationship()
    presences: Mapped[list["Presence"]] = relationship(
        back_populates="reunion", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(cascade="all, delete-orphan")
    photos: Mapped[list["Photo"]] = relationship(cascade="all, delete-orphan")

    @property
    def present_count(self) -> int:
        return sum(1 for p in self.presences if p.present)


class Presence(Base):
    __tablename__ = "presences"
    __table_args__ = (UniqueConstraint("reunion_id", "membre_id", name="uq_presence_reunion_membre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reunion_id: Mapped[int] = mapped_column(ForeignKey("reunions.id"), nullable=False)
    membre_id: Mapped[int] = mapped_column(ForeignKey("membres.id"), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, default=False)

    reunion: Mapped["Reunion"] = relationship(back_populates="presences")
    membre: Mapped["Membre"] = relationship()


class Document(Base):
    """Procès-verbaux et autres documents administratifs, réservés aux comptes connectés."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="pv")  # pv | rapport | autre
    reunion_id: Mapped[int | None] = mapped_column(ForeignKey("reunions.id"), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()


class Photo(Base):
    """Galerie photo — privée par défaut (réservée aux comptes connectés), publiable
    individuellement sur la vitrine par l'administrateur via is_public."""

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    caption: Mapped[str] = mapped_column(String(255), nullable=True)
    reunion_id: Mapped[int | None] = mapped_column(ForeignKey("reunions.id"), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def image_url(self) -> str:
        return f"/api/photos/{self.id}/image"


class PushSubscription(Base):
    """Abonnement Web Push d'un visiteur (navigateur), enregistré depuis la vitrine —
    anonyme, pas lié à un compte : sert uniquement à alerter des actualités urgentes."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    lang: Mapped[str] = mapped_column(String(5), default="fr")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class NewsletterSubscriber(Base):
    """Abonné à la newsletter mensuelle de la LECIM (résumé des actualités du mois) —
    désinscription libre-service via un jeton unique inclus dans chaque envoi."""

    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class Faq(Base):
    """Question fréquente publiée sur la vitrine."""

    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    reponse: Mapped[str] = mapped_column(Text, nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


OPM_CATEGORIES = {
    "objectif": "Objectif",
    "principe": "Principe",
    "moyen": "Moyen",
}


class ObjectifPrincipeMoyen(Base):
    """Élément (objectif, principe ou moyen d'action) de l'identité de la LECIM,
    publié dans la section « Objectifs, principes et moyens » de la page À propos."""

    __tablename__ = "objectifs_principes_moyens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categorie: Mapped[str] = mapped_column(String(20), nullable=False)
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    @property
    def categorie_label(self) -> str:
        return OPM_CATEGORIES.get(self.categorie, self.categorie)


class RessourcePedagogique(Base):
    """Support pédagogique partagé entre écoles membres (manuel, fiche de cours...),
    déposé par un établissement puis modéré par le BEN avant publication."""

    __tablename__ = "ressources_pedagogiques"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    categorie: Mapped[str] = mapped_column(String(30), default="autre")  # manuel | fiche_cours | support_examen | autre
    niveau: Mapped[str] = mapped_column(String(20), default="les_deux")  # primaire | secondaire | les_deux
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement"] = relationship(foreign_keys=[etablissement_id])
    uploaded_by: Mapped["User | None"] = relationship(foreign_keys=[uploaded_by_id])

    @property
    def categorie_label(self) -> str:
        return RESSOURCE_CATEGORIES.get(self.categorie, "Autre")


RESSOURCE_CATEGORIES: dict[str, str] = {
    "manuel": "Manuel scolaire",
    "fiche_cours": "Fiche de cours",
    "support_examen": "Support d'examen blanc",
    "autre": "Autre",
}


# ---------- Finances ----------

class Etablissement(Base):
    """Établissement (école confessionnelle / madrassa) affilié à la LECIM."""

    __tablename__ = "etablissements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code_adhesion: Mapped[str | None] = mapped_column(String(30), nullable=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    # bureau_local sert de commune/ville. La Côte d'Ivoire compte 14 districts au
    # total (2 districts autonomes — Abidjan, Yamoussoukro — plus 12 districts
    # « ordinaires ») et 31 régions, chacune rattachée à l'un des 12 districts
    # ordinaires (les districts autonomes n'ont pas de région propre). Un
    # établissement d'un district ordinaire a donc normalement les deux champs
    # renseignés (district ET région) ; un établissement d'Abidjan ou Yamoussoukro
    # n'a que le district. Texte libre saisi par l'admin, pré-rempli au démarrage
    # quand la commune est reconnue (voir migrations.py).
    bureau_local: Mapped[str] = mapped_column(String(255), nullable=True)
    district: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delegation_id: Mapped[int | None] = mapped_column(ForeignKey("delegations.id"), nullable=True)
    statut: Mapped[str] = mapped_column(String(30), default="non_subventionne")  # subventionne | non_subventionne
    date_adhesion: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    directeur_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # primaire | secondaire | les_deux — détermine les niveaux d'effectifs pertinents
    type_enseignement: Mapped[str] = mapped_column(String(20), default="les_deux")
    numero_agrement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # agree | en_cours | expire — statut du dossier d'agrément ministériel, distinct
    # du simple numéro d'agrément (une école peut avoir un n° et un agrément expiré)
    statut_agrement: Mapped[str] = mapped_column(String(20), default="en_cours")
    date_expiration_agrement: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # Distinction publique accordée manuellement par le BEN, affichée sur la vitrine.
    is_ecole_modele: Mapped[bool] = mapped_column(Boolean, default=False)
    # membre | partenaire — membre = école affiliée à part entière (adhésion validée,
    # cotisation due) ; partenaire = collabore avec la LECIM sans être membre à part
    # entière. Distinct du statut d'agrément ministériel (statut_agrement) et de la
    # cotisation (statut) : purement une catégorie d'affichage/organisation.
    categorie: Mapped[str] = mapped_column(String(20), default="membre")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    delegation: Mapped["Delegation | None"] = relationship()

    @property
    def statut_label(self) -> str:
        return cotisation_rule(self.statut)["label"]

    @property
    def logo_url(self) -> str | None:
        return f"/api/etablissements/{self.id}/logo" if self.logo_path else None

    @property
    def statut_agrement_label(self) -> str:
        return {
            "agree": "Agréée",
            "en_cours": "Agrément en cours",
            "expire": "Agrément expiré",
        }.get(self.statut_agrement, "Agrément en cours")

    @property
    def categorie_label(self) -> str:
        return "Partenaire" if self.categorie == "partenaire" else "Membre affilié"


class Enseignant(Base):
    """Enseignant d'un établissement membre — répertoire distinct de celui des membres du BEN."""

    __tablename__ = "enseignants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    matiere: Mapped[str | None] = mapped_column(String(255), nullable=True)
    diplome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_debut: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement"] = relationship()


class ResultatExamen(Base):
    """Résultat d'un établissement membre à un examen scolaire islamique, pour une
    année scolaire donnée — consultable publiquement, au-delà du PDF publié."""

    __tablename__ = "resultats_examens"
    __table_args__ = (
        UniqueConstraint("etablissement_id", "annee_scolaire", "type_examen", name="uq_resultat_etab_annee_examen"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), index=True, nullable=False)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)
    type_examen: Mapped[str] = mapped_column(String(120), nullable=False)
    nombre_inscrits: Mapped[int] = mapped_column(Integer, default=0)
    nombre_admis: Mapped[int] = mapped_column(Integer, default=0)
    # Détail du nombre d'admis par sexe — informatif, ne doit pas nécessairement
    # sommer à nombre_admis (les écoles ne renseignent pas toujours ce détail).
    nombre_admis_garcons: Mapped[int] = mapped_column(Integer, default=0)
    nombre_admis_filles: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement"] = relationship()

    @property
    def taux_reussite(self) -> float:
        if not self.nombre_inscrits:
            return 0.0
        return round((self.nombre_admis / self.nombre_inscrits) * 100, 1)

    @property
    def etablissement_nom(self) -> str:
        return self.etablissement.nom


class Effectif(Base):
    """Effectif d'élèves d'un établissement membre, par niveau (primaire/secondaire)
    et par année scolaire — déclaré par l'établissement, consultable par le BEN."""

    __tablename__ = "effectifs"
    __table_args__ = (
        UniqueConstraint("etablissement_id", "annee_scolaire", "niveau", name="uq_effectif_etab_annee_niveau"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), index=True, nullable=False)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)
    niveau: Mapped[str] = mapped_column(String(20), nullable=False)  # "primaire" | "secondaire"
    nombre_garcons: Mapped[int] = mapped_column(Integer, default=0)
    nombre_filles: Mapped[int] = mapped_column(Integer, default=0)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement"] = relationship()

    @property
    def total(self) -> int:
        return self.nombre_garcons + self.nombre_filles

    @property
    def niveau_label(self) -> str:
        return "Primaire" if self.niveau == "primaire" else "Secondaire"


class DemandeEtablissement(Base):
    """Demande soumise par un établissement depuis son espace personnel
    (pièces d'adhésion, question administrative...), traitée par le secrétariat."""

    __tablename__ = "demandes_etablissements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    objet: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reponse: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="nouvelle")  # nouvelle | traitee
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    traitee_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    etablissement: Mapped["Etablissement"] = relationship()

    @property
    def statut_label(self) -> str:
        return "Traitée" if self.statut == "traitee" else "Nouvelle"


class MessageEtablissement(Base):
    """Message d'un fil de discussion continu entre le BEN et un établissement
    affilié — remplace le système "Demandes" à sens unique par un vrai échange."""

    __tablename__ = "messages_etablissements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_from_ben: Mapped[bool] = mapped_column(Boolean, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read_by_ben: Mapped[bool] = mapped_column(Boolean, default=False)
    is_read_by_etablissement: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement"] = relationship()
    sender: Mapped["User | None"] = relationship()


class Adhesion(Base):
    """Droit d'adhésion (12 000 FCFA), versé une fois par l'établissement."""

    __tablename__ = "adhesions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), unique=True, nullable=False)
    montant: Mapped[int] = mapped_column(Integer, default=12000)
    date_paiement: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement"] = relationship()


class Cotisation(Base):
    """Cotisation annuelle d'un établissement affilié."""

    __tablename__ = "cotisations"
    __table_args__ = (
        UniqueConstraint("etablissement_id", "annee_scolaire", name="uq_cotisation_etablissement_annee"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), index=True, nullable=False)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)  # ex: "2025-2026"
    montant_du: Mapped[int] = mapped_column(Integer, nullable=False)
    montant_paye: Mapped[int] = mapped_column(Integer, default=0)
    part_bureau_local: Mapped[int] = mapped_column(Integer, default=0)
    date_paiement: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement"] = relationship()

    @property
    def statut_paiement(self) -> str:
        if self.montant_paye <= 0:
            return "impaye"
        if self.montant_paye < self.montant_du:
            return "partiel"
        return "paye"


class VenteLivre(Base):
    """Vente de livres — détachée des autres recettes pour un suivi clair et dédié."""

    __tablename__ = "ventes_livres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    quantite: Mapped[int] = mapped_column(Integer, default=1)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class DroitExamen(Base):
    """Droits d'examens perçus par la LECIM — détachés des autres recettes pour un
    suivi clair et dédié, avec un rattachement optionnel à un établissement."""

    __tablename__ = "droits_examens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int | None] = mapped_column(ForeignKey("etablissements.id"), nullable=True)
    type_examen: Mapped[str | None] = mapped_column(String(120), nullable=True)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    etablissement: Mapped["Etablissement | None"] = relationship()


class Recette(Base):
    """Ressources hors droits d'adhésion / cotisations : subventions, dons, ventes, activités, examens."""

    __tablename__ = "recettes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categorie: Mapped[str] = mapped_column(String(30), nullable=False)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class DonDeclare(Base):
    """Don déclaré en libre-service depuis la vitrine (virement/dépôt effectué hors
    ligne) — en attente de rapprochement par le BEN avant d'être comptabilisé."""

    __tablename__ = "dons_declares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom_donateur: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date_don: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_confirme: Mapped[bool] = mapped_column(Boolean, default=False)
    confirme_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recette_id: Mapped[int | None] = mapped_column(ForeignKey("recettes.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    confirme_par: Mapped["User | None"] = relationship(foreign_keys=[confirme_par_id])


class Depense(Base):
    """Dépense de la LECIM, avec pièce justificative optionnelle."""

    __tablename__ = "depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    justificatif_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    justificatif_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class BudgetPrevisionnel(Base):
    """Montant prévisionnel saisi par le trésorier pour une catégorie et une année
    scolaire données — comparé au montant réalisé (calculé via
    reports.multi_year_financial_summary) pour un suivi budgétaire prévu/réalisé."""

    __tablename__ = "budgets_previsionnels"
    __table_args__ = (
        UniqueConstraint("annee_scolaire", "categorie", name="uq_budget_annee_categorie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)  # ex: "2025-2026"
    categorie: Mapped[str] = mapped_column(String(30), nullable=False)
    montant_prevu: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class RapportGenere(Base):
    """Trace de chaque rapport financier/annuel/comparatif généré, avec les totaux
    figés au moment de la génération — permet de vérifier publiquement (via QR code
    imprimé sur le PDF) qu'un rapport présenté est authentique et n'a pas été altéré,
    sans republier le détail des transactions."""

    __tablename__ = "rapports_generes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    type_rapport: Mapped[str] = mapped_column(String(30), nullable=False)  # periode | annuel | comparatif
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    periode_label: Mapped[str] = mapped_column(String(255), nullable=False)
    total_entrees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_depenses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solde: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genere_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    genere_par: Mapped["User | None"] = relationship()

    @property
    def type_label(self) -> str:
        return {
            "periode": "Rapport financier périodique",
            "annuel": "Rapport d'activités annuel",
            "comparatif": "Rapport financier comparatif",
        }.get(self.type_rapport, self.type_rapport)


class PasswordResetRequest(Base):
    """Demande de réinitialisation de mot de passe — un mot de passe temporaire est
    généré, envoyé par e-mail, et conservé ici en clair jusqu'à utilisation pour que
    le secrétariat puisse le communiquer à la main si l'e-mail n'arrive pas."""

    __tablename__ = "password_reset_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    temp_password: Mapped[str] = mapped_column(String(50), nullable=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    user: Mapped["User"] = relationship()


class ConnexionLog(Base):
    """Journal des connexions réussies — un enregistrement par connexion, avec l'IP et
    le navigateur utilisés, pour repérer les connexions depuis un appareil inconnu."""

    __tablename__ = "connexions_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_new_device: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    user: Mapped["User | None"] = relationship()


# ---------- Notifications ----------

class Notification(Base):
    """Notification affichée dans l'espace personnel d'un compte."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


# ---------- Cartes de membres ----------

CARTE_STATUTS = ["soumise", "validee", "rejetee", "imprimee", "disponible"]


class CarteMembre(Base):
    """Demande de carte de membre du Bureau Exécutif National."""

    __tablename__ = "cartes_membres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    full_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_naissance: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    ville: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cni_numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_urgence_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_urgence_telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_personnel: Mapped[str | None] = mapped_column(String(255), nullable=True)

    numero_carte: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="soumise")
    commentaire_rejet: Mapped[str | None] = mapped_column(Text, nullable=True)

    date_soumission: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    date_validation: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    date_validite: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_impression: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    date_disponibilite: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    validated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    validated_by: Mapped["User | None"] = relationship(foreign_keys=[validated_by_id])

    @property
    def status_label(self) -> str:
        return {
            "soumise": "Soumise — en attente de validation",
            "validee": "Validée — en cours d'impression",
            "rejetee": "Rejetée",
            "imprimee": "Imprimée — en attente de disponibilité",
            "disponible": "Disponible — à récupérer",
        }.get(self.status, self.status)


class CarteScolaire(Base):
    """Demande de carte scolaire d'un élève, soumise par son établissement — porte le
    logo de l'établissement, un matricule LECIM et un QR code de certification."""

    __tablename__ = "cartes_scolaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    eleve_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    eleve_sexe: Mapped[str | None] = mapped_column(String(1), nullable=True)  # "M" | "F"
    eleve_date_naissance: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    classe: Mapped[str] = mapped_column(String(100), nullable=False)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    matricule: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="soumise")
    commentaire_rejet: Mapped[str | None] = mapped_column(Text, nullable=True)

    date_soumission: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    date_validation: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    date_validite: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_impression: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    date_disponibilite: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    validated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    etablissement: Mapped["Etablissement"] = relationship(foreign_keys=[etablissement_id])
    requested_by: Mapped["User | None"] = relationship(foreign_keys=[requested_by_id])
    validated_by: Mapped["User | None"] = relationship(foreign_keys=[validated_by_id])

    @property
    def status_label(self) -> str:
        return {
            "soumise": "Soumise — en attente de validation",
            "validee": "Validée — en cours d'impression",
            "rejetee": "Rejetée",
            "imprimee": "Imprimée — en attente de disponibilité",
            "disponible": "Disponible — à récupérer",
        }.get(self.status, self.status)


# ---------- Relations extérieures : partenaires ----------

class Partenaire(Base):
    __tablename__ = "partenaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="autre")  # ong | institution | pays_ami | reseau | autre
    pays: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="en_discussion")  # actif | en_discussion | inactif
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Renseigné uniquement si la demande a été déposée depuis un projet précis
    # (bouton "Devenir partenaire de ce projet" sur initiatives.html) — reste vide
    # pour une proposition de partenariat générale ou pour un projet non listé.
    projet_id: Mapped[int | None] = mapped_column(ForeignKey("projets.id", ondelete="SET NULL"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    projet: Mapped["Projet | None"] = relationship()

    @property
    def logo_url(self) -> str | None:
        return f"/api/partenaires/{self.id}/logo" if self.logo_path else None


PARTENAIRE_TYPES = {
    "ong": "ONG",
    "institution": "Institution",
    "pays_ami": "Pays frère",
    "reseau": "Réseau international",
    "autre": "Autre",
}
PARTENAIRE_STATUTS = {
    "actif": "Partenariat actif",
    "en_discussion": "En discussion",
    "inactif": "Inactif",
}


# ---------- Projets, équipement et patrimoine ----------

class Projet(Base):
    __tablename__ = "projets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="planifie")  # planifie | en_cours | termine | suspendu
    responsable: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_debut: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_fin_prevue: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    budget_estime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


PROJET_STATUTS = {
    "planifie": "Planifié",
    "en_cours": "En cours",
    "termine": "Terminé",
    "suspendu": "Suspendu",
}


class Patrimoine(Base):
    __tablename__ = "patrimoine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    designation: Mapped[str] = mapped_column(String(255), nullable=False)
    categorie: Mapped[str] = mapped_column(String(30), default="autre")  # mobilier | informatique | vehicule | immobilier | autre
    quantite: Mapped[int] = mapped_column(Integer, default=1)
    etat: Mapped[str] = mapped_column(String(20), default="bon")  # bon | moyen | mauvais | hors_service
    localisation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_acquisition: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    valeur_estimee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


PATRIMOINE_CATEGORIES = {
    "mobilier": "Mobilier",
    "informatique": "Informatique",
    "vehicule": "Véhicule",
    "immobilier": "Immobilier",
    "autre": "Autre",
}
PATRIMOINE_ETATS = {
    "bon": "Bon état",
    "moyen": "État moyen",
    "mauvais": "Mauvais état",
    "hors_service": "Hors service",
}


# ---------- Affaires sociales et solidarité ----------

class DemandeAssistance(Base):
    __tablename__ = "demandes_assistance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom_beneficiaire: Mapped[str] = mapped_column(String(255), nullable=False)
    structure: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nature_besoin: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="nouvelle")  # nouvelle | en_cours | traitee | rejetee
    notes_suivi: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_soumission: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    date_traitement: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


DEMANDE_ASSISTANCE_STATUTS = {
    "nouvelle": "Nouvelle",
    "en_cours": "En cours de traitement",
    "traitee": "Traitée",
    "rejetee": "Rejetée",
}


# ---------- Publications publiques (site vitrine) ----------

class PublicationPublique(Base):
    """Document téléchargeable publié sur le site public (Règlement Intérieur, Statuts,
    résultats aux examens, etc.). Distinct de Document, qui est réservé aux comptes connectés."""

    __tablename__ = "publications_publiques"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="autre")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def file_url(self) -> str:
        return f"/api/publications/{self.id}/file"


PUBLICATION_CATEGORIES = {
    "reglement_interieur": "Règlement Intérieur",
    "statuts": "Statuts de la LECIM",
    "resultats_examens": "Résultats aux examens nationaux",
    "kit_presse": "Kit presse & médias",
    "rapport_impact": "Rapport d'impact annuel",
    "autre": "Autre document",
}


# ---------- Ressources officielles (manuels scolaires, programmes, enseignement islamique) ----------

RESSOURCE_OFFICIELLE_SECTIONS = {
    "manuel_scolaire": "Manuel scolaire officiel",
    "programme_officiel": "Programme officiel",
    "enseignement_islamique": "Enseignement islamique et arabe",
}

RESSOURCE_OFFICIELLE_LANGUES = {
    "arabe": "Arabe",
    "francais": "Français",
}


class RessourceOfficielle(Base):
    """Manuel scolaire, programme officiel ou support d'enseignement islamique/arabe
    mis en avant sur la page d'accueil du site public, avec photo de couverture."""

    __tablename__ = "ressources_officielles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    langue: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def section_label(self) -> str:
        return RESSOURCE_OFFICIELLE_SECTIONS.get(self.section, self.section)

    @property
    def langue_label(self) -> str:
        return RESSOURCE_OFFICIELLE_LANGUES.get(self.langue, "") if self.langue else ""

    @property
    def photo_url(self) -> str:
        return f"/api/ressources-officielles/{self.id}/photo"

    @property
    def file_url(self) -> str | None:
        return f"/api/ressources-officielles/{self.id}/file" if self.file_path else None


# ---------- Historique des anciens présidents (site vitrine) ----------

class HistoriquePresident(Base):
    """Ancien président de la LECIM affiché dans la section « Historique » du site public :
    photo, période du mandat et un mot associé à son portrait."""

    __tablename__ = "historique_presidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    periode: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mot: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def photo_url(self) -> str:
        return f"/api/historique/{self.id}/photo"


# ---------- Membres fondateurs (site vitrine) ----------

class MembreFondateur(Base):
    """Membre fondateur ayant bâti la LECIM, affiché dans une section dédiée du site
    public : photo, rôle lors de la fondation et un mot associé à son portrait."""

    __tablename__ = "membres_fondateurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mot: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def photo_url(self) -> str:
        return f"/api/fondateurs/{self.id}/photo"


# ---------- Conseil d'administration (site vitrine) ----------

class MembreConseilAdministration(Base):
    """Membre du Conseil d'administration de la LECIM, affiché dans une section dédiée
    du site public : photo, rôle et un mot associé à son portrait."""

    __tablename__ = "membres_conseil_administration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mot: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def photo_url(self) -> str:
        return f"/api/conseil-administration/{self.id}/photo"


# ---------- Témoignages d'écoles membres (site vitrine) ----------

class Temoignage(Base):
    """Témoignage d'une école membre ou d'un partenaire, affiché en preuve sociale
    sur la page d'accueil du site public."""

    __tablename__ = "temoignages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auteur_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    auteur_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    texte: Mapped[str] = mapped_column(Text, nullable=False)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def photo_url(self) -> str | None:
        return f"/api/temoignages/{self.id}/photo" if self.photo_path else None


# ---------- Gouvernance (organigramme public du BEN) ----------

GOUVERNANCE_NIVEAUX = {
    "president": "Président (sommet de l'organigramme)",
    "vice_president": "Vice-président",
    "secretariat": "Secrétariat (rattaché à un vice-président)",
    "autre": "Autre poste du bureau",
}


class GouvernanceMembre(Base):
    """Poste du Bureau Exécutif National affiché dans la section « Gouvernance » du site
    public, avec la photo du titulaire et, le cas échéant, de son adjoint. Le président,
    les vice-présidents et les secrétariats qui leur sont rattachés forment un organigramme
    pyramidal (via niveau + parent_id) ; les autres postes restent affichés à part."""

    __tablename__ = "gouvernance_membres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poste_title: Mapped[str] = mapped_column(String(255), nullable=False)
    poste_subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    titulaire_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    titulaire_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    adjoint_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adjoint_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    niveau: Mapped[str] = mapped_column(String(20), default="autre")
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("gouvernance_membres.id", ondelete="SET NULL"), nullable=True
    )
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship(foreign_keys=[uploaded_by_id])
    parent: Mapped["GouvernanceMembre | None"] = relationship(
        remote_side="GouvernanceMembre.id", foreign_keys=[parent_id]
    )

    @property
    def niveau_label(self) -> str:
        return GOUVERNANCE_NIVEAUX.get(self.niveau, self.niveau)

    @property
    def titulaire_photo_url(self) -> str | None:
        return f"/api/gouvernance/{self.id}/photo/titulaire" if self.titulaire_photo_path else None

    @property
    def adjoint_photo_url(self) -> str | None:
        return f"/api/gouvernance/{self.id}/photo/adjoint" if self.adjoint_photo_path else None


# ---------- Contenu éditable du site vitrine ----------

class SiteContent(Base):
    """Texte modifiable d'un bloc du site public (clé fixe définie dans
    site_content_fields.py). Une valeur vide/absente signifie : garder le texte
    par défaut codé dans la page tant que l'admin ne l'a pas personnalisé."""

    __tablename__ = "site_content"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


# ---------- Journal d'audit ----------

class AuditLog(Base):
    """Trace des actions sensibles effectuées depuis l'espace admin (comptes, finances,
    cartes de membres, délégations, contenu du site) — qui a fait quoi, et quand."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)  # create | update | delete | login
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    user: Mapped["User | None"] = relationship()

    @property
    def action_label(self) -> str:
        return {
            "create": "Création",
            "update": "Modification",
            "delete": "Suppression",
            "login": "Connexion",
        }.get(self.action, self.action)


# ---------- Sondages et votes électroniques ----------

class Sondage(Base):
    """Sondage ou vote électronique soumis aux membres du BEN (ex. décisions d'AG)."""

    __tablename__ = "sondages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_ouvert: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    cloture_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    options: Mapped[list["SondageOption"]] = relationship(
        back_populates="sondage", cascade="all, delete-orphan", order_by="SondageOption.ordre"
    )
    votes: Mapped[list["SondageVote"]] = relationship(cascade="all, delete-orphan")

    def votant_ids(self) -> set[int]:
        return {v.user_id for v in self.votes}

    def a_vote(self, user_id: int) -> bool:
        return user_id in self.votant_ids()


class SondageOption(Base):
    __tablename__ = "sondage_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sondage_id: Mapped[int] = mapped_column(ForeignKey("sondages.id"), nullable=False)
    texte: Mapped[str] = mapped_column(String(255), nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0)

    sondage: Mapped["Sondage"] = relationship(back_populates="options")
    votes: Mapped[list["SondageVote"]] = relationship(cascade="all, delete-orphan")

    @property
    def nombre_votes(self) -> int:
        return len(self.votes)


class SondageVote(Base):
    __tablename__ = "sondage_votes"
    __table_args__ = (UniqueConstraint("sondage_id", "user_id", name="uq_sondage_vote_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sondage_id: Mapped[int] = mapped_column(ForeignKey("sondages.id"), nullable=False)
    option_id: Mapped[int] = mapped_column(ForeignKey("sondage_options.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    user: Mapped["User"] = relationship()
    option: Mapped["SondageOption"] = relationship(back_populates="votes")


# ---------- Sondages express (public, anonyme — avis du grand public) ----------

class SondageExpress(Base):
    """Micro-sondage anonyme affiché sur la vitrine pour recueillir l'avis du grand
    public — distinct des sondages du BEN (Sondage), réservés aux membres connectés.
    Un seul sondage actif à la fois ; pas de compte requis pour voter, un seul vote
    par navigateur (empêché côté client, aucune donnée personnelle collectée)."""

    __tablename__ = "sondages_express"
    __table_args__ = (
        # Un seul sondage actif à la fois — index unique partiel (Postgres) plutôt
        # qu'une simple vérification applicative, pour empêcher deux administrateurs
        # concurrents de laisser deux sondages actifs simultanément.
        Index("uq_sondage_express_one_active", "is_active", unique=True, postgresql_where=text("is_active = true")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    options: Mapped[list["SondageExpressOption"]] = relationship(
        back_populates="sondage", cascade="all, delete-orphan", order_by="SondageExpressOption.ordre"
    )

    @property
    def total_votes(self) -> int:
        return sum(o.votes for o in self.options)


class SondageExpressOption(Base):
    __tablename__ = "sondage_express_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sondage_id: Mapped[int] = mapped_column(ForeignKey("sondages_express.id", ondelete="CASCADE"), nullable=False)
    texte: Mapped[str] = mapped_column(String(255), nullable=False)
    votes: Mapped[int] = mapped_column(Integer, default=0)
    ordre: Mapped[int] = mapped_column(Integer, default=0)

    sondage: Mapped["SondageExpress"] = relationship(back_populates="options")


class PageView(Base):
    """Compteur de vues par page et par jour — statistiques de fréquentation
    respectueuses de la vie privée : aucune IP, aucun cookie, aucun identifiant
    de visiteur n'est jamais enregistré, uniquement un total de vues agrégé."""

    __tablename__ = "page_views"
    __table_args__ = (UniqueConstraint("path", "date", name="uq_page_view_path_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0)


class SondageSatisfaction(Base):
    """Sondage de satisfaction envoyé aux participants d'une réunion/formation du
    BEN après sa tenue — réponses anonymes (aucun lien avec l'identité du
    répondant), accessible via un jeton non devinable envoyé par e-mail."""

    __tablename__ = "sondages_satisfaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reunion_id: Mapped[int] = mapped_column(ForeignKey("reunions.id", ondelete="CASCADE"), unique=True, nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    reunion: Mapped["Reunion"] = relationship()
    reponses: Mapped[list["SondageSatisfactionReponse"]] = relationship(cascade="all, delete-orphan")

    @property
    def note_moyenne(self) -> float | None:
        if not self.reponses:
            return None
        return round(sum(r.note for r in self.reponses) / len(self.reponses), 1)


class SondageSatisfactionReponse(Base):
    __tablename__ = "sondage_satisfaction_reponses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sondage_id: Mapped[int] = mapped_column(ForeignKey("sondages_satisfaction.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 (insatisfait) à 5 (très satisfait)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


# ---------- Délégations régionales ----------

class AnnonceDelegation(Base):
    """Annonce publiée par une délégation régionale, visible uniquement par les
    établissements affiliés rattachés à cette délégation."""

    __tablename__ = "annonces_delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delegation_id: Mapped[int] = mapped_column(ForeignKey("delegations.id"), nullable=False)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    delegation: Mapped["Delegation"] = relationship()


class Delegation(Base):
    """Comité local / délégation régionale de la LECIM."""

    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


# ---------- Calendrier scolaire national ----------

class CalendrierScolaireEntry(Base):
    """Date commune à toutes les écoles membres (rentrée, vacances, examens...),
    distincte du calendrier interne des réunions/activités du BEN — visible sur la
    vitrine et dans les espaces établissement."""

    __tablename__ = "calendrier_scolaire_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="autre")  # rentree | vacances | examen | autre
    date_debut: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    @property
    def type_label(self) -> str:
        return {
            "rentree": "Rentrée scolaire",
            "vacances": "Vacances",
            "examen": "Examen",
            "autre": "Autre",
        }.get(self.type, "Autre")


CALENDRIER_SCOLAIRE_TYPES = {
    "rentree": "Rentrée scolaire",
    "vacances": "Vacances",
    "examen": "Examen",
    "autre": "Autre",
}


# ---------- Boîte à idées interne ----------

class Idee(Base):
    """Suggestion soumise par un membre du BEN ou un établissement affilié, votable
    par tous les comptes connectés, pour aider à prioriser les prochains chantiers
    de la plateforme."""

    __tablename__ = "idees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), default="nouvelle")  # nouvelle | en_etude | retenue | rejetee
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    auteur: Mapped["User | None"] = relationship()
    votes: Mapped[list["IdeeVote"]] = relationship(cascade="all, delete-orphan")

    @property
    def nombre_votes(self) -> int:
        return len(self.votes)

    def votant_ids(self) -> set[int]:
        return {v.user_id for v in self.votes}

    def a_vote(self, user_id: int) -> bool:
        return user_id in self.votant_ids()

    @property
    def statut_label(self) -> str:
        return {
            "nouvelle": "Nouvelle",
            "en_etude": "À l'étude",
            "retenue": "Retenue",
            "rejetee": "Rejetée",
        }.get(self.statut, "Nouvelle")

    @property
    def auteur_label(self) -> str:
        if not self.auteur:
            return "Compte supprimé"
        if self.auteur.is_etablissement_account and self.auteur.etablissement:
            return self.auteur.etablissement.nom
        return self.auteur.full_name


class IdeeVote(Base):
    __tablename__ = "idee_votes"
    __table_args__ = (UniqueConstraint("idee_id", "user_id", name="uq_idee_vote_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idee_id: Mapped[int] = mapped_column(ForeignKey("idees.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    user: Mapped["User"] = relationship()


# ---------- Journal des changements (admin) ----------

class ChangelogEntry(Base):
    """Nouveauté ou correctif de la plateforme, consigné pour informer le bureau de
    son évolution sans passer par un canal externe."""

    __tablename__ = "changelog_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    categorie: Mapped[str] = mapped_column(String(20), default="nouveaute")  # nouveaute | correctif | amelioration
    published_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    @property
    def categorie_label(self) -> str:
        return {
            "nouveaute": "Nouveauté",
            "correctif": "Correctif",
            "amelioration": "Amélioration",
        }.get(self.categorie, "Nouveauté")


CHANGELOG_CATEGORIES = {
    "nouveaute": "Nouveauté",
    "correctif": "Correctif",
    "amelioration": "Amélioration",
}
