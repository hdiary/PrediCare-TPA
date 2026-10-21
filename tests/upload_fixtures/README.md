# Donnees de test pour depot de facture

Tous les documents de ce dossier sont fictifs et ne correspondent a aucun patient reel.

- `facture_demo.pdf` : PDF de facture a deposer dans le formulaire prestataire.
- `ordonnance_demo.pdf` : scan PDF a joindre en cochant que la facture est liee a une ordonnance.
- `facture_demo.json` : exemple de payload pour tester directement `POST /predict`.
- Les fichiers HTML sont les sources modifiables des deux PDF.

La facture et l'ordonnance sont coherentes entre elles : ordonnance `ORD-9000001`, assure `ASS-9CAA1484E0`, prestataire `PRE-00001` (Pharmacie Vatolampy), NIF `1939042955` et medicament `MED-AMLO` (Amlodipine 5 mg, boîte de 30). Le NIF et le medicament ont ete verifies dans le referentiel de votre base.

Avant un test contre une autre base, adaptez le prestataire, le NIF, l'assure et le medicament a ses donnees. Gardez le numero et la date de l'ordonnance identiques dans les deux documents.

Pour le parcours PDF, televersez la facture puis joignez l'ordonnance dans la section ordonnance. Le PDF de facture doit rester le document principal.