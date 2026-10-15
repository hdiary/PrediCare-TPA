-- 020_users.sql : comptes utilisateurs de la plateforme
-- ATTENTION : renommer avec le prochain numéro libre de db/migrations/.
-- Les scripts d'initdb ne s'exécutent qu'à la création du volume :
-- pour l'appliquer sur une base existante, lancer `docker compose down -v`
-- (efface les données) ou exécuter ce fichier à la main avec psql.
-- insured_id / provider_id : pas de clé étrangère pour l'instant ; ajouter
-- REFERENCES insureds(...) / providers(...) quand ces tables sont figées.

CREATE TABLE IF NOT EXISTS users (
    user_id       BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN
                    ('professionnel_sante', 'assure', 'gestionnaire', 'administrateur')),
    insured_id    TEXT,          -- pseudonyme de l'assuré (rôle assure)
    provider_id   TEXT,          -- prestataire (rôle professionnel_sante)
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);
