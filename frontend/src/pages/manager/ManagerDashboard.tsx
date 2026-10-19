import { useEffect, useState } from 'react';
import {
  TrendingUp, TrendingDown, FileText, Euro, Target, AlertTriangle,
  ArrowRight, Clock,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { Card, Skeleton, ErrorState, Badge } from '@/components/ui';
import { api } from '@/lib/api';
import { formatEUR, formatPercent, formatDate, riskColor, ALERT_TYPE_LABELS } from '@/lib/format';
import type { BIKpiData, AlertApiSummary } from '@/lib/types';

const ICON_TONES: Record<string, string> = {
  primary: 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300',
  success: 'bg-success-50 text-success-700 dark:bg-success-900/30 dark:text-success-300',
  kraft: 'bg-kraft-100 text-kraft-700 dark:bg-kraft-900/40 dark:text-kraft-300',
  warning: 'bg-warning-50 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300',
};

export function ManagerDashboard() {
  const [kpis, setKpis] = useState<BIKpiData | null>(null);
  const [alerts, setAlerts] = useState<AlertApiSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([api.getBIKPIs(), api.getAlerts({ status: 'EN_ATTENTE' })])
      .then(([k, a]) => { setKpis(k); setAlerts(a.items.slice(0, 5)); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (error || !kpis) return <ErrorState message="Impossible de charger le tableau de bord." />;

  const kpiCards = [
    { label: 'Factures traitées', value: kpis.factures_traitees.toLocaleString('fr-FR'), icon: <FileText className="w-5 h-5" />, trend: '', trendUp: true, color: 'primary' },
    { label: 'Montant à risque', value: formatEUR(kpis.montant_a_risque), icon: <Euro className="w-5 h-5" />, trend: '', trendUp: true, color: 'warning' },
    { label: 'Taux d’alerte', value: formatPercent(kpis.taux_alerte), icon: <Target className="w-5 h-5" />, trend: '', trendUp: true, color: 'kraft' },
    { label: 'Alertes en attente', value: kpis.alertes_en_attente.toString(), icon: <AlertTriangle className="w-5 h-5" />, trend: '', trendUp: false, color: 'warning' },
  ];

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpiCards.map((card) => (
          <Card key={card.label} className="p-5 hover:shadow-card transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${ICON_TONES[card.color]}`}>
                {card.icon}
              </div>
              <div className={`flex items-center gap-1 text-xs font-medium ${card.trendUp ? 'text-success-600' : 'text-danger-600'}`}>
                {card.trendUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {card.trend || '—'}
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
          <p className="text-xs text-surface-400 mb-4">Évolution hebdomadaire</p>
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
          <p className="text-xs text-surface-400 mb-4">Par semaine (EUR)</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={kpis.par_jour.map((point) => ({ date: point.jour, saved: 0 }))}>
              <CartesianGrid strokeDasharray="0" vertical={false} stroke="#86A8A4" strokeOpacity={0.25} />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#86A8A4' }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "rgba(134,168,164,0.12)" }}
                contentStyle={{ borderRadius: '12px', border: '1px solid #1D4A4D', boxShadow: 'none', backgroundColor: '#0F2A2E', color: '#E8F1F0', fontSize: '12px', padding: '10px 14px' }}
                formatter={(value) => [formatEUR(Number(value)), 'Économisé']}
              />
              <Bar dataKey="saved" fill="#14B8A6" radius={[6, 6, 0, 0]} barSize={28} name="Économisé" />
            </BarChart>
          </ResponsiveContainer>
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
              key={alert.facture_id}
              to={`/gestionnaire/alertes/${alert.facture_id}`}
              className="flex items-center gap-4 p-3 rounded-[12px] border border-surface-300/80 dark:border-surface-700 bg-white dark:bg-surface-800 hover:bg-surface-100 dark:hover:bg-surface-700 transition-all"
            >
              <div className={`px-2.5 py-1 rounded-md text-xs font-semibold tabular-nums border ${riskColor(alert.score)}`}>
                {alert.score.toFixed(2)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200">{ALERT_TYPE_LABELS[alert.type] || alert.type}</p>
                <p className="text-xs text-surface-400 font-mono">{alert.prestataire_id} · {alert.assure_id}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold tabular-nums text-surface-700 dark:text-surface-200">{formatEUR(alert.montant_total)}</p>
                <p className="text-xs text-surface-400 flex items-center gap-1 justify-end">
                  <Clock className="w-3 h-3" /> {formatDate(alert.date)}
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
