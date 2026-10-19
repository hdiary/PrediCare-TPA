# Rapport de phase 4 — registre et chargement ML

## Fichiers créés ou modifiés

- `backend/api/services/ml_service.py` : état unique du modèle actif, verrou, vérification SHA-256, smoke test score/SHAP, activation et rechargement inter-workers.
- `backend/api/services/model_registry.py` : façade de compatibilité sans état propre ; tous les symboles viennent de `ml_service`.
- `backend/api/model_seed.py`, `backend/entrypoint.sh`, `backend/ml/models_seed/` : deux artefacts seed suivis par Git, avec schéma, échantillon et métadonnées ; génération de secours depuis l’ancien registre seulement pour les installations historiques.
- `backend/Dockerfile`, `docker-compose.yml` : `libgomp1`, entrypoint, volume persistant `models_data:/models`.
- `backend/api/routers/model.py`, `backend/api/config.py`, `backend/api/main.py`, `backend/api/routers/admin.py` : routes et initialisation du registre.
- `backend/ingestion/migrations/versions/0012_phase4_model_registry.py` : registre des versions et tables manquantes reportées depuis les SQL historiques.
- `tests/test_model_registry_phase4.py`, `tests/test_security_s1_s12.py` : droits `/model/*`, activation/rollback, SHA corrompu et conservation de l’ancienne version.
- `db/backup/scripts/backup.sh`, `db/backup/scripts/restore.sh`, `scripts/backup.sh`, `scripts/restore.sh`, `scripts/backup.ps1`, `scripts/restore.ps1` : sauvegarde et restauration du bundle `models_data` avec PostgreSQL.

## Décisions et écarts

1. `model_versions` est la source de vérité à l’exécution. `registry.json` sert uniquement à fabriquer le seed.
2. `ml_service` est le seul module qui possède `_bundle`, `_lock` et `last_error`. Le module `model_registry` ne fait que réexporter ces objets pour préserver les imports existants.
3. La génération binaire des seeds se fait au démarrage de l’image, car le chargement de LightGBM/SHAP est dépendant de l’environnement Linux de l’image Docker. Le seed contient la version active et la version précédente la plus récente.
4. Les définitions déjà présentes dans Alembic ne sont pas recréées : `predictions` et `decisions_gestionnaires` viennent de `0002_app_tables`. `0012` porte `model_versions`, `factures_rejetees`, `alertes`, `alertes_prescription`, `explications_shap`, `calculs_remboursement` et `journal_audit`. Les fichiers `db/migrations/*.sql` restent historiques et ne sont pas exécutés en parallèle.
5. `0012` donne les droits lecture/écriture aux tables et séquences nouvelles à `app_rw`, retire les droits PUBLIC et révoque explicitement tout accès nouveau à `agent_ro` et `ml_ro`.

## Tables des routes existantes

| Table                       | Créée par Alembic                                  | Décision 0012             |
| --------------------------- | ---------------------------------------------------- | -------------------------- |
| `predictions`             | Oui, `0002_app_tables`                             | Réutilisée, sans doublon |
| `alertes`                 | Non avant 0012                                       | Créée par 0012           |
| `decisions_gestionnaires` | Oui, `0002_app_tables`                             | Réutilisée, sans doublon |
| `journal_audit`           | Non avant 0012 (`audit_log` existait séparément) | Créée par 0012           |
| `factures_rejetees`       | Non avant 0012                                       | Créée par 0012           |

## Validation

- `77 passed` sur les tests ciblés phase 3/4 et sécurité.
- Le test d’activation/rollback vérifie l’acteur, les versions précédente/nouvelle, les deux écritures dans `journal_audit` et `active_par`.
- Les deux artefacts seed sont présents dans `git ls-files` et le `.dockerignore` API ne les exclut pas.
- Ruff : aucun diagnostic sur les fichiers modifiés de la phase 4.
- Tête Alembic statique : `0012_phase4_model_registry`.
- Dockerfile : base Python 3.11 slim et paquet `libgomp1` présents.

## Non réalisé dans cet environnement

Docker Desktop n’était pas disponible : le moteur `dockerDesktopLinuxEngine` n’existait pas au moment de la vérification. Le smoke test LightGBM/SHAP n’a donc pas été exécuté dans le conteneur et `alembic upgrade head` n’a pas été appliqué à un PostgreSQL réel. Les migrations non appliquées sont `0012_phase4_model_registry` et toute migration antérieure non présente dans la base cible, notamment `0011_auth_sessions` si cette base n’est pas déjà à jour.

## Points à valider par l’équipe

- P1 : démarrer Docker, construire l’image API, puis vérifier le smoke test réel et le premier remplissage de `models_data`.
- P2 : appliquer `alembic upgrade head` sur PostgreSQL et contrôler les privilèges des rôles `app_rw`/`ml_ro`.
- P3 : confirmer la compatibilité de la structure historique de `predictions`/`decisions_gestionnaires` avec les repositories déjà existants.

## Procédure de validation Docker à exécuter

Depuis la racine du dépôt :

```powershell
docker version
docker compose config --quiet
docker compose up -d db
docker compose --profile full up --build loader
docker compose --profile full up -d --build api
docker compose --profile full exec api python -c "import os, psycopg; from psycopg.rows import dict_row; from api.services.ml_service import ModelRegistry; conn=psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row); bundle=ModelRegistry().initialize(conn); print(bundle.version, bundle.sha256, len(bundle.feature_names)); conn.close()"
docker compose --profile full exec api python -m api.model_smoke
```

`registry.initialize()` copie les seeds si nécessaire, vérifie le SHA-256, exécute le score dans `[0,1]` et appelle SHAP ; une sortie `version`, `sha256` et `feature_count` confirme le smoke test complet dans le conteneur.

```powershell
docker compose --profile full exec api python -c "import os, psycopg; from psycopg.rows import dict_row; from api.services.ml_service import ModelRegistry; conn=psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row); print(ModelRegistry().current(conn)); conn.close()"
```

Pour un clone propre, sans `backend/ml/models/` local :

```powershell
git clone <url> predicare-clean
cd predicare-clean
Copy-Item env.example .env
docker compose --profile full up --build -d
docker compose --profile full exec api find /models -maxdepth 2 -type f
docker compose --profile full exec api python -c "import os, psycopg; from psycopg.rows import dict_row; from api.services.ml_service import ModelRegistry; conn=psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row); print(ModelRegistry().current(conn)); conn.close()"
```

La première commande `loader` exécute déjà `alembic upgrade head` dans son entrypoint. Pour le lancer explicitement dans l’image ingestion :

```powershell
docker compose --profile full run --rm --entrypoint "" loader alembic upgrade head
```
