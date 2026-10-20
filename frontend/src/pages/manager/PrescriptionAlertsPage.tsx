import { useState, useEffect } from 'react';
import { Search, ClipboardList } from 'lucide-react';
import { Card, Badge, Skeleton, ErrorState, EmptyState, Input, Drawer, ListPagination } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate, PRESCRIPTION_RULES, PRESCRIPTION_SEVERITY } from '@/lib/format';
import type { PrescriptionAlert } from '@/lib/types';

const RULE_FILTERS = [
  { value: 'all', label: 'Toutes' },
  ...Object.entries(PRESCRIPTION_RULES).map(([value, r]) => ({ value, label: r.label })),
];

function SeverityBadge({ severity }: { severity: number }) {
  const s = PRESCRIPTION_SEVERITY[severity];
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border ${s.className}`}>
      {s.label}
    </span>
  );
}

export function PrescriptionAlertsPage() {
  const [alerts, setAlerts] = useState<PrescriptionAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [rule, setRule] = useState('all');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<PrescriptionAlert | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const load = () => {
    setLoading(true);
    setError(false);
    api.getPrescriptionAlerts({ rule })
      .then((data) => { setAlerts(data.items); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, [rule]);

  const q = search.toLowerCase();
  const filtered = alerts
    .filter((a) =>
      a.prescription_id.toLowerCase().includes(q) ||
      a.prescriber_pseudo.toLowerCase().includes(q) ||
      a.insured_pseudo.toLowerCase().includes(q) ||
      a.detail.toLowerCase().includes(q))
    .sort((a, b) => b.severity - a.severity || b.prescription_date.localeCompare(a.prescription_date));
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const grave = alerts.filter((a) => a.severity === 3).length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Anomalies de prescription</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Contrôle des ordonnances : doublons, inadéquation avec le diagnostic, prescripteurs non conformes.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-xs text-surface-500 mb-1">Ordonnances signalées</p>
          <p className="text-2xl font-bold text-surface-800 dark:text-surface-100 tabular-nums">{alerts.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-surface-500 mb-1">Alertes graves</p>
          <p className="text-2xl font-bold text-danger-600 tabular-nums">{grave}</p>
        </Card>
      </div>

      <div className="flex flex-col gap-3">
        <Input
          placeholder="Rechercher par ordonnance, prescripteur, assuré, détail..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          icon={<Search className="w-4 h-4" />}
        />
        <div className="flex gap-2 overflow-x-auto scrollbar-thin pb-1">
          {RULE_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => { setRule(f.value); setPage(1); }}
              className={`px-[18px] py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-all ${
                rule === f.value
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
          <div className="p-8 space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
        ) : error ? (
          <ErrorState message="Impossible de charger les anomalies de prescription." onRetry={load} />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<ClipboardList className="w-8 h-8" />}
            title="Aucune anomalie"
            description="Aucune ordonnance ne correspond à vos critères."
          />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
                  <th className="px-4 md:px-6 py-3.5">Gravité</th>
                  <th className="px-4 md:px-6 py-3.5">Anomalie</th>
                  <th className="px-4 md:px-6 py-3.5">Ordonnance</th>
                  <th className="px-4 md:px-6 py-3.5 hidden md:table-cell">Prescripteur</th>
                  <th className="px-4 md:px-6 py-3.5 hidden md:table-cell">Assuré</th>
                  <th className="px-4 md:px-6 py-3.5">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {paginated.map((a) => (
                  <tr
                    key={a.id}
                    onClick={() => setSelected(a)}
                    className="hover:bg-surface-50 dark:hover:bg-surface-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 md:px-6 py-4"><SeverityBadge severity={a.severity} /></td>
                    <td className="px-4 md:px-6 py-4 text-sm text-surface-700 dark:text-surface-200">{PRESCRIPTION_RULES[a.rule].label}</td>
                    <td className="px-4 md:px-6 py-4 text-sm text-surface-600 dark:text-surface-300 font-mono">{a.prescription_id}</td>
                    <td className="px-4 md:px-6 py-4 text-sm text-surface-600 dark:text-surface-300 font-mono hidden md:table-cell">{a.prescriber_pseudo}</td>
                    <td className="px-4 md:px-6 py-4 text-sm text-surface-600 dark:text-surface-300 font-mono hidden md:table-cell">{a.insured_pseudo}</td>
                    <td className="px-4 md:px-6 py-4 text-sm text-surface-500 tabular-nums">{formatDate(a.prescription_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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

      <Drawer open={!!selected} onClose={() => setSelected(null)} title={selected ? selected.prescription_id : ''}>
        {selected && (
          <div className="space-y-6">
            <div className="flex items-center gap-3">
              <SeverityBadge severity={selected.severity} />
              <Badge className="bg-surface-200 text-surface-700 dark:bg-surface-700 dark:text-surface-200">
                {PRESCRIPTION_RULES[selected.rule].label}
              </Badge>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-500 mb-1">Ce qui a été détecté</p>
              <p className="text-sm text-surface-800 dark:text-surface-100">{selected.detail}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-500 mb-1">Ce que cela signifie</p>
              <p className="text-sm text-surface-600 dark:text-surface-300">{PRESCRIPTION_RULES[selected.rule].meaning}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-500 mb-1">À vérifier</p>
              <p className="text-sm text-surface-600 dark:text-surface-300">{PRESCRIPTION_RULES[selected.rule].check}</p>
            </div>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div><dt className="text-xs text-surface-500">Diagnostic</dt><dd className="text-surface-800 dark:text-surface-100">{selected.diagnosis ?? 'Non renseigné'}</dd></div>
              <div><dt className="text-xs text-surface-500">Date de prescription</dt><dd className="text-surface-800 dark:text-surface-100">{formatDate(selected.prescription_date)}</dd></div>
              <div><dt className="text-xs text-surface-500">Prescripteur</dt><dd className="font-mono text-surface-800 dark:text-surface-100">{selected.prescriber_pseudo}</dd></div>
              <div><dt className="text-xs text-surface-500">Assuré</dt><dd className="font-mono text-surface-800 dark:text-surface-100">{selected.insured_pseudo}</dd></div>
            </dl>
          </div>
        )}
      </Drawer>
    </div>
  );
}
