/** Montants en ariary (MGA), sans décimales : c'est la devise du backend (DEVISE_INVALIDE sinon). */
export function formatMGA(amount: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'MGA',
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(date: string): string {
  const d = new Date(date);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function formatDateTime(date: string): string {
  const d = new Date(date);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

export function formatTime(date: string): string {
  return new Date(date).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

export function formatPercent(value: number, digits = 1): string {
  return new Intl.NumberFormat('fr-FR', { style: 'percent', minimumFractionDigits: digits }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('fr-FR').format(value);
}

export const ALERT_TYPE_LABELS: Record<string, string> = {
  tarification: 'Tarification',
  doublon_prescription: 'Doublon de prescription',
  inadequation_prescription: 'Inadéquation prescription/pathologie',
  surconsommation: 'Surconsommation',
};

export const INVOICE_STATUS_LABELS: Record<string, string> = {
  received: 'Reçue',
  reviewing: 'En cours de contrôle',
  accepted: 'Acceptée',
  rejected: 'Rejetée',
  paid: 'Payée',
};

export const INVOICE_STATUS_COLORS: Record<string, string> = {
  received: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  reviewing: 'bg-warning-100 text-warning-700 dark:bg-warning-800 dark:text-warning-200',
  accepted: 'bg-success-100 text-success-700 dark:bg-success-800 dark:text-success-200',
  rejected: 'bg-danger-100 text-danger-700 dark:bg-danger-800 dark:text-danger-200',
  paid: 'bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200',
};

export const ALERT_STATUS_LABELS: Record<string, string> = {
  pending: 'En attente',
  validated: 'Fraude validée',
  rejected: 'Rejetée',
  investigating: 'À investiguer',
};

export const ALERT_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-warning-100 text-warning-700 dark:bg-warning-800 dark:text-warning-200',
  validated: 'bg-danger-100 text-danger-700 dark:bg-danger-800 dark:text-danger-200',
  rejected: 'bg-success-100 text-success-700 dark:bg-success-800 dark:text-success-200',
  investigating: 'bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200',
};

export function riskColor(score: number): string {
  if (score > 0.8) return 'bg-danger-100 text-danger-700 dark:bg-danger-900 dark:text-danger-200 border-danger-300 dark:border-danger-700';
  if (score >= 0.5) return 'bg-warning-100 text-warning-700 dark:bg-warning-900 dark:text-warning-200 border-warning-300 dark:border-warning-700';
  return 'bg-success-100 text-success-700 dark:bg-success-900 dark:text-success-200 border-success-300 dark:border-success-700';
}

export function serviceStateColor(state: 'ok' | 'degraded' | 'down' | 'unknown'): string {
  if (state === 'ok') return 'bg-success-500';
  if (state === 'degraded') return 'bg-warning-500';
  if (state === 'unknown') return 'bg-surface-400';
  return 'bg-danger-500';
}

export const SERVICE_LABELS: Record<string, string> = {
  api: 'API',
  database: 'Base de données',
  model: 'Modèle',
  n8n: 'n8n',
  vector_db: 'Base vectorielle',
};

export const ROLE_LABELS: Record<string, string> = {
  provider: 'Professionnel de santé',
  insured: 'Assuré',
  manager: 'Gestionnaire',
  admin: 'Administrateur',
};

export const PRESCRIPTION_RULES: Record<string, { label: string; meaning: string; check: string }> = {
  ORDONNANCE_ANTIDATEE: {
    label: 'Ordonnance antidatée',
    meaning: "L'ordonnance est datée avant l'adhésion du bénéficiaire, ce qui peut servir à couvrir un soin antérieur.",
    check: "Comparer la date de prescription avec la date d'adhésion et la date du soin facturé.",
  },
  PRESCRIPTEUR_RADIE: {
    label: 'Prescripteur radié ou non vérifiable',
    meaning: "Le prescripteur était déconventionné à la date de prescription, ou son numéro ONM est absent ou invalide.",
    check: "Vérifier le statut du prescripteur et son numéro ONM auprès du référentiel des prestataires.",
  },
  DOUBLON_PRESCRIPTION: {
    label: 'Doublon de prescription',
    meaning: "Les mêmes lignes ont déjà été prescrites au même assuré quelques jours plus tôt.",
    check: "Consulter l'historique de l'assuré : renouvellement légitime ou nomadisme médical ?",
  },
  INADEQUATION_DIAGNOSTIC: {
    label: 'Inadéquation prescription / diagnostic',
    meaning: "Un médicament ou un examen est prescrit alors qu'il ne l'est presque jamais pour ce diagnostic.",
    check: "Évaluer la cohérence médicale ; demander un avis au médecin conseil si le doute persiste.",
  },
  PRESCRIPTEUR_INCOMPATIBLE: {
    label: 'Prescripteur hors de son champ',
    meaning: "Le diagnostic est très inhabituel pour la spécialité du prescripteur.",
    check: "Contrôler la spécialité déclarée du prescripteur et l'acte prescrit.",
  },
  ORDONNANCE_FALSIFIEE: {
    label: 'Quantité ou durée surchargée',
    meaning: "La quantité ou la durée dépasse le maximum observé pour ce produit, ce qui peut indiquer une surcharge après prescription.",
    check: "Demander l'original de l'ordonnance et comparer les quantités.",
  },
};

export const PRESCRIPTION_SEVERITY: Record<number, { label: string; className: string }> = {
  3: { label: 'Grave', className: 'bg-danger-100 text-danger-700 dark:bg-danger-900 dark:text-danger-200 border-danger-300 dark:border-danger-700' },
  2: { label: 'Suspect', className: 'bg-warning-100 text-warning-700 dark:bg-warning-900 dark:text-warning-200 border-warning-300 dark:border-warning-700' },
  1: { label: 'À vérifier', className: 'bg-success-100 text-success-700 dark:bg-success-900 dark:text-success-200 border-success-300 dark:border-success-700' },
};
