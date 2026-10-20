# Liaison frontend ↔ backend (PrediCare TPA)

Le frontend n'appelle que `/api/...`. Vite et nginx conservent `/api/v1/...` pour les routes
versionnées et retirent le préfixe `/api` pour les routes historiques (par exemple
`/api/auth/login` → `http://api:8000/auth/login`). Toute la traduction (rôles, noms de champs,
statuts, erreurs) est dans **`src/lib/api.ts`**.

## Démarrer en développement

```bash
# 1. backend (docker compose up ... ou uvicorn) sur http://localhost:8000
# 2. frontend
cp .env.example .env
npm ci
npm run dev          # http://localhost:5173
```
Pour avoir des comptes de démonstration, définir `DEMO_PASSWORD` côté backend et
`VITE_SHOW_DEMO_ACCOUNTS=true` côté frontend (les comptes sont `gestionnaire@`, `pro@`, `assure@`,
`admin@predicare.local`, avec ce mot de passe).

## Production (docker compose)

```yaml
  frontend:
    build:
      context: ./frontend
      args:
        VITE_MOCKS: "models"   # fonctions non encore branchées
    ports: ["3000:80"]
    depends_on: [api]
```
Le service du backend doit s'appeler `api` et écouter sur le port 8000 (voir `nginx.conf`).

## Écran par écran

| Écran | Appel backend | État |
|---|---|---|
| Connexion, session | `POST /auth/login`, `GET /auth/me` | **réel** |
| Dépôt de facture (prestataire) | `POST /predict` | **réel** (saisie manuelle ou fichier JSON) |
| Mes factures (prestataire), Remboursements (assuré) | `GET /invoices` (périmètre du compte) | **réel** |
| Alertes (liste, détail, décision) | `GET /alerts`, `GET /alerts/{id}`, `POST /alerts/{id}/decision` | **réel** |
| Configuration (seuil, Slack, e-mail) | `GET/PUT /admin/settings` | **réel**, seuil appliqué dès la prédiction suivante |
| Journal d'audit | `GET /admin/audit-log` | **réel** |
| Utilisateurs | `GET /admin/users` | **réel** |
| Supervision : état des services | `GET /health` | **réel** pour API, base, modèle ; n8n et base vectorielle affichés « Non surveillé » |
| Tableau de bord manager (KPI) | `/bi/kpis` | **réel**, snapshot partagé rafraîchi toutes les 5 min |
| Supervision : métriques, dérive | `/admin/metrics` | **réel** pour latence de scoring et métriques HTTP ; PSI `N/A` sans référence d'entraînement |
| Versions du modèle | `/admin/models` | **simulé** |
| Assistant RAG (assuré et prestataire) | `GET /chat/history`, `POST /chat` | **réel** : agent RAG, index vectoriel PostgreSQL/pgvector, réponses sourcées et historique persistant |
| Inscription, mot de passe oublié, réinitialisation | `/auth/register`, `/auth/forgot-password`, `/auth/reset-password` | **simulé** : aucun compte créé, aucun e-mail envoyé (avertissement affiché) |
| Alertes de prescription | `/prescription-alerts` | **simulé** (règles de `ml/prescription_rules.py` non exposées par l'API) |
| Scan d'ordonnance | `/invoices/{id}/prescription-scan` | **simulé** |

Tant que des fonctions sont simulées, un bandeau jaune « Données de démonstration » les liste.
`VITE_MOCKS=all` rend tout le frontend autonome (démo sans backend).

Les KPI BI et les métriques système ne sont pas simulés : ils utilisent l'API,
et le dashboard indique l'horodatage du snapshot. Le coût FinOps RAG est `N/A`
tant qu'une tarification n'est pas configurée; la dérive du modèle est `N/A`
tant qu'une distribution de référence n'est pas disponible.

Le chat est également connecté à l'API réelle : il n'utilise aucun jeu de
conversations de démonstration. Les messages et conversations sont conservés
dans `chat_messages` et `chat_conversations`; les documents et leurs vecteurs
sont lus dans `rag_documents` et `rag_chunks` via `agent_login` (membre
lecture seule de `agent_ro`). Une instance de l'agent est créée au démarrage
de l'API. Si sa configuration RAG est absente, l'API signale l'indisponibilité
au lieu de renvoyer une réponse fictive.

## Choix à valider par l'équipe

1. **Devise** : les montants du backend sont en ariary (MGA, entiers). L'interface affichait des euros ;
   `formatEUR` est devenu `formatMGA`.
2. **Type d'alerte** : le backend n'en produit pas encore. Toute alerte s'affiche « Tarification »
   (`alertTypeOf` dans `api.ts` utilisera `type_alerte` dès que l'API le renverra).
3. **Montant économisé** : une fraude validée enregistre le montant de la facture comme économie.
4. **Fraude validée / rejetée** correspondent à `fraude_confirmee` / `faux_positif`. La décision
   `a_investiguer` existe côté API mais n'a pas de bouton dans l'interface.
5. **Dépôt par fichier** : seul le JSON du contrat de données est accepté (CSV et PDF refusés avec un message).
   Le formulaire manuel demande désormais N° de contrat, N° de facture, type et heure de soins, exigés par l'API.
6. **Filtres « Reçues » et « Acceptées »** des factures : sans équivalent côté backend (statuts
   EN_COURS, PAYEE, REJETEE), ils renvoient une liste vide.
7. Le jeton JWT est conservé dans `localStorage` et expire après 60 min (pas de renouvellement) :
   compromis simple, exposé en cas de faille XSS.
8. **Ordonnance** : seul son numéro est transmis à l'API (`ordonnance_id`, format `ORD-0000000`). La date de
   prescription, le prescripteur et le diagnostic saisis dans le formulaire ne sont pas encore acceptés par `/predict`.
   Attention : l'API contrôle le format du numéro mais pas son existence dans la table `ordonnances` ; si cette
   table a une clé étrangère, un numéro inconnu provoquera une erreur 500 à l'insertion.
9. L'« historique du prestataire » de l'écran d'alerte affiche les dernières décisions prises sur les
   autres alertes du même prestataire.

## Corrections apportées au passage dans le frontend

- Le dépôt de facture affichait un résultat codé en dur (`FAC-2024-1049`, deux erreurs fictives) quoi que
  réponde l'API : il affiche maintenant le résultat réel.
- La page de connexion plantait après une connexion réussie quand on y arrivait depuis une page protégée
  (`from.startsWith` appelé sur un objet) et décidait de la redirection à partir de comptes simulés.
- « Alertes estimées (30 jours) » de la configuration était un chiffre inventé : supprimé.
- La liste des utilisateurs était écrite en dur : elle vient maintenant de l'API.

## Lecture des PDF (`api/pdf_extract.py`)

Le module lit les factures et ordonnances PDF du jeu de données (30 factures et 22 ordonnances d'exemple lues
sans erreur, PDF « texte », sans OCR). Aucune route de l'API ne l'appelle encore : le dépôt par fichier accepte
donc uniquement le JSON. Pour brancher le PDF, il manque côté API : le `contrat_id` (absent du PDF, à retrouver
par l'assuré et la date de soins) et le `prestataire_id` (le PDF donne le NIF).
