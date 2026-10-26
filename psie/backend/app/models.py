import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# --- Rôles (alignés sur les organes des Statuts, art. 10) ---------------------
ROLES = {
    "admin": "Administrateur de la plate-forme",
    "den": "Directeur Exécutif National",
    "finances": "Secrétaire chargé des finances (ou adjoint)",
    "secretaire": "Secrétaire de la DEN",
    "administrateur_ca": "Administrateur du CA",
    "commissaire": "Commissaire aux comptes",
    "faitiere": "Représentant de faîtière",
}
# Rôles rattachés à un organe de la PSIE (tout sauf le représentant de faîtière)
INTERNAL_ROLES = {r for r in ROLES if r != "faitiere"}
# Rôles autorisés à modifier l'annuaire des membres et les mandats
MEMBER_MANAGER_ROLES = {"admin", "den", "secretaire"}
# Finances : seul le secrétaire aux finances (ou son adjoint) écrit ; le DEN, le CA et les
# commissaires aux comptes lisent. L'administrateur technique n'a pas accès aux finances.
FINANCE_WRITE_ROLES = {"finances"}
FINANCE_READ_ROLES = {"finances", "den", "administrateur_ca", "commissaire"}
# Rôles soumis à la double authentification par e-mail
TWO_FACTOR_ROLES = {"admin", "finances"}

# --- Finances ------------------------------------------------------------------
ECHEANCE_TYPES = {
    "annuelle": "Cotisation annuelle",
    "adhesion": "Droit d'adhésion",
}
MODES_PAIEMENT = {
    "virement": "Virement",
    "depot": "Dépôt bancaire",
    "especes": "Espèces",
    "cheque": "Chèque",
    "mobile_money": "Mobile money",
}

# --- Membres (Statuts art. 8) -------------------------------------------------
CATEGORIES = {
    "fondateur": "Membre fondateur",
    "ordinaire": "Membre ordinaire",
    "honneur": "Membre d'honneur",
}
STATUTS_MEMBRE = {
    "actif": "Actif",
    "suspendu": "Suspendu",
    "radie": "Radié",
    "demissionnaire": "Démissionnaire",
}

# --- Organes et fonctions ------------------------------------------------------
ORGANES = {
    "AG": "Assemblée Générale (délégué)",
    "CA": "Conseil d'Administration",
    "DEN": "Direction Exécutive Nationale",
    "CC": "Commissariat aux Comptes",
    "CNECI": "Commission des Examens et Concours Islamiques",
    "CNVSP": "Commission de Validation et Suivi des Programmes",
}
# Durée statutaire des mandats (Statuts art. 21 et 28)
MANDAT_DUREE_ANS = 3


class Faitiere(Base):
    """Organisation membre de la PSIE (faîtière)."""

    __tablename__ = "faitieres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    sigle: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    categorie: Mapped[str] = mapped_column(String(20), default="ordinaire")
    statut: Mapped[str] = mapped_column(String(20), default="actif")
    date_creation: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_adhesion: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    statut_juridique: Mapped[str | None] = mapped_column(String(255), nullable=True)
    siege: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    mandats: Mapped[list["Mandat"]] = relationship(back_populates="faitiere", order_by="Mandat.organe")
    users: Mapped[list["User"]] = relationship(back_populates="faitiere")

    @property
    def categorie_label(self) -> str:
        return CATEGORIES.get(self.categorie, self.categorie)

    @property
    def statut_label(self) -> str:
        return STATUTS_MEMBRE.get(self.statut, self.statut)

    @property
    def categorie_label_pdf(self) -> tuple[str, str]:
        from .i18n import label
        return label("categorie", self.categorie, "fr"), label("categorie", self.categorie, "ar")

    @property
    def is_membre_actif(self) -> bool:
        """Membre actif au sens des Statuts : fondateur ou ordinaire (donc cotisant)."""
        return self.categorie in ("fondateur", "ordinaire") and self.statut == "actif"


class Mandat(Base):
    """Mandat d'une personne dans un organe de la PSIE (délégué à l'AG, administrateur,
    membre de la DEN, commissaire aux comptes, membre de commission)."""

    __tablename__ = "mandats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int | None] = mapped_column(ForeignKey("faitieres.id"), index=True, nullable=True)
    organe: Mapped[str] = mapped_column(String(10), nullable=False)
    fonction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_debut: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_fin: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    faitiere: Mapped["Faitiere | None"] = relationship(back_populates="mandats")

    @property
    def organe_label(self) -> str:
        return ORGANES.get(self.organe, self.organe)

    @property
    def echeance(self) -> str | None:
        """`expire` | `bientot` (moins de 90 jours) | `en_cours` | None si pas de date de fin."""
        if not self.date_fin:
            return None
        today = datetime.date.today()
        if self.date_fin < today:
            return "expire"
        if self.date_fin <= today + datetime.timedelta(days=90):
            return "bientot"
        return "en_cours"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="faitiere")
    # Renseigné pour un représentant de faîtière : il ne voit que les données de cette faîtière.
    faitiere_id: Mapped[int | None] = mapped_column(ForeignKey("faitieres.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    faitiere: Mapped["Faitiere | None"] = relationship(back_populates="users")

    @property
    def role_label(self) -> str:
        return ROLES.get(self.role, self.role)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_internal(self) -> bool:
        return self.role in INTERNAL_ROLES

    @property
    def can_manage_members(self) -> bool:
        return self.role in MEMBER_MANAGER_ROLES

    @property
    def can_view_finances(self) -> bool:
        return self.role in FINANCE_READ_ROLES

    @property
    def can_write_finances(self) -> bool:
        return self.role in FINANCE_WRITE_ROLES

    @property
    def requires_two_factor(self) -> bool:
        return self.role in TWO_FACTOR_ROLES

    def can_view_faitiere(self, faitiere_id: int) -> bool:
        """Cloisonnement : un représentant de faîtière ne voit que la sienne."""
        if self.is_internal:
            return True
        return self.faitiere_id is not None and self.faitiere_id == faitiere_id


class AuditLog(Base):
    """Journal d'audit : toute action d'écriture sensible y est consignée."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, index=True)


# ---------- Finances : cotisations ----------

class BaremeCotisation(Base):
    """Montant de la cotisation annuelle d'une année civile (montant unique pour toutes
    les faîtières). Le taux est fixé par l'AGO : on garde la référence de la résolution."""

    __tablename__ = "bareme_cotisations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annee: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)  # FCFA, entier
    date_limite: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    reference_decision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class Echeance(Base):
    """Somme due par une faîtière (cotisation annuelle, droit d'adhésion). Le solde et le
    statut sont toujours calculés à partir des paiements, jamais saisis."""

    __tablename__ = "echeances"
    __table_args__ = (
        # Une seule cotisation annuelle par faîtière et par année (garde-fou en base,
        # en plus de la vérification applicative, contre deux générations concurrentes).
        Index(
            "uq_echeance_annuelle", "faitiere_id", "annee", unique=True,
            sqlite_where=text("type = 'annuelle'"), postgresql_where=text("type = 'annuelle'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int] = mapped_column(ForeignKey("faitieres.id"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    montant_du: Mapped[int] = mapped_column(Integer, nullable=False)
    date_limite: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    reference_decision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    faitiere: Mapped["Faitiere"] = relationship()
    paiements: Mapped[list["Paiement"]] = relationship(back_populates="echeance", order_by="Paiement.id")

    @property
    def montant_paye(self) -> int:
        return sum(p.montant for p in self.paiements if not p.annule)

    @property
    def solde(self) -> int:
        return self.montant_du - self.montant_paye

    @property
    def is_en_retard(self) -> bool:
        return self.solde > 0 and self.date_limite is not None and self.date_limite < datetime.date.today()

    @property
    def statut(self) -> str:
        """`paye` | `en_retard` | `partiel` | `impaye`."""
        if self.solde <= 0:
            return "paye"
        if self.is_en_retard:
            return "en_retard"
        return "partiel" if self.montant_paye > 0 else "impaye"

    @property
    def type_label(self) -> str:
        return ECHEANCE_TYPES.get(self.type, self.type)


class Paiement(Base):
    """Versement sur une échéance. Jamais supprimé : une erreur s'annule (avec motif et
    auteur), ce qui laisse la trace comptable intacte."""

    __tablename__ = "paiements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    echeance_id: Mapped[int] = mapped_column(ForeignKey("echeances.id"), index=True, nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date_paiement: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recu_numero: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    verify_token: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    saisi_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    annule: Mapped[bool] = mapped_column(Boolean, default=False)
    annule_motif: Mapped[str | None] = mapped_column(String(500), nullable=True)
    annule_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    annule_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    echeance: Mapped["Echeance"] = relationship(back_populates="paiements")

    @property
    def mode_label(self) -> str:
        return MODES_PAIEMENT.get(self.mode, self.mode)


class RelanceLog(Base):
    """Relance déjà envoyée pour une échéance : évite d'envoyer deux fois le même rappel."""

    __tablename__ = "relances_log"
    __table_args__ = (Index("uq_relance_echeance_kind", "echeance_id", "kind", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    echeance_id: Mapped[int] = mapped_column(ForeignKey("echeances.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    sent_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
