# Rapport section 8 — Phase 5b

## Réalisé

Les dix règles restantes sont implémentées dans [fraud_rules_v2.py](../backend/api/services/fraud_rules_v2.py), chacune avec un flag `is_*`, un libellé, une fonction dédiée et un test positif/négatif :

`QUANTITE_EXCESSIVE`, `LIGNES_NON_PRESCRITES`, `SUBSTITUTION_PRODUIT`,
`ORDONNANCE_EXPIREE`, `SOINS_JOUR_FERME`, `DOUBLON`, `FRACTIONNEMENT`,
`SURCONSOMMATION`, `ACTE_FICTIF`, `INCOHERENCE_PROFIL`.

Les indicateurs `SPECIALITE_NON_DECLAREE` et `TYPE_ORDONNANCE_INCOHERENT` restent explicatifs et ne déclenchent pas seuls une alerte.

## Données et modèle

Le script [integration_validate_db.py](../tests/integration_validate_db.py) a exécuté `validate_invoice` sur 84 593 factures par lots : **0 rejet pour les 10 codes**.

Le script [integration_fraud_rates.py](../tests/integration_fraud_rates.py) dérive les déclenchements à partir des mêmes colonnes et seuils que [features.py](../backend/ml/features.py). Les flags ne sont pas ajoutés au vecteur : le schéma seed reste inchangé.

Écarts importants entre taux de déclenchement et fréquence `type_fraude` chez `est_fraude=true` :

- `LIGNES_NON_PRESCRITES` : 17,37 % contre 9,98 %.
- `DOUBLON` : 5,58 % contre 12,37 %.
- `FRACTIONNEMENT` : 10,92 % contre 4,63 %.
- `SURCONSOMMATION` : 14,14 % contre 6,38 %.
- `SUBSTITUTION_PRODUIT` : 0 % contre 5,01 % ; écart à revoir car le feature d’entraînement `l_n_non_remboursable` ne suffit pas à reconstruire la notion de substitution.

## Validation

- Suite complète : **281 passés, 1 ignoré, 0 échec, 0 erreur**.
- PostgreSQL Docker : `0013_phase5_pending_invoice (head)`.
- Les tests d’intégration sont disponibles avec :
  `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build api`.

La phase 5b est terminée. L’exécution s’arrête avant 5c.
