"""Pydantic contracts for the business tables used by the API phases."""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.schemas import Role

InvoiceType = Literal[
    "CONSULTATION",
    "PHARMACIE",
    "LABORATOIRE",
    "IMAGERIE",
    "DENTAIRE",
    "KINESITHERAPIE",
    "MATERNITE",
    "OPTIQUE",
    "HOSPITALISATION",
]
Formula = Literal["ESSENTIEL", "CONFORT", "PREMIUM"]
PrescriptionType = Literal["MEDICAMENTS", "EXAMENS", "KINE", "OPTIQUE"]
LineType = Literal["ACTE", "MEDICAMENT"]
InvoiceChannel = Literal["PAPIER_SCAN", "EMAIL", "PORTAIL_PRESTATAIRE"]
PaymentMode = Literal["TIERS_PAYANT", "REMBOURSEMENT_ASSURE"]
BeneficiaryRank = Literal["ASSURE_PRINCIPAL", "CONJOINT", "ENFANT"]


class InvoiceLineIn(BaseModel):
    """A line submitted by a healthcare provider."""

    num_ligne: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=80)
    type_ligne: LineType
    libelle: str = Field(min_length=1, max_length=255)
    quantite: int = Field(gt=0)
    prix_unitaire: int = Field(ge=0)
    montant: int = Field(ge=0)

    @model_validator(mode="after")
    def amount_matches_quantity(self):
        if self.montant != self.quantite * self.prix_unitaire:
            raise ValueError("Le montant de la ligne doit correspondre à la quantité et au prix")
        return self


class InvoiceCreate(BaseModel):
    """Invoice input; the provider identity is supplied by the JWT."""

    model_config = ConfigDict(extra="forbid")

    facture_id: str = Field(pattern=r"^FAC-[0-9]{8}$")
    numero_facture: str = Field(min_length=1, max_length=120)
    assure_id: str = Field(pattern=r"^ASS-[0-9A-F]{10}$")
    contrat_id: str = Field(pattern=r"^CTR-[0-9]{6}$")
    ordonnance_id: str | None = Field(default=None, pattern=r"^ORD-[0-9]{7}$")
    type_facture: InvoiceType
    date_soin: date
    heure_soin: time
    date_facture: date
    devise: Literal["MGA"] = "MGA"
    canal_reception: InvoiceChannel = "PORTAIL_PRESTATAIRE"
    mode_reglement: PaymentMode = "TIERS_PAYANT"
    attestation_pec_id: str | None = None
    entente_prealable_id: str | None = None
    lignes: list[InvoiceLineIn] = Field(min_length=1)
    montant_total: int = Field(ge=0)

    @model_validator(mode="after")
    def total_matches_lines(self):
        if self.montant_total != sum(line.montant for line in self.lignes):
            raise ValueError("Le montant total doit correspondre à la somme des lignes")
        if len({line.num_ligne for line in self.lignes}) != len(self.lignes):
            raise ValueError("Les numéros de ligne doivent être uniques")
        return self


class InvoiceOut(BaseModel):
    """Safe invoice representation shared by provider and insured views."""

    model_config = ConfigDict(from_attributes=True)

    facture_id: str
    numero_facture: str
    contrat_id: str
    ordonnance_id: str | None
    type_facture: InvoiceType
    date_soin: date
    heure_soin: time
    date_facture: date
    date_reception: date
    devise: str
    nb_lignes: int
    montant_total: int
    montant_eligible: int
    montant_pris_en_charge: int
    reste_a_charge: int
    statut: Literal["PAYEE", "REJETEE", "EN_COURS"]
    motif_rejet: str | None
    date_traitement: date | None


class FacturePrestataireOut(BaseModel):
    """Provider-safe invoice response.

    Deliberately excludes score, SHAP values, fraud codes, and alert state.
    """

    facture_id: str
    numero_facture: str
    type_facture: InvoiceType
    date_soin: date
    montant_total: int = Field(ge=0)
    devise: Literal["MGA"]
    statut: Literal[
        "EN_COURS",
        "PAYEE",
        "REJETEE",
        "EN_ATTENTE_GESTIONNAIRE",
    ]


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prestataire_id: str
    nom: str
    type_prestataire: str
    specialite: str | None
    ville: str
    quartier: str
    statut: Literal["ACTIF", "RADIE"]
    conventionne: bool


class InsuredOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assure_id: str
    contrat_id: str
    rang_beneficiaire: BeneficiaryRank
    sexe: Literal["M", "F"]
    annee_naissance: int
    ville: str
    date_adhesion: date
    date_radiation: date | None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contrat_id: str
    numero_police: str
    formule: Formula
    date_effet_police: date
    date_effet: date
    date_fin: date | None
    statut: Literal["ACTIF", "RESILIE"]


class GuaranteeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    formule: Formula
    categorie: InvoiceType
    taux_remboursement: int = Field(ge=0, le=100)
    plafond_annuel_categorie: int = Field(ge=0)
    franchise_par_facture: int = Field(ge=0)
    delai_carence_jours: int = Field(ge=0)
    plafond_annuel_global: int = Field(ge=0)
    attestation_requise: bool
    actes_exclus: list[str] | None
    pieces_justificatives: str


class ReferenceCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    type_ligne: LineType
    libelle: str
    tarif_min: int | None
    tarif_reference: int
    tarif_max: int | None


class PrescriptionLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ordonnance_id: str
    num_ligne: int
    code: str
    libelle: str
    quantite: int
    posologie: str | None


class PrescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ordonnance_id: str
    assure_id: str
    prescripteur_id: str
    date_prescription: date
    validite_jours: int
    type_ordonnance: PrescriptionType
    diagnostic: str | None
    renseignement_clinique: str | None
    lignes: list[PrescriptionLineOut] = Field(default_factory=list)


class ModelVersionOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    version: str
    artifact_path: str | None = None
    sha256: str
    metrics: dict
    status: Literal["CANDIDAT", "ACTIF", "ARCHIVE"]
    metadata: dict
    trained_at: datetime | None = None
    activated_at: datetime | None = None
    active_par: int | None = None


class UserAdminOut(BaseModel):
    user_id: int
    email: str
    role: Role
    assure_id: str | None
    prestataire_id: str | None
    actif: bool
    cree_le: datetime
    derniere_connexion: datetime | None
