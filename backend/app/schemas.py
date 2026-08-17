import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, ConfigDict, Field


# ---------- Auth ----------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    access_level: str
    poste: str | None = None
    is_adjoint: bool = False


# ---------- News ----------
# Remarque : les contraintes min_length ne s'appliquent qu'à la création/mise à jour
# via l'API JSON. Les formulaires web de l'administration (routers/admin.py) créent les
# enregistrements directement en base sans passer par ces schémas ; NewsOut/ActivityOut
# restent donc volontairement permissifs en sortie pour ne jamais faire échouer la
# lecture publique (GET /api/news, /api/activities) à cause d'un enregistrement existant
# qui ne respecterait pas ces règles.

class NewsBase(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    excerpt: str = Field(min_length=3)
    content: str = ""
    published_at: datetime.date
    is_published: bool = True


class NewsCreate(NewsBase):
    pass


class NewsUpdate(NewsBase):
    pass


class NewsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    excerpt: str
    content: str = ""
    image_url: str | None = None
    published_at: datetime.date
    is_published: bool = True


# ---------- Activities ----------

class ActivityBase(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3)
    event_date: datetime.date


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(ActivityBase):
    pass


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    event_date: datetime.date
    status: Literal["upcoming", "past"]


# ---------- Contact ----------

class ContactCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    phone: str | None = None
    email: EmailStr
    establishment: str | None = None
    subject: str = Field(min_length=2, max_length=255)
    message: str = Field(min_length=5)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    phone: str | None
    email: EmailStr
    establishment: str | None
    subject: str
    message: str
    is_read: bool
    created_at: datetime.datetime


class AdhesionRequestCreate(BaseModel):
    nom_etablissement: str = Field(min_length=2, max_length=255)
    nom_directeur: str = Field(min_length=2, max_length=255)
    cycle: str | None = None
    type_enseignement: str = Field(min_length=2, max_length=30)
    telephone: str = Field(min_length=6, max_length=50)
    telephone_fixe: str | None = None
    email: EmailStr | None = None
    localite: str = Field(min_length=2, max_length=255)
    boite_postale: str | None = None
    propriete_terrain: str | None = None
    superficie_m2: int | None = None
    nombre_classes: int | None = None
    nombre_garcons: int | None = None
    nombre_filles: int | None = None
    message: str | None = None


class AdhesionRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code_demande: str | None
    nom_etablissement: str
    nom_directeur: str
    cycle: str | None
    type_enseignement: str
    telephone: str
    telephone_fixe: str | None
    email: str | None
    localite: str
    boite_postale: str | None
    propriete_terrain: str | None
    superficie_m2: int | None
    nombre_classes: int | None
    nombre_garcons: int | None
    nombre_filles: int | None
    message: str | None
    etat_demande: str
    etat_label: str
    agree: bool | None
    numero_agrement: str | None
    date_adhesion: datetime.date | None
    notes_examen: str | None
    examinee_at: datetime.datetime | None
    valide_at: datetime.datetime | None
    created_at: datetime.datetime


# ---------- Publications publiques ----------

class PublicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    category: str
    description: str | None
    published_at: datetime.date
    original_filename: str
    file_url: str


class PhotoPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    caption: str | None
    image_url: str
    created_at: datetime.datetime


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    question: str
    reponse: str
    ordre: int


class FaqCreate(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    reponse: str = Field(min_length=3)
    ordre: int = 0
    is_published: bool = True


class FaqUpdate(FaqCreate):
    pass


# ---------- Historique des anciens présidents ----------

class HistoriqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    periode: str | None
    mot: str | None
    ordre: int
    photo_url: str


class FondateurOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    role: str | None
    mot: str | None
    ordre: int
    photo_url: str


# ---------- Résultats aux examens scolaires islamiques ----------

class ResultatExamenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    etablissement_nom: str
    annee_scolaire: str
    type_examen: str
    nombre_inscrits: int
    nombre_admis: int
    nombre_admis_garcons: int
    nombre_admis_filles: int
    taux_reussite: float


class BaremetreAnneeOut(BaseModel):
    annee_scolaire: str
    type_examen: str
    inscrits: int
    admis: int
    taux_reussite: float


class BaremetreRegionOut(BaseModel):
    annee_scolaire: str
    bureau_local: str
    inscrits: int
    admis: int
    taux_reussite: float


class BaremetreOut(BaseModel):
    national: list[BaremetreAnneeOut]
    regional: list[BaremetreRegionOut]


# ---------- Carte interactive (établissements & délégations) ----------

class EtablissementPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    bureau_local: str | None = None
    district: str | None = None
    region: str | None = None
    directeur_nom: str | None = None
    type_enseignement: str
    logo_url: str | None = None
    numero_agrement: str | None = None
    statut_agrement: str
    statut_agrement_label: str
    is_ecole_modele: bool
    categorie: str
    categorie_label: str


class PartenariatRequestCreate(BaseModel):
    nom: str = Field(min_length=2, max_length=255)
    type: str = Field(min_length=2, max_length=30)
    pays: str | None = None
    contact_nom: str = Field(min_length=2, max_length=255)
    contact_email: EmailStr
    contact_telephone: str | None = None
    message: str = Field(min_length=10)
    projet_id: int | None = None


class DonDeclareCreate(BaseModel):
    nom_donateur: str = Field(min_length=2, max_length=255)
    email: EmailStr | None = None
    telephone: str | None = None
    montant: int = Field(gt=0)
    date_don: datetime.date
    message: str | None = None


class SearchResultOut(BaseModel):
    type: str
    title: str
    subtitle: str | None = None
    url: str


class EtablissementsStatsOut(BaseModel):
    ecoles: int
    regions: int
    enseignants: int
    eleves: int


class PartenairePublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    type: str
    pays: str | None = None
    logo_url: str | None = None


class ProjetPublicOut(BaseModel):
    id: int
    titre: str
    description: str | None = None
    statut: str
    statut_label: str


class CarteMarkerOut(BaseModel):
    type: str  # "etablissement" | "delegation"
    nom: str
    detail: str | None = None
    latitude: float
    longitude: float


# ---------- Gouvernance (organigramme public du BEN) ----------

class GouvernanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    poste_title: str
    poste_subtitle: str | None
    titulaire_nom: str | None
    titulaire_photo_url: str | None
    adjoint_nom: str | None
    adjoint_photo_url: str | None
    ordre: int
