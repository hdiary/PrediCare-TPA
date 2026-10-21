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

const FEATURE_LABELS: Record<string, string> = {
  type_facture: 'Type de facture',
  canal_reception: 'Canal de réception',
  mode_reglement: 'Mode de règlement',
  nb_lignes: 'Nombre de lignes facturées',
  montant_total: 'Montant total réclamé',
  montant_eligible: 'Montant admissible au remboursement',
  heure: 'Heure des soins',
  jour_semaine: 'Jour des soins',
  mois_soin: 'Mois des soins',
  l_r_max: 'Dépassement maximal du tarif plafond',
  l_r_ref_max: 'Rapport maximal au tarif de référence',
  l_r_ref_min: 'Rapport minimal au tarif de référence',
  l_r_grille_max: 'Dépassement maximal du tarif conventionné',
  l_n_sur_max: 'Lignes dépassant le tarif plafond',
  l_qte_max: 'Quantité maximale sur une ligne',
  l_q_ratio_max: 'Écart maximal avec la quantité prescrite',
  l_n_hors_ordo: 'Lignes absentes de l’ordonnance',
  l_part_hors_ordo: 'Part des lignes absentes de l’ordonnance',
  l_prix_hors_ordo_max: 'Prix maximal d’un acte non prescrit',
  l_n_viol_age: 'Lignes incompatibles avec l’âge de l’assuré',
  l_n_viol_sexe: 'Lignes incompatibles avec le sexe requis',
  l_n_maj: 'Actes majorés ou réalisés en urgence / nuit',
  l_n_spec_mismatch: 'Lignes hors spécialité du prestataire',
  l_n_exclu: 'Actes exclus par le contrat',
  l_ordo_requise: 'Ordonnance requise pour les actes facturés',
  l_n_non_remboursable: 'Lignes non remboursables',
  l_n_codes_distincts: 'Nombre d’actes ou produits différents',
  validite_jours: 'Durée de validité de l’ordonnance',
  type_ordonnance: 'Type d’ordonnance',
  a_ordonnance: 'Ordonnance jointe',
  delai_ordo_soin: 'Délai entre prescription et soins',
  ordo_exp_jours: 'Dépassement de validité de l’ordonnance',
  ordo_autre_assure: 'Ordonnance au nom d’un autre assuré',
  ordo_vs_facture: 'Correspondance ordonnance / facture',
  ordo_manquante_requise: 'Ordonnance obligatoire manquante',
  ordo_n_factures: 'Factures associées à cette ordonnance',
  ordo_n_prestataires: 'Prestataires ayant utilisé cette ordonnance',
  dup_numero: 'Factures portant le même numéro',
  dup_cle: 'Factures similaires (assuré, prestataire, date et montant)',
  meme_jour_n: 'Factures du même assuré chez ce prestataire le même jour',
  meme_jour_somme: 'Montant cumulé facturé le même jour',
  dup_cle_rang: 'Rang parmi les factures similaires',
  dup_numero_rang: 'Rang parmi les factures portant ce numéro',
  meme_jour_rang: 'Rang parmi les factures du même jour',
  meme_jour_montant_cumule: 'Montant déjà facturé avant cette facture le même jour',
  ordo_rang_usage: 'Rang d’utilisation de l’ordonnance',
  assure_mois_n: 'Factures de l’assuré durant le mois',
  assure_n_total: 'Nombre total de factures de l’assuré',
  prest_n_factures: 'Nombre total de factures du prestataire',
  prest_montant_moy: 'Montant moyen facturé par le prestataire',
  prest_jour_n: 'Factures du prestataire pour cette journée',
  type_prestataire: 'Type de prestataire',
  specialite_prest: 'Spécialité du prestataire',
  niveau_tarif: 'Niveau tarifaire du prestataire',
  note_qualite: 'Note de qualité du prestataire',
  conventionne: 'Prestataire conventionné',
  heure_ouverture: 'Heure d’ouverture du prestataire',
  heure_fermeture: 'Heure de fermeture du prestataire',
  jour_ferme: 'Prestataire fermé le jour des soins',
  hors_horaires: 'Soins réalisés hors des horaires d’ouverture',
  jours_apres_fin_convention: 'Jours depuis la fin de convention',
  jours_depuis_convention: 'Ancienneté de la convention',
  prest_radie: 'Prestataire radié',
  rang_beneficiaire: 'Lien entre l’assuré et le titulaire du contrat',
  formule: 'Formule du contrat',
  delai_carence_jours: 'Délai de carence prévu au contrat',
  taux_remboursement: 'Taux de remboursement prévu au contrat',
  plafond_annuel_categorie: 'Plafond annuel de garantie',
  franchise_par_facture: 'Franchise par facture',
  age_assure: 'Âge de l’assuré',
  jours_depuis_adhesion: 'Jours depuis l’adhésion de l’assuré',
  jours_avant_radiation: 'Jours avant la radiation de l’assuré',
  gap_carence: 'Écart par rapport à la fin du délai de carence',
  jours_depuis_effet: 'Jours depuis le début du contrat',
  jours_avant_fin_contrat: 'Jours avant la fin du contrat',
  hors_periode_assure: 'Soins hors période de couverture',
  en_carence: 'Soins réalisés pendant le délai de carence',
  prest_hors_convention: 'Prestataire hors période conventionnée',
  delai_soin_facture: 'Délai entre les soins et la facturation',
  delai_facture_reception: 'Délai entre la facture et sa réception',
  ratio_eligible: 'Part du montant admissible au remboursement',
  montant_par_ligne: 'Montant moyen par ligne',
  a_attestation: 'Attestation de prise en charge jointe',
  a_entente: 'Entente préalable fournie',
  ratio_vs_prest_moy: 'Montant comparé à la moyenne du prestataire',
};

const BOOLEAN_FEATURES = new Set([
  'a_ordonnance',
  'ordo_autre_assure',
  'ordo_manquante_requise',
  'conventionne',
  'jour_ferme',
  'hors_horaires',
  'prest_radie',
  'hors_periode_assure',
  'en_carence',
  'prest_hors_convention',
  'a_attestation',
  'a_entente',
]);

function formatFeatureLabel(variable: string) {
  return FEATURE_LABELS[variable] || variable.replace(/_/g, ' ');
}

function formatFeatureValue(variable: string, value: number | string | boolean | null | undefined) {
  if (value === null || value === undefined) return '—';
  if (BOOLEAN_FEATURES.has(variable)) {
    return value === true || value === 1 || value === '1' ? 'Oui' : 'Non';
  }
  if (typeof value === 'string') {
    return value
      .replace(/_/g, ' ')
      .replace('>', ' → ')
      .toLocaleLowerCase('fr-FR');
  }
  if (typeof value !== 'number') return String(value);
  if (variable === 'jour_semaine' && Number.isInteger(value) && value >= 1 && value <= 7) {
    return ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'][value - 1];
  }
  if (variable === 'heure' || variable === 'heure_ouverture' || variable === 'heure_fermeture') {
    const hours = Math.floor(value);
    const minutes = Math.round((value - hours) * 60);
    return `${hours.toString().padStart(2, '0')} h ${minutes.toString().padStart(2, '0')}`;
  }
  if (variable === 'ratio_vs_prest_moy') {
    return `${value.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} × la moyenne`;
  }
  if ([
    'l_r_max',
    'l_r_ref_max',
    'l_r_ref_min',
    'l_r_grille_max',
    'l_q_ratio_max',
    'l_part_hors_ordo',
    'ratio_eligible',
  ].includes(variable)) {
    return `${(value * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`;
  }
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
                  <span>Élément pris en compte</span>
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
                          {formatFeatureLabel(item.variable)}
                        </span>
                        <span className="text-xs text-surface-500 sm:text-right sm:text-sm dark:text-surface-400">
                          <span className="mr-2 font-medium sm:hidden">Valeur</span>
                          {formatFeatureValue(item.variable, item.valeur)}
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
