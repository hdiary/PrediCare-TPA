import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, ShieldAlert, XCircle } from 'lucide-react';
import { Badge, Button, Card, ErrorState, Skeleton } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import type { AlertApiDetail, AlertDecisionValue } from '@/lib/types';
import { ALERT_STATUS_COLORS, ALERT_STATUS_LABELS, formatDate, formatMGA, riskColor } from '@/lib/format';

const OPTIONS: { value: AlertDecisionValue; label: string }[] = [
  { value: 'VALIDER', label: 'Valider' },
  { value: 'REJETER', label: 'Rejeter' },
  { value: 'CONFIRMER_FRAUDE', label: 'Confirmer fraude' },
  { value: 'ESCALADER', label: 'Escalader' },
];

function formatFeatureValue(value: number | string | boolean | null | undefined) {
  if (value === null || value === undefined) return '—';
  return typeof value === 'number'
    ? value.toLocaleString('fr-FR', { maximumSignificantDigits: 7 })
    : String(value);
}

export function AlertDetailPage() {
  const { id = '' } = useParams<{ id: string }>();
  const { showToast } = useToast();
  const [detail, setDetail] = useState<AlertApiDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const load = () => {
    setLoading(true);
    api.getAlertDetail(id).then(setDetail).catch(() => setError(true)).finally(() => setLoading(false));
  };
  useEffect(load, [id]);
  const decide = async (decision: AlertDecisionValue) => {
    setSubmitting(true);
    try {
      await api.decideAlert(id, decision, comment);
      showToast('Décision enregistrée', 'success');
      load();
    } catch (exception) {
      showToast(exception instanceof ApiError ? exception.message : 'Erreur lors de la décision', 'error');
    } finally {
      setSubmitting(false);
    }
  };
  if (loading) return <div className="space-y-4"><Skeleton className="h-10 w-32" /><Skeleton className="h-96" /></div>;
  if (error || !detail) return <><Link to="/gestionnaire/alertes" className="inline-flex gap-2 mb-4"><ArrowLeft />Retour aux alertes</Link><ErrorState message="Impossible de charger le détail de l'alerte." onRetry={load} /></>;
  const prediction = detail.prediction;
  const lines = detail.facture.lignes;
  const explanation = detail.shap && !Array.isArray(detail.shap) ? detail.shap : null;
  const shap = Array.isArray(detail.shap) ? detail.shap : detail.shap?.top || [];
  const featureRows = Object.entries(explanation?.toutes || {})
    .map(([variable, contribution]) => ({
      variable,
      contribution,
      value: detail.variables?.[variable] ?? null,
    }))
    .sort((left, right) => Math.abs(right.contribution) - Math.abs(left.contribution));
  return <div className="space-y-5"><Link to="/gestionnaire/alertes" className="inline-flex gap-2"><ArrowLeft />Retour aux alertes</Link>
    <Card className="p-6 space-y-5"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-bold">Facture {prediction.facture_id}</h2><p className="text-sm text-surface-500">{prediction.type} · {formatDate(prediction.date)}</p></div><Badge className={ALERT_STATUS_COLORS[prediction.statut] || ''}>{ALERT_STATUS_LABELS[prediction.statut] || prediction.statut}</Badge></div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div>Score modèle <strong className={riskColor(prediction.score)}>{prediction.score.toFixed(6)}</strong>{prediction.seuil_utilise !== null && prediction.seuil_utilise !== undefined && <p className="text-xs text-surface-500">Seuil : {prediction.seuil_utilise.toFixed(6)}</p>}</div><div>Priorité <strong>{prediction.priorite}</strong></div><div>Montant <strong>{formatMGA(prediction.montant_total || 0)}</strong></div><div>Prestataire / assuré <strong>{prediction.prestataire_id || '—'} / {prediction.assure_id || '—'}</strong></div></div>
      <section><h3 className="font-semibold mb-2">Codes de fraude</h3>{detail.codes_fraude.length ? <div className="flex flex-wrap gap-2">{detail.codes_fraude.map((code) => <Badge key={code}><ShieldAlert className="w-3 h-3 mr-1" />{code}</Badge>)}</div> : <p className="text-sm text-surface-500">Aucun code associé.</p>}</section>
      <section>
        <h3 className="font-semibold mb-2">Explicabilité du modèle (SHAP)</h3>
        <p className="text-xs text-surface-500 mb-3">
          Une contribution positive augmente le score de fraude; une contribution négative le réduit.
          Le score est une estimation du modèle, pas une preuve de fraude.
          {explanation?.valeur_base !== undefined && ` Valeur de référence : ${explanation.valeur_base.toFixed(6)}.`}
        </p>
        {shap.length ? <ul className="space-y-2">{shap.map((value, index) => <li key={`${value.variable}-${index}`} className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-3 border-b py-2 text-sm">
          <span className="font-mono break-all">{value.variable}</span>
          <span className="text-surface-500 tabular-nums">{formatFeatureValue(value.valeur)}</span>
          <strong className={`tabular-nums ${value.contribution > 0 ? 'text-danger-600' : 'text-success-600'}`}>{value.contribution > 0 ? '+' : ''}{value.contribution.toFixed(6)}</strong>
        </li>)}</ul> : <p className="text-sm text-surface-500">Explication SHAP indisponible.</p>}
        {featureRows.length > 0 && <details className="mt-4">
          <summary className="cursor-pointer text-sm font-medium text-primary-700 dark:text-primary-400">
            Détails de debug : toutes les variables ({featureRows.length})
          </summary>
          <div className="mt-3 max-h-96 overflow-auto rounded-lg border border-surface-300 dark:border-surface-700">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-surface-100 dark:bg-surface-800">
                <tr><th className="p-2">Variable</th><th className="p-2 text-right">Valeur entrée</th><th className="p-2 text-right">Contribution SHAP</th></tr>
              </thead>
              <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
                {featureRows.map((row) => <tr key={row.variable}>
                  <td className="p-2 font-mono break-all">{row.variable}</td>
                  <td className="p-2 text-right tabular-nums">{formatFeatureValue(row.value)}</td>
                  <td className={`p-2 text-right tabular-nums ${row.contribution > 0 ? 'text-danger-600' : 'text-success-600'}`}>{row.contribution > 0 ? '+' : ''}{row.contribution.toFixed(8)}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
        </details>}
      </section>
      {lines.length > 0 && <section><h3 className="font-semibold mb-2">Lignes de facture</h3><ul>{lines.map((line, index) => <li key={index} className="border-b py-2">{line.code} · {line.libelle || ''} · {line.quantite || 1} × {formatMGA(line.montant || 0)}</li>)}</ul></section>}
      {prediction.statut === 'EN_ATTENTE' && <section><h3 className="font-semibold mb-2">Décision gestionnaire</h3><textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Commentaire requis" rows={3} className="w-full rounded border p-3 mb-3" /><div className="flex flex-wrap gap-2">{OPTIONS.map((option) => <Button key={option.value} disabled={!comment.trim() || submitting} variant={option.value === 'REJETER' || option.value === 'CONFIRMER_FRAUDE' ? 'danger' : 'outline'} onClick={() => decide(option.value)}>{option.value === 'VALIDER' ? <CheckCircle2 className="w-4 h-4" /> : option.value === 'REJETER' ? <XCircle className="w-4 h-4" /> : null}{option.label}</Button>)}</div></section>}
    </Card></div>;
}
