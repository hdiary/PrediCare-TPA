-- Prédictions simulées : les fraudes labellisées ont des scores plutôt hauts
INSERT INTO predictions (facture_id, model_version, score, threshold, is_alert)
SELECT f.facture_id, 'test-v0', s.score, 0.8, s.score > 0.8
FROM factures f
LEFT JOIN labels_fraude l ON l.facture_id = f.facture_id
CROSS JOIN LATERAL (
    SELECT ROUND(CASE WHEN COALESCE(l.est_fraude, false)
                      THEN 0.55 + random() * 0.44
                      ELSE random() * 0.9 END::numeric, 5) AS score
) s
ON CONFLICT (facture_id, model_version) DO NOTHING;

-- Décisions simulées sur les alertes uniquement
INSERT INTO decisions_gestionnaires (facture_id, prediction_id, user_id, decision)
SELECT p.facture_id, p.prediction_id, 'test-gestionnaire',
       CASE WHEN COALESCE(l.est_fraude, false)
            THEN (CASE WHEN random() < 0.85 THEN 'rejete' ELSE 'a_investiguer' END)
            ELSE (CASE WHEN random() < 0.80 THEN 'valide' ELSE 'rejete' END) END
FROM predictions p
LEFT JOIN labels_fraude l ON l.facture_id = p.facture_id
WHERE p.is_alert AND p.model_version = 'test-v0';