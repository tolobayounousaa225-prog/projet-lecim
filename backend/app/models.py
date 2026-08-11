import datetime

from sqlalchemy import Boolean, DateTime, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .finances_constants import cotisation_rule
from .postes import poste_attributions, poste_label


class User(Base):
    __tablename__ = "users"

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
    def allowed_modules_list(self) -> list[str]:
        return [m for m in (self.allowed_modules or "").split(",") if m]

    def has_module(self, key: str) -> bool:
        return self.is_admin or key in self.allowed_modules_list

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
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()


class Photo(Base):
    """Galerie photo interne, réservée aux comptes connectés."""

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    caption: Mapped[str] = mapped_column(String(255), nullable=True)
    reunion_id: Mapped[int | None] = mapped_column(ForeignKey("reunions.id"), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()


# ---------- Finances ----------

class Etablissement(Base):
    """Établissement (école confessionnelle / madrassa) affilié à la LECIM."""

    __tablename__ = "etablissements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    bureau_local: Mapped[str] = mapped_column(String(255), nullable=True)
    delegation_id: Mapped[int | None] = mapped_column(ForeignKey("delegations.id"), nullable=True)
    statut: Mapped[str] = mapped_column(String(30), default="non_subventionne")  # subventionne | non_subventionne
    date_adhesion: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    delegation: Mapped["Delegation | None"] = relationship()

    @property
    def statut_label(self) -> str:
        return cotisation_rule(self.statut)["label"]


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)
    type_examen: Mapped[str] = mapped_column(String(120), nullable=False)
    nombre_inscrits: Mapped[int] = mapped_column(Integer, default=0)
    nombre_admis: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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


class Adhesion(Base):
    """Droit d'adhésion (12 000 FCFA), versé une fois par l'établissement."""

    __tablename__ = "adhesions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    montant: Mapped[int] = mapped_column(Integer, default=12000)
    date_paiement: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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
    etablissement_id: Mapped[int] = mapped_column(ForeignKey("etablissements.id"), nullable=False)
    annee_scolaire: Mapped[str] = mapped_column(String(20), nullable=False)  # ex: "2025-2026"
    montant_du: Mapped[int] = mapped_column(Integer, nullable=False)
    montant_paye: Mapped[int] = mapped_column(Integer, default=0)
    part_bureau_local: Mapped[int] = mapped_column(Integer, default=0)
    date_paiement: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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


class Recette(Base):
    """Ressources hors droits d'adhésion / cotisations : subventions, dons, ventes, activités, examens."""

    __tablename__ = "recettes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categorie: Mapped[str] = mapped_column(String(30), nullable=False)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class Depense(Base):
    """Dépense de la LECIM, avec pièce justificative optionnelle."""

    __tablename__ = "depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    justificatif_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    justificatif_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


# ---------- Notifications ----------

class Notification(Base):
    """Notification affichée dans l'espace personnel d'un compte."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

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

    numero_carte: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="soumise")
    commentaire_rejet: Mapped[str | None] = mapped_column(Text, nullable=True)

    date_soumission: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    date_validation: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    date_validite: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_impression: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    date_disponibilite: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    validated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

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


# ---------- Relations extérieures : partenaires ----------

class Partenaire(Base):
    __tablename__ = "partenaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="autre")  # ong | institution | pays_ami | reseau | autre
    pays: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="en_discussion")  # actif | en_discussion | inactif
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


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
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


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
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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
    "autre": "Autre document",
}


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
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def photo_url(self) -> str:
        return f"/api/historique/{self.id}/photo"


# ---------- Gouvernance (organigramme public du BEN) ----------

class GouvernanceMembre(Base):
    """Poste du Bureau Exécutif National affiché dans la section « Gouvernance » du site
    public, avec la photo du titulaire et, le cas échéant, de son adjoint."""

    __tablename__ = "gouvernance_membres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poste_title: Mapped[str] = mapped_column(String(255), nullable=False)
    poste_subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    titulaire_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    titulaire_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    adjoint_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adjoint_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    uploaded_by: Mapped["User | None"] = relationship()

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
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


# ---------- Journal d'audit ----------

class AuditLog(Base):
    """Trace des actions sensibles effectuées depuis l'espace admin (comptes, finances,
    cartes de membres, délégations, contenu du site) — qui a fait quoi, et quand."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    user: Mapped["User"] = relationship()
    option: Mapped["SondageOption"] = relationship(back_populates="votes")


# ---------- Délégations régionales ----------

class Delegation(Base):
    """Comité local / délégation régionale de la LECIM."""

    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
