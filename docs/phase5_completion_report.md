# Rapport section 8 — clôture phase 5

## A — règles et indicateurs

Les métriques des 14 règles de fraude restent celles mesurées dans [phase5b_report.md](./phase5b_report.md). Les indicateurs `SPECIALITE_NON_DECLAREE` et `TYPE_ORDONNANCE_INCOHERENT` restent explicatifs, hors vecteur et sans alerte autonome. `feature_schema.json` ne contient aucune colonne `is_*`.

## B — anomalies de prescription

| Contrôle | Effectif sur 47 804 ordonnances |
|---|---:|
| ORDONNANCE_FALSIFIEE | 180 |
| PRESCRIPTEUR_INCOMPATIBLE | 0 |
| PRESCRIPTEUR_RADIE | 2 |
| ORDONNANCE_ANTIDATEE | 86 |

`POST /ordonnances` impose `professionnel_sante` et prend `prescripteur_id` dans le JWT. Les alertes sont écrites avec `type_alerte = PRESCRIPTION` dans `alertes_prescription`; aucune ligne `predictions` n'est créée. La réponse prestataire de validité ne contient pas les anomalies ni leurs motifs.

## C — features et modèle

Le service d'inférence réutilise `ml.features.build_features` via `backend/ml/preprocess.py`. Sur 1 000 factures tirées au hasard dans PostgreSQL Docker : **0 divergence**, tolérance numérique `rtol=1e-9`, `atol=1e-9`.

Smoke test dans l'image API : version `lightgbm-20261018-1157-078e86`, score `0.010342354865443071` dans `[0,1]`, SHAP non vide. `python -m api.model_smoke` : `model seed feature schemas: OK`.

## D — stockage et alertes

Le stockage de facture, lignes, calcul, prédiction, SHAP, alerte et audit est dans une transaction unique. Le test PostgreSQL avec exception injectée après facture+lignes confirme le rollback complet. Le seuil provient de `configuration.seuil_alerte` à chaque requête; son changement est donc pris en compte sans redémarrage. Seuls `QUANTITE_EXCESSIVE`, `INCOHERENCE_PROFIL`, `DOUBLON`, `PRESTATAIRE_RADIE` et `ORDONNANCE_EXPIREE` peuvent produire une alerte de priorité moyenne; les autres codes restent explicatifs.

## Validation finale

- Migration : `0014_phase5_prescription_alerts (head)`.
- API : **392 passed, 1 skipped, 0 échec**.
- Loader : **55 passed, 17 skipped, 0 échec**.
- Total : **447 passed, 18 skipped**.
- Images `api` et `loader` reconstruites avant les tests.
- Aucun secret `.env`, cache ou fichier volumineux ajouté à l'index; `dev_postgres_pwd` n'est pas présent dans `git ls-files`.

## Écarts et limites

Le jeu ne contient aucun cas de spécialité d'acte incompatible avec le prescripteur, donc l'effectif mesuré est zéro. Les métriques de précision/rappel des anomalies de prescription ne sont pas calculables sans labels d'ordonnances. La validation de restauration du volume `models_data` reste couverte par la procédure de sauvegarde existante, sans restauration destructive exécutée pendant cette clôture.
