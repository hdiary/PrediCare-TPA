import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Search } from 'lucide-react';
import { Badge, Card, EmptyState, ErrorState, Input, Skeleton, Button } from '@/components/ui';
import { api } from '@/lib/api';
import type { AlertApiSummary } from '@/lib/types';
import { ALERT_STATUS_COLORS, ALERT_STATUS_LABELS, formatDate, formatEUR, riskColor } from '@/lib/format';

const statuses = [['all', 'Toutes'], ['EN_ATTENTE', 'En attente'], ['VALIDEE', 'Validées'], ['REJETEE', 'Rejetées'], ['CONFIRMEE_FRAUDE', 'Fraudes confirmées']];
const priorities = [['all', 'Toutes priorités'], ['HAUTE', 'Haute'], ['MOYENNE', 'Moyenne'], ['BASSE', 'Basse']];
export function AlertsListPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AlertApiSummary[]>([]); const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('EN_ATTENTE'); const [priority, setPriority] = useState('all');
  const [type, setType] = useState('all'); const [search, setSearch] = useState(''); const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true); const [error, setError] = useState(false); const size = 12;
  const load = () => { setLoading(true); setError(false); api.getAlerts({ status, priority, type, page, pageSize: size }).then(r => { setItems(r.items); setTotal(r.total); }).catch(() => setError(true)).finally(() => setLoading(false)); };
  useEffect(load, [status, priority, type, page]);
  const visible = items.filter(a => [a.facture_id, a.prestataire_id || '', a.assure_id || '', ...a.codes].join(' ').toLowerCase().includes(search.toLowerCase()));
  const totalPages = Math.max(1, Math.ceil(total / size));
  return <div className="space-y-6"><div><h2 className="text-xl font-bold">Alertes de fraude</h2><p className="text-sm text-surface-500">Analysez et traitez les alertes détectées.</p></div>
    <div className="flex flex-wrap gap-3"><Input placeholder="Rechercher facture, prestataire, assuré, code..." value={search} onChange={e => setSearch(e.target.value)} icon={<Search className="w-4 h-4" />} />
      <select aria-label="Statut" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }} className="rounded-xl border px-3 py-2">{statuses.map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select>
      <select aria-label="Priorité" value={priority} onChange={e => { setPriority(e.target.value); setPage(1); }} className="rounded-xl border px-3 py-2">{priorities.map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select>
      <select aria-label="Type" value={type} onChange={e => { setType(e.target.value); setPage(1); }} className="rounded-xl border px-3 py-2"><option value="all">Tous types</option><option value="FRAUDE">Fraude</option><option value="PRESCRIPTION">Prescription</option></select>
    </div>
    <Card className="overflow-hidden">{loading ? <div className="p-8 space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-14 w-full" />)}</div> : error ? <ErrorState message="Impossible de charger les alertes." onRetry={load} /> : !visible.length ? <EmptyState icon={<AlertTriangle className="w-8 h-8" />} title="Aucune alerte" description="Aucune alerte ne correspond aux critères." /> : <div className="overflow-x-auto"><table className="w-full"><thead><tr className="text-left text-xs uppercase"><th className="p-4">Facture / score</th><th className="p-4">Type · priorité</th><th className="p-4">Montant</th><th className="p-4">Prestataire</th><th className="p-4">Assuré</th><th className="p-4">Date</th><th className="p-4">Statut</th></tr></thead><tbody>{visible.map(a => <tr key={a.facture_id} onClick={() => navigate(`/gestionnaire/alertes/${a.facture_id}`)} className="cursor-pointer border-t hover:bg-surface-50"><td className="p-4"><div className="font-mono">{a.facture_id}</div><span className={riskColor(a.score)}>{a.score.toFixed(2)}</span></td><td className="p-4">{a.type} · {a.priorite}</td><td className="p-4">{formatEUR(a.montant_total)}</td><td className="p-4 font-mono">{a.prestataire_id || '—'}</td><td className="p-4 font-mono">{a.assure_id || '—'}</td><td className="p-4">{formatDate(a.date)}</td><td className="p-4"><Badge className={ALERT_STATUS_COLORS[a.statut] || ''}>{ALERT_STATUS_LABELS[a.statut] || a.statut}</Badge></td></tr>)}</tbody></table></div>}
      {!loading && !error && total > size && <div className="flex items-center justify-between p-4"><span>{total} alertes · Page {page}/{totalPages}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</Button><Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Suivant</Button></div></div>}
    </Card></div>;
}
