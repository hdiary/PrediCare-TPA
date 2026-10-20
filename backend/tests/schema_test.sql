-- Schéma MINIMAL pour les tests d'intégration (noms de tables et colonnes lus par l'API).
-- Le vrai schéma vient des migrations de P1/P3 ; ici seules les colonnes utilisées par l'API.
CREATE TABLE utilisateurs (
  utilisateur_id SERIAL PRIMARY KEY, identifiant TEXT UNIQUE, email TEXT UNIQUE NOT NULL, mot_de_passe_hash TEXT NOT NULL,
  role TEXT NOT NULL, assure_id TEXT, prestataire_id TEXT, actif BOOLEAN NOT NULL DEFAULT true,
  tentatives_echouees INT NOT NULL DEFAULT 0, verrouille_jusqua TIMESTAMPTZ,
  derniere_connexion TIMESTAMPTZ);
CREATE TABLE utilisateurs_identites (
  utilisateur_id INT PRIMARY KEY REFERENCES utilisateurs(utilisateur_id),
  donnees_chiffrees BYTEA NOT NULL, key_version SMALLINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE journal_audit (
  audit_id BIGSERIAL PRIMARY KEY, date TIMESTAMPTZ NOT NULL DEFAULT now(), type_evenement TEXT NOT NULL,
  utilisateur_id INT, type_entite TEXT, entite_id TEXT, nom_modele TEXT, version_modele TEXT,
  entree JSONB, sortie JSONB);
CREATE TABLE configuration (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
CREATE TABLE assures (
  assure_id TEXT PRIMARY KEY, contrat_id TEXT, rang_beneficiaire TEXT,
  date_radiation DATE);
CREATE TABLE prestataires (
  prestataire_id TEXT PRIMARY KEY, nom TEXT, ville TEXT, statut TEXT);
CREATE TABLE garanties (categorie TEXT);
CREATE TABLE referentiel_actes (code_acte TEXT PRIMARY KEY, libelle TEXT);
CREATE TABLE referentiel_medicaments (code_medicament TEXT PRIMARY KEY, libelle TEXT);
CREATE TABLE factures (
  facture_id TEXT PRIMARY KEY, numero_facture TEXT, prestataire_id TEXT, assure_id TEXT, contrat_id TEXT,
  ordonnance_id TEXT, type_facture TEXT, date_soin DATE, heure_soin TIME, date_facture DATE,
  date_reception DATE, canal_reception TEXT, mode_reglement TEXT, attestation_pec_id TEXT,
  entente_prealable_id TEXT, devise TEXT, nb_lignes INT, montant_total BIGINT, montant_eligible BIGINT,
  montant_pris_en_charge BIGINT, reste_a_charge BIGINT, statut TEXT, motif_rejet TEXT,
  date_traitement DATE);
CREATE TABLE lignes_facture (
  ligne_id TEXT PRIMARY KEY, facture_id TEXT, num_ligne INT, code TEXT, type_ligne TEXT, libelle TEXT,
  quantite INT, prix_unitaire BIGINT, montant BIGINT);
CREATE TABLE predictions (
  prediction_id SERIAL PRIMARY KEY, facture_id TEXT UNIQUE, nom_modele TEXT, version_modele TEXT,
  score FLOAT, seuil_utilise FLOAT, est_alerte BOOLEAN, latence_ms INT, variables JSONB,
  soumis_par INT, date TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE explications_shap (prediction_id INT, facture_id TEXT, valeurs JSONB);
CREATE TABLE decisions_gestionnaire (
  decision_id SERIAL PRIMARY KEY, prediction_id INT, facture_id TEXT, gestionnaire_id INT,
  decision TEXT, commentaire TEXT, montant_economise BIGINT,
  date_decision TIMESTAMPTZ NOT NULL DEFAULT now());
INSERT INTO assures (assure_id, contrat_id, rang_beneficiaire) VALUES
  ('ASS-9CAA1484E0', 'CTR-000001', 'ASSURE_PRINCIPAL'),
  ('ASS-1111111111', 'CTR-000002', 'CONJOINT');
INSERT INTO prestataires (prestataire_id, nom, ville, statut) VALUES
  ('PRE-00214', 'Cabinet Test', 'Antananarivo', 'ACTIF'),
  ('PRE-00999', 'Clinique Test', 'Toamasina', 'ACTIF');
INSERT INTO garanties VALUES ('CONSULTATION'), ('PHARMACIE');
INSERT INTO referentiel_actes VALUES ('CONS-GEN', 'Consultation générale'), ('RADIO-1', 'Radiographie');
INSERT INTO referentiel_medicaments VALUES ('MED-1', 'Paracétamol 500 mg');
