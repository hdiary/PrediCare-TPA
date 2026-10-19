"""Schémas des listes de factures (suivi prestataire / remboursements assuré)."""
from datetime import date

from pydantic import BaseModel


class InvoiceLineOut(BaseModel):
    num_ligne: int
    code: str
    libelle: str | None = None
    quantite: int
    prix_unitaire: int
    montant: int


class InvoiceOut(BaseModel):
    facture_id: str
    numero_facture: str | None = None
    prestataire_id: str
    assure_id: str
    date_soin: date
    nb_lignes: int | None = None
    montant_total: int
    montant_pris_en_charge: int | None = None
    reste_a_charge: int | None = None
    statut: str
    lignes: list[InvoiceLineOut] = []


class InvoiceList(BaseModel):
    items: list[InvoiceOut]
    total: int
