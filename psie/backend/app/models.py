import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import acces
from .database import Base

# --- Rôles (alignés sur les organes des Statuts, art. 10) ---------------------
ROLES = {
    "admin": "Administrateur de la plate-forme",
    "den": "Directeur Exécutif National",
    "finances": "Secrétaire chargé des finances (ou adjoint)",
    "secretaire": "Secrétaire de la DEN",
    "communication": "Secrétariat Information et Communication",
    "formation": "Secrétariat Formation",
    "examens": "Secrétariat Examens",
    "ressources": "Secrétariat Mobilisation des ressources",
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
# Adhésion : examen et décision par la DEN ; l'avis écrit du CA (Statuts art. 18) peut être
# enregistré par un administrateur ou, en son nom, par la DEN et le secrétariat.
ADHESION_AVIS_ROLES = {"administrateur_ca", "den", "secretaire"}
# Contenu du site vitrine (actualités, équipe, partenaires, documents…) : le Secrétariat Information
# et Communication et l'administrateur. Toute modification est publiée immédiatement.
CONTENT_EDITOR_ROLES = {"admin", "communication"}
# Rôles soumis à la double authentification par e-mail
TWO_FACTOR_ROLES = {"admin", "finances", "communication"}

# --- Finances ------------------------------------------------------------------
ECHEANCE_TYPES = {
    "annuelle": "Cotisation annuelle",
    "adhesion": "Droit d'adhésion",
    "exceptionnelle": "Cotisation exceptionnelle",
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
    users: Mapped[list["User"]] = relationship(back_populates="faitiere", foreign_keys="User.faitiere_id")
    sanctions: Mapped[list["Sanction"]] = relationship(back_populates="faitiere", order_by="Sanction.id")

    @property
    def categorie_label(self) -> str:
        return CATEGORIES.get(self.categorie, self.categorie)

    @property
    def statut_label(self) -> str:
        return STATUTS_MEMBRE.get(self.statut, self.statut)

    @property
    def sanctions_actives(self) -> list["Sanction"]:
        return [x for x in self.sanctions if x.is_active]

    @property
    def categorie_label_pdf(self) -> tuple[str, str]:
        from .i18n import label
        return label("categorie", self.categorie, "fr"), label("categorie", self.categorie, "ar")

    @property
    def is_membre_actif(self) -> bool:
        """Membre actif au sens des Statuts : fondateur ou ordinaire (donc cotisant)."""
        return self.categorie in ("fondateur", "ordinaire") and self.statut == "actif"


MEMBRE_PIECE_TYPES = {
    "statuts": "Statuts de l'organisation",
    "recepisse": "Récépissé de déclaration",
    "pv_designation": "PV ou courrier de désignation des représentants",
    "autre": "Autre pièce",
}


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
    # Organisation qui a proposé cette personne (DEN, secrétaire aux finances) : sert à vérifier
    # que les deux signataires d'un paiement ne viennent pas de la même organisation (Statuts art. 38).
    faitiere_origine_id: Mapped[int | None] = mapped_column(ForeignKey("faitieres.id"), nullable=True)
    notif_email: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    faitiere: Mapped["Faitiere | None"] = relationship(back_populates="users", foreign_keys=[faitiere_id])
    faitiere_origine: Mapped["Faitiere | None"] = relationship(foreign_keys=[faitiere_origine_id])

    @property
    def role_label(self) -> str:
        return ROLES.get(self.role, self.role)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_internal(self) -> bool:
        return self.role in INTERNAL_ROLES

    # --- Accès par rubrique (voir acces.py) : le niveau est calculé une fois par requête et posé sur l'utilisateur ---
    @property
    def perms(self) -> dict[str, int]:
        cached = getattr(self, "_perms", None)
        return cached if cached is not None else acces.defaults_for(self.role)

    def level(self, section: str) -> int:
        return self.perms.get(section, 0)

    def can(self, section: str, write: bool = False) -> bool:
        return self.level(section) >= (acces.ECRITURE if write else acces.LECTURE)

    @property
    def can_manage_members(self) -> bool:
        return self.can("membres", True)

    @property
    def can_write_adhesions(self) -> bool:
        return self.can("adhesions", True)

    @property
    def can_write_assemblees(self) -> bool:
        return self.can("assemblees", True)

    @property
    def can_write_sanctions(self) -> bool:
        return self.can("sanctions", True)

    @property
    def can_edit_site_content(self) -> bool:
        return self.can("contenu", True)

    @property
    def can_view_finances(self) -> bool:
        return self.can("finances")

    @property
    def can_write_finances(self) -> bool:
        return self.can("finances", True)

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
    # Renseigné pour une cotisation exceptionnelle : l'appel de fonds dont elle est issue
    appel_id: Mapped[int | None] = mapped_column(ForeignKey("appels_exceptionnels.id"), index=True, nullable=True)
    # Exonération : la somme n'est plus due (le motif et l'auteur sont conservés)
    exoneree: Mapped[bool] = mapped_column(Boolean, default=False)
    exoneration_motif: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exoneree_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    exoneree_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    faitiere: Mapped["Faitiere"] = relationship()
    appel: Mapped["AppelExceptionnel | None"] = relationship(back_populates="echeances")
    paiements: Mapped[list["Paiement"]] = relationship(back_populates="echeance", order_by="Paiement.id")

    @property
    def montant_paye(self) -> int:
        return sum(p.montant for p in self.paiements if not p.annule)

    @property
    def solde(self) -> int:
        return 0 if self.exoneree else self.montant_du - self.montant_paye

    @property
    def is_en_retard(self) -> bool:
        return self.solde > 0 and self.date_limite is not None and self.date_limite < datetime.date.today()

    @property
    def statut(self) -> str:
        """`exonere` | `paye` | `en_retard` | `partiel` | `impaye`."""
        if self.exoneree:
            return "exonere"
        if self.solde <= 0:
            return "paye"
        if self.is_en_retard:
            return "en_retard"
        return "partiel" if self.montant_paye > 0 else "impaye"

    @property
    def type_label(self) -> str:
        return ECHEANCE_TYPES.get(self.type, self.type)


class AppelExceptionnel(Base):
    """Appel de fonds ponctuel (cotisation exceptionnelle, Règlement Intérieur art. 14 et 35).
    Les textes ne désignent pas l'autorité qui le décide : l'outil enregistre la référence de la
    décision (PV, résolution) saisie par le secrétaire aux finances, sans l'imposer."""

    __tablename__ = "appels_exceptionnels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intitule: Mapped[str] = mapped_column(String(255), nullable=False)
    motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_decision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_limite: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    echeances: Mapped[list["Echeance"]] = relationship(back_populates="appel", order_by="Echeance.id")

    @property
    def total_du(self) -> int:
        return sum(e.montant_du for e in self.echeances if not e.exoneree)

    @property
    def total_paye(self) -> int:
        return sum(e.montant_paye for e in self.echeances if not e.exoneree)

    @property
    def reste(self) -> int:
        return sum(e.solde for e in self.echeances)

    @property
    def taux(self) -> int:
        return round(100 * self.total_paye / self.total_du) if self.total_du else 0

    @property
    def is_solde(self) -> bool:
        return self.reste <= 0


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


# ---------- Adhésion et vitrine ----------

ADHESION_ETATS = {
    "nouvelle": "Demande reçue",
    "en_examen": "En cours d'examen",
    "acceptee": "Adhésion acceptée",
    "refusee": "Demande refusée",
}


class DemandeAdhesion(Base):
    """Demande d'adhésion déposée en ligne par une organisation. Circuit des Statuts :
    examen par la DEN -> avis écrit du CA (art. 18) -> décision de l'AG (art. 13). L'outil
    enregistre la référence de la décision d'AG ; une acceptation exige un avis favorable du CA."""

    __tablename__ = "demandes_adhesion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    # --- renseigné par le demandeur ---
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    sigle: Mapped[str] = mapped_column(String(50), nullable=False)
    representant_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    representant_fonction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    telephone: Mapped[str] = mapped_column(String(50), nullable=False)
    siege: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statut_juridique: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_creation: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    nb_structures: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepte_statuts: Mapped[bool] = mapped_column(Boolean, default=False)
    accepte_cotisations: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    # --- instruction ---
    etat: Mapped[str] = mapped_column(String(20), default="nouvelle")
    notes_examen: Mapped[str | None] = mapped_column(Text, nullable=True)
    avis_ca: Mapped[str | None] = mapped_column(String(20), nullable=True)  # favorable | defavorable
    avis_ca_motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    avis_ca_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    avis_ca_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    decision_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)  # résolution d'AG
    decision_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    decision_motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    decide_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    faitiere_id: Mapped[int | None] = mapped_column(ForeignKey("faitieres.id"), nullable=True)
    cert_token: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)

    faitiere: Mapped["Faitiere | None"] = relationship()

    @property
    def is_open(self) -> bool:
        return self.etat in ("nouvelle", "en_examen")


class Actualite(Base):
    """Actualité publiée sur la vitrine, en français et/ou en arabe (texte brut)."""

    __tablename__ = "actualites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    titre_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contenu_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    contenu_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    publie: Mapped[bool] = mapped_column(Boolean, default=False)
    date_publication: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    def titre(self, lang: str) -> str:
        """Titre dans la langue demandée, à défaut dans l'autre."""
        first, second = (self.titre_ar, self.titre_fr) if lang == "ar" else (self.titre_fr, self.titre_ar)
        return first or second or ""

    def contenu(self, lang: str) -> str:
        first, second = (self.contenu_ar, self.contenu_fr) if lang == "ar" else (self.contenu_fr, self.contenu_ar)
        return first or second or ""


# ---------- Vie statutaire : assemblées, résolutions, votes, sanctions ----------

ASSEMBLEE_TYPES = {
    "AGA": "Assemblée Générale Annuelle",
    "AGO": "Assemblée Générale Ordinaire",
    "AGE": "Assemblée Générale Extraordinaire",
}
ASSEMBLEE_STATUTS = {
    "preparation": "En préparation",
    "convoquee": "Convoquée",
    "en_seance": "En séance",
    "close": "Clôturée",
}
# Statuts art. 14.1 : AGA et AGO sont convoquées au moins 15 jours à l'avance
CONVOCATION_DELAI_JOURS = 15
VOTE_MODES = {
    "organisation": "Une voix par organisation membre",
    "delegue": "Une voix par délégué présent",
}
VOTE_CHOIX = {"pour": "Pour", "contre": "Contre", "abstention": "Abstention"}

SANCTION_TYPES = {
    "avertissement": "Avertissement",
    "blame": "Blâme",
    "suspension": "Suspension",
    "radiation": "Radiation",
}
# Effet d'une sanction sur le statut du membre
SANCTION_EFFETS = {"suspension": "suspendu", "radiation": "radie"}
# Organes dont la composition est contrôlée (nombre de membres prévu par les Statuts)
COMPOSITION_ATTENDUE = {"CA": 13, "DEN": 13, "CC": 2}


class Assemblee(Base):
    __tablename__ = "assemblees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(5), nullable=False)
    date_assemblee: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    heure: Mapped[str | None] = mapped_column(String(5), nullable=True)
    lieu: Mapped[str] = mapped_column(String(255), nullable=False)
    ordre_du_jour: Mapped[str] = mapped_column(Text, nullable=False)
    # Qui vote : paramètre de chaque assemblée (les textes ne le tranchent pas)
    mode_vote: Mapped[str] = mapped_column(String(20), default="organisation")
    # AGE : demande conjointe de deux organes, ou des 2/3 des membres (Statuts art. 14.2)
    demande_age: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Avis favorable du CA sur l'ordre du jour, exigé sauf pour une AGE (Statuts art. 18)
    avis_ca_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avis_ca_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    avis_ca_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="preparation")
    convocation_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    convocation_envoyes: Mapped[int] = mapped_column(Integer, default=0)
    president_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assesseur1_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assesseur2_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    presences: Mapped[list["PresenceAG"]] = relationship(back_populates="assemblee", order_by="PresenceAG.id")
    resolutions: Mapped[list["Resolution"]] = relationship(back_populates="assemblee", order_by="Resolution.numero")

    @property
    def type_label(self) -> str:
        return ASSEMBLEE_TYPES.get(self.type, self.type)

    @property
    def statut_label(self) -> str:
        return ASSEMBLEE_STATUTS.get(self.statut, self.statut)

    @property
    def requires_ca_opinion(self) -> bool:
        return self.type != "AGE"


class PresenceAG(Base):
    """Une personne attendue à l'assemblée (délégué d'une organisation, membre du CA, de la
    DEN ou du CC), avec sa présence constatée à l'émargement."""

    __tablename__ = "presences_ag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assemblee_id: Mapped[int] = mapped_column(ForeignKey("assemblees.id"), index=True, nullable=False)
    mandat_id: Mapped[int | None] = mapped_column(ForeignKey("mandats.id", ondelete="SET NULL"), nullable=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    organe: Mapped[str] = mapped_column(String(10), nullable=False)
    faitiere_id: Mapped[int | None] = mapped_column(ForeignKey("faitieres.id"), nullable=True)
    present: Mapped[bool] = mapped_column(Boolean, default=False)

    assemblee: Mapped["Assemblee"] = relationship(back_populates="presences")
    faitiere: Mapped["Faitiere | None"] = relationship()

    @property
    def is_delegue(self) -> bool:
        return self.organe == "AG" and self.faitiere_id is not None


class Resolution(Base):
    __tablename__ = "resolutions"
    __table_args__ = (UniqueConstraint("assemblee_id", "numero", name="uq_resolution_numero"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assemblee_id: Mapped[int] = mapped_column(ForeignKey("assemblees.id"), index=True, nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    intitule: Mapped[str] = mapped_column(String(255), nullable=False)
    texte: Mapped[str | None] = mapped_column(Text, nullable=True)
    regle: Mapped[str] = mapped_column(String(15), default="majorite")  # majorite | dissolution (4/5)
    statut: Mapped[str] = mapped_column(String(10), default="ouverte")  # ouverte | close
    mode_adoption: Mapped[str | None] = mapped_column(String(10), nullable=True)  # consensus | vote
    pour: Mapped[int] = mapped_column(Integer, default=0)
    contre: Mapped[int] = mapped_column(Integer, default=0)
    abstention: Mapped[int] = mapped_column(Integer, default=0)
    presents: Mapped[int] = mapped_column(Integer, default=0)
    base: Mapped[int] = mapped_column(Integer, default=0)
    adoptee: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    assemblee: Mapped["Assemblee"] = relationship(back_populates="resolutions")
    votes: Mapped[list["Vote"]] = relationship(
        back_populates="resolution", order_by="Vote.id", cascade="all, delete-orphan")


class Vote(Base):
    """Voix d'une unité de vote (organisation ou délégué selon le mode), saisie par le bureau
    de séance à partir du scrutin constaté."""

    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("resolution_id", "unite", name="uq_vote_unite"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resolution_id: Mapped[int] = mapped_column(ForeignKey("resolutions.id"), index=True, nullable=False)
    unite: Mapped[str] = mapped_column(String(20), nullable=False)  # "o:<faitiere_id>" ou "d:<presence_id>"
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    choix: Mapped[str] = mapped_column(String(12), nullable=False)

    resolution: Mapped["Resolution"] = relationship(back_populates="votes")


class Sanction(Base):
    """Sanction disciplinaire contre une organisation membre (Règlement Intérieur art. 15)."""

    __tablename__ = "sanctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int] = mapped_column(ForeignKey("faitieres.id"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(15), nullable=False)
    motif: Mapped[str] = mapped_column(Text, nullable=False)
    # Avertissement, blâme, suspension : décidés par la DEN après avis favorable du CA (référence
    # de l'avis écrit). Radiation : décision de l'AG (référence de la résolution).
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    date_decision: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    notifiee_le: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    levee_le: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    levee_motif: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decide_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    faitiere: Mapped["Faitiere"] = relationship(back_populates="sanctions")

    @property
    def type_label(self) -> str:
        return SANCTION_TYPES.get(self.type, self.type)

    @property
    def is_active(self) -> bool:
        return self.levee_le is None


# ---------- Finances : dépenses, recettes, dons, budget, contrôle ----------

DEPENSE_CATEGORIES = {
    "fonctionnement": "Fonctionnement",
    "mission": "Frais de mission",
    "formation": "Formation",
    "communication": "Communication",
    "equipement": "Équipement",
    "autre": "Autre",
}
DEPENSE_STATUTS = {
    "a_valider": "À valider",
    "validee": "Validée (à payer)",
    "payee": "Payée",
    "annulee": "Annulée",
}
# Signatures requises sur un paiement : le DEN et le secrétaire aux finances (ou son adjoint)
SIGNATAIRE_ROLES = ("den", "finances")
RECETTE_CATEGORIES = {"subvention": "Subvention", "autre": "Autre recette"}
DON_NATURES = {"numeraire": "Numéraire", "nature": "En nature"}
PIECE_TYPES = {"cni": "Carte nationale d'identité", "passeport": "Passeport", "autre": "Autre pièce",
               "organisation": "Organisation (n° d'enregistrement)"}
BUDGET_SENS = {"recette": "Recettes", "depense": "Dépenses"}
# Catégories de recettes d'un budget (les dépenses reprennent DEPENSE_CATEGORIES)
BUDGET_RECETTE_CATEGORIES = {
    "cotisations": "Cotisations (annuelles, exceptionnelles, adhésion)",
    "dons": "Dons et legs",
    "subvention": "Subventions",
    "autre": "Autres recettes",
}
JUSTIFICATIF_TYPES = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}
JUSTIFICATIF_MAX_BYTES = 5 * 1024 * 1024


class Depense(Base):
    """Dépense de la PSIE. Elle n'est payable qu'après les deux signatures (DEN et secrétaire aux
    finances, issus d'organisations différentes). Jamais supprimée : une erreur s'annule avec motif."""

    __tablename__ = "depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    categorie: Mapped[str] = mapped_column(String(20), nullable=False)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date_depense: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    beneficiaire: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ordre_mission: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statut: Mapped[str] = mapped_column(String(12), default="a_valider")
    # Dépense non conforme (pièce manquante) : décision motivée du CA (Statuts art. 39.2)
    derogation_ca_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_le: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    mode_paiement: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference_paiement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    annulee_motif: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    validations: Mapped[list["ValidationDepense"]] = relationship(
        back_populates="depense", order_by="ValidationDepense.id", cascade="all, delete-orphan")
    justificatifs: Mapped[list["Justificatif"]] = relationship(
        back_populates="depense", order_by="Justificatif.id", cascade="all, delete-orphan")

    @property
    def categorie_label(self) -> str:
        return DEPENSE_CATEGORIES.get(self.categorie, self.categorie)

    @property
    def statut_label(self) -> str:
        return DEPENSE_STATUTS.get(self.statut, self.statut)

    def validation_de(self, role: str) -> "ValidationDepense | None":
        return next((v for v in self.validations if v.role == role), None)

    @property
    def roles_manquants(self) -> list[str]:
        return [r for r in SIGNATAIRE_ROLES if not self.validation_de(r)]


class ValidationDepense(Base):
    """Une des deux signatures d'une dépense."""

    __tablename__ = "validations_depenses"
    __table_args__ = (UniqueConstraint("depense_id", "role", name="uq_validation_depense_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    depense_id: Mapped[int] = mapped_column(ForeignKey("depenses.id"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    faitiere_origine_id: Mapped[int] = mapped_column(ForeignKey("faitieres.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    depense: Mapped["Depense"] = relationship(back_populates="validations")
    faitiere_origine: Mapped["Faitiere"] = relationship()


class Justificatif(Base):
    """Pièce justificative, stockée dans la base (donc couverte par les sauvegardes). Le type est
    déterminé par le contenu du fichier, jamais par ce qu'annonce le navigateur."""

    __tablename__ = "justificatifs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    depense_id: Mapped[int] = mapped_column(ForeignKey("depenses.id"), index=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    taille: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ajoute_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    depense: Mapped["Depense"] = relationship(back_populates="justificatifs")


class Recette(Base):
    """Recette hors cotisations et dons : subventions et autres ressources."""

    __tablename__ = "recettes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categorie: Mapped[str] = mapped_column(String(20), nullable=False)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    montant: Mapped[int] = mapped_column(Integer, nullable=False)
    date_recette: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    @property
    def categorie_label(self) -> str:
        return RECETTE_CATEGORIES.get(self.categorie, self.categorie)


class Don(Base):
    """Registre spécial des dons et libéralités (Statuts art. 39.3, RI art. 40)."""

    __tablename__ = "dons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    donateur_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    adresse: Mapped[str] = mapped_column(String(255), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    piece_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    piece_numero: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nature: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valeur: Mapped[int] = mapped_column(Integer, nullable=False)
    date_don: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    origine_fonds: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_renforcee: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    @property
    def nature_label(self) -> str:
        return DON_NATURES.get(self.nature, self.nature)


class Parametre(Base):
    """Réglage modifiable depuis l'application (ex. seuil des dons à vérification renforcée)."""

    __tablename__ = "parametres"

    cle: Mapped[str] = mapped_column(String(50), primary_key=True)
    valeur: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class BudgetAnnee(Base):
    """Budget annuel : élaboré par la DEN, validé par l'AGA (Statuts art. 13.1)."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annee: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    statut: Mapped[str] = mapped_column(String(10), default="projet")  # projet | valide
    reference_validation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    lignes: Mapped[list["BudgetLigne"]] = relationship(
        back_populates="budget", order_by="BudgetLigne.id", cascade="all, delete-orphan")


class BudgetLigne(Base):
    __tablename__ = "budget_lignes"
    __table_args__ = (UniqueConstraint("budget_id", "sens", "categorie", name="uq_budget_ligne"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), index=True, nullable=False)
    sens: Mapped[str] = mapped_column(String(10), nullable=False)
    categorie: Mapped[str] = mapped_column(String(20), nullable=False)
    montant_prevu: Mapped[int] = mapped_column(Integer, nullable=False)

    budget: Mapped["BudgetAnnee"] = relationship(back_populates="lignes")


class RapportCC(Base):
    """Rapport écrit d'un commissaire aux comptes, adressé à la DEN et au CA (Statuts art. 29)."""

    __tablename__ = "rapports_cc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    texte: Mapped[str] = mapped_column(Text, nullable=False)
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    auteur_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class DeclarationInteret(Base):
    """Déclaration d'un intérêt personnel par un membre d'un organe (Statuts art. 39.2, RI art. 41)."""

    __tablename__ = "declarations_interet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    declarant_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    objet: Mapped[str] = mapped_column(Text, nullable=False)
    date_declaration: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


# ---------- Contenu du site vitrine ----------

class ContenuSite(Base):
    """Un élément de contenu du site vitrine (une actualité, un partenaire, le mot du Président…).
    Le détail est un JSON dont la forme dépend de la collection (voir site_content.py)."""

    __tablename__ = "contenus_site"
    __table_args__ = (UniqueConstraint("collection", "cle", name="uq_contenu_collection_cle"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    # Identifiant lisible dans la collection (slug d'une actualité ou d'une faîtière) ; « main » pour
    # les contenus uniques (annonce, Président, contact) ; vide pour les autres.
    cle: Mapped[str | None] = mapped_column(String(80), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow,
                                                          onupdate=datetime.datetime.utcnow)


class MediaSite(Base):
    """Image ou PDF déposé par un éditeur, conservé en base (sauvegardé avec le reste)."""

    __tablename__ = "medias_site"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    extension: Mapped[str] = mapped_column(String(5), nullable=False)
    taille: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


# ---------- Espace d'une faîtière : délégués régionaux et écoles ----------

class DelegueRegional(Base):
    """Délégué d'une faîtière dans une DRENA (renseigné par la faîtière elle-même)."""

    __tablename__ = "delegues_regionaux"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int] = mapped_column(ForeignKey("faitieres.id", ondelete="CASCADE"), index=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    drena: Mapped[str] = mapped_column(String(80), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class Ecole(Base):
    """Établissement d'une faîtière."""

    __tablename__ = "ecoles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int] = mapped_column(ForeignKey("faitieres.id", ondelete="CASCADE"), index=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    localite: Mapped[str | None] = mapped_column(String(120), nullable=True)
    drena: Mapped[str | None] = mapped_column(String(80), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    niveau: Mapped[str | None] = mapped_column(String(20), nullable=True)
    directeur: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    recensements = relationship("RecensementEcole", cascade="all, delete-orphan", order_by="RecensementEcole.annee.desc()")
    resultats = relationship("ResultatExamen", cascade="all, delete-orphan", order_by="ResultatExamen.annee.desc()")
    bilans = relationship("BilanEcole", cascade="all, delete-orphan", order_by="BilanEcole.annee.desc()")

    @property
    def niveau_label(self) -> str:
        return NIVEAUX_ECOLE.get(self.niveau or "", "—")


NIVEAUX_ECOLE = {
    "prescolaire": "Préscolaire", "primaire": "Primaire", "secondaire": "Secondaire", "mixte": "Plusieurs niveaux",
    "superieur": "Supérieur / formation",
}
EXAMENS = {
    "cepe": "CEPE", "bepc": "BEPC", "bac": "Baccalauréat", "arabe_primaire": "Examen d'arabe (primaire)",
    "arabe_secondaire": "Examen d'arabe (secondaire)",
}
BILAN_STATUTS = {"brouillon": "Brouillon", "soumis": "Proposé à la PSIE", "a_corriger": "À corriger", "valide": "Validé"}
DEMANDE_TYPES = {"attestation": "Attestation", "rendez_vous": "Rendez-vous", "soutien": "Soutien / accompagnement",
                 "information": "Demande d'information", "autre": "Autre"}
DEMANDE_STATUTS = {"ouverte": "Ouverte", "en_cours": "En cours", "traitee": "Traitée"}


class RecensementEcole(Base):
    """Recensement annuel d'une école : élèves et personnel (administratif / enseignant, francophone / arabisant)."""

    __tablename__ = "recensements_ecole"
    __table_args__ = (UniqueConstraint("ecole_id", "annee", name="uq_recensement_ecole_annee"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id", ondelete="CASCADE"), index=True, nullable=False)
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    eleves: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    admin_francophone: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    admin_arabisant: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ens_francophone: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ens_arabisant: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    @property
    def personnel_total(self) -> int:
        return self.admin_francophone + self.admin_arabisant + self.ens_francophone + self.ens_arabisant


class ResultatExamen(Base):
    """Résultat d'un examen pour une école et une année."""

    __tablename__ = "resultats_examens"
    __table_args__ = (UniqueConstraint("ecole_id", "annee", "examen", name="uq_resultat_ecole_annee_examen"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id", ondelete="CASCADE"), index=True, nullable=False)
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    examen: Mapped[str] = mapped_column(String(20), nullable=False)
    inscrits: Mapped[int] = mapped_column(Integer, nullable=False)
    admis: Mapped[int] = mapped_column(Integer, nullable=False)

    @property
    def taux(self) -> float:
        return round(100 * self.admis / self.inscrits, 1) if self.inscrits else 0.0

    @property
    def examen_label(self) -> str:
        return EXAMENS.get(self.examen, self.examen)


class BilanEcole(Base):
    """Bilan annuel d'une école : proposé par la faîtière, examiné puis validé par la PSIE."""

    __tablename__ = "bilans_ecole"
    __table_args__ = (UniqueConstraint("ecole_id", "annee", name="uq_bilan_ecole_annee"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id", ondelete="CASCADE"), index=True, nullable=False)
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    resume: Mapped[str] = mapped_column(Text, nullable=False)
    difficultes: Mapped[str | None] = mapped_column(Text, nullable=True)
    perspectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon", nullable=False)
    avis: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    @property
    def statut_label(self) -> str:
        return BILAN_STATUTS.get(self.statut, self.statut)


class Annonce(Base):
    """Message de la PSIE vers toutes les faîtières (faitiere_id vide) ou vers une seule."""

    __tablename__ = "annonces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int | None] = mapped_column(ForeignKey("faitieres.id", ondelete="CASCADE"), index=True, nullable=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    texte: Mapped[str] = mapped_column(Text, nullable=False)
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class DemandeFaitiere(Base):
    """Demande d'une faîtière à la PSIE (attestation, rendez-vous, soutien…), avec réponse et suivi."""

    __tablename__ = "demandes_faitiere"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int] = mapped_column(ForeignKey("faitieres.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    objet: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="ouverte", nullable=False)
    reponse: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    faitiere = relationship("Faitiere")

    @property
    def type_label(self) -> str:
        return DEMANDE_TYPES.get(self.type, self.type)

    @property
    def statut_label(self) -> str:
        return DEMANDE_STATUTS.get(self.statut, self.statut)


DOC_CATEGORIES = {
    "statuts": "Statuts et règlement", "decision": "Décisions et notes", "convention": "Conventions et partenariats",
    "rapport": "Rapports", "modele": "Modèles de documents", "autre": "Autres",
}
COURRIER_SENS = {"arrivee": "Courrier arrivée", "depart": "Courrier départ"}
COURRIER_STATUTS = {"recu": "Reçu", "en_traitement": "En traitement", "traite": "Traité", "archive": "Archivé"}
CONVENTION_STATUTS = {
    "brouillon": "Brouillon", "soumise": "En attente d'avis du CA", "approuvee": "Avis favorable du CA",
    "rejetee": "Avis défavorable du CA", "signee": "Signée",
}


class Document(Base):
    """Document de la PSIE conservé en base (statuts, décisions, rapports, modèles…)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    categorie: Mapped[str] = mapped_column(String(20), default="autre", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    restreint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    mime: Mapped[str] = mapped_column(String(50), nullable=False)
    taille: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    @property
    def categorie_label(self) -> str:
        return DOC_CATEGORIES.get(self.categorie, self.categorie)


class Courrier(Base):
    """Registre du courrier : arrivée et départ, numéroté dans l'ordre (ARR-2026-0001, DEP-2026-0001)."""

    __tablename__ = "courriers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sens: Mapped[str] = mapped_column(String(10), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    date_courrier: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    correspondant: Mapped[str] = mapped_column(String(255), nullable=False)
    objet: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_externe: Mapped[str | None] = mapped_column(String(120), nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="recu", nullable=False)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    echeance: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    reponse_a_id: Mapped[int | None] = mapped_column(ForeignKey("courriers.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    nom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contenu: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    responsable = relationship("User", foreign_keys=[responsable_id])

    @property
    def sens_label(self) -> str:
        return COURRIER_SENS.get(self.sens, self.sens)

    @property
    def statut_label(self) -> str:
        return COURRIER_STATUTS.get(self.statut, self.statut)

    @property
    def en_retard(self) -> bool:
        return bool(self.echeance and self.statut in ("recu", "en_traitement") and self.echeance < datetime.date.today())


class Convention(Base):
    """Convention ou partenariat soumis au circuit d'approbation : DEN → avis du CA → signature du DEN."""

    __tablename__ = "conventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    partenaire: Mapped[str] = mapped_column(String(255), nullable=False)
    objet: Mapped[str | None] = mapped_column(Text, nullable=True)
    montant: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_debut: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_fin: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon", nullable=False)
    nom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contenu: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    etapes = relationship("ConventionEtape", cascade="all, delete-orphan", order_by="ConventionEtape.id")

    @property
    def statut_label(self) -> str:
        return CONVENTION_STATUTS.get(self.statut, self.statut)


class ConventionEtape(Base):
    """Historique du circuit d'une convention : qui a fait quoi, quand, avec quel commentaire."""

    __tablename__ = "convention_etapes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    convention_id: Mapped[int] = mapped_column(ForeignKey("conventions.id", ondelete="CASCADE"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    par: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class RegistreEntree(Base):
    """Registre légal des délibérations d'un organe. Les entrées ne se modifient ni ne se suppriment : chacune est
    chaînée à la précédente par une empreinte (toute altération rompt la chaîne et se voit à la vérification)."""

    __tablename__ = "registre_entrees"
    __table_args__ = (UniqueConstraint("registre", "numero", name="uq_registre_numero"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registre: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    date_acte: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    resume: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    assemblee_id: Mapped[int | None] = mapped_column(ForeignKey("assemblees.id", ondelete="SET NULL"), nullable=True)
    auteur: Mapped[str] = mapped_column(String(255), nullable=False)
    precedent: Mapped[str] = mapped_column(String(64), nullable=False)
    empreinte: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class Notification(Base):
    """Message adressé à une personne : s'affiche dans la cloche de l'application, et par e-mail si elle l'accepte."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="info", nullable=False)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    texte: Mapped[str | None] = mapped_column(Text, nullable=True)
    lien: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lue_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, index=True)


class ReinitialisationMdp(Base):
    """Lien « mot de passe oublié » : seul l'empreinte du jeton est conservée, jamais le jeton."""

    __tablename__ = "reinitialisations_mdp"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class PieceFaitiere(Base):
    """Pièce justificative d'un membre (statuts, récépissé, PV de désignation), conservée en base."""

    __tablename__ = "pieces_faitiere"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faitiere_id: Mapped[int] = mapped_column(ForeignKey("faitieres.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    extension: Mapped[str] = mapped_column(String(5), nullable=False)
    taille: Mapped[int] = mapped_column(Integer, nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    @property
    def type_label(self) -> str:
        return MEMBRE_PIECE_TYPES.get(self.type, self.type)


class RappelLog(Base):
    """Rappel réglementaire déjà envoyé (mandat qui arrive à échéance, rapport semestriel, états financiers
    avant une AG…) : une clé unique par rappel évite de l'envoyer deux fois."""

    __tablename__ = "rappels_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cle: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    sent_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class PieceDemande(Base):
    """Pièce jointe par un organisme à sa demande d'adhésion (statuts, récépissé) : examinée par la DEN, puis
    reversée à la fiche du membre si l'adhésion est acceptée."""

    __tablename__ = "pieces_demande"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demande_id: Mapped[int] = mapped_column(ForeignKey("demandes_adhesion.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    extension: Mapped[str] = mapped_column(String(5), nullable=False)
    taille: Mapped[int] = mapped_column(Integer, nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class AnnexeAssemblee(Base):
    """Document joint à une assemblée (rapport, budget, états financiers, projet de résolutions…)."""

    __tablename__ = "annexes_assemblee"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assemblee_id: Mapped[int] = mapped_column(ForeignKey("assemblees.id", ondelete="CASCADE"), index=True, nullable=False)
    titre: Mapped[str] = mapped_column(String(200), nullable=False)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    extension: Mapped[str] = mapped_column(String(5), nullable=False)
    taille: Mapped[int] = mapped_column(Integer, nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class AccesRole(Base):
    """Réglage de l'administrateur : niveau d'un rôle pour une rubrique, quand il diffère de la valeur par défaut."""

    __tablename__ = "acces_roles"
    __table_args__ = (UniqueConstraint("role", "section", name="uq_acces_role_section"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    niveau: Mapped[int] = mapped_column(Integer, nullable=False)


class AccesUtilisateur(Base):
    """Exception personnelle : niveau d'une personne pour une rubrique, à la place de celui de son rôle."""

    __tablename__ = "acces_utilisateurs"
    __table_args__ = (UniqueConstraint("user_id", "section", name="uq_acces_user_section"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    niveau: Mapped[int] = mapped_column(Integer, nullable=False)
