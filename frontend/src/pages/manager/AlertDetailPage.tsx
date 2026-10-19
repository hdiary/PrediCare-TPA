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
  const lines = Array.isArray(detail.facture.lignes) ? detail.facture.lignes as Array<Record<string, unknown>> : [];
  const shap = Array.isArray(detail.shap) ? detail.shap : detail.shap?.top || [];
  return <div className="space-y-5"><Link to="/gestionnaire/alertes" className="inline-flex gap-2"><ArrowLeft />Retour aux alertes</Link>
    <Card className="p-6 space-y-5"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-bold">Facture {prediction.facture_id}</h2><p className="text-sm text-surface-500">{prediction.type} · {formatDate(prediction.date)}</p></div><Badge className={ALERT_STATUS_COLORS[prediction.statut] || ''}>{ALERT_STATUS_LABELS[prediction.statut] || prediction.statut}</Badge></div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div>Score <strong className={riskColor(prediction.score)}>{prediction.score.toFixed(3)}</strong></div><div>Priorité <strong>{prediction.priorite}</strong></div><div>Montant <strong>{formatMGA(prediction.montant_total || 0)}</strong></div><div>Prestataire / assuré <strong>{prediction.prestataire_id || '—'} / {prediction.assure_id || '—'}</strong></div></div>
      <section><h3 className="font-semibold mb-2">Codes de fraude</h3>{detail.codes_fraude.length ? <div className="flex flex-wrap gap-2">{detail.codes_fraude.map((code) => <Badge key={code}><ShieldAlert className="w-3 h-3 mr-1" />{code}</Badge>)}</div> : <p className="text-sm text-surface-500">Aucun code associé.</p>}</section>
      <section><h3 className="font-semibold mb-2">Explicabilité SHAP</h3>{shap.length ? <ul className="space-y-2">{shap.map((value, index) => <li key={`${value.variable}-${index}`} className="flex justify-between border-b py-2"><span>{value.variable}</span><strong>{value.contribution > 0 ? '+' : ''}{value.contribution.toFixed(4)}</strong></li>)}</ul> : <p className="text-sm text-surface-500">Explication SHAP indisponible.</p>}</section>
      {lines.length > 0 && <section><h3 className="font-semibold mb-2">Lignes de facture</h3><ul>{lines.map((line, index) => <li key={index} className="border-b py-2">{String(line.code_acte || line.code || '')} · {String(line.libelle || line.label || '')} · {String(line.quantite || 1)} × {formatMGA(Number(line.montant_total || line.montant || 0))}</li>)}</ul></section>}
      {prediction.statut === 'EN_ATTENTE' && <section><h3 className="font-semibold mb-2">Décision gestionnaire</h3><textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Commentaire requis" rows={3} className="w-full rounded border p-3 mb-3" /><div className="flex flex-wrap gap-2">{OPTIONS.map((option) => <Button key={option.value} disabled={!comment.trim() || submitting} variant={option.value === 'REJETER' || option.value === 'CONFIRMER_FRAUDE' ? 'danger' : 'outline'} onClick={() => decide(option.value)}>{option.value === 'VALIDER' ? <CheckCircle2 className="w-4 h-4" /> : option.value === 'REJETER' ? <XCircle className="w-4 h-4" /> : null}{option.label}</Button>)}</div></section>}
    </Card></div>;
}
