import { useState, useEffect } from 'react';
import { Receipt, Calendar, Banknote, User, X } from 'lucide-react';
import { Card, Badge, Button, Drawer, Skeleton, ErrorState, EmptyState } from '@/components/ui';
import { api } from '@/lib/api';
import { formatMGA, formatDate, INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS } from '@/lib/format';
import type { Invoice } from '@/lib/types';

const STATUS_FILTERS = [
  { value: 'all', label: 'Tous' },
  { value: 'paid', label: 'Payées' },
  { value: 'accepted', label: 'Acceptées' },
  { value: 'reviewing', label: 'En cours' },
  { value: 'received', label: 'Reçues' },
  { value: 'rejected', label: 'Rejetées' },
];

export function ReimbursementsPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState<Invoice | null>(null);

  const load = () => {
    setLoading(true);
    setError(false);
    api.getInvoices({ mine: true, status: filter }).then((data) => {
      setInvoices(data.items);
      setLoading(false);
    }).catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, [filter]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Mes remboursements</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Suivez le statut de vos factures et remboursements.</p>
      </div>

      {/* Filters */}
      <div className="flex gap-2 overflow-x-auto scrollbar-thin pb-1">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-[18px] py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-all ${
              filter === f.value
                ? 'bg-primary-700 text-white'
                : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-300 border border-surface-300 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-700'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 space-y-3">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
          </div>
        ) : error ? (
          <ErrorState message="Impossible de charger vos remboursements." onRetry={load} />
        ) : invoices.length === 0 ? (
          <EmptyState
            icon={<Receipt className="w-8 h-8" />}
            title="Aucun remboursement"
            description="Vous n'avez pas encore de facture dans cette catégorie."
          />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
                  <th className="px-6 py-3.5">Date</th>
                  <th className="px-6 py-3.5">Prestataire</th>
                  <th className="px-6 py-3.5 text-right">Montant</th>
                  <th className="px-6 py-3.5 text-right">Remboursé</th>
                  <th className="px-6 py-3.5">Statut</th>
                  <th className="px-6 py-3.5"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {invoices.map((inv) => (
                  <tr
                    key={inv.id}
                    onClick={() => setSelected(inv)}
                    className="hover:bg-surface-50 dark:hover:bg-surface-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 text-sm text-surface-700 dark:text-surface-200 tabular-nums">{formatDate(inv.date)}</td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-300 font-mono">{inv.provider_pseudo || '—'}</td>
                    <td className="px-6 py-4 text-sm text-surface-700 dark:text-surface-200 text-right tabular-nums font-medium">{formatMGA(inv.amount)}</td>
                    <td className="px-6 py-4 text-sm text-surface-700 dark:text-surface-200 text-right tabular-nums">{formatMGA(inv.reimbursed_amount)}</td>
                    <td className="px-6 py-4">
                      <Badge className={INVOICE_STATUS_COLORS[inv.status]}>{INVOICE_STATUS_LABELS[inv.status]}</Badge>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="text-xs text-primary-700 dark:text-primary-400 font-medium">Détails →</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Detail drawer */}
      <Drawer open={!!selected} onClose={() => setSelected(null)} title="Détail de la facture" width="md">
        {selected && (
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-surface-400">Facture</p>
                <p className="text-lg font-semibold text-surface-800 dark:text-surface-100 font-mono">{selected.id}</p>
              </div>
              <Badge className={INVOICE_STATUS_COLORS[selected.status]}>{INVOICE_STATUS_LABELS[selected.status]}</Badge>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-4">
                <div className="flex items-center gap-2 text-surface-400 mb-1">
                  <Calendar className="w-4 h-4" />
                  <span className="text-xs">Date de soins</span>
                </div>
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200">{formatDate(selected.date)}</p>
              </div>
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-4">
                <div className="flex items-center gap-2 text-surface-400 mb-1">
                  <User className="w-4 h-4" />
                  <span className="text-xs">Prestataire</span>
                </div>
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200 font-mono">{selected.provider_pseudo || '—'}</p>
              </div>
            </div>

            <div className="rounded-xl border border-surface-300/80 dark:border-surface-600 bg-surface-100 dark:bg-surface-700/50 p-4">
              <div className="flex items-center gap-2 text-surface-400 mb-3">
                <Banknote className="w-4 h-4" />
                <span className="text-xs font-medium">Montants</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-surface-600 dark:text-surface-300">Montant facturé</span>
                  <span className="font-medium tabular-nums text-surface-800 dark:text-surface-100">{formatMGA(selected.amount)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-surface-600 dark:text-surface-300">Montant remboursé</span>
                  <span className="font-medium tabular-nums text-success-600">{formatMGA(selected.reimbursed_amount)}</span>
                </div>
                <div className="border-t border-surface-200 dark:border-surface-600 pt-2 flex justify-between text-sm">
                  <span className="text-surface-600 dark:text-surface-300">Reste à charge</span>
                  <span className="font-medium tabular-nums text-surface-800 dark:text-surface-100">{formatMGA(selected.amount - selected.reimbursed_amount)}</span>
                </div>
              </div>
            </div>

            {selected.lines && selected.lines.length > 0 && (
              <div>
                <p className="text-xs font-medium text-surface-400 mb-2">Actes</p>
                <div className="space-y-2">
                  {selected.lines.map((line, i) => (
                    <div key={i} className="flex justify-between items-center text-sm bg-surface-50 dark:bg-surface-700 rounded-2xl px-3 py-2">
                      <div>
                        <span className="font-mono text-xs text-surface-400 mr-2">{line.code}</span>
                        <span className="text-surface-700 dark:text-surface-200">{line.label}</span>
                        <span className="text-surface-400 ml-1">×{line.quantity}</span>
                      </div>
                      <span className="font-medium tabular-nums text-surface-700 dark:text-surface-200">{formatMGA(line.amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Timeline */}
            <div>
              <p className="text-xs font-medium text-surface-400 mb-3">Suivi</p>
              <div className="space-y-3">
                {['received', 'reviewing', 'accepted', 'paid'].map((step, i) => {
                  const stepOrder = ['received', 'reviewing', 'accepted', 'paid'];
                  const currentIdx = stepOrder.indexOf(selected.status);
                  const isDone = i <= currentIdx && selected.status !== 'rejected';
                  const isRejected = selected.status === 'rejected';
                  return (
                    <div key={step} className="flex items-center gap-3">
                      <div className={`w-2.5 h-2.5 rounded-full ${isDone ? 'bg-success-500' : isRejected ? 'bg-danger-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
                      <span className={`text-sm ${isDone ? 'text-surface-700 dark:text-surface-200 font-medium' : 'text-surface-400'}`}>
                        {INVOICE_STATUS_LABELS[step]}
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
