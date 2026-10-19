-- Jetons de réinitialisation de mot de passe (mot de passe oublié).
-- À intégrer aux migrations Alembic de P1 ; l'API crée aussi cette table à la première
-- utilisation si elle est absente (api/repositories.py::ensure_reset_table).
-- Seul le hachage SHA-256 du jeton est stocké.
CREATE TABLE IF NOT EXISTS reinitialisations_mdp (
    reset_id       BIGSERIAL PRIMARY KEY,
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateurs (utilisateur_id) ON DELETE CASCADE,
    token_hash     TEXT NOT NULL UNIQUE,
    cree_le        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expire_le      TIMESTAMPTZ NOT NULL,
    utilise_le     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_reinitialisations_mdp_utilisateur
    ON reinitialisations_mdp (utilisateur_id);
