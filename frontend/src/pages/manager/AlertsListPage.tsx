import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Search, AlertTriangle, Save, ChevronDown, ChevronUp } from 'lucide-react';
import { Card, Badge, Button, Skeleton, ErrorState, EmptyState, Input } from '@/components/ui';
import { api } from '@/lib/api';
import { formatEUR, formatDate, riskColor, ALERT_TYPE_LABELS, ALERT_STATUS_LABELS, ALERT_STATUS_COLORS } from '@/lib/format';
import type { Alert } from '@/lib/types';

const STATUS_FILTERS = [
  { value: 'all', label: 'Toutes' },
  { value: 'pending', label: 'En attente' },
  { value: 'validated', label: 'Fraudes validées' },
  { value: 'rejected', label: 'Rejetées' },
];

type SortField = 'score' | 'amount' | 'created_at';

export function AlertsListPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState('pending');
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(1);
  const perPage = 12;

  const load = () => {
    setLoading(true);
    setError(false);
    api.getAlerts({ status: filter }).then((data) => {
      setAlerts(data.items);
      setLoading(false);
    }).catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, [filter]);

  const filtered = alerts
    .filter((a) =>
      a.id.toLowerCase().includes(search.toLowerCase()) ||
      a.provider_pseudo.toLowerCase().includes(search.toLowerCase()) ||
      a.insured_pseudo.toLowerCase().includes(search.toLowerCase()) ||
      ALERT_TYPE_LABELS[a.type].toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      let cmp = 0;
      if (sortField === 'score') cmp = a.score - b.score;
      else if (sortField === 'amount') cmp = a.amount - b.amount;
      else cmp = a.created_at.localeCompare(b.created_at);
      return sortAsc ? cmp : -cmp;
    });

  const paginated = filtered.slice((page - 1) * perPage, page * perPage);
  const totalPages = Math.ceil(filtered.length / perPage);

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else { setSortField(field); setSortAsc(false); }
  };

  const SortIcon = ({ field }: { field: SortField }) =>
    sortField === field ? (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Alertes de fraude</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Analysez et traitez les alertes détectées par le modèle.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="flex-1">
          <Input
            placeholder="Rechercher par ID, prestataire, assuré, type..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            icon={<Search className="w-4 h-4" />}
          />
        </div>
        <div className="flex gap-2 overflow-x-auto scrollbar-thin pb-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => { setFilter(f.value); setPage(1); }}
              className={`px-3.5 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                filter === f.value
                  ? 'bg-primary-700 text-white'
                  : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-300 border border-surface-300 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
          </div>
        ) : error ? (
          <ErrorState message="Impossible de charger les alertes." onRetry={load} />
        ) : paginated.length === 0 ? (
          <EmptyState
            icon={<AlertTriangle className="w-8 h-8" />}
            title="Aucune alerte"
            description="Aucune alerte ne correspond à vos critères."
          />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('score')}>
                    <span className="flex items-center gap-1">Score <SortIcon field="score" /></span>
                  </th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('amount')}>
                    <span className="flex items-center gap-1">Montant <SortIcon field="amount" /></span>
                  </th>
                  <th className="px-4 py-3">Prestataire</th>
                  <th className="px-4 py-3">Assuré</th>
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('created_at')}>
                    <span className="flex items-center gap-1">Date <SortIcon field="created_at" /></span>
                  </th>
                  <th className="px-4 py-3">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {paginated.map((alert) => (
                  <tr
                    key={alert.id}
                    onClick={() => window.location.assign(`/gestionnaire/alertes/${alert.id}`)}
                    className="hover:bg-surface-50 dark:hover:bg-surface-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold tabular-nums border ${riskColor(alert.score)}`}>
                        {alert.score.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-surface-600 dark:text-surface-300">{ALERT_TYPE_LABELS[alert.type]}</td>
                    <td className="px-4 py-3 text-sm text-surface-700 dark:text-surface-200 tabular-nums font-medium">{formatEUR(alert.amount)}</td>
                    <td className="px-4 py-3 text-sm text-surface-600 dark:text-surface-300 font-mono">{alert.provider_pseudo}</td>
                    <td className="px-4 py-3 text-sm text-surface-600 dark:text-surface-300 font-mono">{alert.insured_pseudo}</td>
                    <td className="px-4 py-3 text-sm text-surface-500 tabular-nums">{formatDate(alert.created_at)}</td>
                    <td className="px-4 py-3">
                      <Badge className={ALERT_STATUS_COLORS[alert.status]}>{ALERT_STATUS_LABELS[alert.status]}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-3 ">
            <p className="text-xs text-surface-400">
              {filtered.length} alerte{filtered.length > 1 ? 's' : ''} · Page {page}/{totalPages}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Précédent</Button>
              <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(page + 1)}>Suivant</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
