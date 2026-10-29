# Rapport de conformité RGPD, grille d'évaluation EU AI Act et audit d'équité

- **Projet :** PrediCare TPA
- **Version du rapport :** 1.1
- **Statut et limites.** Ce document est une évaluation documentaire du prototype, pas une certification, un avis juridique, une AIPD validée ni un audit statistique indépendant. Les éléments signalés « constatés » sont visibles dans le code ou la documentation du dépôt ; « non documenté » signifie qu'aucune preuve suffisante n'a été trouvée dans le périmètre examiné. Une conformité réelle doit être établie par le responsable de traitement, le DPO et, selon le cas, un conseil juridique, à partir des traitements et données effectivement déployés.

## 1. Synthèse exécutive

PrediCare TPA traite des factures et ordonnances de santé, calcule des remboursements, attribue un score de fraude, produit des alertes explicables par SHAP et propose un assistant conversationnel RAG. Le code matérialise plusieurs mesures techniques utiles : pseudonymisation des comptes, chiffrement séparé de certaines identités et des historiques de chat, contrôle d'accès par rôles, journalisation de prédictions et de décisions, versions de modèles, et validation humaine des alertes.

Ces contrôles sont des **mesures de conception** ; ils ne suffisent pas à établir la conformité du traitement. Le dépôt ne fournit pas les éléments organisationnels et juridiques nécessaires (responsable/sous-traitants, base légale, exception de l'article 9, notices, registre, durées par catégorie, exercice des droits, AIPD, transferts, contrats fournisseurs, procédures d'incident et preuve de supervision).

## 2. Rapport d'évaluation RGPD

Échelle : **Documenté** = preuve observable dans le périmètre ; **Partiel** = contrôle ou intention identifié, preuve ou couverture incomplète ; **À établir** = preuve juridique/organisationnelle absente ou insuffisante. Cette échelle n'est pas une note de conformité officielle.

| Sujet / référence                                                 | Éléments observés                                                                                                                                                                                                                     |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Champ d'application territorial — art. 3                           | Projet TPA orienté MGA/Madagascar et documentation en français.                                                                                                                                                                        |
| Responsable, sous-traitants, gouvernance — art. 4, 24, 26, 28      | Les rôles applicatifs sont gestionnaire, assuré, professionnel de santé et administrateur.                                                                                                                                            |
| Licéité, loyauté, transparence — art. 5(1)(a), 6                | Le code possède des finalités fonctionnelles ; aucune base légale de traitement n'est démontrée dans les documents examinés.                                                                                                       |
| Données de santé — art. 9                                        | Les documents et dossiers de santé sont traités ou susceptibles de l'être dans le parcours facture/ordonnance.                                                                                                                        |
| Minimisation et exactitude — art. 5(1)(c)-(d), 25                  | Les identités de compte sont séparées et chiffrées ; le endpoint d'identité ne renvoie que nom, prénoms, téléphone et e-mail. Les caractéristiques brutes d'identité ne sont pas toutes dans les features finales.             |
| Limitation des finalités et conservation — art. 5(1)(b), (e)      | Suppression automatique des historiques de chat au bout de 180 jours ; sauvegardes chiffrées et rétention configurée dans les guides.                                                                                                 |
| Pseudonymisation et anonymisation — art. 4(5), 25, considérant 26 | HMAC pour identifiants de comptes ; pseudonyme `ASS-` tronqué à 10 caractères hexadécimaux ; identité distincte chiffrée avec Fernet.                                                                                            |
| Sécurité — art. 25, 32                                           | Contrôle d'accès par rôle côté serveur, comptes SQL distincts pour l'agent, chiffrement des identités et chats, sauvegardes chiffrées, clés par variables d'environnement, journal d'audit et limitations d'accès documentées. |
| Information des personnes — art. 12-14                             | Pas de notice complète ni de preuve de remise aux personnes dans le périmètre consulté.                                                                                                                                              |
| Droits — art. 15-22                                                | Un assuré peut consulter son historique dans l'application ; le dépôt mentionne des comptes et une fonctionnalité de gestion de compte.                                                                                              |
| Décision automatisée — art. 22                                   | Le code permet une décision humaine des alertes et indique « aucune décision automatique » dans la documentation.                                                                                                                    |
| Analyse d'impact (AIPD) — art. 35                                  | Aucune AIPD validée n'est présente dans le périmètre examiné. Santé, scoring systématique et effets possibles sur des remboursements indiquent un risque à analyser.                                                             |
| Registre — art. 30                                                 | Le README mentionne un registre à réaliser.                                                                                                                                                                                            |
| Sous-traitance / transferts — art. 28, 44-49                       | Services LLM, e-mail, notifications, BI et stockage sont des flux potentiels selon configuration.                                                                                                                                        |
| Violation de données — art. 33-34                                 | Aucune procédure ni preuve d'exercice n'a été identifiée dans les sources examinées.                                                                                                                                                |
| Responsabilité démontrable — art. 5(2), 24                       | Tests techniques existent et des rapports de phases documentent certaines validations.                                                                                                                                                   |

### 2.1 Mesures techniques positives observées

- Les identités d'utilisateurs peuvent être stockées séparément dans `utilisateurs_identites` sous forme chiffrée ; le service de déchiffrement limite les champs renvoyés dans le parcours d'alerte.
- Le déchiffrement de l'identité d'un assuré est réservé à un administrateur dans la route consultée et l'accès est audité sans inscrire les valeurs déchiffrées.
- Le chat chiffre le contenu, les titres et les sources persistés, et son service supprime l'historique au-delà de 180 jours.
- L'assistant utilise un rôle de base de données en lecture seule et son code limite le périmètre par utilisateur.
- Les décisions de gestionnaire, prédictions, versions de modèle et certains accès sensibles sont journalisés.

Ces mesures doivent être vérifiées sur les migrations effectivement appliquées, les privilèges effectifs, les sauvegardes, la configuration et les logs de l'environnement déployé. Le chiffrement n'annule ni les obligations légales ni le besoin de limiter les accès.

## 3. Grille d'évaluation EU AI Act

Référence : règlement (UE) 2024/1689. Cette grille est une analyse de préparation documentaire, pas une détermination formelle du statut de fournisseur ou de déployeur.

### 3.1 Qualification préalable du système

Le système analyse des factures de santé et produit des alertes de suspicion de fraude, lesquelles peuvent influencer l'instruction et le paiement d'un remboursement. L'annexe III, point 5(c), vise notamment certains systèmes d'évaluation des risques et de tarification en assurance vie et santé. Le seul fait de détecter une fraude dans une facture ne permet pas de conclure automatiquement que ce point s'applique ; il faut analyser la finalité prévue, le rôle exact du score dans la décision, les populations concernées et les effets.

Cette analyse doit aussi examiner l'article 6(3) et sa réserve pour les systèmes de l'annexe III qui effectuent du profilage de personnes physiques, ainsi que l'article 2 (champ territorial), l'article 3 (définitions) et le rôle de chaque organisation comme fournisseur, déployeur, importateur ou distributeur. L'utilisation de caractéristiques bénéficiaire et d'historique peut rendre l'analyse de profilage particulièrement pertinente. **En attendant cette qualification écrite, ne pas annoncer que l'application est juridiquement « système à haut risque » ou, à l'inverse, exemptée.**

### 3.2 Grille de préparation

| Exigence / référence                                                        | Éléments observés                                                                                                                                                         |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Champ, finalité prévue et classification — art. 2, 3, 6, annexe III        | Finalité de détection d'anomalies de factures et assistance au remboursement ; possibilité de conséquences financières.                                                 |
| Gestion des risques — art. 9                                                 | Des validations, contrôles métier, seuils et règles de disponibilité existent ; aucune gestion des risques AI Act intégrée sur tout le cycle de vie n'est documentée. |
| Gouvernance des données — art. 10                                           | Données décrites comme synthétiques ; séparation temporelle train/validation/test ; contrôles de fuite de variables décrits dans le code.                              |
| Documentation technique — art. 11 et annexe IV                               | Métadonnées de modèle, schéma, métriques, versions et rapports techniques présents.                                                                                    |
| Journalisation — art. 12                                                     | Prédiction, score, seuil, modèle/version, décision et accès identité peuvent être enregistrés ; le journal est conçu en ajout seul dans les migrations consultées.  |
| Transparence / instructions — art. 13                                        | SHAP et codes de règles sont disponibles pour les gestionnaires ; la réponse au prestataire ne révèle pas son score.                                                     |
| Contrôle humain — art. 14, art. 26 selon statut                             | Le gestionnaire peut confirmer, rejeter comme faux positif ou escalader ; décisions enregistrées avec commentaire possible.                                                |
| Exactitude, robustesse et cybersécurité — art. 15                          | Versionnement, contrôle de hash, smoke test, seuil configurable, SHAP, mécanismes de dérive et tests sont documentés.                                                    |
| Système de qualité et gouvernance — art. 17                                | Plusieurs processus de modèle existent, mais le système de management qualité réglementaire n'est pas démontré.                                                        |
| Évaluation de conformité, déclaration et enregistrement — art. 43, 47, 49 | Pas de déclaration UE, certificat ni enregistrement identifié.                                                                                                             |
| Obligations du déployeur — art. 26                                          | Une interface de décision gestionnaire et un journal sont implémentés.                                                                                                    |
| Évaluation d'impact droits fondamentaux — art. 27                           | Un flux santé avec scoring et effets financiers potentiels peut soulever un impact important.                                                                               |
| Surveillance après mise en service — art. 72-73 et art. 26 selon rôle      | Dérive et historique de versions existent en partie ; procédure de surveillance et de signalement non établie.                                                            |
| Compétence en IA — art. 4                                                   | Aucun programme formel de compétence IA identifié.                                                                                                                         |
| Interactions avec une IA — art. 50, selon l'usage                            | L'assistant conversationnel répond aux assurés et professionnels ; les sources sont affichées.                                                                            |

### 3.3 Données d'évaluation disponibles

Le modèle actif rapporte une séparation temporelle train/validation/test et, sur le jeu documenté, les résultats globaux suivants :

| Mesure                                                    | Test, seuil du modèle 0,9999 | Test, seuil de référence 0,8 |
| --------------------------------------------------------- | ----------------------------: | -----------------------------: |
| PR-AUC                                                    |                        0,9988 |                   non indiqué |
| ROC-AUC                                                   |                        0,9997 |                   non indiqué |
| Rappel                                                    |                        0,9469 |                         0,9848 |
| Précision                                                |                        0,9993 |                         0,9937 |
| Alertes / vrais positifs / faux positifs / faux négatifs |        1 373 / 1 372 / 1 / 77 |         1 436 / 1 427 / 9 / 22 |

Ces chiffres sont ceux du `metrics.json` et ne sont **pas** des résultats de production ni des mesures d'équité. Ils reposent sur les labels et données du projet, dont le caractère synthétique est revendiqué par sa documentation. Une précision ou un rappel élevés sur des données synthétiques ne démontrent pas que les libellés, les distributions ou les erreurs correspondent au monde réel.

## 4. Audit d'équité du modèle

### 4.1 Conclusion de l'audit disponible

**Conclusion : équité non démontrée ; audit par groupes non exécuté.** Les artefacts disponibles donnent des métriques globales et par type de fraude, mais aucune comparaison par groupe protégé ou pertinent. L'exécution demandée n'a pas pu produire les prédictions et agrégats par groupe : l'accès au socket Docker est refusé pour l'utilisateur courant et l'environnement Python local ne dispose pas des dépendances ML. Il n'est donc pas possible d'affirmer que le modèle est équitable, ni de quantifier un écart entre les groupes.

### 4.2 Résultats effectivement présents

Le rapport phase 5b compare des règles métier à des labels de fraude. Ces résultats ne sont ni des métriques de parité entre groupes, ni une validation de la décision du modèle.

| Règle                | Déclenchements | Labels | Intersection |    Rappel | Précision |
| --------------------- | --------------: | -----: | -----------: | --------: | ---------: |
| SURFACTURATION        |           2 202 |  1 272 |          835 |  65,645 % |   37,920 % |
| QUANTITE_EXCESSIVE    |             563 |    568 |          563 |  99,120 % |  100,000 % |
| UPCODING              |             955 |    742 |            0 |   0,000 % |    0,000 % |
| LIGNES_NON_PRESCRITES |           1 276 |    733 |          733 | 100,000 % |   57,445 % |
| SUBSTITUTION_PRODUIT  |               0 |    368 |            0 |   0,000 % |    0,000 % |
| ORDONNANCE_EXPIREE    |             594 |    502 |          502 | 100,000 % |   84,512 % |
| SOINS_JOUR_FERME      |             474 |    227 |          227 | 100,000 % |   47,890 % |
| DOUBLON               |             553 |    909 |          553 |  60,836 % |  100,000 % |
| FRACTIONNEMENT        |           2 125 |    340 |          197 |  57,941 % |    9,271 % |
| SURCONSOMMATION       |           1 430 |    469 |          469 | 100,000 % |   32,797 % |
| ACTE_FICTIF           |             863 |    496 |          239 |  48,186 % |   27,694 % |
| INCOHERENCE_PROFIL    |             382 |    379 |          379 | 100,000 % |   99,215 % |
| PRESTATAIRE_RADIE     |             157 |    147 |          147 | 100,000 % |   93,631 % |
| HORS_COUVERTURE       |             376 |    195 |          195 | 100,000 % |   51,862 % |

Les écarts explicitement décrits entre règles et labels (notamment `UPCODING` et `SUBSTITUTION_PRODUIT`) montrent aussi que la qualité du label et l'alignement entre définition métier et cible doivent être examinés avant d'interpréter les résultats. Certains groupes ou types de fraude peuvent avoir des effectifs insuffisants ; un résultat à zéro ne signifie pas absence de risque.

### 4.3 Variables et risques d'écarts à tester

| Dimension                     | Indice observé                                                                                                                                                   | Risque à contrôler                                                                                                                                                                                                         |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Âge                          | `age_assure` fait partie du schéma de features ; `l_n_viol_age` est calculée à partir des actes.                                                           | Écarts de taux d'alerte, de faux positifs/négatifs et d'accès au remboursement entre classes d'âge ; effets spécifiques pour les enfants.                                                                               |
| Sexe                          | Le sexe brut est utilisé dans la construction de `l_n_viol_sexe`, qui appartient au schéma de features.                                                       | Le modèle peut utiliser indirectement une caractéristique liée au sexe, même sans champ brut. Vérifier la justification clinique/légale, les erreurs par sexe et les cas où le référentiel d'actes est incomplet.   |
| Rang bénéficiaire / formule | `rang_beneficiaire` et `formule` sont des variables catégorielles.                                                                                           | Différences de couverture ou de population pouvant agir comme proxy socio-économique ou familial ; comparer les erreurs sans confondre différence de risque réel et discrimination.                                      |
| Région / géographie         | Pas d'attribut régional explicite repéré dans le schéma consulté ; certaines identités ou données prestataire peuvent en contenir dans les tables sources. | Vérifier les variables dérivées, les codes prestataires et les effets géographiques ; les résultats par région sont demandés dans le README mais absents des rapports de métriques.                                  |
| Prestataire et spécialité   | Type, spécialité, niveau tarifaire et historique prestataire sont représentés.                                                                                | Le modèle évalue aussi des structures de soins. Vérifier taux d'alerte et faux positifs par type, spécialité, taille et localisation d'établissement ; prévoir une revue distincte des effets sur les professionnels. |
| Intersections                 | Aucune table croisant plusieurs dimensions n'a été trouvée.                                                                                                    | Les écarts âge × sexe × région/type de prestataire peuvent être masqués par les moyennes marginales.                                                                                                                  |

**Formules utilisées pour le tableau de résultats (section 4.5).** Les calculs sont effectués séparément dans chaque groupe `g`, au niveau facture. Pour une facture `i`, `y_i ∈ {0,1}` est le label (`1` = fraude selon le label du jeu), `p_i` sa probabilité calibrée, `t` le seuil de décision et `d_i = 1[p_i ≥ t]` la prédiction d'alerte. `N_g` désigne le nombre de factures du groupe.

- `TP = Σ_i d_i y_i` ; `FP = Σ_i d_i (1-y_i)` ; `FN = Σ_i (1-d_i)y_i` ; `TN = Σ_i (1-d_i)(1-y_i)`.
- Prévalence du label : `(TP + FN) / N_g`. Taux d'alerte : `(TP + FP) / N_g`.
- Rappel / TPR : `TP / (TP + FN)`. FPR : `FP / (FP + TN)`. Précision / PPV : `TP / (TP + FP)`.
- Score de Brier : `Brier_g = (1 / N_g) Σ_i (p_i - y_i)^2`.

Les IC à 95 % de prévalence et de taux d'alerte sont des intervalles de Wilson pour une proportion `x/n`, avec `z = 1,96`, `p̂ = x/n`, centre `c = (p̂ + z²/(2n)) / (1 + z²/n)` et demi-largeur `h = z × sqrt(p̂(1-p̂)/n + z²/(4n²)) / (1 + z²/n)` ; les bornes sont `max(0, c-h)` et `min(1, c+h)`. Pour la FPR, `x=FP` et `n=FP+TN` ; pour la précision, `x=TP` et `n=TP+FP`. Les IC de rappel et de Brier sont les quantiles 2,5 % et 97,5 % de 2 000 réplications bootstrap en grappes : assurés pour les groupes d'assurés et prestataires pour les groupes de prestataires, avec remise et graine `20261029`. Au niveau agrégé, la grappe est l'assuré. Pour les cellules sans dénominateur pertinent, la mesure est `n.c.` ; les IC binomiaux restent calculés au niveau facture et ne corrigent pas la dépendance intra-grappe.

### 4.5 Tableau de résultats d'audit d'équité — état des mesures

Les résultats ci-dessous remplissent les mesures calculables sur le jeu de test synthétique ci-dessus ; ils ne valent pas validation d'équité en production ni validation juridique des attributs de groupe. Dans les cellules, les IC sont à 95 % ; `n.c.` signifie que le dénominateur est nul. Les lignes de spécialité dont l'effectif total est inférieur à 30 sont regroupées et masquées.

| Groupe                                        |      N | Labels positifs / prévalence (IC Wilson) | Alertes / taux d'alerte (IC Wilson) |       TP / FP / FN / TN | Rappel / TPR (IC 95 %)     | FPR (IC Wilson)             | Précision / PPV (IC Wilson) | Brier (IC bootstrap)       |
| --------------------------------------------- | -----: | ----------------------------------------- | ----------------------------------- | ----------------------: | -------------------------- | --------------------------- | ---------------------------- | -------------------------- |
| Ensemble — seuil actif `0,9999`            | 16 922 | 1 449 / 8,56 % (8,15–8,99 %)             | 1 373 / 8,11 % (7,71–8,53 %)       | 1 372 / 1 / 77 / 15 472 | 94,69 % (93,50–95,81 %)   | 0,0065 % (0,0011–0,0366 %) | 99,93 % (99,59–99,99 %)     | 0,00142 (0,00091–0,00198) |
| Sexe — F                                     |  8 522 | 740 / 8,68 % (8,10–9,30 %)               | 705 / 8,27 % (7,71–8,88 %)         |    704 / 1 / 36 / 7 781 | 95,14 % (93,47–96,74 %)   | 0,01 % (0,00–0,07 %)       | 99,86 % (99,20–99,97 %)     | 0,00132 (0,00072–0,00205) |
| Sexe — M                                     |  8 400 | 709 / 8,44 % (7,86–9,05 %)               | 668 / 7,95 % (7,39–8,55 %)         |    668 / 0 / 41 / 7 691 | 94,22 % (92,43–95,83 %)   | 0,00 % (0,00–0,05 %)       | 100,00 % (99,43–100,00 %)   | 0,00152 (0,00077–0,00235) |
| Âge — `<18`                               |  5 747 | 538 / 9,36 % (8,64–10,14 %)              | 494 / 8,60 % (7,90–9,35 %)         |    494 / 0 / 44 / 5 209 | 91,82 % (89,39–94,02 %)   | 0,00 % (0,00–0,07 %)       | 100,00 % (99,23–100,00 %)   | 0,00160 (0,00081–0,00257) |
| Âge — `18-29`                             |  1 549 | 148 / 9,55 % (8,19–11,12 %)              | 140 / 9,04 % (7,71–10,57 %)        |     140 / 0 / 8 / 1 401 | 94,59 % (90,67–97,93 %)   | 0,00 % (0,00–0,27 %)       | 100,00 % (97,33–100,00 %)   | 0,00100 (0,00004–0,00266) |
| Âge — `30-44`                             |  2 838 | 251 / 8,84 % (7,85–9,95 %)               | 245 / 8,63 % (7,65–9,72 %)         |     244 / 1 / 7 / 2 586 | 97,21 % (95,07–99,12 %)   | 0,04 % (0,01–0,22 %)       | 99,59 % (97,72–99,93 %)     | 0,00144 (0,00035–0,00293) |
| Âge — `45-59`                             |  4 883 | 364 / 7,45 % (6,75–8,23 %)               | 349 / 7,15 % (6,46–7,90 %)         |    349 / 0 / 15 / 4 519 | 95,88 % (93,60–97,89 %)   | 0,00 % (0,00–0,08 %)       | 100,00 % (98,91–100,00 %)   | 0,00126 (0,00041–0,00227) |
| Âge — `60+`                               |  1 905 | 148 / 7,77 % (6,65–9,06 %)               | 145 / 7,61 % (6,50–8,89 %)         |     145 / 0 / 3 / 1 757 | 97,97 % (95,27–100,00 %)  | 0,00 % (0,00–0,22 %)       | 100,00 % (97,42–100,00 %)   | 0,00158 (0,00001–0,00367) |
| Ville de l'assuré — Antananarivo            | 12 043 | 1 031 / 8,56 % (8,07–9,07 %)             | 981 / 8,15 % (7,67–8,65 %)         |   981 / 0 / 50 / 11 012 | 95,15 % (93,86–96,48 %)   | 0,00 % (0,00–0,03 %)       | 100,00 % (99,61–100,00 %)   | 0,00104 (0,00057–0,00161) |
| Ville de l'assuré — Antsirabe               |  1 109 | 62 / 5,59 % (4,39–7,10 %)                | 59 / 5,32 % (4,15–6,80 %)          |      59 / 0 / 3 / 1 047 | 95,16 % (89,47–100,00 %)  | 0,00 % (0,00–0,37 %)       | 100,00 % (93,89–100,00 %)   | 0,00008 (0,00000–0,00024) |
| Ville de l'assuré — Antsiranana             |    223 | 18 / 8,07 % (5,17–12,40 %)               | 17 / 7,62 % (4,81–11,87 %)         |        17 / 0 / 1 / 205 | 94,44 % (74,24–99,01 %)   | 0,00 % (0,00–1,84 %)       | 100,00 % (81,57–100,00 %)   | 0,00148 (0,00000–0,00480) |
| Ville de l'assuré — Fianarantsoa            |    732 | 74 / 10,11 % (8,13–12,51 %)              | 72 / 9,84 % (7,88–12,21 %)         |        72 / 0 / 2 / 658 | 97,30 % (93,06–100,00 %)  | 0,00 % (0,00–0,58 %)       | 100,00 % (94,93–100,00 %)   | 0,00011 (0,00000–0,00027) |
| Ville de l'assuré — Mahajanga               |    843 | 74 / 8,78 % (7,05–10,88 %)               | 68 / 8,07 % (6,41–10,10 %)         |        67 / 1 / 7 / 768 | 90,54 % (82,61–96,55 %)   | 0,13 % (0,02–0,73 %)       | 98,53 % (92,13–99,74 %)     | 0,00912 (0,00412–0,01560) |
| Ville de l'assuré — Toamasina               |  1 420 | 151 / 10,63 % (9,14–12,34 %)             | 139 / 9,79 % (8,35–11,44 %)        |    139 / 0 / 12 / 1 269 | 92,05 % (87,50–96,36 %)   | 0,00 % (0,00–0,30 %)       | 100,00 % (97,31–100,00 %)   | 0,00072 (0,00001–0,00215) |
| Ville de l'assuré — Toliara                 |    552 | 39 / 7,07 % (5,21–9,51 %)                | 37 / 6,70 % (4,90–9,10 %)          |        37 / 0 / 2 / 513 | 94,87 % (86,95–100,00 %)  | 0,00 % (0,00–0,74 %)       | 100,00 % (90,59–100,00 %)   | 0,00406 (0,00000–0,00966) |
| Rang bénéficiaire — assuré principal      |  6 544 | 531 / 8,11 % (7,48–8,80 %)               | 517 / 7,90 % (7,27–8,58 %)         |    516 / 1 / 15 / 6 012 | 97,18 % (95,64–98,50 %)   | 0,02 % (0,00–0,09 %)       | 99,81 % (98,91–99,97 %)     | 0,00158 (0,00073–0,00250) |
| Rang bénéficiaire — conjoint               |  3 788 | 304 / 8,03 % (7,20–8,93 %)               | 292 / 7,71 % (6,90–8,60 %)         |    292 / 0 / 12 / 3 484 | 96,05 % (93,58–98,27 %)   | 0,00 % (0,00–0,11 %)       | 100,00 % (98,70–100,00 %)   | 0,00087 (0,00008–0,00189) |
| Rang bénéficiaire — enfant                 |  6 590 | 614 / 9,32 % (8,64–10,04 %)              | 564 / 8,56 % (7,91–9,26 %)         |    564 / 0 / 50 / 5 976 | 91,86 % (89,69–94,08 %)   | 0,00 % (0,00–0,06 %)       | 100,00 % (99,32–100,00 %)   | 0,00157 (0,00084–0,00241) |
| Formule — CONFORT                            |  3 620 | 311 / 8,59 % (7,72–9,55 %)               | 298 / 8,23 % (7,38–9,17 %)         |    298 / 0 / 13 / 3 309 | 95,82 % (93,50–97,86 %)   | 0,00 % (0,00–0,12 %)       | 100,00 % (98,73–100,00 %)   | 0,00053 (0,00001–0,00130) |
| Formule — ESSENTIEL                          |  9 373 | 843 / 8,99 % (8,43–9,59 %)               | 792 / 8,45 % (7,90–9,03 %)         |    792 / 0 / 51 / 8 530 | 93,95 % (92,34–95,54 %)   | 0,00 % (0,00–0,05 %)       | 100,00 % (99,52–100,00 %)   | 0,00171 (0,00101–0,00249) |
| Formule — PREMIUM                            |  3 929 | 295 / 7,51 % (6,73–8,37 %)               | 283 / 7,20 % (6,44–8,05 %)         |    282 / 1 / 13 / 3 633 | 95,59 % (92,83–97,77 %)   | 0,03 % (0,00–0,16 %)       | 99,65 % (98,03–99,94 %)     | 0,00153 (0,00055–0,00278) |
| Type prestataire — CABINET_DENTAIRE          |    363 | 60 / 16,53 % (13,06–20,70 %)             | 45 / 12,40 % (9,40–16,19 %)        |       45 / 0 / 15 / 303 | 75,00 % (66,07–96,67 %)   | 0,00 % (0,00–1,25 %)       | 100,00 % (92,13–100,00 %)   | 0,02807 (0,00000–0,07278) |
| Type prestataire — CABINET_GENERALISTE       |  4 154 | 266 / 6,40 % (5,70–7,19 %)               | 263 / 6,33 % (5,63–7,11 %)         |     263 / 0 / 3 / 3 888 | 98,87 % (97,32–100,00 %)  | 0,00 % (0,00–0,10 %)       | 100,00 % (98,56–100,00 %)   | 0,00086 (0,00014–0,00180) |
| Type prestataire — CABINET_KINE              |     32 | 6 / 18,75 % (8,89–35,31 %)               | 6 / 18,75 % (8,89–35,31 %)         |          6 / 0 / 0 / 26 | 100,00 % (60,97–100,00 %) | 0,00 % (0,00–12,87 %)      | 100,00 % (60,97–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Type prestataire — CABINET_SPECIALISTE       |    947 | 48 / 5,07 % (3,84–6,66 %)                | 40 / 4,22 % (3,12–5,70 %)          |        40 / 0 / 8 / 899 | 83,33 % (71,25–100,00 %)  | 0,00 % (0,00–0,43 %)       | 100,00 % (91,24–100,00 %)   | 0,00028 (0,00000–0,00104) |
| Type prestataire — CENTRE_IMAGERIE           |    351 | 37 / 10,54 % (7,74–14,19 %)              | 32 / 9,12 % (6,53–12,59 %)         |        32 / 0 / 5 / 314 | 86,49 % (77,08–100,00 %)  | 0,00 % (0,00–1,21 %)       | 100,00 % (89,28–100,00 %)   | 0,00288 (0,00000–0,00886) |
| Type prestataire — CLINIQUE                  |  3 233 | 331 / 10,24 % (9,24–11,33 %)             | 293 / 9,06 % (8,12–10,10 %)        |    293 / 0 / 38 / 2 902 | 88,52 % (81,42–92,52 %)   | 0,00 % (0,00–0,13 %)       | 100,00 % (98,71–100,00 %)   | 0,00155 (0,00015–0,00336) |
| Type prestataire — LABORATOIRE               |  1 191 | 93 / 7,81 % (6,42–9,47 %)                | 90 / 7,56 % (6,19–9,20 %)          |      90 / 0 / 3 / 1 098 | 96,77 % (93,59–100,00 %)  | 0,00 % (0,00–0,35 %)       | 100,00 % (95,91–100,00 %)   | 0,00009 (0,00000–0,00031) |
| Type prestataire — MATERNITE                 |     38 | 2 / 5,26 % (1,46–17,29 %)                | 2 / 5,26 % (1,46–17,29 %)          |          2 / 0 / 0 / 36 | 100,00 % (34,24–100,00 %) | 0,00 % (0,00–9,64 %)       | 100,00 % (34,24–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Type prestataire — OPTICIEN                  |    142 | 19 / 13,38 % (8,74–19,95 %)              | 19 / 13,38 % (8,74–19,95 %)        |        19 / 0 / 0 / 123 | 100,00 % (83,18–100,00 %) | 0,00 % (0,00–3,03 %)       | 100,00 % (83,18–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Type prestataire — PHARMACIE                 |  6 471 | 587 / 9,07 % (8,40–9,80 %)               | 583 / 9,01 % (8,34–9,73 %)         |     582 / 1 / 5 / 5 883 | 99,15 % (98,23–99,83 %)   | 0,02 % (0,00–0,10 %)       | 99,83 % (99,03–99,97 %)     | 0,00059 (0,00009–0,00125) |
| Spécialité — CARDIOLOGIE                   |    114 | 3 / 2,63 % (0,90–7,45 %)                 | 3 / 2,63 % (0,90–7,45 %)           |         3 / 0 / 0 / 111 | 100,00 % (43,85–100,00 %) | 0,00 % (0,00–3,35 %)       | 100,00 % (43,85–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Spécialité — DERMATOLOGIE                  |     34 | 7 / 20,59 % (10,35–36,80 %)              | 6 / 17,65 % (8,35–33,51 %)         |          6 / 0 / 1 / 27 | 85,71 % (48,69–97,43 %)   | 0,00 % (0,00–12,46 %)      | 100,00 % (60,97–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Spécialité — ENDOCRINOLOGIE                |     35 | 0 / 0,00 % (0,00–9,89 %)                 | 0 / 0,00 % (0,00–9,89 %)           |          0 / 0 / 0 / 35 | n.c. (aucun positif)       | 0,00 % (0,00–9,89 %)       | n.c.                         | 0,00000 (0,00000–0,00000) |
| Spécialité — GASTRO-ENTEROLOGIE            |     91 | 2 / 2,20 % (0,60–7,66 %)                 | 2 / 2,20 % (0,60–7,66 %)           |          2 / 0 / 0 / 89 | 100,00 % (34,24–100,00 %) | 0,00 % (0,00–4,14 %)       | 100,00 % (34,24–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Spécialité — NEUROLOGIE                    |     38 | 0 / 0,00 % (0,00–9,18 %)                 | 0 / 0,00 % (0,00–9,18 %)           |          0 / 0 / 0 / 38 | n.c. (aucun positif)       | 0,00 % (0,00–9,18 %)       | n.c.                         | 0,00000 (0,00000–0,00000) |
| Spécialité — ORL                           |     38 | 0 / 0,00 % (0,00–9,18 %)                 | 0 / 0,00 % (0,00–9,18 %)           |          0 / 0 / 0 / 38 | n.c. (aucun positif)       | 0,00 % (0,00–9,18 %)       | n.c.                         | 0,00000 (0,00000–0,00000) |
| Spécialité — PEDIATRIE                     |    241 | 24 / 9,96 % (6,78–14,39 %)               | 17 / 7,05 % (4,45–11,01 %)         |        17 / 0 / 7 / 217 | 70,83 % (50,83–85,09 %)   | 0,00 % (0,00–1,74 %)       | 100,00 % (81,57–100,00 %)   | 0,00109 (0,00000–0,01463) |
| Spécialité — PNEUMOLOGIE                   |    208 | 7 / 3,37 % (1,64–6,78 %)                 | 7 / 3,37 % (1,64–6,78 %)           |         7 / 0 / 0 / 201 | 100,00 % (64,57–100,00 %) | 0,00 % (0,00–1,88 %)       | 100,00 % (64,57–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Spécialité — RHUMATOLOGIE                  |     42 | 0 / 0,00 % (0,00–8,38 %)                 | 0 / 0,00 % (0,00–8,38 %)           |          0 / 0 / 0 / 42 | n.c. (aucun positif)       | 0,00 % (0,00–8,38 %)       | n.c.                         | 0,00000 (0,00000–0,00000) |
| Spécialité — sans spécialité renseignée | 15 975 | 1 401 / 8,77 % (8,34–9,22 %)             | 1 333 / 8,34 % (7,93–8,78 %)       | 1 332 / 1 / 69 / 14 573 | 95,07 % (92,83–97,12 %)   | 0,01 % (0,00–0,04 %)       | 99,92 % (99,58–99,99 %)     | 0,00149 (0,00055–0,00293) |
| Spécialité — TRAUMATO-ORTHOPEDIE           |     38 | 2 / 5,26 % (1,46–17,29 %)                | 2 / 5,26 % (1,46–17,29 %)          |          2 / 0 / 0 / 36 | 100,00 % (34,24–100,00 %) | 0,00 % (0,00–9,64 %)       | 100,00 % (34,24–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Spécialité — UROLOGIE                      |     34 | 1 / 2,94 % (0,52–14,92 %)                | 1 / 2,94 % (0,52–14,92 %)          |          1 / 0 / 0 / 33 | 100,00 % (20,65–100,00 %) | 0,00 % (0,00–10,43 %)      | 100,00 % (20,65–100,00 %)   | 0,00000 (0,00000–0,00000) |
| Intersection âge × sexe — `18-29` / F    |    777 | 82 / 10,55 % (8,58–12,91 %)              | 78 / 10,04 % (8,12–12,35 %)        |        78 / 0 / 4 / 695 | 95,12 % (89,71–98,85 %)   | 0,00 % (0,00–0,55 %)       | 100,00 % (95,31–100,00 %)   | 0,00185 (0,00000–0,00499) |
| Intersection âge × sexe — `18-29` / M    |    772 | 66 / 8,55 % (6,78–10,73 %)               | 62 / 8,03 % (6,32–10,16 %)         |        62 / 0 / 4 / 706 | 93,94 % (88,13–98,59 %)   | 0,00 % (0,00–0,54 %)       | 100,00 % (94,17–100,00 %)   | 0,00015 (0,00000–0,00042) |
| Intersection âge × sexe — `30-44` / F    |  1 449 | 125 / 8,63 % (7,29–10,18 %)              | 123 / 8,49 % (7,16–10,04 %)        |     122 / 1 / 3 / 1 323 | 97,60 % (94,53–100,00 %)  | 0,08 % (0,01–0,43 %)       | 99,19 % (95,54–99,86 %)     | 0,00129 (0,00000–0,00338) |
| Intersection âge × sexe — `30-44` / M    |  1 389 | 126 / 9,07 % (7,67–10,70 %)              | 122 / 8,78 % (7,41–10,39 %)        |     122 / 0 / 4 / 1 263 | 96,83 % (93,48–99,29 %)   | 0,00 % (0,00–0,30 %)       | 100,00 % (96,95–100,00 %)   | 0,00160 (0,00005–0,00387) |
| Intersection âge × sexe — `45-59` / F    |  2 427 | 170 / 7,00 % (6,06–8,09 %)               | 163 / 6,72 % (5,79–7,78 %)         |     163 / 0 / 7 / 2 257 | 95,88 % (92,36–98,84 %)   | 0,00 % (0,00–0,17 %)       | 100,00 % (97,70–100,00 %)   | 0,00092 (0,00002–0,00218) |
| Intersection âge × sexe — `45-59` / M    |  2 456 | 194 / 7,90 % (6,90–9,03 %)               | 186 / 7,57 % (6,59–8,69 %)         |     186 / 0 / 8 / 2 262 | 95,88 % (92,86–98,48 %)   | 0,00 % (0,00–0,17 %)       | 100,00 % (97,98–100,00 %)   | 0,00159 (0,00038–0,00334) |
| Intersection âge × sexe — `60+` / F      |    928 | 81 / 8,73 % (7,08–10,72 %)               | 80 / 8,62 % (6,98–10,60 %)         |        80 / 0 / 1 / 847 | 98,77 % (95,83–100,00 %)  | 0,00 % (0,00–0,45 %)       | 100,00 % (95,42–100,00 %)   | 0,00107 (0,00000–0,00348) |
| Intersection âge × sexe — `60+` / M      |    977 | 67 / 6,86 % (5,44–8,62 %)                | 65 / 6,65 % (5,25–8,39 %)          |        65 / 0 / 2 / 910 | 97,01 % (92,21–100,00 %)  | 0,00 % (0,00–0,42 %)       | 100,00 % (94,42–100,00 %)   | 0,00206 (0,00000–0,00550) |
| Intersection âge × sexe — `<18` / F      |  2 941 | 282 / 9,59 % (8,58–10,71 %)              | 261 / 8,87 % (7,90–9,96 %)         |    261 / 0 / 21 / 2 659 | 92,55 % (89,60–95,56 %)   | 0,00 % (0,00–0,14 %)       | 100,00 % (98,55–100,00 %)   | 0,00160 (0,00051–0,00291) |
| Intersection âge × sexe — `<18` / M      |  2 806 | 256 / 9,12 % (8,11–10,25 %)              | 233 / 8,30 % (7,34–9,38 %)         |    233 / 0 / 23 / 2 550 | 91,02 % (87,55–94,14 %)   | 0,00 % (0,00–0,15 %)       | 100,00 % (98,38–100,00 %)   | 0,00160 (0,00050–0,00311) |

Au seuil comparatif `0,8`, les comptes globaux sont TP 1 427, FP 9, FN 22, TN 15 464, soit 1 436 alertes, un rappel de **98,48 %**, une FPR de **0,058 %** et une précision de **99,37 %**. Les plages descriptives par dimension (cellules de moins de 30 factures exclues) sont :

| Dimension                 | Rappel / TPR (min–max des groupes) | Taux d'alerte (min–max) | FPR maximale observée |
| ------------------------- | ----------------------------------: | -----------------------: | ---------------------: |
| Sexe                      |                      98,38–98,59 % |             8,36–8,61 % |                0,077 % |
| Âge                      |                      97,77–99,32 % |             7,43–9,36 % |                0,114 % |
| Ville de l'assuré        |                     94,87–100,00 % |            5,50–10,70 % |                0,650 % |
| Rang bénéficiaire       |                      97,72–99,06 % |             7,95–9,14 % |                0,116 % |
| Formule                   |                     97,97–100,00 % |             7,43–8,87 % |                0,083 % |
| Type prestataire          |                     86,67–100,00 % |            4,86–18,75 % |                1,650 % |
| Spécialité              |                     91,67–100,00 % |            0,00–20,59 % |                0,062 % |
| Intersection âge × sexe |                     96,81–100,00 % |            6,86–10,30 % |                0,151 % |

**État et action.** Les écarts observés sont descriptifs, notamment les rappels plus faibles pour certains groupes d'âge et types/spécialités de prestataires ; ils justifient une revue métier et des labels, sans permettre d'attribuer une cause ni de conclure à une discrimination ou à son absence. Le taux de contestation/annulation, les décisions gestionnaires et les délais de revue restent **non disponibles**. Avant toute conclusion ou usage en production, faire valider les labels et l'usage des attributs, examiner les groupes à rappel faible et les cellules peu documentées, tester l'ablation sur une procédure distincte autorisée, et répéter l'audit sur des données de production gouvernées.
