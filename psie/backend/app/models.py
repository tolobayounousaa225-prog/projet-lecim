import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
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
