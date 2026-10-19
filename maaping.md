
Mapping entre le Référentiel métier (xlsx) et les tables du contrat de données P1
Vue d'ensemble
Le Référentiel métier définit les valeurs autorisées (énumérations, codes de fraude, codes d'invalidité). Le Contrat de données P1 définit les tables physiques (colonnes, types, contraintes).

Le mapping ci-dessous montre, pour chaque élément du référentiel, où il est implémenté dans les tables (colonne, contrainte, ou table dédiée).

1. Feuille « Référentiels » — les 5 énumérations de base
   1.1 Types de facture (9 valeurs)
   Valeurs du référentiel	Table(s) concernée(s)	Colonne	Implémentation
   CONSULTATION, PHARMACIE, LABORATOIRE, IMAGERIE, HOSPITALISATION, MATERNITE, DENTAIRE, OPTIQUE, KINESITHERAPIE	factures	type_facture	Énumération en base (CHECK ou ENUM PostgreSQL)
   Idem	garanties	categorie	Clé primaire composite (formule, categorie) — 9 catégories × 3 formules = 27 lignes
   Idem	referentiel_actes	categorie	8 valeurs (pas 9 — pas de « MATERNITE » dans les actes, la maternité est un type de facture mais pas une catégorie d'acte standard)
   Lien : factures.type_facture → garanties.categorie (jointure pour récupérer taux/plafonds). C'est le pont entre la facture et la formule.

1.2 Types d'ordonnance (4 valeurs)
Valeurs du référentiel	Table	Colonne	Implémentation
MEDICAMENTS, EXAMENS, KINE, OPTIQUE	ordonnances	type_ordonnance	Énumération (CHECK)
Lien métier : type_ordonnance doit être cohérent avec factures.type_facture :

PHARMACIE → MEDICAMENTS

LABORATOIRE / IMAGERIE → EXAMENS

KINESITHERAPIE → KINE

OPTIQUE → OPTIQUE

C'est un contrôle de cohérence à implémenter dans l'API (Flux 1, étape 3).

1.3 Types de prestataire (10 valeurs)
Valeurs du référentiel	Table	Colonne	Implémentation
PHARMACIE, CABINET_GENERALISTE, CABINET_SPECIALISTE, CLINIQUE, LABORATOIRE, CENTRE_IMAGERIE, CABINET_DENTAIRE, OPTICIEN, CABINET_KINE, MATERNITE	prestataires	type_prestataire	Énumération (CHECK)
Lien métier : le type_prestataire doit être cohérent avec le type_facture :

PHARMACIE → PHARMACIE

CONSULTATION → CABINET_GENERALISTE ou CABINET_SPECIALISTE

LABORATOIRE → LABORATOIRE

IMAGERIE → CENTRE_IMAGERIE

etc.

C'est un contrôle de cohérence à implémenter (Flux 1, étape 5 — détection SPECIALITE_NON_DECLAREE).

1.4 Spécialités médicales (16 valeurs)
Valeurs du référentiel	Table	Colonne	Implémentation
CARDIOLOGIE, PEDIATRIE, GYNECOLOGIE, OPHTALMOLOGIE, DERMATOLOGIE, ORL, NEUROLOGIE, PNEUMOLOGIE, ENDOCRINOLOGIE, GASTRO-ENTEROLOGIE, RHUMATOLOGIE, PSYCHIATRIE, UROLOGIE, NEPHROLOGIE, TRAUMATO-ORTHOPEDIE, CANCEROLOGIE	referentiel_actes	specialite	18 valeurs (2 de plus que le référentiel : probablement MEDECINE_GENERALE et CHIRURGIE) — nullable (38 nulls sur 58)
Idem	prestataires	specialite	16 valeurs — nullable (209 nulls sur 251)
Lien métier : la specialite de l'acte doit correspondre à la specialite du prestataire prescripteur (détection PRESCRIPTEUR_INCOMPATIBLE).

Écart à noter : le référentiel xlsx liste 16 spécialités, mais referentiel_actes.specialite en contient 18. Il faut aligner les deux (soit ajouter 2 valeurs au xlsx, soit retirer 2 valeurs de la table). À valider avec P1/P2.

1.5 Formules de couverture (3 valeurs)
Valeurs du référentiel	Table	Colonne	Implémentation
ESSENTIEL, CONFORT, PREMIUM	garanties	formule	Partie de la clé primaire composite (formule, categorie)
Idem	contrats	formule	CHECK (doit référencer garanties.formule)
Lien métier : contrats.formule détermine la ligne de garanties à utiliser pour le calcul de remboursement (Flux 1, étape 4).

2. Feuille « Fraudes factures » — 14 codes
   Ces codes sont utilisés à 3 endroits :

Règles métier (Flux 1, étape 5) — détection déterministe.

Features ML (Flux 1, étape 6) — encodage binaire pour XGBoost.

Labels supervisés (labels_fraude.type_fraude) — vérité terrain pour l'entraînement.

Code fraude	Règle métier (étape 5)	Feature ML (étape 6)	Label (labels_fraude)
SURFACTURATION	prix_unitaire > tarif_max_barème	is_surfacturation	type_fraude = 'SURFACTURATION'
QUANTITE_EXCESSIVE	quantite_facturee > quantite_prescrite × 1.2	is_quantite_excessive	type_fraude = 'QUANTITE_EXCESSIVE'
UPCODING	code_facture ≠ code_ordonnance avec tarif_facture > tarif_prescrit	is_upcoding	type_fraude = 'UPCODING'
LIGNES_NON_PRESCRITES	code_facture ∉ ordonnance_lignes	is_lignes_non_prescrites	type_fraude = 'LIGNES_NON_PRESCRITES'
SUBSTITUTION_PRODUIT	medicament_facture ≠ medicament_prescrit + remboursable=false	is_substitution_produit	type_fraude = 'SUBSTITUTION_PRODUIT'
ORDONNANCE_EXPIREE	date_soin > date_prescription + validite_jours	is_ordonnance_expiree	type_fraude = 'ORDONNANCE_EXPIREE'
SOINS_JOUR_FERME	jour_semaine(date_soin) ∉ jours_ouverture(prestataire)	is_soins_jour_ferme	type_fraude = 'SOINS_JOUR_FERME'
DOUBLON	numero_facture répété (84 040/84 593)	is_doublon	type_fraude = 'DOUBLON'
FRACTIONNEMENT	N factures même jour / même prestataire / même assuré	is_fractionnement	type_fraude = 'FRACTIONNEMENT'
SURCONSOMMATION	ordonnance_id réutilisé par N factures (1 430 cas)	is_surconsommation	type_fraude = 'SURCONSOMMATION'
ACTE_FICTIF	ordonnance_id NULL + acte nécessitant ordonnance	is_acte_fictif	type_fraude = 'ACTE_FICTIF'
INCOHERENCE_PROFIL	sexe_requis/age_min/age_max incompatibles avec assures.sexe/annee_naissance	is_incoherence_profil	type_fraude = 'INCOHERENCE_PROFIL'
PRESTATAIRE_RADIE	date_soin > date_fin_convention ou statut='RADIE'	is_prestataire_radie	type_fraude = 'PRESTATAIRE_RADIE'
HORS_COUVERTURE	date_soin < date_adhesion OU date_soin > date_radiation OU date_soin pendant carence	is_hors_couverture	type_fraude = 'HORS_COUVERTURE'
Tables mobilisées par ces règles :

Règle	Tables sources
SURFACTURATION	factures, lignes_facture, grille_tarifaire, referentiel_actes/medicaments
QUANTITE_EXCESSIVE	lignes_facture, ordonnance_lignes
UPCODING	lignes_facture, ordonnance_lignes, referentiel_actes
LIGNES_NON_PRESCRITES	lignes_facture, ordonnance_lignes
SUBSTITUTION_PRODUIT	lignes_facture, ordonnance_lignes, referentiel_medicaments
ORDONNANCE_EXPIREE	factures.date_soin, ordonnances.date_prescription, ordonnances.validite_jours
SOINS_JOUR_FERME	factures.date_soin, prestataires.jours_ouverture
DOUBLON	factures.numero_facture (agrégation)
FRACTIONNEMENT	factures (agrégation par date/prestataire/assuré)
SURCONSOMMATION	factures.ordonnance_id (agrégation)
ACTE_FICTIF	factures.ordonnance_id, referentiel_actes.ordonnance_requise
INCOHERENCE_PROFIL	factures, assures.sexe/annee_naissance, referentiel_actes.sexe_requis/age_min/age_max
PRESTATAIRE_RADIE	prestataires.date_fin_convention/statut
HORS_COUVERTURE	assures.date_adhesion/date_radiation, garanties.delai_carence_jours
Label dans labels_fraude : chaque facture reçoit est_fraude (booléen) + type_fraude (1 des 14 codes) + detail_fraude (texte explicatif).

3. Feuille « Factures invalides » — 10 codes
   Ces codes sont utilisés uniquement à l'étape 3 (contrôle d'invalidité, avant le ML). Ils sont stockés dans labels_fraude.motif_invalidite (quand est_valide = false).

Code d'invalidité	Règle de détection (Contrat §9.1)	Tables sources
MONTANT_NEGATIF	quantite ≤ 0 OU prix_unitaire < 0 OU montant < 0	lignes_facture
CODE_ACTE_INCONNU	code ∉ ref_codes	lignes_facture, vue ref_codes
DATE_FUTURE	date_soin > CURRENT_DATE	factures
DATE_IMPOSSIBLE	Date non analysable	factures (validation d'ingestion)
CHAMP_OBLIGATOIRE_MANQUANT	assure_id NULL OU prestataire_id NULL	factures
TOTAL_INCOHERENT	montant_total ≠ Σ lignes.montant	factures, lignes_facture
PRESTATAIRE_INCONNU	prestataire_id ∉ prestataires	factures
ASSURE_INCONNU	assure_id ∉ assures	factures
DEVISE_INVALIDE	devise ≠ 'MGA'	factures
FACTURE_SANS_LIGNE	Aucune ligne dans lignes_facture pour ce facture_id	factures, lignes_facture
Bonne nouvelle : le Contrat §9.1 précise que sur le jeu fourni, aucune violation n'est détectée. Les 10 codes servent donc principalement à valider l'API (tests d'ingestion) et à rejeter les futures factures invalides.

4. Feuille « Fraudes ordonnances » — 4 codes
   Ces codes sont utilisés pour enrichir les features ML et pour le contrôle métier (étape 5).

Code fraude ordonnance	Règle de détection	Tables sources
ORDONNANCE_FALSIFIEE	Quantité/durée surchargée : ordonnance_lignes.quantite > seuil attendu pour ce code	ordonnance_lignes, referentiel_medicaments
PRESCRIPTEUR_INCOMPATIBLE	prestataires.specialite (prescripteur) ≠ referentiel_actes.specialite (acte prescrit)	ordonnances, prestataires, ordonnance_lignes, referentiel_actes
PRESCRIPTEUR_RADIE	prestataires.statut = 'RADIE' OU date_prescription > date_fin_convention	ordonnances, prestataires
ORDONNANCE_ANTIDATEE	ordonnances.date_prescription < assures.date_adhesion	ordonnances, assures
Non stocké comme label dans labels_fraude (qui est au niveau facture). Ces codes sont dérivés à la volée ou stockés dans une future table labels_ordonnances (non prévue dans le Contrat P1 — à discuter avec P2).

5. Feuille « Fraudes contrats » — 4 codes
   Ces codes concernent la relation assuré ↔ contrat, pas la facture. Ils sont vérifiés à l'adhésion et à chaque facture.

Code fraude contrat	Règle de détection	Tables sources
BENEFICIAIRE_FICTIF	Écart d'âge parent/enfant incohérent (ex. parent 20 ans, enfant 18 ans)	assures (via assure_principal_id auto-référence)
AGE_LIMITE_DEPASSE	annee_naissance > 25 ans pour un ENFANT (CG Article 3)	assures
DOUBLE_AFFILIATION	Même assure_id sur 2 contrat_id différents	assures (agrégation)
ADHESION_RETROACTIVE	assures.date_adhesion < contrats.date_effet_police	assures, contrats
Non stocké comme label dans labels_fraude. À implémenter dans le contrôle d'ingestion (rejet de l'adhésion) ou dans les features ML (Flux 1, étape 6).

6. Feuille « Fraudes prestataires » — 4 codes
   Ces codes concernent la relation prestataire ↔ convention. Ils sont vérifiés en amont (référentiel prestataire) et à chaque facture.

Code fraude prestataire	Règle de détection	Tables sources
PRESTATAIRE_FICTIF	Coordonnées invérifiables, création récente, tarifs très élevés	prestataires (analyse manuelle ou scoring)
FAUX_CONVENTIONNEMENT	prestataires.statut = 'ACTIF' mais date_fin_convention < CURRENT_DATE	prestataires
TARIFS_ABUSIFS	grille_tarifaire.tarif_pratique > referentiel_actes.tarif_max de façon systématique	grille_tarifaire, referentiel_actes/medicaments
SPECIALITE_NON_DECLAREE	prestataires.type_prestataire incompatible avec les actes de sa grille	prestataires, grille_tarifaire, referentiel_actes
Stocké dans labels_prestataires (table dédiée, clé prestataire_id, colonne est_suspect booléen).

7. Récapitulatif : où vit chaque élément du référentiel
   Feuille du référentiel	Table(s) cible(s)	Colonne(s)	Type d'implémentation
   Référentiels — Types de facture	factures, garanties	type_facture, categorie	Énumération (CHECK/ENUM)
   Référentiels — Types d'ordonnance	ordonnances	type_ordonnance	Énumération (CHECK)
   Référentiels — Types de prestataire	prestataires	type_prestataire	Énumération (CHECK)
   Référentiels — Spécialités médicales	referentiel_actes, prestataires	specialite	Énumération (CHECK) — écart 16 vs 18 à aligner
   Référentiels — Formules	garanties, contrats	formule	Clé composite + CHECK
   Fraudes factures (14)	labels_fraude, v_factures_features	type_fraude, is_* (14 features)	Label + features ML
   Factures invalides (10)	labels_fraude	motif_invalidite	Label (validation d'ingestion)
   Fraudes ordonnances (4)	(non stocké en label)	—	Features ML + contrôle métier
   Fraudes contrats (4)	assures	(dérivé)	Contrôle d'ingestion
   Fraudes prestataires (4)	labels_prestataires	est_suspect	Label
