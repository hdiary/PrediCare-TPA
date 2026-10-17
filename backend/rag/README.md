# RAG PrediCare

## Démarrer l'indexation avec Docker

Aucun paquet Python n'a besoin d'être installé sur le poste. Depuis la racine
du dépôt, crée `.env` à partir du modèle si nécessaire, ajoute ta clé API, puis
démarre la plateforme :

```powershell
if (!(Test-Path .env)) { Copy-Item env.example .env }
# Modifier .env et renseigner LLM_API_KEY
docker compose up
```

Le modèle d'embeddings configuré est `bge-m3`, avec des vecteurs de 1024
dimensions. L'endpoint d'exemple est l'API d'embeddings compatible OpenAI à
`http://host.docker.internal:11434/v1/embeddings`. Ajuste ensemble le nom du
modèle, sa dimension et son endpoint si tu utilises un autre serveur.
Le délai d'attente des réponses LLM est de 300 secondes par défaut
(`LLM_TIMEOUT_SECONDS`) afin de laisser le temps aux modèles locaux de générer
une réponse, notamment lors de leur premier chargement.

Le service `rag-indexer` installe ses dépendances dans son image, attend que
PostgreSQL et le chargement des données soient prêts, puis indexe les PDF de
`backend/rag/corpus_rag/` :

- `CP_CTR-xxxxxx.pdf` est rattaché au contrat correspondant ;
- `Conditions_Generales_ESSENTIEL.pdf`, `...CONFORT.pdf` et `...PREMIUM.pdf`
  sont rattachés à leur formule ;
- le barème et les guides du réseau sont communs.

La recherche limite les résultats aux documents du contrat connecté, de sa
formule et aux documents communs. Les empreintes SHA-256 rendent les
redémarrages idempotents. À la première exécution, Docker doit télécharger les
dépendances et le service doit joindre l'API d'embeddings. Sans clé API valide,
l'indexation échoue explicitement.

Pour vérifier l'indexation :

```powershell
docker compose logs rag-indexer
```

Le message final `Corpus ready: ...` confirme la fin de l'indexation. Ce
conteneur indexe le corpus ; la route API chat authentifiée n'est pas encore
intégrée à l'application.
Lors d'une recherche, le RAG garde aussi un extrait des conditions particulières
du contrat demandé. Les questions chiffrées par catégorie (taux, plafond,
franchise ou carence) sont répondues directement depuis la ligne correspondante
de l'article 5, avec sa source, plutôt que laissées à l'interprétation du LLM.
Les questions générales sur les garanties incluent également cet article dans
le contexte. Les réponses sur les bénéficiaires sont limitées à leurs catégories
(assuré principal, conjoint, enfant) ; les identifiants `ASS-...` sont bloqués
par le filtre de sortie et ne doivent pas être affichés.
Les questions sur la prime annuelle, le souscripteur, le statut et la date de
fin du contrat sont extraites directement des conditions particulières. Les
montants de prime indiquent le tarif par bénéficiaire et le total du contrat ;
pour un contrat individuel, le souscripteur est désigné comme « adhésion
individuelle », sans révéler d'identité personnelle.
Les questions sur les exclusions sont sourcées depuis l'article 10. Les
identifiants de contrat mentionnés dans une question doivent correspondre au
contrat fourni à l'agent ; une demande visant un autre contrat est bloquée.
Les demandes d'identité réelle d'un bénéficiaire sont également bloquées.
Le cache ne réutilise une réponse que pour la même question textuelle (sans
tenir compte de la casse et des espaces en bordure), afin d'éviter de répondre
à une question avec le résultat d'une question seulement similaire.

Pour les questions qui nécessitent le LLM, l'agent dispose d'outils à fonctions
fermées : `search_contract_documents` pour les PDF et `search_my_claims` pour
les factures du contexte assuré fourni. Le modèle ne produit jamais de SQL.
L'outil de suivi appelle une requête paramétrée sur la vue
`v_agent_claim_status`, qui n'expose que l'identifiant pseudonymisé, le contrat,
les dates utiles, le type de facture, les montants facturé et pris en charge,
et le statut. Les statuts internes sont convertis en libellés destinés à
l'assuré dans le toolkit. Le rôle PostgreSQL `agent_ro` n'a qu'un droit
`SELECT` sur cette vue pour cet accès métier. Les statuts obtenus par SQL ne
sont pas mis en cache.

En mode CLI, l'identifiant `--assure-id` active l'outil de suivi ; sans cet
argument, une question de suivi reçoit une explication et aucun accès SQL n'est
effectué. Cette valeur pseudonymisée saisie en CLI sert uniquement aux essais
locaux : elle ne constitue pas une authentification et ne doit pas être exposée
à des utilisateurs. L'API devra ultérieurement fournir l'identifiant depuis la
session authentifiée.
Les demandes explicites de statut ou de liste des dernières factures sont
formatées directement depuis les résultats SQL ; le LLM ne choisit pas de
filtres de date et ne peut pas contredire les statuts retournés par la base.
Ce raccourci ne s'applique pas aux demandes contenant une date ou un numéro de
facture, afin que le filtre soit traité par l'outil.
Pour un total historique des remboursements, l'agent appelle l'outil dédié
`get_my_reimbursement_total`, qui agrège toutes les factures `PAYEE` du compte
et du contrat. Ce calcul n'est pas limité aux 10 factures renvoyées par l'outil
de consultation récente ; les dossiers en cours ou rejetés sont exclus.

## Tester un prompt avec Docker

Après l'indexation, il est possible d'envoyer une question à l'agent depuis un
conteneur éphémère. Compose configure `AGENT_DATABASE_URL` avec le compte
`agent_login`, membre du rôle PostgreSQL à privilèges limités `agent_ro` ; ne
remplacez pas cette URL par le compte administrateur. `agent_ro` peut lire les
vues autorisées et écrire uniquement dans les tables de cache et de journal du
RAG. Le service `loader` provisionne ce compte à partir de
`DB_AGENT_RO_PASSWORD`. Comme la commande utilise `--no-deps`, démarrez d'abord
la base de données si elle n'est pas déjà active :

```powershell
docker compose up -d db
```

Puis exécutez le test :

```powershell
docker compose run --rm --no-deps `
  rag-indexer python -m rag.ask `
  --contract-id CTR-000048 `
  --assure-id ASS-C60624BAFB `
  --question "Quelles sont mes garanties principales ?"
```

Configure `DB_AGENT_RO_PASSWORD` si le mot de passe du compte `agent_login` a
été modifié. Le contrat doit exister dans la base ; pour les conditions
particulières, il faut choisir un contrat présent dans le corpus, par exemple
`CTR-000048`. Le conteneur affiche la réponse et les sources récupérées. Pour
tester le suivi, utilisez la question « Où en est mon dossier ? » avec
l'identifiant pseudonymisé d'un assuré de ce contrat. La migration
`0007_agent_claim_amounts` doit avoir été appliquée pour que la vue fournisse
aussi les montants. Chaque appel peut consommer des crédits auprès du
fournisseur LLM et d'embeddings.

## Schéma et code

Les migrations `0004_rag_tables`, `0005_rag_embedding_1024`,
`0006_agent_claim_status_view` et `0007_agent_claim_amounts` créent les tables
RAG et la vue de suivi, puis
adaptent les vecteurs à BGE-M3. La migration 0005 supprime les anciens vecteurs
et documents RAG, y compris ceux de l'ancienne table `documents_vectorises`,
pour que le corpus soit réindexé avec le nouveau modèle. La vue SQL n'expose
que les champs nécessaires au suivi des factures et est accessible en lecture
au rôle `agent_ro`. Les PDF et les autres données métier restent inchangés. Le
code Python, le Dockerfile et le script d'ingestion automatique du corpus sont
tous dans ce dossier.
