# Rapport Phase 5

## Réalisé

- `POST /factures` accepte `InvoiceCreate`; `prestataire_id` est ajouté depuis le JWT.
- Le calcul de remboursement est déterministe et est enregistré dans `calculs_remboursement`.
- Les rejets du parcours POST sont enregistrés dans `factures_rejetees` et `journal_audit`.
- Une facture reste `EN_ATTENTE_GESTIONNAIRE` avec `scoring_indisponible` dans l’audit si le modèle n’est pas disponible.
- Les règles de base `SURFACTURATION`, `UPCODING`, `PRESTATAIRE_RADIE` et `HORS_COUVERTURE` produisent des codes gestionnaire.
- La migration `0013_phase5_pending_invoice` étend le contrôle de statut.

## Validation

`tests/test_predict_flow.py` et `tests/test_phase5_services.py` : **22 tests passés**.
La compilation Python du backend passe. La tête Alembic locale est `0013_phase5_pending_invoice`.

## Limites à traiter avant clôture de Phase 5

Le raccordement complet des 14 règles métier détaillées, l’insertion dédiée des alertes de fraude et la validation d’intégration sur PostgreSQL Docker restent à exécuter avec Docker disponible. Le test local ne remplace pas le smoke test dans le conteneur.
