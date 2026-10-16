#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
  -- Base interne de Metabase (séparée des données métier)
  CREATE DATABASE metabase_app;

  -- Utilisateur lecture seule pour les requêtes du dashboard
  CREATE ROLE metabase_ro LOGIN PASSWORD '${METABASE_RO_PASSWORD}';
  GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO metabase_ro;
  GRANT USAGE ON SCHEMA public TO metabase_ro;
EOSQL