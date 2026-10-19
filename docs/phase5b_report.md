# Rapport section 8 — phase 5b corrigée

Mesure exécutée dans le conteneur API sur les 84 593 factures PostgreSQL. Rappel = intersection avec le même type_fraude / nombre de labels du type. Précision = intersection / déclenchements.

| Règle | Déclenchements | Labels | Intersection | Rappel | Précision |
|---|---:|---:|---:|---:|---:|
| SURFACTURATION | 2 202 | 1 272 | 835 | 65,645 % | 37,920 % |
| QUANTITE_EXCESSIVE | 563 | 568 | 563 | 99,120 % | 100,000 % |
| UPCODING | 955 | 742 | 0 | 0,000 % | 0,000 % |
| LIGNES_NON_PRESCRITES | 1 276 | 733 | 733 | 100,000 % | 57,445 % |
| SUBSTITUTION_PRODUIT | 0 | 368 | 0 | 0,000 % | 0,000 % |
| ORDONNANCE_EXPIREE | 594 | 502 | 502 | 100,000 % | 84,512 % |
| SOINS_JOUR_FERME | 474 | 227 | 227 | 100,000 % | 47,890 % |
| DOUBLON | 553 | 909 | 553 | 60,836 % | 100,000 % |
| FRACTIONNEMENT | 2 125 | 340 | 197 | 57,941 % | 9,271 % |
| SURCONSOMMATION | 1 430 | 469 | 469 | 100,000 % | 32,797 % |
| ACTE_FICTIF | 863 | 496 | 239 | 48,186 % | 27,694 % |
| INCOHERENCE_PROFIL | 382 | 379 | 379 | 100,000 % | 99,215 % |
| PRESTATAIRE_RADIE | 157 | 147 | 147 | 100,000 % | 93,631 % |
| HORS_COUVERTURE | 376 | 195 | 195 | 100,000 % | 51,862 % |

## Vérifications

- **DOUBLON** : 553 déclenchements = 84 593 lignes - 84 040 numéros distincts. Le départage par identifiant donne 553 recouvrements et un rappel de 60,836 %. Le départage par date donne 404 recouvrements et 44,444 %. Le départage par identifiant est conservé.
- **SURCONSOMMATION** : 1 430 déclenchements, exactement le repère du mapping. Le rang exclut la première facture de chaque ordonnance réutilisée. Aucun resserrement n'est nécessaire.
- **SUBSTITUTION_PRODUIT** : le calcul utilise lignes_facture, ordonnance_lignes et referentiel_medicaments : médicament facturé absent de l'ordonnance et remboursable=false. Les dix exemples sont FAC-00000059, FAC-00000178, FAC-00000379, FAC-00000384, FAC-00000638, FAC-00000888, FAC-00000907, FAC-00001000, FAC-00001082 et FAC-00001434. Leurs détails disent bien « médicament X facturé à la place de Y prescrit », mais le référentiel donne `remboursable=true` pour les médicaments facturés. La divergence labels/mapping explique les 0 déclenchements pour 368 labels ; le mapping est conservé.
- **UPCODING** : les dix exemples contrôlés portent sur des actes sans ordonnance : consultation simple facturée en urgence, consultation spécialisée par un généraliste ou majoration nuit/dimanche un jour ouvré. La règle mapping exige pourtant `code_facture != code_ordonnance` et un tarif supérieur ; elle ne déclenche donc aucun de ces exemples. Le mapping est conservé et l'écart labels/mapping est documenté.
- **SUBSTITUTION_PRODUIT** : les dix exemples contrôlés décrivent bien un médicament facturé à la place d'un médicament prescrit, mais les références des médicaments facturés sont toutes `remboursable=true`. Le mapping exige `remboursable=false`; la règle stricte ne déclenche donc aucun exemple. Le mapping est conservé.
- **feature_schema.json** ne contient aucune colonne `is_*`. Un test verrouille cette propriété ; les flags restent des libellés d'explicabilité et ne sont pas dans le vecteur ML.
- **Exemples contrôlés UPCODING** : FAC-00000002, FAC-00000022, FAC-00000072, FAC-00000100, FAC-00000302, FAC-00000323, FAC-00000487, FAC-00000735, FAC-00000772, FAC-00000797. **SUBSTITUTION_PRODUIT** : FAC-00000059, FAC-00000178, FAC-00000379, FAC-00000384, FAC-00000638, FAC-00000888, FAC-00000907, FAC-00001000, FAC-00001082, FAC-00001434.
- **PRESTATAIRE_RADIE** : seuls les soins postérieurs à `date_fin_convention` ou `date_radiation` déclenchent la règle. Résultat : 157 déclenchements, 147 labels en commun, rappel 100 %, précision 93,631 %. Un statut `RADIE` sans date ne suffit plus.
- **SURFACTURATION** : le seuil actuel reste strictement `prix_unitaire > tarif_max` (facteur 1,0) : 2 202 déclenchements, rappel 65,645 %, précision 37,920 %. Le test `prix_unitaire > 1,2 × tarif_max` donne 592 déclenchements, rappel 42,217 %, précision 90,709 %. Le mapping impose le seuil 1,0 ; le seuil 1,2 est conservé comme comparaison de sensibilité.
- Les indicateurs restent explicatifs et ne déclenchent pas seuls une alerte.

| Indicateur | est_fraude=true | est_fraude=false |
|---|---:|---:|
| SPECIALITE_NON_DECLAREE | 0,1769 % | 0,0000 % |
| TYPE_ORDONNANCE_INCOHERENT | 2,1778 % | 0,4453 % |

SPECIALITE_NON_DECLAREE compare la spécialité de l'acte de la grille tarifaire à celle du prestataire. Les types de facture sans type d'ordonnance attendu restent acceptés.

## Tests et clôture

Le point de départ phase 4 était 281 tests. Les phases 5a/5b ont ajouté ou activé 106 tests, soit 387 ; la vérification de date de radiation ajoutée pour cette clôture porte la suite API à 388. La modification de `test_model_registry_phase4.py` ne change aucune assertion : elle cherche la migration sous `backend/ingestion/...` dans le dépôt et sous `ingestion/...` dans l'image API, dont `/app` est déjà le dossier backend.

Suite API dans le conteneur : **388 passed, 1 skipped**. Suite ingestion dans l'image loader : **55 passed, 17 skipped**. Total exécutable : **443 passed, 18 skipped, 0 échec**. L'ancien échec loader était `pytest: not found`, puis, après installation du runner, `ModuleNotFoundError: No module named 'encrypt_identities'` et `No module named 'pseudo'`; le montage et les chemins de tests ont été corrigés.

La phase 5c n'est pas commencée.
