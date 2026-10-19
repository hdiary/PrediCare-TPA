import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, ShieldAlert, XCircle } from 'lucide-react';
import { Badge, Button, Card, ErrorState, Skeleton } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { api, ApiError } from '@/lib/api';
import type { AlertApiDetail, AlertDecisionValue } from '@/lib/types';
import { ALERT_STATUS_COLORS, ALERT_STATUS_LABELS, formatDate, formatEUR, riskColor } from '@/lib/format';

const options: { value: AlertDecisionValue; label: string }[] = [
  { value: 'VALIDER', label: 'Valider' }, { value: 'REJETER', label: 'Rejeter' },
  { value: 'CONFIRMER_FRAUDE', label: 'Confirmer fraude' }, { value: 'ESCALADER', label: 'Escalader' },
];
export function AlertDetailPage() {
  const { id = '' } = useParams<{ id: string }>(); const { showToast } = useToast();
  const [detail, setDetail] = useState<AlertApiDetail | null>(null); const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false); const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false); const [conflict, setConflict] = useState('');
  const load = () => { setLoading(true); api.getAlertDetail(id).then(setDetail).catch(() => setError(true)).finally(() => setLoading(false)); };
  useEffect(load, [id]);
  const decide = async (decision: AlertDecisionValue) => {
    setSubmitting(true); setConflict('');
    try { await api.decideAlert(id, decision, comment); showToast('Décision enregistrée', 'success'); load(); }
    catch (e) { if (e instanceof ApiError && e.status === 409) { setConflict('Une décision a déjà été prise pour cette alerte.'); load(); } else showToast(e instanceof Error ? e.message : 'Erreur lors de la décision', 'error'); }
    finally { setSubmitting(false); }
  };
  if (loading) return <div className="space-y-4"><Skeleton className="h-10 w-32"/><Skeleton className="h-96"/></div>;
  if (error || !detail) return <><Link to="/gestionnaire/alertes" className="inline-flex gap-2 mb-4"><ArrowLeft/>Retour aux alertes</Link><ErrorState message="Impossible de charger le détail de l'alerte." onRetry={load}/></>;
  const p = detail.prediction; const lines = Array.isArray(detail.facture.lignes) ? detail.facture.lignes as Array<Record<string, unknown>> : [];
  const shap = Array.isArray(detail.shap) ? detail.shap : detail.shap?.top || [];
  return <div className="space-y-5"><Link to="/gestionnaire/alertes" className="inline-flex gap-2"><ArrowLeft/>Retour aux alertes</Link>
    <Card className="p-6 space-y-5"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-bold">Facture {p.facture_id}</h2><p className="text-sm text-surface-500">{p.type} · {formatDate(p.date)}</p></div><Badge className={ALERT_STATUS_COLORS[p.statut] || ''}>{ALERT_STATUS_LABELS[p.statut] || p.statut}</Badge></div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div>Score <strong className={riskColor(p.score)}>{p.score.toFixed(3)}</strong></div><div>Priorité <strong>{p.priorite}</strong></div><div>Montant <strong>{formatEUR(p.montant_total)}</strong></div><div>Prestataire / assuré <strong>{p.prestataire_id || '—'} / {p.assure_id || '—'}</strong></div></div>
      <section><h3 className="font-semibold mb-2">Codes de fraude</h3>{detail.codes_fraude.length ? <div className="flex flex-wrap gap-2">{detail.codes_fraude.map(c => <Badge key={c}><ShieldAlert className="w-3 h-3 mr-1"/>{c}</Badge>)}</div> : <p className="text-sm text-surface-500">Aucun code associé.</p>}</section>
      <section><h3 className="font-semibold mb-2">Explicabilité SHAP</h3>{sh.length ? <ul className="space-y-2">{sh.map((v,i) => <li key={`${v.variable}-${i}`} className="flex justify-between border-b py-2"><span>{v.variable}</span><strong>{v.contribution > 0 ? '+' : ''}{v.contribution.toFixed(4)}</strong></li>)}</ul> : <p className="text-sm text-surface-500">Explication SHAP indisponible.</p>}</section>
      {lines.length > 0 && <section><h3 className="font-semibold mb-2">Lignes de facture</h3><ul>{lines.map((l,i) => <li key={i} className="border-b py-2">{String(l.code_acte || l.code || '')} · {String(l.libelle || l.label || '')} · {String(l.quantite || 1)} × {formatEUR(Number(l.montant_total || l.montant || 0))}</li>)}</ul></section>}
      {detail.regles.length > 0 && <section><h3 className="font-semibold mb-2">Règles</h3><pre className="overflow-auto text-xs">{JSON.stringify(detail.regles, null, 2)}</pre></section>}
      {conflict && <p role="alert" className="rounded bg-danger-50 p-3 text-danger-700">{conflict}</p>}
      {p.statut === 'EN_ATTENTE' && <section><h3 className="font-semibold mb-2">Décision gestionnaire</h3><textarea value={comment} onChange={e => setComment(e.target.value)} placeholder="Commentaire requis" rows={3} className="w-full rounded border p-3 mb-3"/><div className="flex flex-wrap gap-2">{options.map(o => <Button key={o.value} disabled={!comment.trim() || submitting} variant={o.value === 'REJETER' || o.value === 'CONFIRMER_FRAUDE' ? 'danger' : 'outline'} onClick={() => decide(o.value)}>{o.value === 'VALIDER' ? <CheckCircle2 className="w-4 h-4"/> : o.value === 'REJETER' ? <XCircle className="w-4 h-4"/> : null}{o.label}</Button>)}</div></section>}
      {detail.decisions.length > 0 && <section><h3 className="font-semibold mb-2">Décisions précédentes</h3>{detail.decisions.map((d,i)=><p key={i} className="border-b py-2">{String(d.decision)} · {String(d.commentaire || '')} · {String(d.date_decision || '')}</p>)}</section>}
    </Card></div>;
}
