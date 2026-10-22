# Lot de test : 20 factures et 20 ordonnances

Les documents de ce dossier sont entierement fictifs et sans valeur medicale.
Chaque facture_NN.pdf correspond a ordonnance_NN.pdf avec le meme numero
d'ordonnance ORD-91000NN.

Les documents reprennent les references confirmees dans la base de test :
prestataire PRE-00001, NIF 1939042955, assure ASS-9CAA1484E0 et medicament
MED-AMLO. Le mode de reglement est TIERS_PAYANT.

Televersez une facture comme document principal, cochez le lien avec une
ordonnance, puis joignez le PDF d'ordonnance portant le meme suffixe. Relancez
node scripts/generate_upload_fixtures.mjs pour regenerer le lot.
