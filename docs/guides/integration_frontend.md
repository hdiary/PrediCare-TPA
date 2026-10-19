# Intégration du frontend avec l'API (P3-20)

Contrat entre l'API et le frontend. Base : `http://localhost:8000` (configurable). Documentation interactive : `/docs`.
Le schéma complet est téléchargeable sur `/openapi.json` (à utiliser pour générer des types TypeScript).

## 1. CORS

- Origines autorisées : variable `CORS_ORIGINS` de l'API (par défaut `http://localhost:3000`). L'URL doit être exacte
  (schéma + domaine + port). Plusieurs origines : séparées par des virgules.
- Méthodes et en-têtes de requête : tous autorisés (le préflight `OPTIONS` est géré).
- En-têtes de **réponse** lisibles par le JavaScript du front : `X-Total-Count`, `X-Request-ID`, `Retry-After`.

## 2. Authentification

1. `POST /auth/login` avec `{"email": "...", "password": "..."}` → `{"access_token", "token_type": "bearer", "expires_in", "user"}`.
2. Envoyer `Authorization: Bearer <access_token>` sur chaque appel protégé.
3. Le champ `user.role` pilote l'affichage : `professionnel_sante`, `assure`, `gestionnaire`, `administrateur`.
   **Le masquage d'un écran dans le front n'est qu'un confort : le contrôle réel est fait par l'API (403).**
4. Stocker le jeton en mémoire (ou `sessionStorage`), pas dans `localStorage` si possible. `expires_in` est en secondes :
   au-delà, l'API répond 401 et le front redirige vers la connexion.

```ts
const res = await fetch(`${API}/alerts?statut=en_attente&limit=20`, {
  headers: { Authorization: `Bearer ${token}` },
});
const total = Number(res.headers.get("X-Total-Count"));   // pour la pagination
const alerts = await res.json();
```

## 3. Format des erreurs

Toutes les erreurs sont du JSON avec un champ `detail` (texte). Des champs s'ajoutent selon le cas.

| Code | Quand | Corps |
|---|---|---|
| 401 | Jeton absent, invalide ou expiré | `{"detail": "..."}` → rediriger vers la connexion |
| 403 | Rôle non autorisé | `{"detail": "Accès refusé pour ce rôle"}` |
| 404 | Alerte introuvable | `{"detail": "..."}` |
| 409 | Facture déjà enregistrée / décision sur une non-alerte | `{"detail": "...", "codes": [...]}` ou `{"detail": "..."}` |
| 422 (requête mal formée) | Paramètre ou corps invalide | `{"detail": "Requête invalide", "errors": [{"field", "message", "type"}]}` |
| 422 (facture rejetée) | `POST /predict` : règles du contrat de données | `{"detail": "Facture rejetée", "codes": [...], "erreurs": [{"code", "champ", "message"}]}` |
| 429 | Compte verrouillé | `{"detail": "..."}` + en-tête `Retry-After` (secondes) |
| 500 | Erreur inattendue | `{"detail": "Erreur interne du serveur", "request_id": "..."}` |
| 502 / 503 | MLflow ou base indisponible | `{"detail": "..."}` : afficher « service momentanément indisponible » |

Pour une erreur 500, afficher le `request_id` à l'utilisateur : l'exploitant le retrouve dans les logs.
`errors[].field` est de la forme `query.jours` ou `body.decision` : afficher le message près du champ concerné.

Les 12 codes de rejet de facture (`codes`) et leur sens sont dans `GUIDE_UTILISATION_API.md`, section 4.3.

## 4. Formats de données

- Dates et heures : ISO 8601 (`2026-10-16T09:30:00Z`) ; `date_soin` en `AAAA-MM-JJ`, `heure_soin` en `HH:MM`.
- Montants : **entiers en MGA**, sans décimales.
- Scores : nombres entre 0 et 1.
- Absence de valeur : `null` (jamais une chaîne vide).

## 5. Écrans et endpoints

| Écran | Rôle | Endpoints |
|---|---|---|
| Saisie / envoi d'une facture | professionnel_sante, gestionnaire | `POST /predict` |
| Liste des alertes | gestionnaire | `GET /alerts?statut=en_attente\|traitees\|toutes&limit&offset` (+ `X-Total-Count`) |
| Détail d'une alerte (SHAP, règles, historique) | gestionnaire | `GET /alerts/{facture_id}` |
| Identité de l'assuré | gestionnaire | `GET /alerts/{facture_id}/identite` |
| Décision | gestionnaire | `POST /alerts/{facture_id}/decision` |
| Tableau de bord | gestionnaire, administrateur | `GET /kpis?jours=30` |
| Administration | administrateur | `/admin/threshold`, `/admin/model/*`, `/admin/audit`, `/admin/metrics`, `/admin/drift` |

Particularité de `POST /predict` : le professionnel de santé reçoit un simple accusé `{accepte, facture_id, prediction_id}`,
sans score ; le gestionnaire reçoit aussi `score`, `seuil`, `is_alert`, `version_modele`, `shap`, `regles`, `latence_ms`.

### Détail d'une alerte : `GET /alerts/{facture_id}`

```json
{
  "prediction": {"prediction_id": 12, "facture_id": "FAC-90000001", "score": 0.91, "seuil_utilise": 0.8,
                 "est_alerte": true, "version_modele": "7", "date": "2026-10-16T09:30:00Z"},
  "shap": {"valeur_base": 0.12, "top": [{"variable": "...", "valeur": 4, "contribution": 0.31}], "toutes": {"...": 0.0}},
  "regles": [{"regle_code": "ORDONNANCE_REUTILISEE", "severite": "haute", "message": "...", "details": {}}],
  "decisions": []
}
```

Afficher `shap.top` (graphique en barres signé : contribution > 0 pousse vers la fraude) et la liste `regles`
(sévérités : `info`, `moyenne`, `haute`).

### Tableau de bord : `GET /kpis`

Champs : `factures_scorees`, `taux_alerte`, `alertes_total`, `alertes_en_attente`, `alertes_traitees`, `fraudes_confirmees`,
`faux_positifs`, `a_investiguer`, `precision` (peut être `null` s'il n'y a aucune décision), `montant_en_attente`,
`montant_fraude_confirmee`, `montant_economise`, `score_moyen`, `par_jour[]` (courbe), `regles[]` (répartition par règle).

## 6. Liste de contrôle « front branché »

- [ ] Connexion, déconnexion, redirection sur 401.
- [ ] Menus filtrés selon `user.role` (et 403 géré proprement si l'URL est saisie à la main).
- [ ] Pagination des alertes avec `X-Total-Count`.
- [ ] Affichage des erreurs 422 (champ par champ) et des codes de rejet de facture.
- [ ] Message 429 avec le délai `Retry-After`.
- [ ] Montants formatés en MGA ; dates affichées en heure de Madagascar (UTC+3).
- [ ] Aucune clé ni secret dans le code du front.
