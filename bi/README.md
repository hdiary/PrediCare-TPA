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
  seule sur la vue `v_bi_factures`; ne pas utiliser le superutilisateur pour
  les questions BI.
- Les vues exposent, par facture, la dernière prédiction enregistrée et la
  dernière décision associée à cette prédiction. En cas d'égalité
  d'horodatage, l'identifiant de ligne le plus élevé départage les versions.
- Les filtres **Date début** et **Date fin** portent sur `date_facture` et
  s'appliquent à toutes les cartes.

## Cartes et définitions des indicateurs

| Carte | Définition |
|---|---|
| Factures observées | Nombre de factures du jeu chargé dans la période. Ce n'est pas un décompte des inférences réussies du modèle. |
| Montant des factures alertées rejetées (MGA) | Somme de `montant_total` des factures alertées et dont la dernière décision est `rejete`, limitées à la devise MGA. C'est un montant facturé rejeté, **pas une économie réalisée**. |
| Rappel sur les fraudes valides labellisées (%) | Parmi les factures avec `est_fraude = true`, `est_valide = true` et une prédiction, part de celles dont la dernière prédiction est une alerte. Sans labels scorés dans la période, le résultat est vide. |
| Taux de rejet des alertes décidées (%) | Parmi les alertes avec décision finale `valide` ou `rejete`, part des décisions `rejete`. Les décisions `a_investiguer` et les alertes sans décision finale sont exclues. C'est un taux de rejet, pas la précision du modèle. |
| Factures avec prédiction (%) | Part des factures de la période disposant d'une prédiction. Ce taux de couverture permet d'interpréter le rappel et d'identifier un scoring incomplet. |
| Volume de factures par mois | Nombre de factures par mois de `date_facture`, toutes devises confondues. |
| Montants facturés vs alertés par mois (MGA) | Sommes mensuelles en MGA de `montant_total`, pour toutes les factures et pour le sous-ensemble alerté. Les autres devises sont exclues de cette carte. |
| Top 10 prestataires alertés (factures) | Prestataires ayant le plus grand nombre de factures alertées dans la période. |

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
   docker compose up -d db loader metabase metabase-init
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
