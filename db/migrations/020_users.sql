

CREATE TABLE IF NOT EXISTS users (
    user_id       BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN
                    ('professionnel_sante', 'assure', 'gestionnaire', 'administrateur')),
    insured_id    TEXT,          -- pseudonyme de l'assuré (rôle assure)
    provider_id   TEXT,          -- prestataire (rôle professionnel_sante)
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ DEFAULT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    lock_expired BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);
