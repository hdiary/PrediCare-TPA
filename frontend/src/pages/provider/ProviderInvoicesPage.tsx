import { useState, useEffect } from 'react';
import { Receipt, Search, FileText } from 'lucide-react';
import { Card, Badge, Button, Drawer, Skeleton, ErrorState, EmptyState, Input } from '@/components/ui';
import { api } from '@/lib/api';
import { formatEUR, formatDate, INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS } from '@/lib/format';
import type { Invoice } from '@/lib/types';

const STATUS_FILTERS = [
  { value: 'all', label: 'Toutes' },
  { value: 'received', label: 'Reçues' },
  { value: 'reviewing', label: 'En cours' },
  { value: 'accepted', label: 'Acceptées' },
  { value: 'rejected', label: 'Rejetées' },
  { value: 'paid', label: 'Payées' },
];

export function ProviderInvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Invoice | null>(null);
  const perPage = 10;

  const load = () => {
    setLoading(true);
    setError(false);
    api.getInvoices({ status: filter }).then((data) => {
      setInvoices(data.items);
      setLoading(false);
    }).catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, [filter]);

  const filtered = invoices.filter((inv) =>
    inv.id.toLowerCase().includes(search.toLowerCase()) ||
    (inv.insured_pseudo || '').toLowerCase().includes(search.toLowerCase())
  );
  const paginated = filtered.slice((page - 1) * perPage, page * perPage);
  const totalPages = Math.ceil(filtered.length / perPage);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Mes factures</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Suivez le statut de toutes vos factures déposées.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="flex-1">
          <Input
            placeholder="Rechercher par n° de facture ou assuré..."
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
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
          </div>
        ) : error ? (
          <ErrorState message="Impossible de charger les factures." onRetry={load} />
        ) : paginated.length === 0 ? (
          <EmptyState
            icon={<Receipt className="w-8 h-8" />}
            title="Aucune facture"
            description="Vous n'avez pas encore déposé de facture."
          />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
                  <th className="px-6 py-3">N° Facture</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Assuré</th>
                  <th className="px-6 py-3 text-right">Montant</th>
                  <th className="px-6 py-3">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {paginated.map((inv) => (
                  <tr
                    key={inv.id}
                    onClick={() => setSelected(inv)}
                    className="hover:bg-surface-50 dark:hover:bg-surface-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 text-sm font-mono font-medium text-surface-700 dark:text-surface-200">{inv.id}</td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-300 tabular-nums">{formatDate(inv.date)}</td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-300 font-mono">{inv.insured_pseudo || '—'}</td>
                    <td className="px-6 py-4 text-sm text-surface-700 dark:text-surface-200 text-right tabular-nums font-medium">{formatEUR(inv.amount)}</td>
                    <td className="px-6 py-4">
                      <Badge className={INVOICE_STATUS_COLORS[inv.status]}>{INVOICE_STATUS_LABELS[inv.status]}</Badge>
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
              {filtered.length} facture{filtered.length > 1 ? 's' : ''} · Page {page}/{totalPages}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Précédent</Button>
              <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(page + 1)}>Suivant</Button>
            </div>
          </div>
        )}
      </Card>

      <Drawer open={!!selected} onClose={() => setSelected(null)} title="Détail de la facture" width="md">
        {selected && (
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-surface-400" />
                <p className="text-lg font-semibold font-mono text-surface-800 dark:text-surface-100">{selected.id}</p>
              </div>
              <Badge className={INVOICE_STATUS_COLORS[selected.status]}>{INVOICE_STATUS_LABELS[selected.status]}</Badge>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-4">
                <p className="text-xs text-surface-400 mb-1">Date</p>
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200">{formatDate(selected.date)}</p>
              </div>
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-4">
                <p className="text-xs text-surface-400 mb-1">Assuré</p>
                <p className="text-sm font-medium font-mono text-surface-700 dark:text-surface-200">{selected.insured_pseudo}</p>
              </div>
            </div>

            <div className="rounded-xl border border-surface-300/80 dark:border-surface-600 bg-surface-100 dark:bg-surface-700/50 p-4">
              <p className="text-xs font-medium text-surface-400 mb-3">Montants</p>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-surface-600 dark:text-surface-300">Montant facturé</span>
                  <span className="font-medium tabular-nums">{formatEUR(selected.amount)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-surface-600 dark:text-surface-300">Remboursé</span>
                  <span className="font-medium tabular-nums text-success-600">{formatEUR(selected.reimbursed_amount)}</span>
                </div>
              </div>
            </div>

            {/* Timeline */}
            <div>
              <p className="text-xs font-medium text-surface-400 mb-3">Suivi de la facture</p>
              <div className="space-y-3">
                {[
                  { label: 'Reçue', key: 'received' },
                  { label: 'En cours de contrôle', key: 'reviewing' },
                  { label: 'Décision', key: 'accepted' },
                  { label: 'Paiement', key: 'paid' },
                ].map((step, i) => {
                  const stepOrder = ['received', 'reviewing', 'accepted', 'paid'];
                  const currentIdx = stepOrder.indexOf(selected.status);
                  const isDone = i <= currentIdx && selected.status !== 'rejected';
                  return (
                    <div key={step.key} className="flex items-center gap-3">
                      <div className={`w-2.5 h-2.5 rounded-full ${isDone ? 'bg-success-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
                      <span className={`text-sm ${isDone ? 'text-surface-700 dark:text-surface-200 font-medium' : 'text-surface-400'}`}>
                        {step.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
