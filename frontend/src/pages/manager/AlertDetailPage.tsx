import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowDownRight,
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  FileText,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import { Badge, Button, Card, ErrorState, Skeleton } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import type { AlertApiDetail, AlertDecisionValue } from '@/lib/types';
import {
  ALERT_STATUS_COLORS,
  ALERT_STATUS_LABELS,
  formatDate,
  formatMGA,
  riskColor,
} from '@/lib/format';

const OPTIONS: {
  value: AlertDecisionValue;
  label: string;
  variant: 'primary' | 'outline' | 'danger';
}[] = [
  { value: 'VALIDER', label: 'Valider', variant: 'primary' },
  { value: 'REJETER', label: 'Rejeter', variant: 'outline' },
  { value: 'CONFIRMER_FRAUDE', label: 'Confirmer la fraude', variant: 'danger' },
];

function formatFeatureValue(value: number | string | boolean | null | undefined) {
  if (value === null || value === undefined) return '—';
  return typeof value === 'number'
    ? value.toLocaleString('fr-FR', { maximumSignificantDigits: 7 })
    : String(value);
}

export function AlertDetailPage() {
  const { id = '' } = useParams<{ id: string }>();
  const { showToast } = useToast();
  const [detail, setDetail] = useState<AlertApiDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    api.getAlertDetail(id)
      .then(setDetail)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [id]);

  const decide = async (decision: AlertDecisionValue) => {
    setSubmitting(true);
    try {
      await api.decideAlert(id, decision, comment);
      showToast('Décision enregistrée', 'success');
      load();
    } catch (exception) {
      showToast(
        exception instanceof ApiError ? exception.message : 'Erreur lors de la décision',
        'error',
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl space-y-5">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-[30rem] w-full" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="mx-auto max-w-6xl space-y-4">
        <Link
          to="/gestionnaire/alertes"
          className="inline-flex items-center gap-2 text-sm font-medium text-primary-700 hover:text-primary-800 dark:text-primary-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Retour aux alertes
        </Link>
        <ErrorState
          message="Impossible de charger le détail de l'alerte."
          onRetry={load}
        />
      </div>
    );
  }

  const prediction = detail.prediction;
  const lines = detail.facture.lignes;
  const explanation = detail.shap && !Array.isArray(detail.shap) ? detail.shap : null;
  const shap = Array.isArray(detail.shap) ? detail.shap : detail.shap?.top || [];
  const featureRows = Object.entries(explanation?.toutes || {})
    .map(([variable, contribution]) => ({
      variable,
      contribution,
      value: detail.variables?.[variable] ?? null,
    }))
    .sort((left, right) => Math.abs(right.contribution) - Math.abs(left.contribution));
  const score = prediction.score;
  const threshold = prediction.seuil_utilise;
  const thresholdPercent = threshold === null || threshold === undefined
    ? null
    : Math.min(100, Math.max(0, threshold * 100));
  const scorePercent = Math.min(100, Math.max(0, score * 100));
  const maxContribution = Math.max(1, ...shap.map((item) => Math.abs(item.contribution)));
  const isPending = prediction.statut === 'EN_ATTENTE';

  return (
    <div className="mx-auto max-w-6xl space-y-5 pb-8">
      <Link
        to="/gestionnaire/alertes"
        className="inline-flex items-center gap-2 rounded-lg text-sm font-medium text-primary-700 transition-colors hover:text-primary-900 dark:text-primary-300 dark:hover:text-primary-100"
      >
        <ArrowLeft className="h-4 w-4" />
        Retour aux alertes
      </Link>

      <Card className="overflow-hidden">
        <header className="flex flex-col gap-4 border-b border-surface-200 p-5 dark:border-surface-700 sm:flex-row sm:items-start sm:justify-between sm:p-7">
          <div className="min-w-0">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">
              Validation de facture
            </p>
            <h1 className="break-all text-2xl font-bold text-surface-900 dark:text-surface-50">
              {prediction.facture_id}
            </h1>
            <p className="mt-2 text-sm text-surface-500 dark:text-surface-400">
              {prediction.type} <span aria-hidden="true">·</span> {formatDate(prediction.date)}
            </p>
          </div>
          <Badge className={`${ALERT_STATUS_COLORS[prediction.statut] || ''} shrink-0 px-3 py-2 text-sm`}>
            {ALERT_STATUS_LABELS[prediction.statut] || prediction.statut}
          </Badge>
        </header>

        <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-7 lg:grid-cols-4">
          <section
            aria-label="Score de risque"
            className={`rounded-2xl border p-4 ${riskColor(score)}`}
          >
            <p className="text-xs font-semibold uppercase tracking-wide opacity-80">
              Score modèle
            </p>
            <p className="mt-2 font-mono text-2xl font-bold tabular-nums">
              {score.toFixed(6)}
            </p>
            <div
              className="relative mt-3 h-2 overflow-hidden rounded-full bg-black/10 dark:bg-white/10"
              role="meter"
              aria-label="Score de risque"
              aria-valuemin={0}
              aria-valuemax={1}
              aria-valuenow={score}
            >
              <div
                className="h-full rounded-full bg-current transition-all"
                style={{ width: `${scorePercent}%` }}
              />
              {thresholdPercent !== null && (
                <span
                  className="absolute inset-y-0 w-0.5 bg-surface-900 dark:bg-white"
                  style={{ left: `${thresholdPercent}%` }}
                  title={`Seuil : ${threshold!.toFixed(6)}`}
                />
              )}
            </div>
            <p className="mt-2 text-xs">
              {threshold === null || threshold === undefined
                ? 'Seuil non disponible'
                : `Seuil d’alerte : ${threshold.toFixed(6)}`}
            </p>
          </section>

          <InfoTile label="Priorité" value={prediction.priorite} />
          <InfoTile label="Montant réclamé" value={formatMGA(prediction.montant_total || 0)} />
          <InfoTile
            label="Prestataire / assuré"
            value={`${prediction.prestataire_id || '—'} / ${prediction.assure_id || '—'}`}
            mono
          />
        </div>

        <div className="space-y-8 px-5 pb-6 sm:px-7 sm:pb-8">
          <section aria-labelledby="fraud-codes-title">
            <SectionTitle
              id="fraud-codes-title"
              title="Motifs de l’alerte"
              subtitle="Règles et signaux associés à cette facture."
            />
            {detail.codes_fraude.length ? (
              <ul className="mt-3 flex flex-wrap gap-2">
                {detail.codes_fraude.map((code) => (
                  <li key={code}>
                    <Badge className="border border-danger-200 bg-danger-50 text-danger-800 dark:border-danger-800 dark:bg-danger-900/30 dark:text-danger-200">
                      <ShieldAlert className="h-3.5 w-3.5" />
                      {code.replace(/_/g, ' ')}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-surface-500 dark:text-surface-400">
                Aucun code de fraude associé.
              </p>
            )}
          </section>

          <section aria-labelledby="explanation-title">
            <SectionTitle
              id="explanation-title"
              title="Explication du score"
              subtitle="Principales variables ayant influencé la prédiction."
            />
            <div className="mt-3 rounded-xl border border-primary-200 bg-primary-50/70 p-4 text-sm leading-6 text-primary-950 dark:border-primary-900 dark:bg-primary-950/30 dark:text-primary-100">
              Une contribution positive pousse le modèle vers la classe « fraude »; une
              contribution négative l’en éloigne. Les contributions sont exprimées dans
              l’échelle interne du modèle — elles ne sont pas des pourcentages ni des
              points de probabilité. Le score reste une estimation, pas une preuve.
              {explanation?.valeur_base !== undefined && (
                <span className="mt-1 block text-xs text-primary-800 dark:text-primary-200">
                  Valeur de référence du modèle : {explanation.valeur_base.toFixed(6)}
                </span>
              )}
            </div>

            {shap.length ? (
              <div className="mt-4 overflow-hidden rounded-xl border border-surface-200 dark:border-surface-700">
                <div className="hidden grid-cols-[minmax(0,1fr)_minmax(8rem,0.8fr)_minmax(7rem,auto)] gap-4 bg-surface-100 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-surface-500 dark:bg-surface-800 dark:text-surface-300 sm:grid">
                  <span>Variable</span>
                  <span className="text-right">Valeur observée</span>
                  <span className="text-right">Impact SHAP</span>
                </div>
                <ul className="divide-y divide-surface-200 dark:divide-surface-700">
                  {shap.map((item, index) => {
                    const positive = item.contribution >= 0;
                    const width = Math.max(
                      3,
                      (Math.abs(item.contribution) / maxContribution) * 100,
                    );
                    return (
                      <li
                        key={`${item.variable}-${index}`}
                        className="grid gap-2 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(8rem,0.8fr)_minmax(7rem,auto)] sm:items-center sm:gap-4"
                      >
                        <span className="break-all font-mono text-sm font-medium text-surface-800 dark:text-surface-100">
                          {item.variable}
                        </span>
                        <span className="text-xs text-surface-500 sm:text-right sm:text-sm dark:text-surface-400">
                          <span className="mr-2 font-medium sm:hidden">Valeur</span>
                          {formatFeatureValue(item.valeur)}
                        </span>
                        <div className="flex items-center justify-between gap-3 sm:justify-end">
                          <span className="h-1.5 min-w-10 flex-1 overflow-hidden rounded-full bg-surface-100 dark:bg-surface-700 sm:max-w-24">
                            <span
                              className={`block h-full rounded-full ${positive ? 'bg-danger-500' : 'bg-success-500'}`}
                              style={{ width: `${width}%` }}
                            />
                          </span>
                          <strong
                            className={`inline-flex min-w-28 items-center justify-end gap-1 font-mono text-sm tabular-nums ${
                              positive ? 'text-danger-700 dark:text-danger-300' : 'text-success-700 dark:text-success-300'
                            }`}
                          >
                            {positive
                              ? <ArrowUpRight className="h-4 w-4" aria-label="Augmente le risque" />
                              : <ArrowDownRight className="h-4 w-4" aria-label="Réduit le risque" />}
                            {positive ? '+' : ''}{item.contribution.toFixed(6)}
                          </strong>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : (
              <p className="mt-3 text-sm text-surface-500 dark:text-surface-400">
                Explication SHAP indisponible pour cette alerte.
              </p>
            )}

            {featureRows.length > 0 && (
              <details className="group mt-4 rounded-xl border border-surface-200 dark:border-surface-700">
                <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-primary-700 marker:hidden hover:bg-surface-50 dark:text-primary-300 dark:hover:bg-surface-800">
                  <span aria-hidden="true" className="mr-2 inline-block transition-transform group-open:rotate-90">›</span>
                  Données techniques ({featureRows.length} variables)
                </summary>
                <div className="max-h-96 overflow-auto border-t border-surface-200 dark:border-surface-700">
                  <table className="w-full min-w-[34rem] text-left text-xs">
                    <thead className="sticky top-0 bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-300">
                      <tr>
                        <th scope="col" className="px-4 py-3">Variable</th>
                        <th scope="col" className="px-4 py-3 text-right">Valeur entrée</th>
                        <th scope="col" className="px-4 py-3 text-right">Impact SHAP</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
                      {featureRows.map((row) => (
                        <tr key={row.variable}>
                          <th scope="row" className="break-all px-4 py-2.5 font-mono font-medium">
                            {row.variable}
                          </th>
                          <td className="px-4 py-2.5 text-right tabular-nums">
                            {formatFeatureValue(row.value)}
                          </td>
                          <td className={`px-4 py-2.5 text-right font-mono tabular-nums ${row.contribution >= 0 ? 'text-danger-700 dark:text-danger-300' : 'text-success-700 dark:text-success-300'}`}>
                            {row.contribution > 0 ? '+' : ''}{row.contribution.toFixed(6)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </section>

          <section aria-labelledby="invoice-lines-title">
            <SectionTitle
              id="invoice-lines-title"
              title="Lignes de facture"
              subtitle={`${lines.length} ligne${lines.length === 1 ? '' : 's'} · Total réclamé : ${formatMGA(prediction.montant_total || 0)}`}
            />
            {lines.length > 0 ? (
              <ul className="mt-3 divide-y divide-surface-200 rounded-xl border border-surface-200 dark:divide-surface-700 dark:border-surface-700">
                {lines.map((line, index) => (
                  <li
                    key={`${line.code}-${index}`}
                    className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="mt-0.5 rounded-lg bg-surface-100 p-2 text-surface-500 dark:bg-surface-800 dark:text-surface-300">
                        <FileText className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="font-mono text-sm font-semibold text-surface-800 dark:text-surface-100">
                          {line.code}
                        </p>
                        <p className="break-words text-sm text-surface-500 dark:text-surface-400">
                          {line.libelle || 'Libellé non disponible'}
                        </p>
                      </div>
                    </div>
                    <p className="shrink-0 text-sm tabular-nums text-surface-700 dark:text-surface-200 sm:text-right">
                      {line.quantite} × {formatMGA(line.prix_unitaire)}
                      <span className="mx-2 text-surface-400">=</span>
                      <strong>{formatMGA(line.montant)}</strong>
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-surface-500 dark:text-surface-400">
                Aucune ligne détaillée disponible.
              </p>
            )}
          </section>

          {isPending ? (
            <section
              aria-labelledby="decision-title"
              className="rounded-2xl border border-primary-200 bg-primary-50/50 p-4 sm:p-6 dark:border-primary-900 dark:bg-primary-950/20"
            >
              <SectionTitle
                id="decision-title"
                title="Décision du gestionnaire"
                subtitle="Ajoutez un commentaire pour activer les actions de traitement."
              />
              <label
                htmlFor="manager-comment"
                className="mt-4 block text-sm font-medium text-surface-700 dark:text-surface-200"
              >
                Commentaire <span className="text-danger-600">*</span>
              </label>
              <textarea
                id="manager-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Expliquez brièvement les éléments qui motivent votre décision…"
                rows={4}
                required
                aria-required="true"
                className="mt-2 w-full resize-y rounded-xl border border-surface-300 bg-white p-3.5 text-sm text-surface-800 outline-none transition placeholder:text-surface-400 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-100"
              />
              <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap">
                {OPTIONS.map((option) => (
                  <Button
                    key={option.value}
                    disabled={!comment.trim() || submitting}
                    variant={option.variant}
                    className="w-full sm:w-auto"
                    onClick={() => decide(option.value)}
                  >
                    {option.value === 'VALIDER' && <CheckCircle2 className="h-4 w-4" />}
                    {(option.value === 'REJETER' || option.value === 'CONFIRMER_FRAUDE') && (
                      <XCircle className="h-4 w-4" />
                    )}
                    {option.label}
                  </Button>
                ))}
              </div>
            </section>
          ) : (
            <section
              aria-live="polite"
              className="rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-sm text-surface-600 dark:border-surface-700 dark:bg-surface-800 dark:text-surface-300"
            >
              Cette alerte a déjà été traitée. La décision enregistrée est affichée dans son statut.
            </section>
          )}
        </div>
      </Card>
    </div>
  );
}

function SectionTitle({
  id,
  title,
  subtitle,
}: {
  id: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div>
      <h2 id={id} className="text-base font-bold text-surface-900 dark:text-surface-50">
        {title}
      </h2>
      <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">{subtitle}</p>
    </div>
  );
}

function InfoTile({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0 rounded-2xl border border-surface-200 bg-white/70 p-4 dark:border-surface-700 dark:bg-surface-900/40">
      <p className="text-xs font-semibold uppercase tracking-wide text-surface-500 dark:text-surface-400">
        {label}
      </p>
      <p className={`mt-2 break-words text-lg font-semibold text-surface-900 dark:text-surface-50 ${mono ? 'font-mono text-sm' : ''}`}>
        {value}
      </p>
    </div>
  );
}
