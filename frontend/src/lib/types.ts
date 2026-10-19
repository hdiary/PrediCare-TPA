export type Role = 'provider' | 'insured' | 'manager' | 'admin';

export interface User {
  role: Role;
  display_name: string;
  pseudonym: string;
  email: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token?: string;
  role: Role;
  display_name: string;
  pseudonym: string;
}

export interface Invoice {
  id: string;
  date: string;
  amount: number;
  status: 'received' | 'reviewing' | 'accepted' | 'rejected' | 'paid';
  reimbursed_amount: number;
  provider_pseudo?: string;
  insured_pseudo?: string;
  lines?: InvoiceLine[];
}

export interface InvoiceLine {
  code: string;
  label: string;
  quantity: number;
  unit_price: number;
  amount: number;
  suspicious?: boolean;
}

export type AlertStatus = 'pending' | 'validated' | 'rejected';

export interface Alert {
  id: string;
  invoice_id: string;
  score: number;
  amount: number;
  provider_pseudo: string;
  insured_pseudo: string;
  created_at: string;
  status: AlertStatus;
  type: AlertType;
}

export type AlertType =
  | 'tarification'
  | 'doublon_prescription'
  | 'inadequation_prescription'
  | 'surconsommation';

export interface AlertDetail extends Alert {
  top_factors: SHAPFactor[];
  prescription_flags: string[];
  invoice_lines: InvoiceLine[];
  provider_history: DecisionHistoryItem[];
}

export type AlertDecisionValue = 'VALIDER' | 'REJETER' | 'CONFIRMER_FRAUDE' | 'ESCALADER';
export interface AlertApiSummary {
  facture_id: string; score: number; version_modele: string | null; date: string;
  montant_total: number | null; nb_regles: number; derniere_decision: AlertDecisionValue | null;
  date_decision: string | null; type: string; priorite: string; statut: string;
  codes: string[]; etat_notification: string | null; tentatives_notification: number;
  prestataire_id?: string | null; assure_id?: string | null;
}
export interface AlertApiDetail {
  prediction: AlertApiSummary; facture: Record<string, unknown>;
  shap: Array<{ variable: string; valeur?: number | string | null; contribution: number }> | { top?: Array<{ variable: string; valeur?: number | string | null; contribution: number }>; [key: string]: unknown } | null;
  codes_fraude: string[]; regles: Array<Record<string, unknown>>; decisions: Array<Record<string, unknown>>;
}
export interface AlertDecisionResult {
  decision_id: number; facture_id: string; gestionnaire_id: number;
  decision: AlertDecisionValue; commentaire: string | null;
  montant_economise: number; date_decision: string;
}

export interface SHAPFactor {
  feature: string;
  label_fr: string;
  impact: number;
  direction: 'positive' | 'negative';
}

export interface DecisionHistoryItem {
  ts: string;
  decision: 'validated' | 'rejected';
  actor_pseudo: string;
  score: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: ChatSource[];
  feedback?: 'up' | 'down' | null;
}

export interface ChatSource {
  document: string;
  page?: number;
  excerpt: string;
}

export interface Conversation {
  id: string;
  title: string;
  last_message: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface KPIData {
  invoices_processed: number;
  amount_saved: number;
  detection_rate: number;
  alerts_pending: number;
  series: { date: string; invoices: number; alerts: number; saved: number }[];
}

export interface BIKpiData {
  factures_traitees: number;
  alertes_generees: number;
  alertes_en_attente: number;
  alertes_traitees: number;
  alertes_escaladees: number;
  montant_reclame: number;
  montant_a_risque: number;
  montant_economise: number;
  fraudes_confirmees: number;
  alertes_decidees: number;
  taux_alerte: number;
  precision_operationnelle: number | null;
  date_rafraichissement: string;
  stale: boolean;
  par_jour: { jour: string; factures: number; alertes: number }[];
  top_prestataires: { prestataire_id: string; prestataire_nom: string; alertes: number }[];
  distribution_scores: { bucket: number; count: number }[];
  notifications: { etat: string; count: number }[];
}

export interface ServiceStatus {
  api: ServiceState;
  database: ServiceState;
  model: ServiceState;
  n8n: ServiceState;
  vector_db: ServiceState;
}

export type ServiceState = 'ok' | 'degraded' | 'down';

export interface SystemMetrics {
  latency_p95_ms: number;
  requests_per_min: number;
  error_rate: number;
  drift_psi: number;
  series: { date: string; latency: number; requests: number; errors: number; psi: number }[];
}

export interface ModelVersion {
  version: string;
  created_at: string;
  recall: number;
  precision: number;
  status: 'active' | 'archived';
}

export interface AuditLogEntry {
  ts: string;
  actor_pseudo: string;
  action: string;
  object: string;
  model_version: string;
}

export interface AdminSettings {
  alert_threshold: number;
  extended_rule_enabled: boolean;
  channels: {
    slack: { enabled: boolean; channel: string };
    email: { enabled: boolean; address: string };
  };
}

export interface InvoiceSubmissionResult {
  invoice_id: string;
  status: 'accepted' | 'rejected';
  errors: { field: string; message: string }[];
}

export type PrescriptionRuleCode =
  | 'ORDONNANCE_ANTIDATEE'
  | 'PRESCRIPTEUR_RADIE'
  | 'DOUBLON_PRESCRIPTION'
  | 'INADEQUATION_DIAGNOSTIC'
  | 'PRESCRIPTEUR_INCOMPATIBLE'
  | 'ORDONNANCE_FALSIFIEE';

/** Alerte produite par backend/ml/prescription_rules.py (une ligne par ordonnance et règle). */
export interface PrescriptionAlert {
  id: string;
  prescription_id: string;
  rule: PrescriptionRuleCode;
  severity: 1 | 2 | 3;
  detail: string;
  diagnosis: string | null;
  prescription_date: string;
  prescriber_pseudo: string;
  insured_pseudo: string;
}

/** Ordonnance rattachée à une facture (champs lus par le modèle et prescription_rules.py). */
export interface InvoicePrescription {
  prescription_id: string;
  prescription_date: string;
  prescriber_pseudo: string;
  diagnosis?: string;
}

/** Rôles ouverts à l'inscription ; gestionnaire et administrateur sont créés par un administrateur. */
export type SignupRole = 'insured' | 'provider';

export interface RegisterPayload {
  role: SignupRole;
  email: string;
  password: string;
  consent: boolean;
  // assuré
  first_name?: string;
  last_name?: string;
  policy_number?: string;
  birth_date?: string;
  // professionnel de santé
  organization_name?: string;
  provider_code?: string;
  tax_id?: string;
  onm_number?: string;
}
