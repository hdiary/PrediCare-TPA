export function formatEUR(amount: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
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
};

export const ALERT_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-warning-100 text-warning-700 dark:bg-warning-800 dark:text-warning-200',
  validated: 'bg-danger-100 text-danger-700 dark:bg-danger-800 dark:text-danger-200',
  rejected: 'bg-success-100 text-success-700 dark:bg-success-800 dark:text-success-200',
};

export function riskColor(score: number): string {
  if (score > 0.8) return 'bg-danger-100 text-danger-700 dark:bg-danger-900 dark:text-danger-200 border-danger-300 dark:border-danger-700';
  if (score >= 0.5) return 'bg-warning-100 text-warning-700 dark:bg-warning-900 dark:text-warning-200 border-warning-300 dark:border-warning-700';
  return 'bg-success-100 text-success-700 dark:bg-success-900 dark:text-success-200 border-success-300 dark:border-success-700';
}

export function serviceStateColor(state: 'ok' | 'degraded' | 'down'): string {
  if (state === 'ok') return 'bg-success-500';
  if (state === 'degraded') return 'bg-warning-500';
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
