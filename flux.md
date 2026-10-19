
# PrediCare TPA : Flux corrigés (v2)

Légende : `[MODIF]` bloc modifié · `[NOUVEAU]` bloc ajouté · le reste est inchangé par rapport à la v1.

---

## FLUX 1 : Pipeline factures et ordonnances

```
Réception facture (HTTP POST /api/v1/factures)   [rôle : professionnel_sante]
    │
    ├──► [1] Validation syntaxique (schéma Pydantic)
    │       │
    │       ├── Vérification du schéma : assure_id, prestataire_id, lignes[], date, ordonnance_ref
    │       ├── Authentification JWT + rôle
    │       ├── [NOUVEAU] Contrôle de propriété : prestataire_id == prestataire du JWT
    │       └── SI ÉCHEC → HTTP 400 / 401 / 403 (format d'erreur {code, message, details}), FIN
    │
    ├──► [2] Contrôle d'invalidité (10 codes : Feuille 4 du Référentiel)
    │       │
    │       ├── Codes : MONTANT_NEGATIF, CODE_ACTE_INCONNU, DATE_FUTURE, DATE_IMPOSSIBLE,
    │       │           CHAMP_OBLIGATOIRE_MANQUANT, TOTAL_INCOHERENT, PRESTATAIRE_INCONNU,
    │       │           ASSURE_INCONNU, DEVISE_INVALIDE, FACTURE_SANS_LIGNE
    │       │
    │       ├── SI INVALIDE :
    │       │     ├── HTTP 422 + liste des codes déclenchés (affichée par DepositInvoicePage)
    │       │     ├── [MODIF] Écriture dans `factures_rejetees` (Option B retenue)
    │       │     ├── [MODIF] Écriture dans `journal_audit`
    │       │     └── FIN : PAS de ML, PAS de SHAP, PAS d'alerte n8n
    │       │
    │       └── SI VALIDE : continuer
    │
    ├──► [3] Prétraitement : construction du `contexte` (contexte_service)
    │       │
    │       ├── Facture ↔ Contrat (formule, plafonds, dates, statut)
    │       ├── Facture ↔ Barème (tarif min/réf/max par code acte)
    │       ├── Facture ↔ Ordonnance (actes prescrits, validité, prescripteur)
    │       ├── Facture ↔ Prestataire (convention active, spécialité, horaires)
    │       ├── Facture ↔ Assuré (bénéficiaire couvert, âge, sexe, plafonds consommés)
    │       ├── Normalisation : devise MGA, arrondis, dates ISO
    │       └── Enrichissement : écart tarifaire, ancienneté, fréquence, etc.
    │
    ├──► [4] Calcul du remboursement (métier, déterministe, indépendant du ML)
    │       │
    │       ├── Base = MIN(prix_facturé, tarif_max_barème)
    │       ├── Montant_brut = Base × taux_catégorie (Article 5 CG)
    │       ├── Montant_net = MIN(Montant_brut, plafond_catégorie_restant, plafond_global_restant) − franchise
    │       ├── Reste_à_charge = prix_facturé − Montant_net
    │       ├── Vérification carence + période de couverture
    │       └── Sortie : montant_calculé, montant_réclamé, écart
    │
    ├──► [5] Détection fraudes factures (14 codes : Feuille 3, règles métier)
    │       │
    │       ├── SURFACTURATION, QUANTITE_EXCESSIVE, UPCODING, LIGNES_NON_PRESCRITES,
    │       │   SUBSTITUTION_PRODUIT, ORDONNANCE_EXPIREE, SOINS_JOUR_FERME, DOUBLON,
    │       │   FRACTIONNEMENT, SURCONSOMMATION, ACTE_FICTIF, INCOHERENCE_PROFIL,
    │       │   PRESTATAIRE_RADIE, HORS_COUVERTURE
    │       │
    │       ├── [NOUVEAU] Appel de `regles_ordonnance` (voir bloc [5bis]) :
    │       │             les anomalies de prescription liées à l'ordonnance de la facture
    │       │             sont ajoutées à la liste des codes
    │       └── Sortie : liste codes déclenchés + indicateurs associés
    │
    ├──► [6] Inférence ML (XGBoost/LightGBM)
    │       │
    │       ├── Entrée : features du prétraitement exactement dans feature_schema.json
    │       │             (les flags is_* des règles ne sont pas des features du modèle)
    │       ├── Modèle Dockerisé, exposé via FastAPI (POST /predict)
    │       ├── Sortie : score ∈ [0, 1] + version_modele
    │       ├── [NOUVEAU] Versioning : la version du modèle est stockée avec la prédiction
    │       └── [MODIF] SI MODÈLE INDISPONIBLE :
    │             ├── PAS de score par défaut (risque de masquer des fraudes)
    │             ├── statut = EN_ATTENTE_GESTIONNAIRE + indicateur `scoring_indisponible = true`
    │             ├── SHAP ignoré, codes de règles conservés
    │             └── Erreur journalisée, alerte admin
    │
    ├──► [7] SHAP (explicabilité)
    │       │
    │       ├── Valeurs SHAP : contribution de chaque feature au score
    │       ├── Sortie : top-k features (positives et négatives)
    │       └── Exigence CDC : rapport SHAP pour chaque alerte transmise
    │
    ├──► [8] Stockage : transaction ACID (tout ou rien)
    │       │
    │       ├── Tables : factures, lignes_facture, calculs_remboursement,
    │       │            predictions (score + version_modele), explications_shap,
    │       │            journal_audit
    │       └── [NOUVEAU] Une alerte (`is_alert = true`) est créée si la condition [9] est vraie
    │
    ├──► [9] Décision d'alerte et notification n8n   [MODIF]
    │       │
    │       ├── Condition CDC (toujours active) : score > SEUIL_ALERTE
    │       │     SEUIL_ALERTE = valeur lue dans la table `configuration` (défaut 0.8),
    │       │     modifiable en direct depuis AdminConfig
    │       ├── Condition étendue (optionnelle, désactivable dans la config) :
    │       │     code de règle critique déclenché (ex. DOUBLON, PRESTATAIRE_RADIE, ACTE_FICTIF)
    │       │     → priorité « moyenne », sans envoi Slack immédiat (revue dans la file)
    │       ├── Action (si score > seuil) : `notification_service` → webhook n8n
    │       │     → Slack/Email gestionnaire, avec retry (3 essais) et journalisation
    │       ├── Contenu : rapport d'explicabilité (SHAP + codes + montants)
    │       └── SI n8n injoignable : l'alerte reste en base (visible dans AlertsListPage),
    │                                erreur journalisée, nouvel essai planifié
    │
    ├──► [10] Décision du gestionnaire   [NOUVEAU]
    │       │
    │       ├── Écran : AlertDetailPage → PATCH /api/v1/alertes/{id}/decision
    │       ├── Actions : VALIDER / REJETER / CONFIRMER_FRAUDE / ESCALADER + commentaire
    │       ├── Écriture dans `decisions_gestionnaires` (utilisateur, date, motif)
    │       ├── Mise à jour du statut facture : VALIDE / REJETEE / ESCALADEE
    │       ├── Écriture dans `journal_audit`
    │       └── Ces décisions alimentent les KPI BI (Flux 3) : fraude confirmée, précision
    │
    └──► [11] HTTP 200 (réponse à l'étape [8]-[9], ne dépend pas de [10])
            │
            └── Sortie : transaction_id, montant_calculé, score, codes_fraude,
                         statut (VALIDE / REJETEE / EN_ATTENTE_GESTIONNAIRE),
                         scoring_indisponible (bool)
```

### [5bis] Détection des anomalies de prescription   [NOUVEAU]

Le CDC demande une détection d'anomalies de prescriptions, indépendante du moment où la facture arrive.

```
Déclencheurs :
    ├── (a) Création d'ordonnance : POST /api/v1/ordonnances   [rôle : professionnel_sante]
    └── (b) Étape [5] du Flux 1 (ordonnance référencée par la facture)

Contrôles (regles_ordonnance_service) :
    ├── DOUBLON_PRESCRIPTION        même assuré + mêmes médicaments/actes sur fenêtre N jours
    ├── PRESCRIPTION_MULTI_PRESCRIPTEURS  même assuré, plusieurs prescripteurs, même classe
    ├── INADEQUATION_PATHOLOGIE     médicament/acte incohérent avec le diagnostic
    │                               (table de compatibilité diagnostic ↔ actes/médicaments)
    ├── POSOLOGIE_ABERRANTE         quantité/durée hors bornes du référentiel médicaments
    └── PRESCRIPTEUR_HORS_SPECIALITE  spécialité du prescripteur incompatible avec la prescription

Sortie :
    ├── Écriture dans `alertes` (type = PRESCRIPTION) avec codes déclenchés
    ├── Notification n8n selon la même règle de priorité que [9]
    ├── Features supplémentaires pour le ML (flags ordonnance)
    └── Même circuit de décision gestionnaire que [10]
```

> Les noms de codes ci-dessus sont des propositions : aligne-les avec le référentiel fourni par l'encadrement.

### Points à documenter pour le jury (Flux 1)

| Sujet           | Argument à préparer                                                                                                                                                                                                                |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Fuite de labels | `feature_schema.json` ne contient aucun flag `is_*`. Les règles restent des libellés d'explicabilité ; elles ne sont pas ajoutées au vecteur ML. |
| Déséquilibre  | SMOTE/seuils appliqués uniquement sur le jeu d'entraînement ; seuil de décision choisi pour maximiser le rappel (Module 2).                                                                                                       |

---

## FLUX 2 : Assistant conversationnel RAG

```
Requête assuré (HTTP POST /api/v1/assistant/ask)   [rôle : assure]
    │
    ├──► [1] Réception et garde-fous INPUT
    │       │
    │       ├── Entrée : message texte ; assure_id et contract_id tirés du JWT (jamais du corps)
    │       ├── Garde-fous INPUT :
    │       │     ├── Blocage des injections de prompt
    │       │     ├── Blocage des demandes d'identité réelle
    │       │     └── Blocage des questions sur un autre contrat
    │       ├── SI garde-fou déclenché → refus poli, journalisé, FIN
    │       └── [NOUVEAU] Limite de débit par assuré (anti-abus, maîtrise des coûts tokens)
    │
    ├──► [2] Cache sémantique   [NOUVEAU : Module 6 FinOps]
    │       │
    │       ├── Embedding de la question
    │       ├── Recherche d'une question proche (similarité ≥ seuil configurable)
    │       │   DANS LE PÉRIMÈTRE du même contract_id
    │       ├── SI HIT et réponse ne dépendant pas de données personnelles → réponse en cache
    │       │   (sources incluses), passage à [7]
    │       ├── Les réponses issues de `query_sql` (données personnelles) ne sont JAMAIS mises en cache
    │       └── SI MISS → continuer
    │
    ├──► [3] Agent IA : boucle ReAct (agent_service)   [MODIF : étapes 3 à 5 de la v1 imbriquées ici]
    │       │
    │       ├── Boucle (max N itérations, ex. 6 ; N configurable) :
    │       │     RAISONNER → CHOISIR UN OUTIL → AGIR → OBSERVER → répéter
    │       │
    │       ├── Outils disponibles :
    │       │     │
    │       │     ├── search_vector_db(question)
    │       │     │     ├── Embedding de la question → top-k chunks (pgvector)
    │       │     │     ├── Filtre IMPOSÉ par le code sur contract_id (non fourni par le LLM)
    │       │     │     ├── Priorité sourcing : CP_<contract_id>.pdf > CG_<FORMULE>.pdf
    │       │     │     │                      > Barème > Guide Réseau
    │       │     │     └── Sortie : chunks + métadonnées [fichier, article, page]
    │       │     │
    │       │     ├── query_sql(requete)   [MODIF : sécurité côté base]
    │       │     │     ├── Rôle PostgreSQL en lecture seule (`agent_ro`)
    │       │     │     ├── Accès uniquement à des VUES dédiées (ex. v_agent_claim_status)
    │       │     │     ├── Row-Level Security : le filtre sur assure_id est appliqué par la base
    │       │     │     │   via un paramètre de session (SET LOCAL app.assure_id = <JWT>),
    │       │     │     │   et ne dépend PAS du SQL généré par le LLM
    │       │     │     ├── Requête validée avant exécution (SELECT unique, pas de multi-statements)
    │       │     │     └── Timeout + limite de lignes
    │       │     │
    │       │     ├── ask_user(clarification)   → pose une question à l'assuré, puis reprise
    │       │     └── final_answer(reponse)     → sort de la boucle
    │       │
    │       ├── Inférence LLM sécurisée (à chaque tour) :
    │       │     ├── SYSTEM_PROMPT : langue imposée, pas de PII, pas d'identité réelle,
    │       │     │                   priorité de sourcing CP > CG > Barème > Guide
    │       │     └── Contexte : chunks + résultats SQL + question
    │       │
    │       └── SI limite d'itérations atteinte → repli (étape [4])
    │
    ├──► [4] Réponse sourcée et factuelle
    │       │
    │       ├── Format : réponse directe + détail + source [fichier, article, page]
    │       ├── Traçabilité : chaque affirmation rattachée à un chunk ou à une ligne SQL
    │       └── Repli : info absente / boucle épuisée / outil en erreur
    │             → « Veuillez contacter un gestionnaire »
    │
    ├──► [5] Garde-fous OUTPUT
    │       │
    │       ├── Pas d'identifiants `ASS-…`
    │       ├── Pas de données d'autres assurés
    │       ├── Pas de fuite du prompt système
    │       └── SI déclenché → réponse censurée / repli
    │
    ├──► [6] Mise en cache de la réponse (si éligible, voir [2])   [NOUVEAU]
    │
    ├──► [7] Journalisation (journal_audit)
    │       │
    │       ├── Champs : question, réponse, sources, outils appelés, nb d'itérations,
    │       │            durée, tokens (entrée/sortie), cache_hit, garde-fou déclenché
    │       ├── [NOUVEAU] Coût estimé par requête (alimente le suivi FinOps du dashboard)
    │       └── Exigence CDC : traçabilité et supervision
    │
    └──► [8] Réponse HTTP 200 à l'assuré
            │
            └── Sortie : réponse + sources citées + message_id
                (ChatPage peut ensuite appeler POST /assistant/feedback
                 et GET /assistant/sources/{message_id})
```

### Notes d'intégration (Flux 2)

| Sujet         | Règle                                                                                                                                    |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Déploiement  | Module RAG importé dans l'API (même JWT, un conteneur de moins) ; le Dockerfile de `backend/rag/` reste utile pour les tests isolés. |
| Configuration | Seuil du cache, nombre max d'itérations, modèle LLM lus depuis `configuration` ou `.env`.                                           |
| Identité     | `assure_id` n'apparaît jamais dans le corps ni dans l'URL ; uniquement dans le JWT.                                                    |

---

## FLUX 3 : Pilotage décisionnel (BI)

```
Dashboard BI (Metabase / endpoints JSON /api/v1/bi/*)   [rôle : gestionnaire ; admin pour la supervision]
    │
    ├──► [1] Collecte des données   [MODIF : un seul mode de rafraîchissement]
    │       │
    │       ├── Sources :
    │       │     ├── `factures`, `factures_rejetees`
    │       │     ├── `predictions`           (scores, version_modele)
    │       │     ├── `calculs_remboursement` (montants calculés, écarts)
    │       │     ├── `alertes`
    │       │     ├── `decisions_gestionnaires` (validations, rejets, fraudes confirmées)
    │       │     ├── `labels_fraude`         (évaluation hors ligne uniquement)
    │       │     └── `journal_audit`         (latence, tokens, coûts, erreurs)
    │       │
    │       ├── Mode unique : vues matérialisées rafraîchies toutes les 5 minutes
    │       │   (REFRESH ... CONCURRENTLY) ; pas de trigger sur INSERT/UPDATE
    │       │
    │       └── SI source ou vue indisponible → dernière valeur connue + bandeau
    │           « données au <horodatage> » + alerte admin
    │
    ├──► [2] Agrégation (KPI)   [MODIF : définitions corrigées]
    │       │
    │       ├── Volumes
    │       │     ├── Factures traitées : par jour, par formule, par prestataire
    │       │     └── Factures rejetées (invalides) : par code d'invalidité
    │       │
    │       ├── Montants   [MODIF]
    │       │     ├── Montant total réclamé
    │       │     ├── Montant total remboursé
    │       │     ├── Montant à risque = somme du réclamé des factures en alerte
    │       │     │     (potentiel, avant décision)
    │       │     └── Montant économisé = somme de (montant_réclamé − montant_calculé)
    │       │           sur les factures dont la décision gestionnaire = REJETER ou
    │       │           CONFIRMER_FRAUDE (confirmé, après décision)
    │       │     ⚠ L'ancienne définition (réclamé − remboursé) est supprimée : elle incluait
    │       │       ticket modérateur, franchises et plafonds, qui ne sont pas de la fraude.
    │       │
    │       ├── Qualité de détection   [MODIF : 3 indicateurs distincts]
    │       │     ├── Taux d'alerte      = factures en alerte / factures traitées
    │       │     ├── Précision opérationnelle = fraudes confirmées / alertes décidées
    │       │     │                              (via decisions_gestionnaires)
    │       │     └── Rappel (hors ligne) = fraudes détectées / fraudes réelles
    │       │                               (via labels_fraude, sur jeu de test ; indicateur
    │       │                               du modèle, affiché dans la vue Modèle)
    │       │
    │       ├── Distribution des scores (histogramme [0, 1], avec le seuil d'alerte en repère)
    │       ├── Top prestataires / assurés à risque
    │       ├── Alertes : générées, en attente, traitées, escaladées, délai moyen de traitement
    │       ├── Notifications n8n : envoyées / échouées
    │       ├── Latence de traitement du Flux 1 (p50, p95)
    │       └── [NOUVEAU] Suivi FinOps du RAG : tokens, coût estimé, taux de cache_hit
    │
    ├──► [3] Visualisation
    │       │
    │       ├── Outil : Metabase (vue détaillée) + cartes JSON de /bi/kpis pour ManagerDashboard
    │       ├── Vues :
    │       │     ├── Synthétique     : volume, montants (réclamé / à risque / économisé), taux
    │       │     ├── Par formule     : ESSENTIEL / CONFORT / PREMIUM
    │       │     ├── Par catégorie   : type d'acte
    │       │     ├── Temporelle      : jour / semaine / mois
    │       │     ├── Explicabilité   : drill-down vers les SHAP d'une alerte
    │       │     └── [NOUVEAU] Modèle : version active, rappel/AUC-PR, dérive
    │       │         (distribution des scores et des features vs référence d'entraînement,
    │       │          ex. PSI) : exigence « Supervisable »
    │       │
    │       └── SI donnée manquante → « N/A » + lien vers journal_audit
    │
    ├──► [4] Alerting admin (optionnel, seuils configurables dans AdminConfig)
    │       │
    │       ├── Chute du taux d'alerte ou de la précision → alerte admin
    │       ├── Explosion du volume ou du taux de rejet   → alerte admin
    │       ├── Hausse de la latence p95                  → alerte admin
    │       ├── [NOUVEAU] Dérive du modèle au-dessus du seuil → alerte admin
    │       └── Canal : Slack / Email admin
    │
    └──► [5] Sortie dashboard
            │
            └── KPI (rafraîchis toutes les 5 min) + vues + drill-down + alertes éventuelles
```

---

## Récapitulatif des corrections

| #  | Flux | Correction                                                                                               |
| -- | ---- | -------------------------------------------------------------------------------------------------------- |
| 1  | 1    | Option B (`factures_rejetees`) retenue                                                                 |
| 2  | 1    | Bloc [5bis] : anomalies de prescription (mission explicite du CDC)                                       |
| 3  | 1    | Seuil d'alerte configurable ; condition « score > seuil » conforme au CDC, règles critiques en option |
| 4  | 1    | Étape [10] : décision gestionnaire écrite dans `decisions_gestionnaires`                            |
| 5  | 1    | ML indisponible → `EN_ATTENTE_GESTIONNAIRE`, plus de score par défaut                                |
| 6  | 1    | Retry n8n, alerte conservée en base si le webhook échoue                                               |
| 7  | 2    | Étapes retrieval / SQL / LLM imbriquées dans la boucle ReAct, avec limite d'itérations                |
| 8  | 2    | Filtre assuré imposé par RLS PostgreSQL et vues, pas par le prompt                                     |
| 9  | 2    | Cache sémantique (Module 6), jamais sur les réponses contenant des données personnelles               |
| 10 | 2    | Identité issue du JWT uniquement ; limite de débit ; coûts journalisés                               |
| 11 | 3    | « Montant économisé » redéfini sur les décisions confirmées                                       |
| 12 | 3    | Taux de détection scindé : taux d'alerte, précision, rappel                                           |
| 13 | 3    | Un seul mode de rafraîchissement (vues matérialisées, 5 min)                                          |
| 14 | 3    | Vue Modèle avec dérive, alerte de dérive, suivi FinOps du RAG                                         |
