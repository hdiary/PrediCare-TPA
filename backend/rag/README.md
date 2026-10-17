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
conteneur indexe le corpus ; le dépôt ne fournit pas encore de route API chat
authentifiée pour envoyer des questions à l'agent depuis l'interface.
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

## Tester un prompt avec Docker

Après l'indexation, il est possible d'envoyer une question à l'agent depuis un
conteneur éphémère. En développement, fournissez la connexion PostgreSQL
administrateur de votre `.env` au test (ne pas utiliser cette configuration en
production). Comme la commande utilise `--no-deps`, démarrez d'abord la base
de données si elle n'est pas déjà active :

```powershell
docker compose up -d db
```

Puis exécutez le test :

```powershell
docker compose run --rm --no-deps `
  -e AGENT_DATABASE_URL="postgresql://postgres:dev_postgres_pwd@db:5432/predicare" `
  rag-indexer python -m rag.ask `
  --contract-id CTR-000048 `
  --question "Quelles sont mes garanties principales ?"
```

Adapte le mot de passe `dev_postgres_pwd` si `POSTGRES_PASSWORD` a été changé.
Le contrat doit exister dans la base ; pour les conditions particulières, il
faut choisir un contrat présent dans le corpus, par exemple `CTR-000048`. Le
conteneur affiche la réponse et les sources récupérées. Chaque appel peut
consommer des crédits auprès du fournisseur LLM et d'embeddings.

## Schéma et code

Les migrations `0004_rag_tables` et `0005_rag_embedding_1024` créent les tables
`rag_documents`, `rag_chunks`, `rag_semantic_cache` et `rag_query_log`, puis
adaptent les vecteurs à BGE-M3. La migration 0005 supprime les anciens vecteurs
et documents RAG, y compris ceux de l'ancienne table `documents_vectorises`,
pour que le corpus soit réindexé avec le nouveau modèle. Les PDF et les autres
données métier restent inchangés. Le code Python, le Dockerfile et le script
d'ingestion automatique du corpus sont tous dans ce dossier.
