import { useState, useEffect } from 'react';
import { Search, ScrollText, Download } from 'lucide-react';
import { Card, Button, Skeleton, ErrorState, EmptyState, Input } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import type { AuditLogEntry } from '@/lib/types';

export function AdminAuditLog() {
  const { showToast } = useToast();
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('all');

  const ACTIONS = [
    { value: 'all', label: 'Toutes les actions' },
    { value: 'décision', label: 'Décisions' },
    { value: 'modèle', label: 'Modèles' },
    { value: 'seuil', label: 'Configuration' },
    { value: 'facture', label: 'Factures' },
  ];

  const load = () => {
    setLoading(true);
    setError(false);
    api.getAuditLog().then((data) => { setEntries(data.items); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, []);

  const filtered = entries.filter((e) => {
    const matchSearch = e.actor_pseudo.toLowerCase().includes(search.toLowerCase()) ||
      e.object.toLowerCase().includes(search.toLowerCase()) ||
      e.action.toLowerCase().includes(search.toLowerCase());
    const matchAction = actionFilter === 'all' ||
      (actionFilter === 'décision' && e.action.toLowerCase().includes('décision')) ||
      (actionFilter === 'modèle' && e.action.toLowerCase().includes('modèle')) ||
      (actionFilter === 'seuil' && e.action.toLowerCase().includes('seuil')) ||
      (actionFilter === 'facture' && e.action.toLowerCase().includes('facture'));
    return matchSearch && matchAction;
  });

  const exportCSV = () => {
    const headers = ['Horodatage', 'Acteur', 'Action', 'Objet', 'Version du modèle'];
    const rows = filtered.map((e) => [e.ts, e.actor_pseudo, e.action, e.object, e.model_version]);
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${c}"`).join(',')).join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `journal_audit_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Journal exporté en CSV', 'success');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Journal d'audit</h2>
          <p className="text-sm text-surface-500 dark:text-surface-400">Traçabilité de toutes les actions du système.</p>
        </div>
        <Button variant="outline" onClick={exportCSV} disabled={filtered.length === 0}>
          <Download className="w-4 h-4" /> Exporter CSV
        </Button>
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="flex-1">
          <Input
            placeholder="Rechercher par acteur, action, objet..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={<Search className="w-4 h-4" />}
          />
        </div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 text-surface-700 dark:text-surface-200 px-4 py-2.5 text-sm focus:border-primary-500"
        >
          {ACTIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
        </select>
      </div>

      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
          </div>
        ) : error ? (
          <ErrorState message="Impossible de charger le journal." onRetry={load} />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<ScrollText className="w-8 h-8" />}
            title="Aucune entrée"
            description="Aucune action ne correspond à vos critères."
          />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
                  <th className="px-6 py-3.5">Horodatage</th>
                  <th className="px-6 py-3.5">Acteur</th>
                  <th className="px-6 py-3.5">Action</th>
                  <th className="px-6 py-3.5">Objet</th>
                  <th className="px-6 py-3.5">Modèle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {filtered.map((entry, i) => (
                  <tr key={i} className="hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors">
                    <td className="px-6 py-3.5 text-sm text-surface-500 dark:text-surface-400 tabular-nums whitespace-nowrap">{formatDateTime(entry.ts)}</td>
                    <td className="px-6 py-3.5 text-sm font-mono text-surface-600 dark:text-surface-300">{entry.actor_pseudo}</td>
                    <td className="px-6 py-3.5 text-sm text-surface-700 dark:text-surface-200">{entry.action}</td>
                    <td className="px-6 py-3.5 text-sm font-mono text-surface-600 dark:text-surface-300">{entry.object}</td>
                    <td className="px-6 py-3.5 text-sm text-surface-500 dark:text-surface-400 font-mono">{entry.model_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
