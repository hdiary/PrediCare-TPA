# Notifications e-mail

## Configuration du relais

Les e-mails transactionnels (création de compte et réinitialisation) ainsi que les alertes de
fraude utilisent le relais SMTP configuré pour le service `api`. Définir ces variables dans le
fichier `.env` du déploiement, sans les commiter :

```dotenv
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_USER=compte-smtp
SMTP_PASSWORD=mot-de-passe-fourni-par-le-relais
SMTP_FROM=notifications@votre-domaine.example
SMTP_STARTTLS=true
APP_PUBLIC_URL=https://votre-application.example
```

Le port 587 utilise généralement STARTTLS. Pour un relais TLS implicite sur le port 465, définir
`SMTP_PORT=465` et `SMTP_STARTTLS=false`. `SMTP_FROM` doit être autorisé par le fournisseur. Après
modification, recréer/redémarrer l'API afin qu'elle recharge les variables.

## Destinataires et vérification

Dans **Administration > Configuration**, activer le canal e-mail, saisir une ou plusieurs adresses
séparées par des virgules ou des points-virgules, puis enregistrer. Le bouton **Tester l’envoi**
confirme la livraison au relais. Une alerte de fraude déclenche ensuite un e-mail minimal contenant
l'identifiant de facture, le score, le montant et les codes de fraude, sans identité d'assuré.

La cloche des espaces de travail affiche les alertes en attente pour les gestionnaires et
administrateurs, et les dernières factures du compte pour les professionnels et assurés. Elle se
rafraîchit chaque minute. L'e-mail est un canal additionnel ; les données restent consultables dans
l'application si le relais est indisponible.