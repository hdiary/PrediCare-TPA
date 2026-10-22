# Analyse FinOps PrediCare TPA (Madagascar)

> **Hypothèses de cohérence retenues pour cette version** (à valider) :
>
> - Gestionnaire : **temps plein, 1 500 000 Ar/mois** (le « 2 j/mois » est abandonné car incompatible avec 1 000 alertes/mois).
> - Ingénieur MLOps : **temps partiel, 1 200 000 Ar/mois**.
> - GPU : **RTX 3090 24 GB** (occasion) — cohérent avec Qwen3 4B + bge-m3.
> - CAPEX serveur : **7 000 000 Ar** (milieu de fourchette 6,5–7,5 M), amorti sur 24 mois = **291 667 Ar/mois**.
> - Taux de change : **4 548 Ar/USD** (donneesmondiales.com, 20/10/2026).
> - Provision pour aléas : **10 % des OPEX** (cf. tableau initial).
> - Frais de change/paiement : **5 %** sur les postes libellés en USD.

---

# 1. Contexte & Hypothèses (Adaptation Madagascar)


### Détail du CAPEX serveur

| Poste                                                      | Estimation                                      | Source / logique                                |
| :--------------------------------------------------------- | :---------------------------------------------- | :---------------------------------------------- |
| RTX 3090 24 GB (occasion)                                  | ~1 149 $ (~5 226 000 Ar à 4 548 Ar/USD)        | eBay                                            |
| Éléments serveur (CPU, RAM, SSD, alimentation, châssis) | ~1 500 000 – 2 000 000 Ar                      | Prix du marché local                           |
| **Total CAPEX**                                      | **~6,5 à 7,5 millions Ar** (réf. 7,0 M) | Amorti sur 24 mois ≈ **291 667 Ar/mois** |

---

# 2. Analyse TCO (Total Cost of Ownership)

Tableau FinOps détaillé (mensuel)

| Poste de coût                                            | Type  |    Coût mensuel (Ariary) | Détail                                                      |
| :-------------------------------------------------------- | :---- | ------------------------: | :----------------------------------------------------------- |
| **Serveur GPU (amorti sur 24 mois)**                | CAPEX |         **291 667** | 7 000 000 / 24                                               |
| **Électricité (Jirama + onduleur)**               | OPEX  |         **250 000** | Serveur 24/7 (≈ 500 W)                                      |
| **Connexion Internet (fibre pro)**                  | OPEX  |         **300 000** | Indispensable pour l'API et Metabase                         |
| **Ingénieur MLOps (temps partiel)**                | OPEX  |       **1 200 000** | Maintenance, mise à jour du modèle                         |
| **Gestionnaire (temps plein)**                      | OPEX  |       **1 500 000** | Traitement des alertes (Human-in-the-loop)                   |
| **Coût API LLM (Ollama)**                          | OPEX  |               **0** | Avantage du local                                            |
| **Hébergement BDD / Backup cloud**                 | OPEX  |         **285 000** | Reclassé en OPEX (récurrent) — inclut 5 % frais de change |
| **Sous-total OPEX (hors amortissement)**            |       |       **3 535 000** | 250 000 + 300 000 + 1 200 000 + 1 500 000 + 0 + 285 000      |
| **Provision pour aléas (10 % du sous-total OPEX)** | OPEX  |         **353 500** | Hypothèse standard FinOps                                   |
| **TOTAL OPEX MENSUEL**                              |       | **≈ 4 180 167 Ar** | 291 667 + 3 535 000 + 353 500                                |
| **dont OPEX récurrents purs**                      |       |       **3 888 500** | 3 535 000 + 353 500                                          |

# 3. Démonstration du ROI (Return On Investment)

 *"Le ROI, c'est simple. Combien on économise en évitant la fraude par rapport à ce que l'on dépense pour faire tourner la plateforme ?"*

### Calcul des économies

- **Volume mensuel** : 10 000 factures.
- **Taux de fraude** : 10 % → **1 000 factures** frauduleuses potentielles.
- **Montant moyen** : 150 000 Ar.
- **Montant total des fraudes potentielles** : 1 000 × 150 000 = **150 000 000 Ar** (≈ 32 980 $ à 4 548 Ar/USD).
- **Taux de détection du modèle (rappel)** : **94 %** (cf. slide 8).
- **Économies brutes** : 150 000 000 × 0,94 = **141 000 000 Ar** (≈ 31 000 $).

> ⚠️ **Limite à mentionner** : le rappel ne dit rien des **faux positifs** (factures saines bloquées). Le coût de traitement des faux positifs est absorbé par le gestionnaire à temps plein ; on peut ajouter une sensibilité (cf. § 6).

### Calcul du ROI

\[
ROI = \frac{\text{Économies générées} - \text{Coût de la plateforme}}{\text{Coût de la plateforme}} \times 100
\]
\[
ROI = \frac{141\,000\,000 - 4\,180\,167}{4\,180\,167} \times 100 \approx \mathbf{3\,273\ \%}
\]

> **Interprétation corrigée** : *"Pour 1 Ariary investi dans PrediCare TPA, l'assureur en économise environ **33** (ratio = 1 + ROI/100 ≈ 33,7). Le retour sur investissement est immédiat. Même en divisant nos estimations par deux, la plateforme reste extrêmement rentable."*

# 4. Le « Semantic Caching » (Le secret de la performance)

 *"Le Semantic Caching, c'est notre arme secrète. Sur Ollama, c'est facile à mettre en place avec notre base PostgreSQL/pgvector. Au lieu de faire réfléchir l'IA à chaque fois, on stocke les réponses déjà données."*

### Comment ça marche ?

1. **Question de l'assuré** : *« Quel est le plafond de ma garantie dentaire ? »*
2. **Recherche** : le système transforme la question en vecteur (embedding) et cherche dans PostgreSQL/pgvector si une question **similaire** a déjà été posée.
3. **Si trouvée** : réponse stockée renvoyée instantanément (0 appel LLM).
4. **Si non trouvée** : interrogation d'Ollama, génération, puis **stockage** de la nouvelle réponse dans le cache.

### Impact économique du cache

| Sans cache                   | Avec cache (30 % de hit)                     |
| :--------------------------- | :------------------------------------------- |
| 10 000 appels LLM            | 7 000 appels LLM                             |
| Temps de réponse : 2 à 4 s | Temps de réponse : < 200 ms (pour les hits) |
| Utilisation GPU : 100 %      | Utilisation GPU : ~70 %                      |
| Coût API : 0 $ (Ollama)     | Coût API : 0 $ (Ollama)                     |

> **Argument FinOps** : *"Même si Ollama est gratuit, le cache sémantique réduit la charge GPU, ce qui **prolonge la durée de vie du serveur et réduit la consommation électrique** — c'est notre optimisation « Runtime » (cf. Module 6). Cet effet est **qualitatif** : nous ne le chiffrons pas dans le TCO, faute de données de fiabilité matérielle."*

# 5. Le Pitch « Business » pour la Soutenance

> *"En conclusion de notre analyse FinOps :*
> *Notre TCO s'élève à **≈ 4,18 millions d'Ariary par mois**, soit environ **920 dollars** (à 4 548 Ar/USD). C'est le prix d'un serveur local et de deux salaires locaux.*
> *En face, nous évitons **141 millions d'Ariary** de fraudes.*
> *Le ROI est de **≈ 3 270 %**, soit **1 Ar investi → ≈ 33 Ar économisés**.*
> *Nous avons fait le choix stratégique d'**Ollama en local** pour deux raisons : d'abord la **souveraineté des données de santé** (loi malgache n° 2014-006 sur la protection des données personnelles, équivalent fonctionnel du RGPD), ensuite l'**indépendance économique** : nous ne payons pas de dollars de tokens à une entreprise américaine, nous faisons travailler des ingénieurs malgaches sur une infrastructure malgache. C'est notre contribution à l'écosystème IA de Madagascar (cf. Vision 2028)."*

---

# 6. Ce qu'il faut répondre aux questions du Jury

- **« Et si vous avez un pic de charge ? »**
  *« Le serveur local peut être upgradé. Et nous avons prévu une abstraction `LLMProvider` qui permet, en une variable d'environnement, de basculer sur Groq (gratuit) ou Mistral API (souverain UE) en cas de surcharge. »*
- **« Pourquoi ne pas utiliser AWS ? »**
  *« Pour les données de santé, la souveraineté et le coût. AWS nous facturerait en dollars, avec un egress coûteux (Madagascar est une île). Ollama local est la seule option viable pour un ROI à court terme. »*
- **« Le Semantic Caching ne risque-t-il pas de donner de mauvaises réponses ? »**
  *« Non : le cache a un seuil de similarité strict (ex. 0,95). Si la question est trop différente, le système interroge à nouveau l'IA. Et le cache est purgé tous les 7 jours (politique de protection des données). »*
- **« Quel est l'impact des faux positifs ? »**
  *« Le rappel de 94 % signifie que 6 % des fraudes passent. Symétriquement, des factures saines peuvent être bloquées : c'est le rôle du gestionnaire à temps plein que de les traiter. Une sensibilité est présentée ci-dessous. »*
- **« Et si l'Ariary se déprécie ? »**
  *« La quasi-totalité de nos coûts est libellée en Ariary (serveur, salaires, électricité). Seul le backup cloud est en USD : il subit 5 % de frais de change et une dépréciation annuelle hypothétique de 5 % (cf. tableau initial). Impact mensuel négligeable (< 15 000 Ar). »*

---

# 7. Sensibilité (nouvelle section — promise dans le tableau initial)

### 7.1 Sensibilité au taux de détection (rappel)

|                 Rappel |       Économies (Ar) |  ROI (OPEX = 4,18 M) |
| ---------------------: | --------------------: | -------------------: |
|                   80 % |           120 000 000 |           ≈ 2 771 % |
|                   90 % |           135 000 000 |           ≈ 3 129 % |
| **94 % (réf.)** | **141 000 000** | **≈ 3 273 %** |
|                   98 % |           147 000 000 |           ≈ 3 416 % |

### 7.2 Sensibilité au taux de fraude

|         Taux de fraude |          Fraudes (Ar) | Économies à 94 % (Ar) |                  ROI |
| ---------------------: | --------------------: | ----------------------: | -------------------: |
|                    8 % |           120 000 000 |             112 800 000 |           ≈ 2 598 % |
| **10 % (réf.)** | **150 000 000** |   **141 000 000** | **≈ 3 273 %** |
|                   15 % |           225 000 000 |             211 500 000 |           ≈ 4 960 % |

### 7.3 Sensibilité à la dépréciation de l'Ariary (5 %/an, postes USD)

Le backup cloud (~285 000 Ar, dont une part en USD) est le seul poste exposé. À 5 %/an, le surcoût reste **< 15 000 Ar/mois** en année 1 — négligeable devant 4,18 M. ✅
