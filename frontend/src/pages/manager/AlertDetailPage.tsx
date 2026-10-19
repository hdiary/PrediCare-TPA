import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, ShieldAlert, XCircle } from 'lucide-react';
import { Badge, Button, Card, ErrorState, Skeleton } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { api, ApiError } from '@/lib/api';
import type { AlertApiDetail, AlertDecisionValue } from '@/lib/types';
import { ALERT_STATUS_COLORS, ALERT_STATUS_LABELS, formatDate, formatEUR, riskColor } from '@/lib/format';
import { api } from '@/lib/api';
import {
  formatMGA, formatDate, formatDateTime, riskColor,
  ALERT_TYPE_LABELS, ALERT_STATUS_LABELS, ALERT_STATUS_COLORS,
} from '@/lib/format';
import type { AlertDetail } from '@/lib/types';

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
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [comment, setComment] = useState('');
  const [decision, setDecision] = useState<'validate' | 'reject' | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.getAlertDetail(id).then((data) => { setDetail(data); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [id]);

  const handleConfirm = async () => {
    if (!detail || !decision) return;
    setSubmitting(true);
    try {
      await api.decideAlert(detail.id, decision, comment, detail.amount);
      showToast(
        decision === 'validate' ? 'Fraude validée et enregistrée' : 'Alerte rejetée',
        'success'
      );
      navigate('/gestionnaire/alertes');
    } catch {
      showToast('Erreur lors de la décision', 'error');
    } finally {
      setSubmitting(false);
      setShowConfirm(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-10 w-32" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div>
        <Link to="/gestionnaire/alertes" className="inline-flex items-center gap-2 text-sm text-primary-700 dark:text-primary-400 mb-4">
          <ArrowLeft className="w-4 h-4" /> Retour aux alertes
        </Link>
        <ErrorState message="Impossible de charger le détail de l'alerte." />
      </div>
    );
  }

  const scoreColor = detail.score > 0.8 ? 'text-danger-600' : detail.score >= 0.5 ? 'text-warning-600' : 'text-success-600';
  const gaugeColor = detail.score > 0.8 ? '#C62828' : detail.score >= 0.5 ? '#F9A825' : '#2E7D32';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Link to="/gestionnaire/alertes" className="inline-flex items-center gap-2 text-sm text-primary-700 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 font-medium">
          <ArrowLeft className="w-4 h-4" /> Retour aux alertes
        </Link>
        <Badge className={ALERT_STATUS_COLORS[detail.status]}>{ALERT_STATUS_LABELS[detail.status]}</Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Invoice summary */}
        <div className="space-y-6">
          <Card className="p-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center">
                <FileText className="w-5 h-5 text-primary-700 dark:text-primary-400" />
              </div>
              <div>
                <h3 className="font-semibold text-surface-800 dark:text-surface-100">Facture {detail.invoice_id}</h3>
                <p className="text-xs text-surface-400">{ALERT_TYPE_LABELS[detail.type]} · {formatDate(detail.created_at)}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-5">
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-3">
                <p className="text-xs text-surface-400 mb-1">Prestataire</p>
                <p className="text-sm font-mono font-medium text-surface-700 dark:text-surface-200">{detail.provider_pseudo}</p>
              </div>
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-3">
                <p className="text-xs text-surface-400 mb-1">Assuré</p>
                <p className="text-sm font-mono font-medium text-surface-700 dark:text-surface-200">{detail.insured_pseudo}</p>
              </div>
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-3">
                <p className="text-xs text-surface-400 mb-1">Montant</p>
                <p className="text-sm font-bold tabular-nums text-surface-800 dark:text-surface-100">{formatMGA(detail.amount)}</p>
              </div>
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-3">
                <p className="text-xs text-surface-400 mb-1">Score</p>
                <p className={`text-sm font-bold tabular-nums ${scoreColor}`}>{detail.score.toFixed(2)}</p>
              </div>
            </div>

            <div>
              <p className="text-xs font-medium text-surface-400 mb-3">Lignes de la facture</p>
              <div className="space-y-2">
                {detail.invoice_lines.map((line, i) => (
                  <div
                    key={i}
                    className={`flex items-center justify-between p-3 rounded-xl border ${
                      line.suspicious
                        ? 'bg-danger-50 dark:bg-danger-900/20'
                        : 'border-surface-300/80 dark:border-surface-600 bg-surface-100 dark:bg-surface-700/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {line.suspicious && <AlertTriangle className="w-4 h-4 text-danger-500" />}
                      <div>
                        <span className="font-mono text-xs text-surface-400 mr-2">{line.code}</span>
                        <span className="text-sm text-surface-700 dark:text-surface-200">{line.label}</span>
                        <span className="text-xs text-surface-400 ml-1">×{line.quantity}</span>
                      </div>
                    </div>
                    <span className="text-sm font-medium tabular-nums text-surface-700 dark:text-surface-200">{formatMGA(line.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Provider history */}
          <Card className="p-8">
            <div className="flex items-center gap-2 mb-4">
              <History className="w-4 h-4 text-surface-400" />
              <h3 className="font-semibold text-surface-800 dark:text-surface-100">Historique du prestataire</h3>
            </div>
            <div className="space-y-3">
              {detail.provider_history.map((h, i) => (
                <div key={i} className="flex items-center gap-3 pb-3 border-b border-surface-300/60 dark:border-surface-700 last:border-0 last:pb-0">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    h.decision === 'validated' ? 'bg-danger-50 dark:bg-danger-900/30 text-danger-600' : 'bg-success-50 dark:bg-success-900/30 text-success-600'
                  }`}>
                    {h.decision === 'validated' ? <XCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-surface-700 dark:text-surface-200">
                      {h.decision === 'validated' ? 'Fraude validée' : h.decision === 'investigating' ? 'À investiguer' : 'Alerte rejetée'} · Score {h.score.toFixed(2)}
                    </p>
                    <p className="text-xs text-surface-400">{formatDateTime(h.ts)} · {h.actor_pseudo}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right: Explanation + decision */}
        <div className="space-y-6">
          <Card className="p-8">
            <h3 className="font-semibold text-surface-800 dark:text-surface-100 mb-5">Explication de l'alerte</h3>

            {/* Risk gauge */}
            <div className="flex flex-col items-center mb-6">
              <div className="relative w-40 h-40">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 144 144">
                  <circle cx="72" cy="72" r="60" fill="none" stroke="#e2e8f0" strokeWidth="12" className="dark:stroke-surface-700" />
                  <circle
                    cx="72" cy="72" r="60" fill="none" stroke={gaugeColor} strokeWidth="12"
                    strokeDasharray={`${detail.score * 377} 377`}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={`text-3xl font-bold tabular-nums ${scoreColor}`}>{detail.score.toFixed(2)}</span>
                  <span className="text-xs text-surface-400 mt-1">Score de risque</span>
                </div>
              </div>
            </div>

            {/* SHAP-style factors */}
            <div>
              <p className="text-xs font-medium text-surface-400 mb-3">Facteurs contributifs (top 5)</p>
              <div className="space-y-3">
                {detail.top_factors.map((factor, i) => {
                  const maxImpact = Math.max(...detail.top_factors.map((f) => Math.abs(f.impact)));
                  const widthPct = (Math.abs(factor.impact) / maxImpact) * 50;
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <div className="flex-1 relative h-7 flex items-center">
                        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-surface-200 dark:bg-surface-600" />
                        <div
                          className={`absolute h-5 rounded-xl border ${
                            factor.direction === 'positive' ? 'bg-danger-400 dark:bg-danger-600' : 'bg-success-400 dark:bg-success-600'
                          }`}
                          style={
                            factor.direction === 'positive'
                              ? { left: '50%', width: `${widthPct}%` }
                              : { right: '50%', width: `${widthPct}%` }
                          }
                        />
                      </div>
                      <div className="w-64 flex-shrink-0">
                        <p className="text-xs text-surface-600 dark:text-surface-300 leading-snug">{factor.label_fr}</p>
                        <p className="text-xs text-surface-400 tabular-nums">{factor.direction === 'positive' ? '+' : ''}{factor.impact.toFixed(2)}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="flex items-center gap-4 mt-3 text-xs text-surface-400">
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-success-400" /> Réduit le risque</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-danger-400" /> Augmente le risque</span>
              </div>
            </div>
          </Card>

          {/* Prescription flags */}
          {detail.prescription_flags.length > 0 && (
            <Card className="p-8">
              <h3 className="font-semibold text-surface-800 dark:text-surface-100 mb-4">Contrôles de prescription</h3>
              <div className="space-y-2">
                {detail.prescription_flags.map((flag, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2.5 rounded-2xl bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800">
                    <ShieldAlert className="w-4 h-4 text-warning-600 flex-shrink-0" />
                    <span className="text-sm text-warning-700 dark:text-warning-300">{flag}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Decision panel */}
          {detail.status === 'pending' && (
            <Card className="p-8 sticky top-20">
              <h3 className="font-semibold text-surface-800 dark:text-surface-100 mb-2">Décision</h3>
              <div className="flex items-start gap-2 mb-4 p-3 rounded-2xl bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800">
                <Info className="w-4 h-4 text-primary-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-primary-700 dark:text-primary-300">
                  Aucune décision n'est automatique : votre validation est enregistrée et tracée.
                </p>
              </div>

              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Commentaire (requis)..."
                rows={3}
                className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 text-surface-900 dark:text-surface-100 placeholder-surface-400 px-3.5 py-2.5 text-sm mb-4 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
              />

              <div className="flex gap-3">
                <Button
                  variant="danger"
                  className="flex-1"
                  disabled={!comment.trim() || submitting}
                  onClick={() => { setDecision('validate'); setShowConfirm(true); }}
                >
                  <XCircle className="w-4 h-4" /> Valider la fraude
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  disabled={!comment.trim() || submitting}
                  onClick={() => { setDecision('reject'); setShowConfirm(true); }}
                >
                  <CheckCircle2 className="w-4 h-4" /> Rejeter l'alerte
                </Button>
              </div>
            </Card>
          )}

          {detail.status !== 'pending' && (
            <Card className="p-8">
              <div className="flex items-center gap-3">
                <Clock className="w-5 h-5 text-surface-400" />
                <div>
                  <p className="text-sm font-medium text-surface-700 dark:text-surface-200">
                    Décision: {ALERT_STATUS_LABELS[detail.status]}
                  </p>
                  <p className="text-xs text-surface-400">Cette alerte a déjà été traitée.</p>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Confirmation modal */}
      <Modal
        open={showConfirm}
        onClose={() => setShowConfirm(false)}
        title="Confirmer la décision"
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowConfirm(false)}>Annuler</Button>
            <Button
              variant={decision === 'validate' ? 'danger' : 'primary'}
              disabled={submitting}
              onClick={handleConfirm}
            >
              {submitting ? 'Enregistrement...' : 'Confirmer'}
            </Button>
          </>
        }
      >
        <p className="text-sm text-surface-600 dark:text-surface-300">
          {decision === 'validate'
            ? 'Vous allez valider cette alerte comme fraude confirmée. Cette action sera enregistrée et tracée dans le journal d\'audit.'
            : 'Vous allez rejeter cette alerte. Cette action sera enregistrée et tracée dans le journal d\'audit.'}
        </p>
      </Modal>
    </div>
  );
}
