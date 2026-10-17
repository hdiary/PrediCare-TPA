# PrediCare TPA

\*\*Système intelligent de détection de fraudes médicales, d'optimisation des remboursements santé et d'assistant conversationnel RAG.\*\*

# Projet Capstone - Cohorte IA - Partenariat Orange Digital Center (ODC) \& Ingedata.

> ⚠️ \*\*Données 100 % synthétiques.\*\* Aucune donnée de santé réelle n'est utilisée dans ce projet.

# \---

# \## Sommaire

# 1\. \[Présentation](#1-présentation)

# 2\. \[Fonctionnalités](#2-fonctionnalités)

# 3\. \[Architecture](#3-architecture)

# 4\. \[Démarrage rapide](#4-démarrage-rapide)

# 5\. \[Configuration](#5-configuration)

# 6\. \[Utilisation par rôle](#6-utilisation-par-rôle)

# 7\. \[Structure du dépôt](#7-structure-du-dépôt)

# 8\. \[Exploitation](#8-exploitation)

# 9\. \[Tests et CI](#9-tests-et-ci)

# 10\. \[Sécurité, RGPD et AI Act](#10-sécurité-rgpd-et-ai-act)

# 11\. \[Organisation de l'équipe](#11-organisation-de-léquipe)

# 12\. \[Documentation](#12-documentation)

# \---

# \## 1. Présentation

# \### Le problème

# Dans la gestion du Tiers-Payant (TPA) et de l'assurance santé :

# \- la fraude médicale, la surconsommation d'actes et les erreurs de tarification représentent \*\*8 % à 15 %\*\* des remboursements ;

# \- le contrôle manuel des factures et ordonnances est lent et faillible ;

# \- les centres d'appels sont saturés par des demandes de suivi de dossier et d'interprétation des garanties.

# \### Notre réponse

# PrediCare TPA est une plateforme unique, déployable en une commande, qui :

# \- \*\*contrôle automatiquement les factures\*\* et détecte les anomalies financières avec une explication (SHAP) pour chaque alerte ;

# \- \*\*détecte les anomalies de prescription\*\* (doublons pour un même assuré, inadéquation entre prescription et pathologie) ;

# \- \*\*alerte les gestionnaires\*\* en temps réel (Slack / Email) ;

# \- offre aux assurés un \*\*assistant IA\*\* (RAG + agent) qui répond sur leurs contrats et leur historique, avec des sources citées ;

# \- fournit un \*\*tableau de bord décisionnel\*\* (volumes, montants économisés, taux de détection).

# Principe fondamental : \*\*aucune décision n'est automatique\*\*. Le modèle propose, le gestionnaire valide ou rejette, et chaque décision est tracée.

# \---

# \## 2. Fonctionnalités

# | Domaine | Fonctionnalité |

# |---|---|

# | Données | Ingestion et nettoyage idempotents, quarantaine des lignes invalides, pseudonymisation, identités chiffrées à part |

# | Machine learning | Modèle XGBoost/LightGBM, gestion du déséquilibre de classes, seuil optimisé pour le Recall |

# | Explicabilité | Valeurs SHAP pour chaque alerte, top 5 des facteurs en langage clair |

# | Ordonnances | Détection de doublons et d'incohérences prescription / pathologie |

# | API | FastAPI conteneurisée, validation stricte, rejet propre des factures invalides |

# | Alertes | Workflow n8n : score au-dessus du seuil → notification Slack / Email |

# | Assistant | Agent ReAct sur contrats (pgvector) et historique SQL (lecture seule), protégé contre le prompt injection |

# | Pilotage | Dashboard BI, supervision, suivi de dérive du modèle |

# | Exploitation | Sauvegarde et restauration scriptées, versioning du modèle avec retour arrière |

# \---

# \## 3. Architecture

# ```mermaid

# flowchart LR

# &#x20;   U\[Utilisateurs4 rôles] --> W\[webFrontend]

# &#x20;   W --> A\[apiFastAPI]

# &#x20;   A --> D\[(dbPostgreSQL + pgvector)]

# &#x20;   A --> M\[mlflowversions du modèle]

# &#x20;   A -->|score > seuil| N\[n8nworkflow]

# &#x20;   N --> S\[Slack / Email]

# &#x20;   A --> L\[LLM]

# &#x20;   B\[biDashboard] --> D

# ```

# \### Les 3 flux

# 1\. \*\*Pipeline analytique et ML\*\* : réception de la facture → prétraitement → inférence (XGBoost) → valeurs SHAP → stockage → workflow n8n (si score > seuil, alerte au gestionnaire avec explication).

# 2\. \*\*Assistant conversationnel\*\* : question de l'assuré → agent IA (ReAct) → base vectorielle (contrats PDF) et base SQL (historique du compte, lecture seule) → LLM sécurisé → réponse sourcée.

# 3\. \*\*Pilotage décisionnel\*\* : tableau de bord BI (volumes traités, montants économisés, taux de détection).

# \### Conteneurs (Docker Compose)

# | Service | Rôle | Port |

# |---|---|---|

# | `db` | PostgreSQL + pgvector (données, prédictions, SHAP, vecteurs, audit) | interne |

# | `loader` | Chargement initial des données (s'exécute une fois) | - |

# | `api` | API FastAPI (modèle, RAG, rôles, administration) | 8000 |

# | `mlflow` | Registre des versions du modèle | 5000 |

# | `n8n` | Workflow d'alertes | 5678 |

# | `web` | Interface web | 3000 |

# | `bi` | Tableau de bord décisionnel | à compléter |

# \### Choix techniques

# | Brique | Choix | Raison |

# |---|---|---|

# | Base de données | PostgreSQL + pgvector | Une seule instance pour toutes les données |

# | Modèle | XGBoost / LightGBM | Performant sur données tabulaires, compatible SHAP |

# | Versions du modèle | MLflow | Mise à jour et retour arrière sans interruption |

# | Alertes | n8n | Low-code, workflows exportables en `.json` |

# | BI | à compléter (Superset ou Metabase) | - |

# | LLM / embeddings | à compléter | Coût et confidentialité (voir analyse FinOps) |

# \---

# \## 4. Démarrage rapide

# \### Prérequis

# \- Docker et Docker Compose v2

# \- 8 Go de RAM recommandés

# \- Ports libres : 3000, 5000, 5678, 8000

# \### Installation

# ```bash

# git clone <URL\_DU\_DEPOT>

# cd predicare-tpa

#### 1. Créer la configuration

# cp .env.example .env

# \#    puis remplacer chaque valeur "change\_me" (voir section 5)

# \# 2. Démarrer toute la plateforme

# docker compose up --build

# ```

# Au \*\*premier démarrage\*\*, la base est créée par les migrations versionnées et les données sont chargées automatiquement.

# \### Accès

# | Service | URL |

# |---|---|

# | Interface web | http://localhost:3000 |

# | Documentation de l'API | http://localhost:8000/docs |

# | Santé de l'API | http://localhost:8000/health |

# | n8n | http://localhost:5678 |

# | MLflow | http://localhost:5000 |

# \### Arrêt et remise à zéro

# ```bash

# docker compose down        # arrêt (les données sont conservées)

# docker compose down -v     # arrêt ET suppression des données (remise à zéro)

# ```

# > ⚠️ Les migrations SQL ne s'exécutent qu'à la création du volume. Pour rejouer une migration modifiée : `docker compose down -v` puis `docker compose up --build`.

# \---

# \## 5. Configuration

# Toute la configuration passe par le fichier `.env` (jamais versionné) ou par l'écran d'administration. \*\*Aucune valeur n'est écrite dans le code.\*\*

# | Variable | Rôle |

# |---|---|

# | `POSTGRES\_\*` | Accès à la base |

# | `DB\_BI\_RO\_PASSWORD`, `DB\_ML\_RO\_PASSWORD`, `DB\_AGENT\_RO\_PASSWORD` | Comptes à droits limités (BI, ML, agent IA) |

# | `JWT\_SECRET` | Signature des jetons de connexion |

# | `PSEUDO\_HMAC\_KEY` | Clé secrète de la pseudonymisation (ne jamais la perdre) |

# | `IDENTITY\_ENCRYPTION\_KEY` | Chiffrement de la table d'identités |

# | `ALERT\_THRESHOLD` | Seuil d'alerte initial (modifiable en direct par l'administrateur) |

# | `LLM\_API\_KEY`, `LLM\_MODEL` | Modèle de langage de l'assistant |

# | `SLACK\_WEBHOOK\_URL`, `ALERT\_EMAIL\_TO` | Canaux de notification |

# | `NEXT\_PUBLIC\_API\_URL` | Adresse publique de l'API (\*\*visible dans le navigateur, aucun secret\*\*) |

# Générer une clé : `openssl rand -hex 32`

# \*\*Seuil d'alerte\*\* : modifiable sans toucher au code depuis l'écran d'administration ; le changement est appliqué immédiatement.

# \---

# \## 6. Utilisation par rôle

# L'interface web unique propose quatre parcours, sans ligne de commande :

# | Rôle | Ce qu'il peut faire |

# |---|---|

# | \*\*Professionnel de santé\*\* | Déposer une facture, suivre son statut, corriger en cas de rejet |

# | \*\*Assuré\*\* | Interroger l'assistant IA (réponses sourcées), consulter ses remboursements |

# | \*\*Gestionnaire\*\* | Consulter les alertes, lire l'explication SHAP, valider ou rejeter avec commentaire |

# | \*\*Administrateur\*\* | Régler le seuil et les canaux, superviser, gérer les versions du modèle, consulter le journal d'audit |

# \### Comptes de démonstration

# | Rôle | Identifiant | Mot de passe |

# |---|---|---|

# | Professionnel de santé | à compléter | à compléter |

# | Assuré | à compléter | à compléter |

# | Gestionnaire | à compléter | à compléter |

# | Administrateur | à compléter | à compléter |

# > Ces comptes n'existent que pour la démonstration. Ne jamais les réutiliser en production.

# \---

# \## 7. Structure du dépôt

# ```

# predicare-tpa/

# ├── docker-compose.yml        # démarrage de toute la plateforme

# ├── .env.example              # modèle de configuration

# ├── frontend/                 # interface web

# ├── backend/

# │   ├── api/                  # routes FastAPI, authentification, rôles

# │   ├── ml/                   # entraînement, SHAP, règles d'ordonnances

# │   ├── rag/                  # agent, embeddings, protections

# │   ├── ingestion/            # nettoyage, pseudonymisation, chargement

# │   ├── tests/

# │   ├── Dockerfile

# │   └── requirements.txt

# ├── db/

# │   ├── migrations/           # scripts SQL versionnés (001\_\*.sql, ...)

# │   └── seed/                 # données de chargement initial

# ├── n8n/workflows/            # workflows importables (.json)

# ├── bi/                       # export du tableau de bord

# ├── scripts/                  # backup.sh, restore.sh

# └── docs/                     # architecture, conformité, sécurité, FinOps, guides

# ```

# \---

# \## 8. Exploitation

# \### Les 8 conditions « plateforme exploitable »

# | Condition | Comment c'est couvert | Statut |

# |---|---|---|

# | Déployable | `docker compose up` | à compléter |

# | Utilisable | Interface web, connexion, 4 rôles | à compléter |

# | Persistante | Volume PostgreSQL, sauvegarde et restauration | à compléter |

# | Configurable | `.env` et écran d'administration (seuil en direct) | à compléter |

# | Supervisable | `/health`, journaux, métriques, dérive | à compléter |

# | Maintenable | Modèle versionné, retour arrière, tests, CI | à compléter |

# | Robuste | Rejet propre des factures invalides | à compléter |

# | Documentée | Guides d'exploitation et utilisateur | à compléter |

# \### Sauvegarde et restauration

# ```bash

# ./scripts/backup.sh                    # sauvegarde chiffrée de la base

# ./scripts/restore.sh <fichier></fichier>         # restauration

# ```

# Procédure détaillée, planification quotidienne et résolution des incidents : voir `docs/guides/guide\_exploitation.md` (à compléter).

# \### Mise à jour et retour arrière du modèle

# Depuis l'écran d'administration, onglet « Modèles » : activer une version enregistrée dans MLflow ; la bascule vers une version précédente se fait sans interruption.

# \### Supervision

# \- `GET /health` : état de l'API et de ses dépendances

# \- métriques de latence, de volume et d'erreurs, suivi de dérive : écran d'administration

# \---

# \## 9. Tests et CI

# ```bash

# cd backend

# pip install -r requirements.txt

# pytest

# ```

# L'intégration continue (GitHub Actions) exécute le lint et les tests à chaque pull request ; la fusion dans `main` exige une CI verte.

# Le \*\*cahier de recette sécurité\*\* (`docs/securite/cahier\_recette\_securite.xlsx`) liste les 14 tests de sécurité et les 15 attaques de test contre l'assistant.

# \---

# \## 10. Sécurité, RGPD et AI Act

# \### Sécurité

# \- authentification et contrôle d'accès par rôle \*\*côté serveur\*\* ;

# \- assistant IA : compte SQL \*\*en lecture seule\*\*, limité à l'assuré connecté, protégé contre le prompt injection ;

# \- secrets uniquement dans `.env` (jamais dans Git) ;

# \- sauvegardes chiffrées ;

# \- validation stricte des entrées de l'API.

# \### RGPD

# \- \*\*pseudonymisation\*\* : noms et coordonnées dans une table chiffrée à part, le reste de la base n'utilise que des pseudonymes ;

# \- minimisation des données, registre des traitements, analyse d'impact (AIPD) ;

# \- aucune décision automatisée : le gestionnaire valide chaque alerte.

# \### AI Act

# Le système est cadré comme \*\*système à haut risque\*\* : gestion des risques, qualité des données, journalisation (journal d'audit), transparence (explication SHAP), contrôle humain, exactitude et robustesse, information de l'utilisateur sur l'interaction avec une IA. La grille complète est dans `docs/conformite/`.

# \### Équité

# Audit par groupe (sexe, âge, région, type de prestataire) : voir `docs/conformite/`.

# \---

# \## 11. Organisation de l'équipe

# | Membre | Rôle | Périmètre |

# |---|---|---|

# | à compléter | Données, BI, RGPD | Base, ingestion, pseudonymisation, dashboard |

# | à compléter | ML, explicabilité, rentabilité | Modèle, SHAP, équité, TCO/ROI |

# | à compléter | Plateforme et MLOps | Docker, API, n8n, supervision, CI |

# | à compléter | RAG et sécurité | Assistant, agent, anti-injection, cahier de recette |

# \### Workflow Git

# \- `main` protégée : fusion uniquement par pull request, avec une relecture et une CI verte ;

# \- branches courtes `feat/...`, `fix/...`, `docs/...` ;

# \- commits au format `type(portée): description`.

# \---

# \## 12. Documentation

# | Document | Emplacement |

# |---|---|

# | Dossier de cadrage stratégique et gouvernance | `docs/` |

# | Modèle FinOps (TCO / ROI) | `docs/finops/couts.xlsx` |

# | Registre RGPD, AIPD, grille AI Act, audit d'équité | `docs/conformite/` |

# | Cahier de recette sécurité | `docs/securite/` |

# | Journal de conformité | `docs/journal\_conformite.md` |

# | Guide utilisateur et guide d'exploitation | `docs/guides/` |

# \---

# \*Projet pédagogique réalisé dans le cadre de la Cohorte IA. Données synthétiques uniquement.\*
