backend/
│
├── main.py
│   # Point d'entrée de l'application FastAPI.
│   # Crée l'instance `app = FastAPI()`, configure les middlewares (CORS,
│   # authentification, logging, gestion d'erreurs), monte les routers
│   # (/auth, /factures, /alertes, ...), et lance uvicorn en dev.
│   # C'est le fichier exécuté par `uvicorn backend.main:app`.
│
├── core/
│   │
│   ├── config.py
│   │   # Configuration centralisée via Pydantic Settings.
│   │   # Charge les variables d'environnement (.env) : DATABASE_URL,
│   │   # JWT_SECRET, IDENTITY_KEY, SEUIL_ALERTE, MODEL_VERSION, etc.
│   │   # Expose un objet `settings` importable partout.
│   │   # Permet de changer un seuil sans toucher au code (CDC §2 "Configurable").
│   │
│   ├── security.py
│   │   # Tout ce qui touche à la sécurité applicative :
│   │   # - Hash des mots de passe (bcrypt/argon2)
│   │   # - Génération et vérification des JWT (access + refresh tokens)
│   │   # - Définition des rôles (professionnel_sante, assure, gestionnaire,
│   │   #   administrateur) et des permissions associées
│   │   # - Helpers : `create_access_token()`, `decode_token()`, `has_role()`
│   │
│   └── database.py
│       # Connexion à PostgreSQL (avec pgvector).
│       # - Crée l'engine SQLAlchemy
│       # - Fournit `SessionLocal` (factory de sessions)
│       # - Définit `Base` (classe de base des modèles ORM)
│       # - Gère le pool de connexions, les retries, et la session par requête
│       # - Point unique de configuration DB (pas de connexion ailleurs)
│
├── api/
│   │
│   ├── deps.py
│   │   # Dépendances FastAPI réutilisables (`Depends(...)`) :
│   │   # - `get_db()` : fournit une session SQLAlchemy par requête
│   │   # - `get_current_user()` : décode le JWT, retourne l'utilisateur connecté
│   │   # - `require_role(...)` : factory qui vérifie qu'un utilisateur a un rôle
│   │   #   donné, sinon 403
│   │   # - `get_contract_id()` : extrait le contrat actif de l'utilisateur
│   │   # Évite la duplication de code d'auth dans chaque route.
│   │
│   └── v1/
│       # Version 1 de l'API. Tous les routers sont montés sous /api/v1.
│       # Chaque fichier = un domaine fonctionnel, avec ses routes et
│       # ses schémas Pydantic d'entrée/sortie.
│       │
│       ├── auth.py
│       │   # Routes d'authentification :
│       │   # POST /auth/login        → JWT
│       │   # POST /auth/logout       → invalide le token
│       │   # POST /auth/refresh      → renouvelle le token
│       │   # GET  /auth/me           → profil + rôle
│       │   # POST /auth/change-password
│       │   # POST /auth/forgot-password / reset-password
│       │   # Gère la session utilisateur, les cookies, la rotation des tokens.
│       │
│       ├── factures.py
│       │   # Cœur du Flux 1 (pipeline de traitement des factures).
│       │   # POST /factures                   → pipeline complet (validation,
│       │   #                                  invalidation, calcul, ML, SHAP,
│       │   #                                  stockage, alerte n8n)
│       │   # POST /factures/batch             → ingestion en lot
│       │   # GET  /factures                   → liste paginée + filtres
│       │   # GET  /factures/{id}              → détail
│       │   # GET  /factures/{id}/explication  → rapport SHAP
│       │   # GET  /factures/{id}/lignes       → lignes détaillées
│       │   # PATCH /factures/{id}/statut      → décision gestionnaire
│       │   # GET  /factures/rejetees          → factures invalides (audit)
│       │   # Ce router orchestre les services `facture_service`,
│       │   # `calcul_service`, `validation_service`, `regles_service`,
│       │   # `features_service`, `ml_service` pour produire la décision.
│       │
│       ├── predict.py
│       │   # API d'inférence ML pure (contrat §11.1 avec P2/P3).
│       │   # POST /predict        → score + is_alert + version_modele + SHAP
│       │   # POST /predict/batch  → inférence en lot
│       │   # Séparé de `/factures` pour :
│       │   # - Permettre à P3 d'appeler le modèle sans repasser par le pipeline
│       │   # - Tester le modèle isolément
│       │   # - Exposer les endpoints model versioning (/model/*)
│       │   # Ne fait AUCUN calcul métier — uniquement l'inférence ML.
│       │
│       ├── alertes.py
│       │   # Gestion des alertes de fraude (score > seuil).
│       │   # GET  /alertes                     → liste triée par priorité
│       │   # GET  /alertes/{id}                → détail + SHAP + codes fraude
│       │   # PATCH /alertes/{id}/traiter       → marquer traitée
│       │   # POST /alertes/{id}/escalader      → escalader
│       │   # POST /notifications/test          → test envoi Slack/Email
│       │   # GET  /notifications/config        → config canaux
│       │   # Ce router fait le lien entre le pipeline ML (Flux 1), n8n,
│       │   # et l'interface gestionnaire. Il lit la table `alertes` (ou
│       │   # `predictions` avec `is_alert = true`).
│       │
│       ├── contrats.py
│       │   # Données de référence contractuelles.
│       │   # GET /contrats                     → liste (filtres)
│       │   # GET /contrats/{id}                → détail (formule, dates, statut)
│       │   # GET /contrats/{id}/garanties      → tableau Article 5 (taux,
│       │   #                                    plafonds, carences, franchises)
│       │   # GET /contrats/{id}/beneficiaires  → bénéficiaires pseudonymisés
│       │   # GET /garanties/{formule}          → garanties par formule
│       │   # Sert de source de vérité pour le calcul de remboursement et
│       │   # pour le RAG (Flux 2).
│       │
│       ├── referentiels.py
│       │   # Référentiels métier (barème, actes, médicaments).
│       │   # GET /referentiels/actes           → 58 actes
│       │   # GET /referentiels/actes/{code}    → détail d'un acte
│       │   # GET /referentiels/medicaments     → 28 médicaments
│       │   # GET /bareme                       → barème complet
│       │   # Fournit les tarifs min/référence/max utilisés par le calcul
│       │   # et par la détection de SURFACTURATION.
│       │
│       ├── prestataires.py
│       │   # Guide réseau des prestataires.
│       │   # GET /prestataires                 → liste (filtres type/ville/spé)
│       │   # GET /prestataires/{id}            → détail (horaires, adresse)
│       │   # GET /prestataires/{id}/grille-tarifaire → tarifs pratiqués
│       │   # GET /prestataires/recherche       → recherche pour le frontend/RAG
│       │   # GET /prestataires/{id}/labels     → labels de suspicion
│       │   # Alimente la détection SOINS_JOUR_FERME, TARIFS_ABUSIFS,
│       │   # PRESTATAIRE_RADIE, et le RAG (guide réseau).
│       │
│       ├── assures.py
│       │   # Données des assurés (pseudonymisées + identités chiffrées).
│       │   # GET /assures                      → liste (pseudonymisée)
│       │   # GET /assures/{id}                 → détail (sans PII)
│       │   # GET /assures/{id}/factures        → historique
│       │   # GET /assures/{id}/consommation    → plafonds restants
│       │   # GET /assures/{id}/ordonnances     → historique ordonnances
│       │   # GET /assures/{id}/identite        → DÉCHIFFREMENT (gestionnaire
│       │   #                                    habilité uniquement, accès
│       │   #                                    tracé dans journal_audit)
│       │   # Respecte la séparation PII (CDC §6.4) : seul le rôle
│       │   # identity_reader peut lire `identites_chiffrees`.
│       │
│       ├── ordonnances.py
│       │   # Gestion des ordonnances.
│       │   # GET  /ordonnances                 → liste
│       │   # GET  /ordonnances/{id}            → détail + lignes
│       │   # POST /ordonnances                 → création (professionnel_sante)
│       │   # GET  /ordonnances/{id}/validite   → vérifie validité (10j/30j)
│       │   # Alimente la détection ORDONNANCE_EXPIREE, LIGNES_NON_PRESCRITES,
│       │   # ACTE_FICTIF, SURCONSOMMATION.
│       │
│       ├── assistant.py
│       │   # Flux 2 — Assistant conversationnel RAG.
│       │   # POST /assistant/ask               → question → réponse sourcée
│       │   # GET  /assistant/historique        → conversations passées
│       │   # POST /assistant/feedback          → 👍/👎 pour amélioration
│       │   # GET  /assistant/sources/{msg_id}  → sources détaillées
│       │   # Garde-fous input (injection, identité, autre contrat) +
│       │   # filtrage par contract_id + accès SQL restreint à l'assuré connecté.
│       │   # S'appuie sur `rag_service` pour la génération.
│       │
│       ├── bi.py
│       │   # Flux 3 — Tableau de bord décisionnel.
│       │   # GET /bi/kpis                      → KPIs principaux
│       │   # GET /bi/kpis/evolution            → évolution temporelle
│       │   # GET /bi/kpis/par-formule          → par formule
│       │   # GET /bi/kpis/par-categorie        → par catégorie d'acte
│       │   # GET /bi/top-prestataires          → top prestataires à risque
│       │   # GET /bi/top-assures               → top assurés à risque
│       │   # GET /bi/distribution-scores       → distribution des scores
│       │   # GET /bi/alertes-stats             → stats alertes
│       │   # GET /bi/latence                   → latence du pipeline
│       │   # S'appuie sur `bi_service` pour les agrégations SQL.
│       │   # Alimente le dashboard Superset/Metabase/Grafana.
│       │
│       ├── admin.py
│       │   # Administration & supervision (CDC §2).
│       │   # GET  /admin/config                → config actuelle
│       │   # PATCH /admin/config               → modification à chaud
│       │   # GET  /admin/utilisateurs          → liste
│       │   # POST /admin/utilisateurs          → création
│       │   # PATCH /admin/utilisateurs/{id}    → modification
│       │   # DELETE /admin/utilisateurs/{id}   → désactivation
│       │   # GET  /admin/journal-audit         → audit
│       │   # GET  /admin/health                → /health (supervisable)
│       │   # GET  /admin/metrics               → métriques Prometheus
│       │   # POST /admin/backup                → sauvegarde
│       │   # POST /admin/restore               → restauration
│       │   # GET  /admin/logs                  → logs applicatifs
│       │   # Couvre les exigences CDC §2 :
│       │   # Configurable, Supervisable, Persistante.
│       │
│       └── model.py
│           # Gestion du cycle de vie du modèle ML (CDC §2 "Maintenance").
│           # GET  /model/versions              → liste des versions
│           # GET  /model/current               → version active
│           # POST /model/rollback/{version}    → retour arrière
│           # GET  /model/metrics               → métriques (Recall, AUC-PR,
│           #                                    dérive)
│           # Permet la mise à jour et le rollback sans interruption.
│
├── services/
│   │
│   │   # Couche métier. Chaque service est une classe ou un module avec
│   │   # des méthodes pures (testables sans HTTP). Les routers appellent
│   │   # ces services — jamais l'inverse (pas de dépendance API → métier
│   │   # inversée).
│   │
│   ├── facture_service.py
│   │   # Orchestrateur du pipeline Flux 1.
│   │   # Méthode principale : `traiter_facture(facture_in) -> FactureOut`
│   │   # Enchaîne :
│   │   #   1. validation_service.valider()
│   │   #   2. (si valide) calcul_service.calculer()
│   │   #   3. regles_service.detecter()
│   │   #   4. features_service.construire()
│   │   #   5. ml_service.predire()
│   │   #   6. stockage en base (factures, lignes, predictions, shap)
│   │   #   7. alerte n8n si score > seuil
│   │   # Gère les transactions ACID (tout ou rien).
│   │
│   ├── calcul_service.py
│   │   # Calcul du remboursement (déterministe, métier).
│   │   # Implémente la formule :
│   │   #   Base = MIN(prix_facturé, tarif_max_barème)
│   │   #   Montant_brut = Base × taux_catégorie
│   │   #   Montant_net = MIN(brut, plafond_cat_restant, plafond_global_restant)
│   │   #                  − franchise
│   │   #   Reste_à_charge = prix_facturé − montant_net
│   │   # Vérifie carence, période de couverture, plafonds.
│   │   # Ne dépend PAS du ML (dégradation gracieuse possible).
│   │
│   ├── validation_service.py
│   │   # Contrôle d'invalidité (10 codes du référentiel métier).
│   │   # Méthode : `valider(facture) -> list[CodeInvalidite]`
│   │   # Codes : MONTANT_NEGATIF, CODE_ACTE_INCONNU, DATE_FUTURE,
│   │   # DATE_IMPOSSIBLE, CHAMP_OBLIGATOIRE_MANQUANT, TOTAL_INCOHERENT,
│   │   # PRESTATAIRE_INCONNU, ASSURE_INCONNU, DEVISE_INVALIDE,
│   │   # FACTURE_SANS_LIGNE.
│   │   # Si liste non vide → la facture est rejetée (HTTP 422) et
│   │   # n'entre PAS dans le pipeline ML.
│   │
│   ├── regles_service.py
│   │   # Détection des 14 codes de fraude facture (règles métier).
│   │   # Méthode : `detecter(facture, contexte) -> list[CodeFraude]`
│   │   # Codes : SURFACTURATION, QUANTITE_EXCESSIVE, UPCODING,
│   │   # LIGNES_NON_PRESCRITES, SUBSTITUTION_PRODUIT, ORDONNANCE_EXPIREE,
│   │   # SOINS_JOUR_FERME, DOUBLON, FRACTIONNEMENT, SURCONSOMMATION,
│   │   # ACTE_FICTIF, INCOHERENCE_PROFIL, PRESTATAIRE_RADIE, HORS_COUVERTURE.
│   │   # Chaque code a une règle déterministe (SQL/Python) qui le déclenche.
│   │   # Sortie = features binaires pour le ML + labels pour l'explicabilité.
│   │
│   ├── features_service.py
│   │   # Feature engineering pour le ML.
│   │   # Méthode : `construire(facture, contexte, codes_fraude) -> dict`
│   │   # Produit :
│   │   # - Les 14 booléens des règles (is_surfacturation, is_doublon, …)
│   │   # - Les features brutes (montant_total, ecart_tarifaire,
│   │   #   ratio_prix_max, quantite_ratio_prescrite, nb_factures_30j,
│   │   #   anciennete_prestataire_jours, taux_rejet_prestataire,
│   │   #   est_nouveau_patient, delai_soin_facture, est_weekend, est_nuit,
│   │   #   age_assure, sexe_assure, …)
│   │   # - Les encodages catégoriels (one-hot : type_facture, canal_reception)
│   │   # Doit être IDENTIQUE à l'entraînement et à l'inférence (même ordre
│   │   # des features, même encodage). Sauvegarde le feature pipeline.
│   │
│   ├── ml_service.py
│   │   # Inférence ML + explicabilité SHAP.
│   │   # Méthodes :
│   │   # - `predire(features) -> (score, version_modele)`
│   │   # - `expliquer(features) -> list[ShapContribution]`
│   │   # - `charger_modele(version)` / `recharger_modele()`
│   │   # Charge le modèle XGBoost/LightGBM depuis le registry (versioning).
│   │   # Supporte le rollback (CDC §2 "Maintenance").
│   │   # Gère les erreurs : si le modèle est indisponible, on continue
│   │   # avec un score par défaut (dégradation gracieuse) et on log.
│   │
│   ├── rag_service.py
│   │   # Flux 2 — génération de la réponse RAG.
│   │   # Méthode : `repondre(question, contract_id, assure_id) -> Reponse`
│   │   # Enchaîne :
│   │   #   1. Garde-fous input (injection, identité, autre contrat)
│   │   #   2. Retrieval vectoriel (pgvector) filtré par contract_id
│   │   #   3. Requête SQL (historique de l'assuré, lecture seule)
│   │   #   4. Inférence LLM sécurisée (SYSTEM_PROMPT)
│   │   #   5. Post-traitement (masquage ASS-…, sources)
│   │   # Retourne réponse + sources traçables.
│   │
│   └── bi_service.py
│       # Agrégations SQL pour le Flux 3.
│       # Méthodes : `kpis()`, `evolution()`, `top_prestataires()`,
│       # `distribution_scores()`, etc.
│       # Optimise les requêtes (index, vues matérialisées) pour le dashboard.
│       # Sépare les KPIs métier (montants économisés, taux de détection)
│       # des KPIs techniques (latence, volume).
│
├── models/
│   # Modèles SQLAlchemy (ORM) — un fichier par table ou par domaine.
│   # Exemples :
│   # - facture.py       → Facture, LigneFacture
│   # - contrat.py       → Contrat, Garantie
│   # - assure.py        → Assure, IdentiteChiffree
│   # - prestataire.py   → Prestataire, GrilleTarifaire
│   # - referentiel.py   → ReferentielActe, ReferentielMedicament
│   # - ordonnance.py    → Ordonnance, OrdonnanceLigne
│   # - prediction.py    → Prediction, ExplicationShap
│   # - alerte.py        → Alerte
│   # - audit.py         → JournalAudit, FactureRejetee
│   # - user.py         → Utilisateur, Role
│   # - document.py     → DocumentVectorise (pgvector)
│   # Chaque modèle est mappé à une table et porte les contraintes
│   # (FK, CHECK, UNIQUE, INDEX).
│
├── schemas/
│   # Schémas Pydantic — contrat d'API (entrée/sortie HTTP).
│   # Un fichier par domaine, aligné sur les routers.
│   # Exemples :
│   # - facture.py       → FactureIn, FactureOut, LigneIn, LigneOut
│   # - predict.py       → PredictIn, PredictOut, ShapContribution
│   # - contrat.py       → ContratOut, GarantieOut
│   # - assistant.py     → AssistantIn, AssistantOut, SourceOut
│   # - auth.py         → LoginIn, TokenOut, UserOut
│   # Les schémas In valident les données (types, formats, regex ID) ;
│   # les schémas Out garantissent le contrat de sortie (pas de fuite
│   # de colonnes internes comme `montant_pris_en_charge`).
│   # Ne JAMAIS exposer les modèles ORM directement.
│
└── tests/
    # Tests unitaires et d'intégration (pytest).
    # Structure recommandée :
    # - test_auth.py            → login, JWT, rôles
    # - test_factures.py        → pipeline complet (valide, invalide, fraude)
    # - test_validation.py      → les 10 codes d'invalidité
    # - test_regles.py          → les 14 codes de fraude
    # - test_calcul.py          → formule de remboursement
    # - test_ml.py              → inférence + SHAP
    # - test_assistant.py       → RAG (garde-fous, sources)
    # - test_bi.py              → KPIs
    # - test_integration.py     → Flux 1 + Flux 2 + Flux 3 bout en bout
    # - conftest.py             → fixtures (DB test, client HTTP, JWT, données)
    # Objectif CDC : couverture des cas nominaux + cas limites + sécurité
    # (injection, identité, autre contrat).
