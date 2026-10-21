import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Search } from 'lucide-react';
import { Badge, Card, EmptyState, ErrorState, Input, ListPagination, Skeleton } from '@/components/ui';
import { api } from '@/lib/api';
import type { Alert } from '@/lib/types';
import { ALERT_STATUS_COLORS, ALERT_STATUS_LABELS, ALERT_TYPE_LABELS, formatDate, formatMGA, riskColor } from '@/lib/format';

const STATUS_FILTERS = [
  { value: 'all', label: 'Toutes' },
  { value: 'pending', label: 'En attente' },
  { value: 'validated', label: 'Fraudes validées' },
  { value: 'rejected', label: 'Rejetées' },
];

type SortField = 'score' | 'amount' | 'created_at';

export function AlertsListPage() {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState('pending');
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const load = () => {
    setLoading(true);
    setError(false);
    api.getAlerts({ status: filter }).then((data) => {
      setAlerts(data.items);
      setLoading(false);
    }).catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, [filter]);

  const filtered = alerts.filter((alert) => (
    [alert.id, alert.provider_pseudo, alert.insured_pseudo, ALERT_TYPE_LABELS[alert.type]]
      .join(' ')
      .toLowerCase()
      .includes(search.toLowerCase())
  )).sort((a, b) => {
    const left = sortField === 'score' ? a.score : sortField === 'amount' ? a.amount : a.created_at;
    const right = sortField === 'score' ? b.score : sortField === 'amount' ? b.amount : b.created_at;
    const comparison = typeof left === 'string'
      ? left.localeCompare(right as string)
      : left - (right as number);
    return sortAsc ? comparison : -comparison;
  });

  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);
  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else { setSortField(field); setSortAsc(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Alertes de fraude</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Analysez et traitez les alertes détectées par le modèle.</p>
      </div>
      <div className="flex flex-col md:flex-row gap-3">
        <div className="flex-1">
          <Input placeholder="Rechercher par ID, prestataire, assuré, type..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} icon={<Search className="w-4 h-4" />} />
        </div>
        <div className="flex gap-2 overflow-x-auto scrollbar-thin pb-1">
          {STATUS_FILTERS.map((item) => (
            <button key={item.value} onClick={() => { setFilter(item.value); setPage(1); }} className={`px-[18px] py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-all ${filter === item.value ? 'bg-primary-700 text-white' : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-300 border border-surface-300 dark:border-surface-700'}`}>
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <Card className="overflow-hidden">
        {loading ? <div className="p-8 space-y-3">{[1, 2, 3, 4, 5].map((item) => <Skeleton key={item} className="h-14 w-full" />)}</div>
          : error ? <ErrorState message="Impossible de charger les alertes." onRetry={load} />
          : paginated.length === 0 ? <EmptyState icon={<AlertTriangle className="w-8 h-8" />} title="Aucune alerte" description="Aucune alerte ne correspond à vos critères." />
          : <div className="overflow-x-auto scrollbar-thin"><table className="w-full"><thead><tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
            <th className="px-6 py-3.5 cursor-pointer" onClick={() => toggleSort('score')}>Score</th>
            <th className="px-6 py-3.5">Type</th>
            <th className="px-6 py-3.5 cursor-pointer" onClick={() => toggleSort('amount')}>Montant</th>
            <th className="px-6 py-3.5">Prestataire</th><th className="px-6 py-3.5">Assuré</th>
            <th className="px-6 py-3.5 cursor-pointer" onClick={() => toggleSort('created_at')}>Date</th><th className="px-6 py-3.5">Statut</th>
          </tr></thead><tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
            {paginated.map((alert) => <tr key={alert.id} onClick={() => navigate(`/gestionnaire/alertes/${alert.id}`)} className="hover:bg-surface-50 dark:hover:bg-surface-700/50 cursor-pointer">
              <td className="px-6 py-4"><span className={`inline-flex px-2.5 py-1 rounded-md text-xs font-semibold border ${riskColor(alert.score)}`}>{alert.score.toFixed(6)}</span></td>
              <td className="px-6 py-4 text-sm">{ALERT_TYPE_LABELS[alert.type]}</td><td className="px-6 py-4 text-sm">{formatMGA(alert.amount)}</td>
              <td className="px-6 py-4 text-sm font-mono">{alert.provider_pseudo}</td><td className="px-6 py-4 text-sm font-mono">{alert.insured_pseudo}</td>
              <td className="px-6 py-4 text-sm">{formatDate(alert.created_at)}</td><td className="px-6 py-4"><Badge className={ALERT_STATUS_COLORS[alert.status]}>{ALERT_STATUS_LABELS[alert.status]}</Badge></td>
            </tr>)}
          </tbody></table></div>}
        {!loading && !error && filtered.length > 0 && (
          <ListPagination
            page={page}
            pageSize={pageSize}
            total={filtered.length}
            onPageChange={setPage}
            onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
          />
        )}
      </Card>
    </div>
  );
}
