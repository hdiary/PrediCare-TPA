# Rapport de phase 3 — schémas et accès aux données

## Fichiers créés ou modifiés

- `backend/api/schemas_domain.py` : contrats Pydantic des factures, référentiels,
  contrats, assurés, ordonnances, versions de modèle et utilisateurs.
- `backend/api/repositories_domain.py` : lectures SQL paramétrées des tables métier
  existantes, avec filtrage par assuré ou prestataire.
- `backend/api/schemas_alerts.py` : ajout du contrat détaillé d’alerte gestionnaire.
- `backend/api/routers/alerts.py` : branchement de `AlertDetailOut` sur la route de
  détail gestionnaire.
- `tests/test_schemas_domain.py` : neuf tests de contrats valides, invalides,
  sécurité prestataire et schémas d’alerte.
- `.gitignore` : exclusion du venv local Python 3.11 créé pour reproduire l’image API.

## Décisions et écarts documentaires

1. `InvoiceCreate` contient `assure_id`. `prestataire_id` reste absent du corps et
   doit être injecté depuis le JWT.
2. `FacturePrestataireOut` exclut score, SHAP, codes de fraude et état d’alerte.
   Le statut `EN_ATTENTE_GESTIONNAIRE` est disponible pour l’affichage « en cours
   d’examen ».
3. Les migrations Alembic `p1_0001` à `p1_0004`, `0010` et `0011` sont la source de
   vérité. Les fichiers `database/sql/*.sql` sont des scripts historiques ou de
   transition : ils ne sont pas exécutés par le service `loader` et ne seront pas
   maintenus en parallèle. Leurs définitions seront reportées, après comparaison,
   dans Alembic `0012`.
4. Les tables absentes mentionnées par les documents ont été portées dans
   `0012_phase4_model_registry` sans recréer les tables déjà déclarées par Alembic.

## Tables nécessaires aux phases 4 à 7

| Table ou vue | Phase | Présence Alembic | À créer ou aligner en 0012 |
|---|---:|---|---|
| `referentiel_actes`, `referentiel_medicaments`, `garanties` | 5, 7 | Oui, `p1_0002` | Non |
| `prestataires`, `grille_tarifaire`, `contrats`, `assures` | 5, 7 | Oui, `p1_0002` | Non |
| `ordonnances`, `ordonnance_lignes` | 5, 6 | Oui, `p1_0002` | Non |
| `factures`, `lignes_facture` | 5, 7 | Oui, `p1_0002` | Non |
| `labels_fraude`, `labels_prestataires` | 5, 7 | Oui, `p1_0002` | Non |
| `ref_codes`, `v_factures_features` | 5 | Oui, `p1_0004` | Non |
| `configuration` | 5, 6, 7 | Oui, `0010` | Non |
| `model_versions` | 4, 5, 7 | Oui, `0012` | Créée |
| `predictions` | 5, 6, 7 | Oui, mais ancienne structure `0002` incompatible avec l’API | Aligner |
| `explications_shap` | 5, 6 | Oui, `0012` (`0002` avait `shap_explanations`) | Créée |
| `calculs_remboursement` | 5, 7 | Oui, `0012` | Créée |
| `factures_rejetees` | 5, 7 | Oui, `0012` | Créée |
| `alertes` | 6, 7 | Oui, `0012` | Créée |
| `alertes_prescription` | 5, 6 | Oui, `0012` (anciennement seulement `database/sql/040`) | Créée |
| `decisions_gestionnaires` | 6, 7 | Oui, mais ancienne structure `0002` incompatible | Aligner |
| `journal_audit` | 4, 5, 6, 7 | Oui, `0012` (`0002` avait `audit_log`) | Créée |

Les volumes de fichiers de modèle (`/models`) et les appels n8n ne sont pas des
tables PostgreSQL. Aucun registre concurrent à `model_versions` ne doit être lu à
l’exécution ; `registry.json` restera une source d’import de seed.

## Validation et limites

- Image API vérifiée : `python:3.11-slim`.
- Environnement local créé : Python `3.11.17`, `.venv-api311`.
- `backend/requirements.txt` installé dans cet environnement.
- Tests ciblés : `9 passed`.
- Diagnostics Pylance : aucun diagnostic sur les schémas et dépôts ajoutés.
- Aucun test PostgreSQL réel, migration Alembic appliquée ou démarrage Docker n’a
  été exécuté pendant cette phase.

## Points à valider avec l’équipe

- P1 : structure finale de `0012` et compatibilité avec les tables déjà produites
  par `0002_app_tables`.
- P2 : conservation des colonnes de labels et définition exacte des calculs de
  remboursement.
- P3 : choix définitif entre une table `alertes` dédiée et `predictions.est_alerte`,
  ainsi que le statut public prestataire.

La phase 3 est terminée et la phase 4 est amorcée par `0012`, le registre et les
routes administrateur `/api/v1/model/*`.
