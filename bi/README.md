# PrediCare BI — Metabase

Le dashboard **PrediCare : Pilotage** est généré dans Metabase depuis
[`dashboard.json`](./dashboard.json). Ce JSON versionné est l'export déclaratif
portable du dashboard : les cartes, leurs requêtes SQL, les filtres de date et
la disposition peuvent être relus, révisés et recréés par
`db/metabase/setup.sh`. Il est monté par Docker Compose et importé au premier
démarrage de Metabase. Augmenter le champ `version` dans le JSON quand une
définition change permet au script d'archiver le dashboard précédent et de le
recréer. Les exécutions répétées d'une même version sont idempotentes.

## Accès et données

- URL locale : <http://localhost:3000>
- La connexion Metabase à PostgreSQL utilise le rôle `metabase_ro`, en lecture
  seule sur la vue matérialisée `mv_bi_factures`; ne pas utiliser le
  superutilisateur pour les questions BI.
- `mv_bi_factures` est rafraîchie exclusivement par `bi-refresh` toutes les
  cinq minutes avec `REFRESH MATERIALIZED VIEW CONCURRENTLY`. Aucun trigger
  BI n'est installé sur les tables métier.
- Le dashboard manager consomme aussi `GET /api/v1/bi/kpis?jours=30`.
  Le champ `stale=true` signale que l'API sert la dernière valeur connue
  lorsqu'une source BI est temporairement indisponible.
- Les vues exposent, par facture, la dernière prédiction enregistrée et la
  dernière décision associée à cette prédiction. En cas d'égalité
  d'horodatage, l'identifiant de ligne le plus élevé départage les versions.
- Les filtres **Date début** et **Date fin** portent sur `date_facture` et
  s'appliquent à toutes les cartes.

## Cartes et définitions des indicateurs

| Carte | Définition |
|---|---|
| Factures traitées | Nombre de factures de la période. |
| Montant total réclamé | Somme de `montant_total`. |
| Montant à risque | Somme du réclamé des factures en alerte, avant décision. |
| Montant économisé | Somme de `montant_reclame - montant_calcule` pour les décisions `REJETER` et `CONFIRMER_FRAUDE`. |
| Taux d'alerte | Factures en alerte / factures traitées. |
| Précision opérationnelle | Fraudes confirmées / alertes décidées. |
| Volume journalier | Factures et alertes groupées par `date_facture`. |
| Distribution des scores | Histogramme en dix tranches sur `[0, 1]`. |
| Top prestataires à risque | Prestataires ayant le plus d'alertes. |

Le jeu fourni est en MGA. Si d'autres devises sont introduites, adapter les
cartes monétaires pour ne jamais additionner des devises différentes. Pour
calculer une **économie effectivement évitée**, il faut une règle métier
validée et une référence de remboursement contrefactuel; le montant total
facturé à lui seul ne prouve pas cette économie.

Le rappel est calculé uniquement sur les fraudes valides labellisées pour
lesquelles une prédiction existe; les factures sans score sont exclues du
dénominateur. Sans décision finale, les cartes monétaires des rejets et le
taux de rejet restent vides plutôt que de laisser croire à un montant nul.

## Création ou mise à jour

1. Copier `env.example` vers `.env`, compléter les secrets puis démarrer la
   base, le loader et Metabase :

   ```sh
   docker compose up -d db loader bi-refresh metabase metabase-init
   ```

   `metabase-db-init` crée la base applicative `metabase_app` si elle n'existe
   pas. Cette étape fonctionne aussi avec un volume PostgreSQL déjà initialisé;
   ne supprimez pas le volume pour corriger une erreur de base manquante.

2. `metabase-init` configure la connexion en lecture seule et installe les
   cartes définies dans le JSON. Pour appliquer une nouvelle version, incrémenter
   `version` dans `dashboard.json`, puis relancer le conteneur d'initialisation :

   ```sh
   docker compose up -d --force-recreate metabase-init
   ```

Le script conserve l'ancienne version en l'archivant. Le dashboard peut
ensuite être consulté ou exporté avec les outils Metabase; le JSON du dépôt
reste la source portable et reproductible de ses questions et de sa disposition.

## Vérification des KPI

Les définitions sont vérifiées par un test SQL déterministe, indépendant des
prédictions aléatoires de démonstration. Il utilise une vue temporaire contenant
des exemples de fraude, décisions et devises, puis annule toute modification :

```sh
docker compose exec -T db psql -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-predicare}" < tests/bi_kpi_checks.sql
```

Le script termine sans exception si le rappel (50 %), la couverture (83,333 %),
le taux de rejet (75 %) et les sommes en MGA correspondent aux cas de test.
