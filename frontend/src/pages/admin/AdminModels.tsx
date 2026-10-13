import { useState, useEffect } from 'react';
import { GitBranch, CheckCircle2, Archive, ArrowLeftRight, TrendingUp, TrendingDown } from 'lucide-react';
import { Card, Button, Skeleton, ErrorState, Badge, Modal, Drawer } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { api } from '@/lib/api';
import { formatDate, formatPercent } from '@/lib/format';
import type { ModelVersion } from '@/lib/types';

export function AdminModels() {
  const { showToast } = useToast();
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [active, setActive] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activateTarget, setActivateTarget] = useState<ModelVersion | null>(null);
  const [comparePair, setComparePair] = useState<ModelVersion[]>([]);
  const [showCompare, setShowCompare] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    api.getModelVersions().then((data) => {
      setVersions(data.versions);
      setActive(data.active);
      setLoading(false);
    }).catch(() => { setError(true); setLoading(false); });
  };

  useEffect(load, []);

  const handleActivate = async () => {
    if (!activateTarget) return;
    try {
      await api.activateModel(activateTarget.version);
      setActive(activateTarget.version);
      setVersions((vs) => vs.map((v) => ({ ...v, status: v.version === activateTarget.version ? 'active' : 'archived' })));
      showToast(`Modèle ${activateTarget.version} activé`, 'success');
    } catch {
      showToast('Erreur lors de l\'activation', 'error');
    }
    setActivateTarget(null);
  };

  const toggleCompare = (v: ModelVersion) => {
    setComparePair((pair) => {
      const exists = pair.find((p) => p.version === v.version);
      if (exists) return pair.filter((p) => p.version !== v.version);
      if (pair.length >= 2) return [pair[1], v];
      return [...pair, v];
    });
  };

  if (loading) return <div className="space-y-4"><Skeleton className="h-16" /><Skeleton className="h-96" /></div>;
  if (error) return <ErrorState message="Impossible de charger les modèles." onRetry={load} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Modèles</h2>
          <p className="text-sm text-surface-500 dark:text-surface-400">Gérez les versions du modèle de détection de fraude.</p>
        </div>
        {comparePair.length === 2 && (
          <Button variant="outline" onClick={() => setShowCompare(true)}>
            <ArrowLeftRight className="w-4 h-4" /> Comparer {comparePair[0].version} vs {comparePair[1].version}
          </Button>
        )}
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
                <th className="px-6 py-3">Version</th>
                <th className="px-6 py-3">Date</th>
                <th className="px-6 py-3 text-right">Recall</th>
                <th className="px-6 py-3 text-right">Précision</th>
                <th className="px-6 py-3">Statut</th>
                <th className="px-6 py-3">Comparer</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
              {versions.map((v) => (
                <tr key={v.version} className="hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <GitBranch className="w-4 h-4 text-surface-400" />
                      <span className="text-sm font-mono font-medium text-surface-700 dark:text-surface-200">{v.version}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-300 tabular-nums">{formatDate(v.created_at)}</td>
                  <td className="px-6 py-4 text-sm text-surface-700 dark:text-surface-200 text-right tabular-nums font-medium">{formatPercent(v.recall)}</td>
                  <td className="px-6 py-4 text-sm text-surface-700 dark:text-surface-200 text-right tabular-nums font-medium">{formatPercent(v.precision)}</td>
                  <td className="px-6 py-4">
                    {v.status === 'active' ? (
                      <Badge className="bg-success-100 text-success-700 dark:bg-success-900 dark:text-success-200">
                        <CheckCircle2 className="w-3 h-3" /> Actif
                      </Badge>
                    ) : (
                      <Badge className="bg-surface-100 text-surface-500 dark:bg-surface-700 dark:text-surface-400">
                        <Archive className="w-3 h-3" /> Archivé
                      </Badge>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <input
                      type="checkbox"
                      checked={comparePair.some((p) => p.version === v.version)}
                      onChange={() => toggleCompare(v)}
                      className="w-4 h-4 rounded accent-primary-600"
                      disabled={v.status === 'active' && comparePair.length === 0}
                    />
                  </td>
                  <td className="px-6 py-4 text-right">
                    {v.status !== 'active' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setActivateTarget(v)}
                      >
                        Activer
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Activation confirmation */}
      <Modal
        open={!!activateTarget}
        onClose={() => setActivateTarget(null)}
        title="Activer le modèle"
        footer={
          <>
            <Button variant="ghost" onClick={() => setActivateTarget(null)}>Annuler</Button>
            <Button variant="primary" onClick={handleActivate}>Activer {activateTarget?.version}</Button>
          </>
        }
      >
        <p className="text-sm text-surface-600 dark:text-surface-300">
          Vous allez activer le modèle <strong className="font-mono">{activateTarget?.version}</strong>.
          Le modèle actuel ({active}) sera archivé. Cette action inclut un retour arrière possible.
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {activateTarget && (
            <>
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-3 text-center">
                <p className="text-xs text-surface-400 mb-1">Recall</p>
                <p className="text-lg font-bold tabular-nums text-surface-800 dark:text-surface-100">{formatPercent(activateTarget.recall)}</p>
              </div>
              <div className="rounded-2xl bg-surface-50 dark:bg-surface-700 p-3 text-center">
                <p className="text-xs text-surface-400 mb-1">Précision</p>
                <p className="text-lg font-bold tabular-nums text-surface-800 dark:text-surface-100">{formatPercent(activateTarget.precision)}</p>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Comparison drawer */}
      <Drawer open={showCompare} onClose={() => setShowCompare(false)} title="Comparaison des modèles" width="lg">
        {comparePair.length === 2 && (
          <div className="space-y-6">
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <p className="text-xs text-surface-400 mb-1">Métrique</p>
              </div>
              <div className="text-center">
                <p className="text-sm font-mono font-bold text-surface-700 dark:text-surface-200">{comparePair[0].version}</p>
              </div>
              <div className="text-center">
                <p className="text-sm font-mono font-bold text-surface-700 dark:text-surface-200">{comparePair[1].version}</p>
              </div>
            </div>

            {[
              { label: 'Recall', a: comparePair[0].recall, b: comparePair[1].recall },
              { label: 'Précision', a: comparePair[0].precision, b: comparePair[1].precision },
            ].map((metric) => {
              const diff = metric.b - metric.a;
              const better = diff > 0;
              return (
                <div key={metric.label} className="grid grid-cols-3 gap-4 items-center py-3 border-b border-surface-300/60 dark:border-surface-700">
                  <p className="text-sm text-surface-600 dark:text-surface-300">{metric.label}</p>
                  <p className="text-center text-sm font-medium tabular-nums text-surface-700 dark:text-surface-200">{formatPercent(metric.a)}</p>
                  <div className="flex items-center justify-center gap-2">
                    <p className="text-sm font-medium tabular-nums text-surface-700 dark:text-surface-200">{formatPercent(metric.b)}</p>
                    <span className={`flex items-center gap-0.5 text-xs font-medium ${better ? 'text-success-600' : 'text-danger-600'}`}>
                      {better ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                      {diff > 0 ? '+' : ''}{(diff * 100).toFixed(1)}pt
                    </span>
                  </div>
                </div>
              );
            })}

            <div className="grid grid-cols-3 gap-4 items-center py-3 border-b border-surface-300/60 dark:border-surface-700">
              <p className="text-sm text-surface-600 dark:text-surface-300">Date</p>
              <p className="text-center text-sm text-surface-500 tabular-nums">{formatDate(comparePair[0].created_at)}</p>
              <p className="text-center text-sm text-surface-500 tabular-nums">{formatDate(comparePair[1].created_at)}</p>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
