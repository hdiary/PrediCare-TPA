import { useEffect, useRef, useState } from 'react';
import {
  FileText, Target, AlertTriangle, Euro, Banknote, ArrowRight, Clock,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { Card, Skeleton, ErrorState } from '@/components/ui';
import { api } from '@/lib/api';
import { formatMGA, formatPercent, formatDate, riskColor, ALERT_TYPE_LABELS } from '@/lib/format';
import type { Alert, BIKpiData, BIModelData } from '@/lib/types';

const ICON_TONES: Record<string, string> = {
  primary: 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300',
  success: 'bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300',
  kraft: 'bg-kraft-100 text-kraft-700 dark:bg-kraft-900/40 dark:text-kraft-300',
  warning: 'bg-warning-50 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300',
};

export function ManagerDashboard() {
  const [kpis, setKpis] = useState<BIKpiData | null>(null);
  const [model, setModel] = useState<BIModelData | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const hasLoaded = useRef(false);

  useEffect(() => {
    let active = true;
    let refreshing = false;
    const refresh = () => {
      if (refreshing || document.visibilityState === 'hidden') return;
      refreshing = true;
      Promise.all([api.getBIKPIs(), api.getAlerts({ status: 'pending' }), api.getBIModel()])
        .then(([k, a, m]) => {
          if (!active) return;
          setKpis(k);
          setAlerts(a.items.slice(0, 5));
          setModel(m);
          hasLoaded.current = true;
          setError(false);
        })
        .catch(() => { if (active && !hasLoaded.current) setError(true); })
        .finally(() => {
          refreshing = false;
          if (active) setLoading(false);
        });
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    refresh();
    const timer = window.setInterval(refresh, 15 * 1000);
    window.addEventListener('focus', refresh);
    window.addEventListener('predicare:data-updated', refresh);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('predicare:data-updated', refresh);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (error || !kpis || !model) return <ErrorState message="Impossible de charger le tableau de bord." />;

  const kpiCards = [
    { label: 'Factures enregistrées', value: kpis.factures_enregistrees.toLocaleString('fr-FR'), icon: <FileText className="w-5 h-5" />, color: 'primary' },
    { label: 'Factures scorées', value: kpis.factures_traitees.toLocaleString('fr-FR'), icon: <Target className="w-5 h-5" />, color: 'primary' },
    { label: 'Montant réclamé', value: formatMGA(kpis.montant_reclame), icon: <Euro className="w-5 h-5" />, color: 'primary' },
    { label: 'Montant remboursé', value: formatMGA(kpis.montant_rembourse), icon: <Banknote className="w-5 h-5" />, color: 'success' },
    { label: 'Montant à risque', value: formatMGA(kpis.montant_a_risque), icon: <Target className="w-5 h-5" />, color: 'warning' },
    { label: 'Montant économisé', value: formatMGA(kpis.montant_economise), icon: <Euro className="w-5 h-5" />, color: 'success' },
    { label: 'Taux d’alerte', value: kpis.taux_alerte === null ? 'N/A' : formatPercent(kpis.taux_alerte), icon: <AlertTriangle className="w-5 h-5" />, color: 'kraft' },
    { label: 'Précision opérationnelle', value: kpis.precision_operationnelle === null ? 'N/A' : formatPercent(kpis.precision_operationnelle), icon: <Target className="w-5 h-5" />, color: 'success' },
    { label: 'Alertes en attente', value: kpis.alertes_en_attente.toString(), icon: <AlertTriangle className="w-5 h-5" />, color: 'warning' },
  ];

  return (
    <div className="space-y-6">
      {kpis.stale && (
        <div role="status" className="rounded-xl border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-800 dark:border-warning-800 dark:bg-warning-900/30 dark:text-warning-200">
          Données BI potentiellement anciennes
          {kpis.date_rafraichissement && ` — dernière mise à jour : ${new Date(kpis.date_rafraichissement).toLocaleString('fr-FR')}`}
          {kpis.erreur_rafraichissement && ` — ${kpis.erreur_rafraichissement}`}
        </div>
      )}
      {kpis.date_rafraichissement && !kpis.stale && (
        <p className="text-xs text-surface-400">
          Données au {new Date(kpis.date_rafraichissement).toLocaleString('fr-FR')}
        </p>
      )}
      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {kpiCards.map((card) => (
          <Card key={card.label} className="p-5 hover:shadow-card transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${ICON_TONES[card.color]}`}>
                {card.icon}
              </div>
            </div>
            <p className="text-xs text-surface-400 mb-1">{card.label}</p>
            <p className="text-2xl font-bold text-surface-800 dark:text-surface-100 tabular-nums">{card.value}</p>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-8">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200 mb-1">Factures vs Alertes</h3>
          <p className="text-xs text-surface-400 mb-4">Évolution quotidienne</p>
          {kpis.par_jour.length === 0 && (
            <p className="mb-2 text-xs text-surface-400">Aucune facture sur la période affichée.</p>
          )}
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={kpis.par_jour.map((point) => ({ date: point.jour, invoices: point.factures, alerts: point.alertes }))}>
              <CartesianGrid strokeDasharray="0" vertical={false} stroke="#86A8A4" strokeOpacity={0.25} />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "rgba(134,168,164,0.12)" }}
                contentStyle={{ borderRadius: '12px', border: '1px solid #1D4A4D', boxShadow: 'none', backgroundColor: '#0F2A2E', color: '#E8F1F0', fontSize: '12px', padding: '10px 14px' }}
                labelStyle={{ color: '#E8F1F0' }} itemStyle={{ color: '#C9D8D6' }}
              />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Line type="monotone" dataKey="invoices" stroke="#14B8A6" strokeWidth={2.5} name="Factures" dot={{ r: 3 }} />
              <Line type="monotone" dataKey="alerts" stroke="#D9622B" strokeWidth={2.5} name="Alertes" dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-8">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200 mb-1">Montant économisé</h3>
          <p className="text-xs text-surface-400 mb-4">Par jour (MGA)</p>
          {kpis.par_jour.length === 0 && (
            <p className="mb-2 text-xs text-surface-400">Aucune décision enregistrée sur la période affichée.</p>
          )}
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={kpis.par_jour.map((point) => ({ date: point.jour, saved: point.montant_economise }))}>
              <CartesianGrid strokeDasharray="0" vertical={false} stroke="#86A8A4" strokeOpacity={0.25} />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "rgba(134,168,164,0.12)" }}
                contentStyle={{ borderRadius: '12px', border: '1px solid #1D4A4D', boxShadow: 'none', backgroundColor: '#0F2A2E', color: '#E8F1F0', fontSize: '12px', padding: '10px 14px' }}
                formatter={(value) => [formatMGA(Number(value)), 'Économisé']}
              />
              <Bar dataKey="saved" fill="#14B8A6" radius={[6, 6, 0, 0]} barSize={28} name="Économisé" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-6">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200 mb-3">Prestataires à risque</h3>
          {kpis.top_prestataires.length === 0 && <p className="text-sm text-surface-400">Aucune alerte enregistrée</p>}
          <ul className="space-y-2">
            {kpis.top_prestataires.slice(0, 5).map((provider) => (
              <li key={provider.prestataire_id} className="flex justify-between gap-3 text-sm text-surface-600 dark:text-surface-300">
                <span className="truncate">{provider.prestataire_nom || provider.prestataire_id}</span>
                <span className="font-semibold tabular-nums">{provider.alertes}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-6">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200 mb-4">Distribution des scores</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={kpis.distribution_scores}>
              <CartesianGrid strokeDasharray="0" vertical={false} stroke="#86A8A4" strokeOpacity={0.25} />
              <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#14B8A6" radius={[4, 4, 0, 0]} name="Prédictions" />
              {kpis.seuil_alerte !== null && (
                <ReferenceLine x={Math.ceil(kpis.seuil_alerte * 10)} stroke="#D9622B" label="Seuil" />
              )}
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-surface-400">
            Seuil d'alerte : {kpis.seuil_alerte === null ? 'N/A' : kpis.seuil_alerte.toFixed(2)}
          </p>
        </Card>

        <Card className="p-6">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200 mb-3">FinOps RAG</h3>
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Jetons : {(kpis.rag_finops.tokens_entree + kpis.rag_finops.tokens_sortie).toLocaleString('fr-FR')}
          </p>
          <p className="mt-2 text-sm text-surface-500">
            Cache hit : {kpis.rag_finops.taux_cache_hit === null ? 'N/A' : formatPercent(kpis.rag_finops.taux_cache_hit)}
          </p>
          <p className="mt-2 text-xs text-surface-400">
            Coût estimé : {kpis.rag_finops.cout_estime === null ? 'N/A (tarification non configurée)' : formatMGA(kpis.rag_finops.cout_estime)}
          </p>
          <p className="mt-2 text-xs text-surface-400">
            Latence p50 / p95 : {kpis.rag_finops.latence_p50_ms?.toFixed(0) ?? 'N/A'} / {kpis.rag_finops.latence_p95_ms?.toFixed(0) ?? 'N/A'} ms
          </p>
        </Card>

        <Card className="p-6">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200 mb-3">Modèle actif</h3>
          <p className="text-lg font-bold text-surface-800 dark:text-surface-100">{model.version_active ?? 'N/A'}</p>
          <p className="mt-3 text-sm text-surface-500">
            Rappel hors ligne : {model.rappel_hors_ligne === null ? 'N/A' : formatPercent(model.rappel_hors_ligne)}
          </p>
          <p className="mt-1 text-sm text-surface-500">
            AUC-PR : {model.auc_pr === null ? 'N/A' : model.auc_pr.toFixed(3)}
          </p>
          <p className="mt-3 text-xs text-surface-400">
            Dérive PSI : {model.derive_disponible && model.derive_psi !== null ? model.derive_psi.toFixed(3) : 'N/A (référence absente)'}
          </p>
        </Card>

        <Card className="p-6">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200 mb-3">Notifications</h3>
          {kpis.notifications.length === 0 && <p className="text-sm text-surface-400">Aucune notification enregistrée</p>}
          <ul className="space-y-2">
            {kpis.notifications.map(({ etat, count }) => (
              <li key={etat} className="flex justify-between text-sm text-surface-600 dark:text-surface-300">
                <span>{etat}</span><span className="font-semibold tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
          <h4 className="mt-5 text-xs font-semibold text-surface-500">Rejets invalides par code</h4>
          {kpis.factures_rejetees.length === 0 && <p className="mt-2 text-sm text-surface-400">Aucun rejet invalide enregistré</p>}
          <ul className="mt-2 space-y-1">
            {kpis.factures_rejetees.slice(0, 5).map(({ code, count }) => (
              <li key={code} className="flex justify-between text-xs text-surface-500">
                <span>{code}</span><span className="tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Priority alerts */}
      <Card className="p-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200">Alertes prioritaires</h3>
            <p className="text-xs text-surface-400">Les alertes les plus récentes en attente</p>
          </div>
          <Link to="/gestionnaire/alertes" className="flex items-center gap-1 text-sm text-primary-700 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 font-medium">
            Voir tout <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="space-y-2">
          {alerts.map((alert) => (
            <Link
              key={alert.id}
              to={`/gestionnaire/alertes/${alert.id}`}
              className="flex items-center gap-4 p-3 rounded-[12px] border border-surface-300/80 dark:border-surface-700 bg-white dark:bg-surface-800 hover:bg-surface-100 dark:hover:bg-surface-700 transition-all"
            >
              <div className={`px-2.5 py-1 rounded-md text-xs font-semibold tabular-nums border ${riskColor(alert.score)}`}>
                {alert.score.toFixed(2)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200">{ALERT_TYPE_LABELS[alert.type] || alert.type}</p>
                <p className="text-xs text-surface-400 font-mono">{alert.provider_pseudo} · {alert.insured_pseudo}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold tabular-nums text-surface-700 dark:text-surface-200">{formatMGA(alert.amount)}</p>
                <p className="text-xs text-surface-400 flex items-center gap-1 justify-end">
                  <Clock className="w-3 h-3" /> {formatDate(alert.created_at)}
                </p>
              </div>
            </Link>
          ))}
          {alerts.length === 0 && (
            <p className="text-sm text-surface-400 text-center py-6">Aucune alerte en attente</p>
          )}
        </div>
      </Card>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Skeleton className="h-72" />
        <Skeleton className="h-72" />
      </div>
      <Skeleton className="h-64" />
    </div>
  );
}
