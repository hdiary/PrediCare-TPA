# Workflow n8n d'alertes PrediCare

Le workflow `workflows/alerte_fraude.json` reçoit une alerte de l'API, vérifie
l'en-tête `X-Webhook-Secret`, prépare un rapport à partir du score, des montants,
des codes de fraude et du top 5 SHAP, puis envoie le message sur Slack et/ou
par email selon les canaux de la table `configuration`. Les données d'identité
réelle ne sont jamais ajoutées au message.

## Variables d'environnement

Copier `.env.example` vers `.env`, puis définir des valeurs aléatoires distinctes :

```sh
openssl rand -hex 32
```

- `N8N_ENCRYPTION_KEY` : clé persistante utilisée par n8n pour chiffrer ses credentials.
- `N8N_DB_PASSWORD` : mot de passe du compte PostgreSQL à privilèges minimaux `n8n_alert`.
- `N8N_WEBHOOK_SECRET` : secret partagé par l'API et n8n pour le webhook.
- `N8N_WEBHOOK_URL` : URL appelée par l'API, par défaut
  `http://n8n:5678/webhook/predicare-alert` sur le réseau Docker.

Ne jamais committer `.env`. Le webhook n'est accepté que si le secret reçu dans
`X-Webhook-Secret` correspond à `N8N_WEBHOOK_SECRET`.

## Démarrage et import

Compose crée un rôle PostgreSQL dédié `n8n_alert` (lecture de `configuration`,
insertion dans `journal_audit`) et importe le credential n8n correspondant à la
première initialisation du workflow. Son mot de passe est défini par
`N8N_DB_PASSWORD` dans `.env`. Le service attend que les migrations de la base
soient terminées avant de créer le rôle.

Le service officiel `n8nio/n8n` conserve sa base interne dans le volume `n8n_data`.
Après la création du compte propriétaire n8n, le démarrage importe le credential
PostgreSQL chiffré dans la base n8n, importe le workflow puis le publie. Pour
démarrer :

```sh
docker compose up -d n8n
```

Le workflow est importé et publié automatiquement au premier démarrage. Pour
mettre à jour sa définition, importer `workflows/alerte_fraude.json` dans
`http://localhost:5678`, puis le publier. Le volume conserve l'instance.

Si le volume n8n ne contient pas encore de compte propriétaire, ouvrez n8n,
terminez sa configuration initiale, puis redémarrez le service (`docker compose
restart n8n`) afin que le credential puisse être attribué à ce compte.

Le secret est vérifié avant la lecture de la configuration PostgreSQL. Une requête
dont l'en-tête `X-Webhook-Secret` est absent ou incorrect est rejetée par le workflow.

## Identifiants des canaux

Le credential PostgreSQL est importé automatiquement après la création du compte
propriétaire. Associer ensuite les credentials n8n aux nœuds de notification :

- **Slack account** sur `Envoyer Slack`;
- **Gmail OAuth2** sur `Envoyer Email (Gmail)`;

Configurer `notif_slack`, `notif_email`, `notif_email_destinataire` et
`notif_slack_canal` dans l'administration PrediCare. L'API conserve l'alerte en
base et inscrit chaque tentative même si n8n ne répond pas.
