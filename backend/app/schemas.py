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


# ---------- Historique des anciens présidents ----------

class HistoriqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    periode: str | None
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
    taux_reussite: float


# ---------- Carte interactive (établissements & délégations) ----------

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
