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
  email: string;
}

export interface Invoice {
  id: string;
  date: string;
  amount: number;
  status: 'received' | 'reviewing' | 'pending' | 'accepted' | 'rejected' | 'paid';
  reimbursed_amount: number;
  provider_pseudo?: string;
  provider_name?: string;
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

export type AlertStatus = 'pending' | 'validated' | 'rejected' | 'investigating';

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
  facture_id: string; score: number; seuil_utilise?: number | null; version_modele: string | null; date: string;
  montant_total: number | null; nb_regles: number; derniere_decision: AlertDecisionValue | null;
  date_decision: string | null; type: string; priorite: string; statut: string;
  codes: string[]; etat_notification: string | null; tentatives_notification: number;
  prestataire_id?: string | null; assure_id?: string | null;
}
export interface ShapContribution {
  variable: string;
  valeur?: number | string | null;
  contribution: number;
}
export interface ShapExplanation {
  valeur_base?: number;
  top?: ShapContribution[];
  toutes?: Record<string, number>;
}
export interface AlertApiDetail {
  prediction: AlertApiSummary;
  facture: {
    prestataire_id?: string | null;
    assure_id?: string | null;
    montant_total?: number | null;
    lignes: ApiInvoiceLine[];
  };
  shap: ShapContribution[] | ShapExplanation | null;
  variables: Record<string, number | string | boolean | null>;
  codes_fraude: string[]; regles: Array<Record<string, unknown>>; decisions: Array<Record<string, unknown>>;
  lignes: ApiInvoiceLine[];
  historique_prestataire: {
    facture_id: string;
    score: number;
    decision: string;
    date_decision: string;
    gestionnaire_id: number;
  }[];
}
export interface ApiInvoiceLine {
  code: string;
  libelle?: string | null;
  quantite: number;
  prix_unitaire: number;
  montant: number;
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
  decision: 'validated' | 'rejected' | 'investigating';
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
  factures_enregistrees: number;
  factures_traitees: number;
  alertes_generees: number;
  alertes_en_attente: number;
  alertes_traitees: number;
  alertes_escaladees: number;
  montant_reclame: number;
  montant_rembourse: number;
  montant_a_risque: number;
  montant_economise: number;
  fraudes_confirmees: number;
  alertes_decidees: number;
  taux_alerte: number | null;
  precision_operationnelle: number | null;
  latence_p50_ms: number | null;
  latence_p95_ms: number | null;
  date_rafraichissement: string | null;
  stale: boolean;
  erreur_rafraichissement: string | null;
  par_jour: { jour: string; factures: number; alertes: number; montant_economise: number }[];
  top_prestataires: { prestataire_id: string; prestataire_nom: string; alertes: number }[];
  distribution_scores: { bucket: number; count: number }[];
  seuil_alerte: number | null;
  factures_rejetees: { code: string; count: number }[];
  notifications: { etat: string; count: number }[];
  rag_finops: {
    tokens_entree: number;
    tokens_sortie: number;
    taux_cache_hit: number | null;
    latence_p50_ms: number | null;
    latence_p95_ms: number | null;
    cout_estime: number | null;
  };
}

export interface RagCorpusDocument {
  id: number;
  filename: string;
  scope: 'global' | 'formula' | 'contract';
  contrat_id: string | null;
  formule: string | null;
  n_pages: number | null;
  ingested_at: string;
  chunks: number;
}

export interface BIModelData {
  version_active: string | null;
  activee_le: string | null;
  rappel_hors_ligne: number | null;
  auc_pr: number | null;
  derive_psi: number | null;
  derive_disponible: boolean;
}

export interface ServiceStatus {
  api: ServiceState;
  database: ServiceState;
  model: ServiceState;
  n8n: ServiceState;
  vector_db: ServiceState;
}

export type ServiceState = 'ok' | 'degraded' | 'down' | 'unknown';

export interface SystemMetrics {
  latency_p95_ms: number | null;
  requests_per_min: number;
  error_rate: number | null;
  drift_psi: number | null;
  series: { date: string; latency: number | null }[];
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
  status: 'accepted' | 'pending' | 'rejected';
  errors: { field: string; message: string }[];
  warnings?: string[];
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

export interface UserRow {
  user_id?: number;
  pseudonym: string;
  display_name: string;
  role: Role;
  email: string | null;
  status: 'active' | 'inactive';
  assure_id?: string | null;
  prestataire_id?: string | null;
}

export type AdminAccountRole = 'assure' | 'professionnel_sante' | 'gestionnaire' | 'administrateur';

export interface CreatedUserCredentials {
  user_id: number;
  identifier: string;
  temporary_password: string;
  email_sent: boolean;
  user: UserRow;
}

export interface AdminUserCreatePayload {
  role: AdminAccountRole;
  nom: string;
  prenoms: string;
  sexe: 'F' | 'M';
  date_naissance: string;
  telephone: string;
  email: string;
  adresse: string;
  ville: string;
  numero_cin: string;
  assure_id?: string;
  prestataire_id?: string;
}

export interface UserReferences {
  assures: { assure_id: string; contrat_id: string; rang_beneficiaire: string }[];
  prestataires: { prestataire_id: string; nom: string; ville: string }[];
}
