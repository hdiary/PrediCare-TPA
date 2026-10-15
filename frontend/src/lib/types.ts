export type Role = 'provider' | 'insured' | 'manager' | 'admin';

export interface User {
  role: Role;
  display_name: string;
  pseudonym: string;
  email: string;
}

export interface AuthResponse {
  access_token: string;
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
  page: number;
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
  channels: {
    slack: { enabled: boolean; webhook: string };
    email: { enabled: boolean; address: string };
  };
}

export interface InvoiceSubmissionResult {
  invoice_id: string;
  status: 'accepted' | 'rejected';
  errors: { field: string; message: string }[];
}
