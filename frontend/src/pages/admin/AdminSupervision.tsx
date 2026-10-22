import { useState, useEffect } from 'react';
import {
  Server, Database, Brain, Workflow, Activity,
  AlertTriangle, Zap, Timer, TrendingDown,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import { Card, Skeleton, ErrorState, Badge } from '@/components/ui';
import { api } from '@/lib/api';
import { serviceStateColor, SERVICE_LABELS, formatNumber } from '@/lib/format';
import type { BIKpiData, ServiceStatus, SystemMetrics } from '@/lib/types';

const TIME_RANGES = [
  { value: '24h', label: '24h' },
  { value: '7d', label: '7 jours' },
  { value: '30d', label: '30 jours' },
];

const SERVICE_ICONS: Record<string, React.ReactNode> = {
  api: <Server className="w-5 h-5" />,
  database: <Database className="w-5 h-5" />,
  model: <Brain className="w-5 h-5" />,
  n8n: <Workflow className="w-5 h-5" />,
};

const STATE_LABELS: Record<string, string> = {
  ok: 'Opérationnel',
  degraded: 'Dégradé',
  down: 'Hors service',
  unknown: 'Non surveillé',
};

export function AdminSupervision() {
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [biKpis, setBiKpis] = useState<BIKpiData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [timeRange, setTimeRange] = useState('24h');

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([api.getServiceStatus(), api.getSystemMetrics(timeRange), api.getBIKPIs()])
      .then(([s, m, bi]) => { setStatus(s); setMetrics(m); setBiKpis(bi); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, [timeRange]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (error || !status || !metrics || !biKpis) {
    return <ErrorState message="Impossible de charger les données de supervision." onRetry={load} />;
  }

  const driftHigh = metrics.drift_psi !== null && metrics.drift_psi > 0.1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Supervision système</h2>
          <p className="text-sm text-surface-500 dark:text-surface-400">État des services et métriques en temps réel.</p>
        </div>
        <div className="flex gap-2">
          {TIME_RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setTimeRange(r.value)}
              className={`px-3 py-1.5 rounded-2xl text-sm font-medium transition-all ${
                timeRange === r.value
                  ? 'bg-primary-700 text-white'
                  : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-300 border border-surface-300 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-700'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Drift alert banner */}
      {biKpis.stale && (
        <div role="status" className="rounded-xl border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-800 dark:border-warning-800 dark:bg-warning-900/30 dark:text-warning-200">
          Données BI potentiellement anciennes
          {biKpis.date_rafraichissement && ` — dernière mise à jour : ${new Date(biKpis.date_rafraichissement).toLocaleString('fr-FR')}`}
          {biKpis.erreur_rafraichissement && ` — ${biKpis.erreur_rafraichissement}`}
        </div>
      )}

      {driftHigh && (
        <div className="flex items-center gap-3 px-[18px] py-4 rounded-xl bg-danger-50 dark:bg-danger-900/30 border border-danger-200 dark:border-danger-800 animate-fade-in">
          <AlertTriangle className="w-5 h-5 text-danger-600 flex-shrink-0" />
          <p className="text-sm text-danger-700 dark:text-danger-300">
            <strong>Dérive du modèle détectée.</strong> Le PSI ({metrics.drift_psi?.toFixed(3)}) dépasse le seuil de 0,10. Une réévaluation du modèle est recommandée.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          { label: 'Factures traitées', value: formatNumber(biKpis.factures_traitees) },
          { label: 'Montant à risque', value: `${formatNumber(biKpis.montant_a_risque)} MGA` },
          { label: 'Montant économisé', value: `${formatNumber(biKpis.montant_economise)} MGA` },
          { label: 'Précision opérationnelle', value: biKpis.precision_operationnelle === null ? 'N/A' : `${(biKpis.precision_operationnelle * 100).toFixed(1)}%` },
        ].map((stat) => (
          <Card key={stat.label} className="p-4">
            <p className="text-xs text-surface-400">{stat.label}</p>
            <p className="mt-1 text-lg font-bold tabular-nums text-surface-800 dark:text-surface-100">{stat.value}</p>
          </Card>
        ))}
      </div>

      {/* Service status cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(status).filter(([key]) => key !== 'vector_db').map(([key, state]) => (
          <Card key={key} className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="w-8 h-8 rounded-lg bg-surface-100 dark:bg-surface-700 flex items-center justify-center text-surface-500 dark:text-surface-300">
                {SERVICE_ICONS[key]}
              </div>
              <span className={`w-2.5 h-2.5 rounded-full ${serviceStateColor(state)} ${state === 'degraded' || state === 'down' ? 'animate-pulse' : ''}`} />
            </div>
            <p className="text-sm font-semibold text-surface-700 dark:text-surface-200">{SERVICE_LABELS[key]}</p>
            <p className={`text-xs mt-0.5 ${state === 'ok' ? 'text-success-600' : state === 'degraded' ? 'text-warning-600' : 'text-danger-600'}`}>
              {STATE_LABELS[state]}
            </p>
          </Card>
        ))}
      </div>

      {/* Live metrics charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-8">
          <div className="flex items-center gap-2 mb-4">
            <Timer className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200">Latence p95 (ms)</h3>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={metrics.series}>
              <defs>
                <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#14B8A6" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#14B8A6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="0" vertical={false} stroke="#86A8A4" strokeOpacity={0.25} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <Tooltip labelStyle={{ color: '#E8F1F0' }} itemStyle={{ color: '#C9D8D6' }} contentStyle={{ borderRadius: '12px', border: '1px solid #1D4A4D', boxShadow: 'none', backgroundColor: '#0F2A2E', color: '#E8F1F0', fontSize: '12px', padding: '10px 14px' }} />
              <Area type="monotone" dataKey="latency" stroke="#14B8A6" strokeWidth={2} fill="url(#latGrad)" name="Latence (ms)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-8">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200">Requêtes / min depuis le démarrage</h3>
          </div>
          <p className="text-4xl font-bold tabular-nums text-surface-800 dark:text-surface-100">{formatNumber(metrics.requests_per_min)}</p>
          <p className="mt-3 text-xs text-surface-400">Compteur HTTP en mémoire, remis à zéro au redémarrage de l'API.</p>
        </Card>

        <Card className="p-8">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200">Taux d'erreur HTTP 5xx</h3>
          </div>
          <p className="text-4xl font-bold tabular-nums text-surface-800 dark:text-surface-100">
            {metrics.error_rate === null ? 'N/A' : `${(metrics.error_rate * 100).toFixed(2)}%`}
          </p>
          <p className="mt-3 text-xs text-surface-400">Erreurs 5xx depuis le démarrage de l'API.</p>
        </Card>

        {/* Drift card */}
        <Card className="p-8">
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-200">Dérive du modèle (PSI)</h3>
          </div>
          <div className="flex items-center gap-6 mb-4">
            <div className="flex flex-col items-center">
              <span className={`text-4xl font-bold tabular-nums ${driftHigh ? 'text-danger-600' : 'text-success-600'}`}>
                {metrics.drift_psi === null ? 'N/A' : metrics.drift_psi.toFixed(3)}
              </span>
              <span className="text-xs text-surface-400 mt-1">PSI actuel</span>
            </div>
            <div className="flex-1">
              <div className="relative h-3 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
                <div
                  className={`absolute h-full rounded-full transition-all ${driftHigh ? 'bg-danger-500' : 'bg-success-500'}`}
                  style={{ width: `${Math.min((metrics.drift_psi ?? 0) / 0.2 * 100, 100)}%` }}
                />
                <div className="absolute h-full w-px bg-surface-500" style={{ left: '50%' }} />
              </div>
              <div className="flex justify-between text-xs text-surface-400 mt-1">
                <span>0</span>
                <span className="font-medium text-warning-600">Seuil: 0,10</span>
                <span>0,20+</span>
              </div>
            </div>
          </div>
          {metrics.drift_psi === null && (
            <p className="text-sm text-surface-500">N/A — la distribution de référence d'entraînement n'est pas configurée.</p>
          )}
        </Card>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Latence p95', value: metrics.latency_p95_ms === null ? 'N/A' : `${metrics.latency_p95_ms} ms`, icon: <Timer className="w-4 h-4" /> },
          { label: 'Requêtes/min', value: formatNumber(metrics.requests_per_min), icon: <Zap className="w-4 h-4" /> },
          { label: 'Taux d\'erreur', value: metrics.error_rate === null ? 'N/A' : `${(metrics.error_rate * 100).toFixed(2)}%`, icon: <Activity className="w-4 h-4" /> },
          { label: 'Dérive PSI', value: metrics.drift_psi === null ? 'N/A' : metrics.drift_psi.toFixed(3), icon: <TrendingDown className="w-4 h-4" />, badge: driftHigh },
        ].map((stat) => (
          <Card key={stat.label} className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-surface-100 dark:bg-surface-700 flex items-center justify-center text-surface-500">
              {stat.icon}
            </div>
            <div>
              <p className="text-xs text-surface-400">{stat.label}</p>
              <div className="flex items-center gap-2">
                <p className="text-lg font-bold tabular-nums text-surface-800 dark:text-surface-100">{stat.value}</p>
                {stat.badge && <Badge className="bg-danger-100 text-danger-700 dark:bg-danger-900 dark:text-danger-200">Élevé</Badge>}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
