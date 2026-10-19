-- 020_utilisateurs_configuration.sql : tables de P3 (contrat de données, section 11)
-- PRÉREQUIS : les migrations de P1 (assures, prestataires...) doivent avoir un numéro INFÉRIEUR.
-- Renommer ce fichier au besoin. Rappel : initdb.d ne s'exécute qu'à la création du volume.

CREATE TABLE IF NOT EXISTS roles (
    code    TEXT PRIMARY KEY,
    libelle TEXT NOT NULL
);
INSERT INTO roles (code, libelle) VALUES
    ('professionnel_sante', 'Professionnel de santé'),
    ('assure',              'Assuré'),
    ('gestionnaire',        'Gestionnaire'),
    ('administrateur',      'Administrateur')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS utilisateurs (
    utilisateur_id     BIGSERIAL PRIMARY KEY,
    email              TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    mot_de_passe_hash  TEXT NOT NULL,
    role               TEXT NOT NULL REFERENCES roles(code),
    assure_id          TEXT REFERENCES assures(assure_id),            -- rôle assuré
    prestataire_id     TEXT REFERENCES prestataires(prestataire_id),  -- rôle professionnel de santé
    actif              BOOLEAN NOT NULL DEFAULT TRUE,
    cree_le            TIMESTAMPTZ NOT NULL DEFAULT now(),
    derniere_connexion TIMESTAMPTZ,
    tentatives_echouees INT NOT NULL DEFAULT 0,   -- échecs de connexion consécutifs (S12)
    verrouille_jusqua  TIMESTAMPTZ                -- compte verrouillé jusqu'à cette date
);

-- Configuration modifiable en direct (seuil, canaux de notification)
CREATE TABLE IF NOT EXISTS configuration (
    cle            TEXT PRIMARY KEY,
    valeur         TEXT NOT NULL,
    mis_a_jour_le  TIMESTAMPTZ NOT NULL DEFAULT now(),
    mis_a_jour_par TEXT
);
INSERT INTO configuration (cle, valeur) VALUES
    ('seuil_alerte', '0.8'),
    ('notif_slack', 'true'),
    ('notif_email', 'true'),
    ('notif_email_destinataire', 'gestionnaire@predicare.local')
ON CONFLICT (cle) DO NOTHING;
