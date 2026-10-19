# Workflow n8n d'alertes PrediCare

Le workflow `workflows/alerte_fraude.json` reçoit une alerte de l'API, vérifie
l'en-tête `X-Webhook-Secret`, prépare un rapport à partir du score, des montants,
des codes de fraude et du top 5 SHAP, puis envoie le message sur Slack et/ou
par email selon les canaux de la table `configuration`. Les données d'identité
réelle ne sont jamais ajoutées au message.

## Variables d'environnement

Copier `env.example` vers `.env`, puis définir des valeurs aléatoires distinctes :

```sh
openssl rand -hex 32
```

- `N8N_ENCRYPTION_KEY` : clé persistante utilisée par n8n pour chiffrer ses credentials.
- `N8N_WEBHOOK_SECRET` : secret partagé par l'API et n8n pour signer le webhook.
- `N8N_WEBHOOK_URL` : URL appelée par l'API, par défaut
  `http://n8n:5678/webhook/predicare-alert` sur le réseau Docker.

Ne jamais committer `.env`. Le webhook n'est accepté que si le secret reçu dans
`X-Webhook-Secret` correspond à `N8N_WEBHOOK_SECRET`.

## Démarrage et import

Le service officiel `n8nio/n8n` conserve sa base interne dans le volume `n8n_data`.
Au premier démarrage, il importe une fois les fichiers JSON de `/workflows`, puis
lance n8n. Le workflow est actif après import. Sur la configuration Compose avec
profil, démarrer avec :

```sh
docker compose --profile full up -d n8n
```

Pour importer manuellement une version mise à jour, ouvrir n8n à
`http://localhost:5678`, choisir **Import from File**, sélectionner
`workflows/alerte_fraude.json`, enregistrer, puis activer le workflow. Le volume
conserve l'instance; l'import initial automatique ne se répète pas à chaque redémarrage.

## Identifiants des canaux

Après import, associer les credentials n8n aux nœuds concernés :

- **Slack account** sur `Envoyer Slack`;
- **Gmail OAuth2** sur `Envoyer Email (Gmail)`;
- **Postgres** sur `Lire la configuration` et `Journaliser (audit S8)`, avec accès
  uniquement aux clés de notification de `configuration` et à l'insertion dans
  `journal_audit`.

Configurer `notif_slack`, `notif_email`, `notif_email_destinataire` et
`notif_slack_canal` dans l'administration PrediCare. L'API conserve l'alerte en
base et inscrit chaque tentative même si n8n ne répond pas.
