# API FastAPI (`backend/api`)

Cœur applicatif de PrediCare TPA : authentification et rôles, scoring des factures avec explications SHAP, alertes et décisions des gestionnaires, journal d'audit, déchiffrement ciblé des identités, chargement du modèle depuis MLflow.

Aligné sur le **contrat de données v0.1** (tables et colonnes en français, montants entiers en MGA). Documentation interactive : http://localhost:8000/docs (bouton **Authorize**).

## 1. Structure

```
backend/api/
├── main.py              # App FastAPI, CORS, gestion des erreurs, démarrage
├── config.py            # Variables d'environnement (pydantic-settings)
├── db.py                # Pool PostgreSQL (psycopg 3) et dépendance get_db
├── security.py          # Hachage bcrypt, jetons JWT
├── deps.py              # get_current_user, require_role(...)
├── bootstrap.py         # Comptes de démonstration au démarrage
├── audit.py             # write_audit(...) -> table journal_audit
├── repositories.py      # SQL des tables du contrat (seul fichier à adapter si le schéma change)
├── validation.py        # Les 10 codes de rejet du contrat (section 9.1)
├── schemas.py           # Schémas auth et santé
├── schemas_predict.py   # Réponse de /predict (contrat 11.1)
├── schemas_alerts.py    # Alertes, décisions, identité
├── routers/             # health, auth, predict, alerts, admin
└── services/
    ├── model_registry.py  # Modèle actif depuis MLflow
    ├── features.py        # Pont vers backend/ml/preprocess.py
    ├── scoring.py         # Score + SHAP
    └── identity.py        # Déchiffrement Fernet des identités
```

## 2. Endpoints et rôles

| Méthode et route | Rôles | Rôle de l'endpoint |
|---|---|---|
| `GET /health` | public | État (base, modèle) |
| `POST /auth/login`, `POST /auth/token` | public | Connexion, retourne un JWT |
| `GET /auth/me` | connecté | Profil |
| `POST /auth/register` | public | Demande de compte (assuré ou professionnel de santé), créé **inactif** |
| `POST /auth/forgot-password` | public | Envoie un lien de réinitialisation par e-mail (réponse toujours identique) |
| `POST /auth/reset-password` | public (jeton) | Nouveau mot de passe à partir du lien (usage unique) |
| `POST /auth/change-password` | connecté | Changement du mot de passe (ancien requis) |
| `POST /predict` | professionnel_sante, gestionnaire | Scorer une facture |
| `GET /alerts` | gestionnaire | Liste (`statut=en_attente`, `traitees`, `toutes`) |
| `GET /alerts/{facture_id}` | gestionnaire | Détail avec SHAP et décisions |
| `POST /alerts/{facture_id}/decision` | gestionnaire | Enregistrer une décision |
| `GET /alerts/{facture_id}/identite` | gestionnaire | Identité déchiffrée de l'assuré (tracée) |
| `GET /admin/model`, `POST /admin/model/reload` | administrateur | Version du modèle, rechargement |
| `GET /admin/ping` | administrateur | Test du contrôle d'accès |
| `GET /admin/users` | administrateur | Liste des comptes (`role`, `statut=actifs\|inactifs\|tous`, `q`, `limit`, `offset`) |
| `GET /admin/users/{id}` | administrateur | Détail d'un compte |
| `POST /admin/users` | administrateur | Crée un compte, tout rôle |
| `PATCH /admin/users/{id}` | administrateur | Rôle, rattachement, activation (valide une inscription) |
| `DELETE /admin/users/{id}` | administrateur | Désactive le compte (jamais supprimé) |
| `POST /admin/users/{id}/unlock` | administrateur | Lève le verrouillage après échecs de connexion |
| `POST /admin/users/{id}/reset-password` | administrateur | Envoie un lien de réinitialisation à l'utilisateur |

L'identifiant d'une alerte est le `facture_id` (une prédiction par facture).

## 3. Authentification

1. `POST /auth/login` avec `{"email": "...", "password": "..."}` retourne un JWT.
2. En-tête `Authorization: Bearer <jeton>`.
3. Le rôle et l'état du compte sont relus en base à chaque requête (`utilisateurs`).
4. `assure_id` et `prestataire_id` viennent de la base, jamais du client. L'agent IA doit utiliser `user["assure_id"]`.

Protéger un endpoint : `dependencies=[Depends(require_role("gestionnaire"))]`.

**Sécurité de la connexion (S12)** :

- mots de passe hachés avec bcrypt (sel aléatoire), jamais renvoyés par l'API ;
- jeton à durée limitée (`JWT_EXPIRE_MINUTES`), un jeton sans date d'expiration est refusé ;
- après `LOGIN_MAX_ATTEMPTS` échecs consécutifs (5 par défaut), le compte est verrouillé `LOGIN_LOCKOUT_MINUTES` (15 par défaut) : réponse **429** avec l'en-tête `Retry-After`, même avec le bon mot de passe. Un succès remet le compteur à zéro. Colonnes `tentatives_echouees` et `verrouille_jusqua` de `utilisateurs` ;
- limite connue : le compteur est par compte, pas par adresse IP ; un email inconnu n'est pas suivi.

**Contrôle d'accès (S1)** : le rôle est relu en base à chaque requête, donc un jeton falsifié ou un rôle modifié n'ouvre aucun droit. Un rôle non autorisé reçoit **403**, l'absence de jeton **401**.

### Comptes : inscription, mot de passe, gestion

**Inscription** (`POST /auth/register`, `{"email", "password", "role"}`) : seuls `assure` et `professionnel_sante` sont demandables. Le compte est créé **inactif et non rattaché** (le rattachement n'est jamais pris dans la requête, cf. règle ci-dessus). Tant qu'un administrateur ne l'a pas validé, la connexion avec le bon mot de passe renvoie **403** (« Compte inactif ou en attente de validation »). Réponse 202 identique si l'adresse existe déjà. `REGISTRATION_ENABLED=false` ferme l'inscription.

Valider : `GET /admin/users?statut=inactifs`, puis `PATCH /admin/users/{id}` avec `{"is_active": true, "assure_id": "ASS-..."}` (ou `prestataire_id`). Un compte actif `assure` ou `professionnel_sante` doit être rattaché à un assuré ou à un prestataire existant ; `gestionnaire` et `administrateur` ne le sont à rien. Changer de rôle efface les rattachements non renvoyés. Un administrateur ne peut ni se désactiver ni se rétrograder.

**Mot de passe** : 10 à 128 caractères, au moins une lettre et un chiffre.

**Mot de passe oublié** : `POST /auth/forgot-password` (réponse 202 identique que le compte existe ou non, aucun e-mail pour un compte inactif) génère un jeton aléatoire de 256 bits, **dont seul le hachage SHA-256 est stocké** (table `reinitialisations_mdp`, `api/sql/001_reinitialisations_mdp.sql`, créée à la première utilisation si absente). Le lien `APP_PUBLIC_URL + PASSWORD_RESET_PATH + ?token=...` est valable `PASSWORD_RESET_TTL_MINUTES` (30), à usage unique ; une nouvelle demande invalide les précédentes ; limite de `PASSWORD_RESET_MAX_PER_HOUR` (3) demandes par compte et par heure. `POST /auth/reset-password` (`{"token", "new_password"}`) lève aussi un éventuel verrouillage. Le **frontend** doit fournir la page `/reset-password` qui lit `?token=` et appelle cette route.

**E-mails** : SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`). Sans `SMTP_HOST`, aucun e-mail n'est envoyé ; en développement, `DEV_LOG_RESET_LINK=true` écrit le lien dans les journaux (à ne jamais activer en production).

**Changement de mot de passe** : `POST /auth/change-password` ; les échecs alimentent le même verrouillage que la connexion.

## 4. `POST /predict`

Entrée (contrat 11.1) : `facture_id`, `numero_facture`, `prestataire_id`, `assure_id`, `contrat_id`, `ordonnance_id` (optionnel), `type_facture`, `date_soin`, `heure_soin`, `devise`, `lignes[]` (`code`, `type_ligne` optionnel, `quantite`, `prix_unitaire`). Facultatifs acceptés : `montant_total`, `date_facture`, `date_reception`, `canal_reception`, `mode_reglement`, `attestation_pec_id`, `entente_prealable_id`.

**Champs interdits** (fuite de données) : `statut`, `motif_rejet`, `montant_pris_en_charge`, `reste_a_charge`, `date_traitement` → rejet `CHAMP_INTERDIT`.

### Rejets : HTTP 422 avec la liste des codes

```json
{"detail": "Facture rejetée", "codes": ["DEVISE_INVALIDE", "MONTANT_NEGATIF"],
 "erreurs": [{"code": "DEVISE_INVALIDE", "champ": "devise", "message": "..."}]}
```

| Code | Déclencheur |
|---|---|
| `MONTANT_NEGATIF` | quantité ≤ 0, prix ou montant < 0 |
| `CODE_ACTE_INCONNU` | code absent des référentiels actes et médicaments |
| `DATE_FUTURE` | `date_soin` postérieure à aujourd'hui (UTC+3) |
| `DATE_IMPOSSIBLE` | date ou heure non analysable (format `AAAA-MM-JJ`, `HH:MM`), ou dates incohérentes |
| `CHAMP_OBLIGATOIRE_MANQUANT` | champ obligatoire absent ou vide |
| `TOTAL_INCOHERENT` | `montant_total` ou `montant` de ligne différent du calcul |
| `PRESTATAIRE_INCONNU` | absent de `prestataires` (ou format invalide) |
| `ASSURE_INCONNU` | absent de `assures` (ou format invalide) |
| `DEVISE_INVALIDE` | devise différente de `MGA` |
| `FACTURE_SANS_LIGNE` | aucune ligne |
| `CHAMP_INTERDIT` | champ de fuite envoyé *(ajout API)* |
| `VALEUR_INVALIDE` | format d'identifiant, non-entier, type/catégorie inconnus *(ajout API)* |

Doublon de `facture_id` : HTTP **409** (`FACTURE_DEJA_ENREGISTREE`). Le `numero_facture` n'est **jamais** dédoublonné (signal de fraude). Modèle absent : 503. Colonnes de prétraitement incompatibles : 500. Tous les rejets sont consignés dans `journal_audit`.

### Réponse

- **gestionnaire** : `score`, `seuil`, `is_alert`, `version_modele`, `shap` (`variable`, `valeur`, `contribution`), `latence_ms`.
- **professionnel_sante** : accusé de réception seulement (`accepte`, `facture_id`, `prediction_id`).

Déroulement : validation, modèle, variables, score + SHAP, seuil (table `configuration`), puis **une transaction** qui écrit `factures`, `lignes_facture`, `predictions`, `explications_shap` et `journal_audit`.

## 5. Alertes, décisions, identités

- Une **alerte** est une prédiction dont le score atteint le seuil.
- Décisions : `fraude_confirmee`, `faux_positif`, `a_investiguer`. `montant_economise` (MGA) seulement pour `fraude_confirmee`. **Aucune décision automatique.**
- `GET /alerts/{facture_id}/identite` déchiffre (Fernet, clé `IDENTITY_ENCRYPTION_KEY`) et ne renvoie que nom, prénoms, téléphone, email. Chaque accès est tracé (`acces_identite`), sans les valeurs.

## 6. Journal d'audit (AI Act art. 12)

Table `journal_audit`, en ajout seul (triggers contre UPDATE / DELETE / TRUNCATE).

| `type_evenement` | Quand |
|---|---|
| `prediction` | Chaque prédiction (entrée, score, SHAP, seuil, version du modèle) |
| `decision` | Chaque décision (avec la version du modèle de l'alerte) |
| `facture_rejetee` | Rejet de validation ou doublon |
| `erreur_prediction` | Échec du prétraitement |
| `modele_charge` | Rechargement du modèle |
| `acces_identite` | Déchiffrement d'une identité |
| `compte_demande`, `compte_cree`, `compte_modifie`, `compte_desactive`, `compte_deverrouille` | Inscription et gestion des comptes (ni e-mail ni mot de passe dans le journal) |
| `mdp_reinitialisation_demandee`, `mdp_reinitialise`, `mdp_modifie` | Cycle du mot de passe |

Vérification S8 : `tests/s8_audit_check.sh`.

## 7. Modèle et MLflow

Chargement de la version portant l'alias `champion` du modèle `predicare-fraud`. Contrat avec le rôle Data & ML : modèle de l'API sklearn entraîné sur un DataFrame ; `backend/ml/preprocess.py::build_features(payload, conn)` (même fonction qu'à l'entraînement) ; entraînement sur la vue `v_factures_features` (sans colonnes de fuite).

Mise à jour ou retour arrière : déplacer l'alias dans MLflow, puis `POST /admin/model/reload`.

## 8. Configuration

| Variable | Rôle | Défaut |
|---|---|---|
| `DATABASE_URL` | PostgreSQL | obligatoire |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | Jetons | obligatoire / 60 |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES` | Verrouillage après échecs de connexion | 5 / 15 |
| `CORS_ORIGINS` | Origines autorisées | `http://localhost:3000` |
| `ALERT_THRESHOLD` | Seuil initial (`configuration.seuil_alerte` prime) | 0.8 |
| `IDENTITY_ENCRYPTION_KEY` | Clé Fernet (ou 64 caractères hex) | requise pour `/identite` |
| `MLFLOW_TRACKING_URI`, `MLFLOW_MODEL_NAME`, `MLFLOW_MODEL_ALIAS` | MLflow | voir `config.py` |
| `DEMO_PASSWORD` | Mot de passe des 4 comptes démo (désactivé si vide) | vide |
| `REGISTRATION_ENABLED` | Inscription publique ouverte | true |
| `PASSWORD_RESET_TTL_MINUTES`, `PASSWORD_RESET_MAX_PER_HOUR` | Validité du lien, demandes par compte et par heure | 30 / 3 |
| `APP_PUBLIC_URL`, `PASSWORD_RESET_PATH` | Base du lien envoyé par e-mail (page du frontend) | `http://localhost:3000`, `/reset-password` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | Envoi des e-mails | vide, 587, vide, vide, `no-reply@predicare.local`, true |
| `DEV_LOG_RESET_LINK` | Développement : lien de réinitialisation dans les journaux si pas de SMTP | false |

Comptes démo : `pro@`, `assure@`, `gestionnaire@`, `admin@predicare.local`. Le compte assuré est lié à un assuré principal ayant des factures, le compte pro à un prestataire actif ayant des factures.

## 9. Tests

```bash
pip install -r backend/requirements.txt
pytest tests -q
```

Les tests des comptes (`tests/test_comptes.py`) et ceux du frontend s'exécutent contre un vrai PostgreSQL si `TEST_DATABASE_URL` est défini (sinon ignorés).

Couverture : authentification et rôles, inscription, mot de passe oublié et changé, gestion des comptes, un test par code de rejet, audit (S8), absence de décision automatique, identités, et les tests de sécurité **S1** et **S12** (`tests/test_security_s1_s12.py`).



## 10. Points ouverts

- Notification n8n quand une alerte est créée (fin de `predict.py`) ; import de factures en lot ; `/metrics` et dérive ; seuil modifiable depuis l'écran d'administration.
- Lecture des identités avec le rôle SQL `identity_reader` (le contrat le prévoit) plutôt qu'avec le compte propriétaire.
- Connexion de l'API avec un rôle à droits limités.
- Comptes : un jeton JWT déjà émis reste valide jusqu'à son expiration après un changement de mot de passe (réduire `JWT_EXPIRE_MINUTES` ou ajouter un identifiant de session) ; pas de `logout` ni de `refresh` ; pas de limite par adresse IP sur `/auth/register` ni `/auth/forgot-password` (à poser au reverse proxy).
- Si `journal_audit.type_evenement` porte une contrainte CHECK dans vos migrations, y ajouter les nouveaux types (l'échec est journalisé sans bloquer l'opération sur le compte).
