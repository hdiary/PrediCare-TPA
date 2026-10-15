"""P1 0002 - business tables (data contract v0.1, sections 4 to 8 and 10)

Types follow the contract: amounts are BIGINT (MGA, no decimals), dates are
DATE, 0/1 flags are BOOLEAN. Only structural constraints live in the database;
business suspicion (prices above max tariff, repeated numero_facture, re-used
ordonnance_id...) is deliberately NOT blocked: those are the frauds P2 detects.

Revision ID: p1_0002
Revises: p1_0001
"""
from alembic import op

revision = "p1_0002"
down_revision = "p1_0001"
branch_labels = None
depends_on = None

TABLES = [
    "labels_prestataires", "labels_fraude", "lignes_facture", "factures",
    "ordonnance_lignes", "ordonnances", "assures", "contrats",
    "grille_tarifaire", "prestataires", "garanties",
    "referentiel_medicaments", "referentiel_actes",
]  # drop order (children first)

UPGRADE_SQL = r"""
CREATE TABLE referentiel_actes (
    code_acte          TEXT PRIMARY KEY,
    libelle            TEXT NOT NULL,
    categorie          TEXT NOT NULL,
    specialite         TEXT,
    tarif_min          BIGINT NOT NULL CHECK (tarif_min >= 0),
    tarif_reference    BIGINT NOT NULL,
    tarif_max          BIGINT NOT NULL,
    ordonnance_requise BOOLEAN NOT NULL,
    entente_prealable  BOOLEAN NOT NULL,
    sexe_requis        CHAR(1) CHECK (sexe_requis IN ('F', 'M')),
    age_min            SMALLINT NOT NULL,
    age_max            SMALLINT NOT NULL,
    CHECK (tarif_min <= tarif_reference AND tarif_reference <= tarif_max),
    CHECK (age_min <= age_max)
);

CREATE TABLE referentiel_medicaments (
    code_medicament TEXT PRIMARY KEY,
    libelle         TEXT NOT NULL,
    prix_reference  BIGINT NOT NULL CHECK (prix_reference >= 0),
    remboursable    BOOLEAN NOT NULL,
    classe          TEXT NOT NULL,
    chronique       BOOLEAN NOT NULL
);

CREATE TABLE garanties (
    formule                         TEXT NOT NULL
        CHECK (formule IN ('ESSENTIEL', 'CONFORT', 'PREMIUM')),
    categorie                       TEXT NOT NULL CHECK (categorie IN (
        'CONSULTATION', 'PHARMACIE', 'LABORATOIRE', 'IMAGERIE', 'DENTAIRE',
        'KINESITHERAPIE', 'MATERNITE', 'OPTIQUE', 'HOSPITALISATION')),
    taux_remboursement              SMALLINT NOT NULL
        CHECK (taux_remboursement BETWEEN 0 AND 100),
    plafond_annuel_categorie        BIGINT NOT NULL
        CHECK (plafond_annuel_categorie >= 0),
    franchise_par_facture           BIGINT NOT NULL
        CHECK (franchise_par_facture >= 0),
    delai_carence_jours             SMALLINT NOT NULL
        CHECK (delai_carence_jours >= 0),
    plafond_annuel_global           BIGINT NOT NULL
        CHECK (plafond_annuel_global >= 0),
    prime_annuelle_par_beneficiaire BIGINT NOT NULL
        CHECK (prime_annuelle_par_beneficiaire >= 0),
    attestation_requise             BOOLEAN NOT NULL,
    actes_exclus                    TEXT[],
    pieces_justificatives           TEXT NOT NULL,
    PRIMARY KEY (formule, categorie)
);

CREATE TABLE prestataires (
    prestataire_id        TEXT PRIMARY KEY
        CHECK (prestataire_id ~ '^PRE-[0-9]{5}$'),
    nom                   TEXT NOT NULL,
    type_prestataire      TEXT NOT NULL,
    specialite            TEXT,
    ville                 TEXT NOT NULL,
    quartier              TEXT NOT NULL,
    adresse               TEXT NOT NULL,
    telephone             TEXT NOT NULL,
    numero_onm            TEXT CHECK (numero_onm ~ '^ONM-[0-9]{5}$'),
    nif                   TEXT NOT NULL CHECK (nif ~ '^[0-9]{10}$'),
    horaires              TEXT NOT NULL,
    jours_ouverture       TEXT NOT NULL CHECK (jours_ouverture ~ '^[1-7]{1,7}$'),
    heure_ouverture       SMALLINT NOT NULL
        CHECK (heure_ouverture BETWEEN 0 AND 24),
    heure_fermeture       SMALLINT NOT NULL
        CHECK (heure_fermeture BETWEEN 0 AND 24),
    niveau_tarif          TEXT NOT NULL
        CHECK (niveau_tarif IN ('RAISONNABLE', 'ELEVE', 'TRES_ELEVE')),
    note_qualite          SMALLINT NOT NULL CHECK (note_qualite BETWEEN 1 AND 5),
    conventionne          BOOLEAN NOT NULL,
    date_conventionnement DATE NOT NULL,
    date_fin_convention   DATE,
    statut                TEXT NOT NULL CHECK (statut IN ('ACTIF', 'RADIE')),
    CHECK (date_fin_convention IS NULL
           OR date_fin_convention >= date_conventionnement)
);

CREATE TABLE grille_tarifaire (
    prestataire_id TEXT NOT NULL REFERENCES prestataires (prestataire_id),
    code           TEXT NOT NULL,  -- acte OR medicament, see view ref_codes
    tarif_pratique BIGINT NOT NULL CHECK (tarif_pratique >= 0),
    PRIMARY KEY (prestataire_id, code)
);

CREATE TABLE contrats (
    contrat_id            TEXT PRIMARY KEY CHECK (contrat_id ~ '^CTR-[0-9]{6}$'),
    numero_police         TEXT NOT NULL,
    souscripteur_id       TEXT NOT NULL,  -- SOU-nnnn or SOU-IND
    souscripteur_nom      TEXT NOT NULL,
    secteur               TEXT NOT NULL,
    formule               TEXT NOT NULL
        CHECK (formule IN ('ESSENTIEL', 'CONFORT', 'PREMIUM')),
    date_effet_police     DATE NOT NULL,
    date_effet            DATE NOT NULL,
    date_fin              DATE,
    statut                TEXT NOT NULL CHECK (statut IN ('ACTIF', 'RESILIE')),
    nb_beneficiaires      SMALLINT NOT NULL CHECK (nb_beneficiaires >= 1),
    prime_annuelle_totale BIGINT NOT NULL CHECK (prime_annuelle_totale >= 0),
    CHECK (date_fin IS NULL OR date_fin >= date_effet),
    CHECK ((statut = 'RESILIE') = (date_fin IS NOT NULL))
);

CREATE TABLE assures (
    assure_id           TEXT PRIMARY KEY CHECK (assure_id ~ '^ASS-[0-9A-F]{10}$'),
    contrat_id          TEXT NOT NULL REFERENCES contrats (contrat_id),
    rang_beneficiaire   TEXT NOT NULL CHECK (rang_beneficiaire IN
                            ('ASSURE_PRINCIPAL', 'CONJOINT', 'ENFANT')),
    assure_principal_id TEXT NOT NULL
        REFERENCES assures (assure_id) DEFERRABLE INITIALLY DEFERRED,
    sexe                CHAR(1) NOT NULL CHECK (sexe IN ('M', 'F')),
    annee_naissance     SMALLINT NOT NULL CHECK (annee_naissance >= 1900),
    ville               TEXT NOT NULL,
    date_adhesion       DATE NOT NULL,
    date_radiation      DATE,
    CHECK (date_radiation IS NULL OR date_radiation >= date_adhesion),
    CHECK (rang_beneficiaire <> 'ASSURE_PRINCIPAL'
           OR assure_principal_id = assure_id)
);

CREATE TABLE ordonnances (
    ordonnance_id          TEXT PRIMARY KEY
        CHECK (ordonnance_id ~ '^ORD-[0-9]{7}$'),
    assure_id              TEXT NOT NULL REFERENCES assures (assure_id),
    prescripteur_id        TEXT NOT NULL REFERENCES prestataires (prestataire_id),
    date_prescription      DATE NOT NULL,
    validite_jours         SMALLINT NOT NULL CHECK (validite_jours >= 1),
    type_ordonnance        TEXT NOT NULL CHECK (type_ordonnance IN
                               ('MEDICAMENTS', 'EXAMENS', 'KINE', 'OPTIQUE')),
    diagnostic             TEXT,
    renseignement_clinique TEXT
);

CREATE TABLE ordonnance_lignes (
    ordonnance_id TEXT NOT NULL
        REFERENCES ordonnances (ordonnance_id) ON DELETE CASCADE,
    num_ligne     SMALLINT NOT NULL CHECK (num_ligne >= 1),
    code          TEXT NOT NULL,  -- acte OR medicament
    libelle       TEXT NOT NULL,
    quantite      SMALLINT NOT NULL CHECK (quantite > 0),
    posologie     TEXT,
    PRIMARY KEY (ordonnance_id, num_ligne)
);

-- numero_facture is NOT unique on purpose (DOUBLON / FRACTIONNEMENT signal);
-- ordonnance_id may be re-used (SURCONSOMMATION signal).
CREATE TABLE factures (
    facture_id             TEXT PRIMARY KEY CHECK (facture_id ~ '^FAC-[0-9]{8}$'),
    numero_facture         TEXT NOT NULL,
    prestataire_id         TEXT NOT NULL REFERENCES prestataires (prestataire_id),
    assure_id              TEXT NOT NULL REFERENCES assures (assure_id),
    contrat_id             TEXT NOT NULL REFERENCES contrats (contrat_id),
    ordonnance_id          TEXT REFERENCES ordonnances (ordonnance_id),
    type_facture           TEXT NOT NULL CHECK (type_facture IN (
        'CONSULTATION', 'PHARMACIE', 'LABORATOIRE', 'IMAGERIE', 'DENTAIRE',
        'KINESITHERAPIE', 'MATERNITE', 'OPTIQUE', 'HOSPITALISATION')),
    date_soin              DATE NOT NULL,
    heure_soin             TIME NOT NULL,
    date_facture           DATE NOT NULL,
    date_reception         DATE NOT NULL,
    canal_reception        TEXT NOT NULL CHECK (canal_reception IN
                               ('PAPIER_SCAN', 'EMAIL', 'PORTAIL_PRESTATAIRE')),
    mode_reglement         TEXT NOT NULL CHECK (mode_reglement IN
                               ('TIERS_PAYANT', 'REMBOURSEMENT_ASSURE')),
    attestation_pec_id     TEXT,
    entente_prealable_id   TEXT,
    devise                 TEXT NOT NULL CHECK (devise = 'MGA'),
    nb_lignes              SMALLINT NOT NULL CHECK (nb_lignes >= 1),
    montant_total          BIGINT NOT NULL CHECK (montant_total >= 0),
    montant_eligible       BIGINT NOT NULL CHECK (montant_eligible >= 0),
    -- LEAK columns (result of the historical decision): kept for BI/audit,
    -- excluded from view v_factures_features, never used by the model.
    montant_pris_en_charge BIGINT NOT NULL CHECK (montant_pris_en_charge >= 0),
    reste_a_charge         BIGINT NOT NULL,
    statut                 TEXT NOT NULL
        CHECK (statut IN ('PAYEE', 'REJETEE', 'EN_COURS')),
    motif_rejet            TEXT,
    date_traitement        DATE,
    CHECK (montant_eligible <= montant_total)
);

CREATE TABLE lignes_facture (
    ligne_id      TEXT PRIMARY KEY CHECK (ligne_id ~ '^FAC-[0-9]{8}-L[0-9]{2}$'),
    facture_id    TEXT NOT NULL REFERENCES factures (facture_id)
        ON DELETE CASCADE,
    num_ligne     SMALLINT NOT NULL CHECK (num_ligne >= 1),
    code          TEXT NOT NULL,  -- acte OR medicament
    type_ligne    TEXT NOT NULL CHECK (type_ligne IN ('ACTE', 'MEDICAMENT')),
    libelle       TEXT NOT NULL,
    quantite      SMALLINT NOT NULL CHECK (quantite > 0),
    prix_unitaire BIGINT NOT NULL CHECK (prix_unitaire >= 0),
    montant       BIGINT NOT NULL CHECK (montant >= 0),
    UNIQUE (facture_id, num_ligne)
);

-- Ground truth for P2 (file provided separately by the course team).
-- Never exposed in v_factures_features.
CREATE TABLE labels_fraude (
    facture_id       TEXT PRIMARY KEY REFERENCES factures (facture_id)
        ON DELETE CASCADE,
    est_fraude       BOOLEAN NOT NULL,
    type_fraude      TEXT CHECK (type_fraude IN (
        'SURFACTURATION', 'QUANTITE_EXCESSIVE', 'UPCODING',
        'LIGNES_NON_PRESCRITES', 'SUBSTITUTION_PRODUIT', 'ORDONNANCE_EXPIREE',
        'SOINS_JOUR_FERME', 'DOUBLON', 'FRACTIONNEMENT', 'SURCONSOMMATION',
        'ACTE_FICTIF', 'INCOHERENCE_PROFIL', 'PRESTATAIRE_RADIE',
        'HORS_COUVERTURE')),
    detail_fraude    TEXT,
    est_valide       BOOLEAN NOT NULL,
    motif_invalidite TEXT
);

CREATE TABLE labels_prestataires (
    prestataire_id TEXT PRIMARY KEY REFERENCES prestataires (prestataire_id)
        ON DELETE CASCADE,
    est_suspect    BOOLEAN NOT NULL
);

-- foreign-key and filter indexes
CREATE INDEX ix_assures_contrat        ON assures (contrat_id);
CREATE INDEX ix_ordonnances_assure     ON ordonnances (assure_id);
CREATE INDEX ix_ordonnances_prescr     ON ordonnances (prescripteur_id);
CREATE INDEX ix_factures_assure        ON factures (assure_id);
CREATE INDEX ix_factures_prestataire   ON factures (prestataire_id);
CREATE INDEX ix_factures_contrat       ON factures (contrat_id);
CREATE INDEX ix_factures_ordonnance    ON factures (ordonnance_id);
CREATE INDEX ix_factures_date_soin     ON factures (date_soin);
CREATE INDEX ix_factures_numero        ON factures (numero_facture);
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        bind.exec_driver_sql(f"DROP TABLE IF EXISTS {table} CASCADE")
