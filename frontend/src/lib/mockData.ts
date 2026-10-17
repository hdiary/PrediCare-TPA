import type {
  Alert,
  AlertDetail,
  ChatMessage,
  Conversation,
  Invoice,
  InvoiceSubmissionResult,
  KPIData,
  ModelVersion,
  AuditLogEntry,
  AdminSettings,
  ServiceStatus,
  SystemMetrics,
  User,
  Role,
} from './types';

export const MOCK_ACCOUNTS: { email: string; password: string; role: Role; display_name: string; pseudonym: string }[] = [
  { email: 'demo@predicare.fr', password: 'demo1234', role: 'insured', display_name: 'Assuré Démo', pseudonym: 'ASS-004217' },
  { email: 'provider@predicare.fr', password: 'demo1234', role: 'provider', display_name: 'Dr. Démo', pseudonym: 'PRS-0031' },
  { email: 'manager@predicare.fr', password: 'demo1234', role: 'manager', display_name: 'Gestionnaire Démo', pseudonym: 'GST-0012' },
  { email: 'admin@predicare.fr', password: 'demo1234', role: 'admin', display_name: 'Administrateur Démo', pseudonym: 'ADM-0001' },
];

export const mockUser: User = {
  role: 'manager',
  display_name: 'Gestionnaire Démo',
  pseudonym: 'GST-0012',
  email: 'manager@predicare.fr',
};

export const mockInvoices: Invoice[] = [
  { id: 'FAC-2024-1042', date: '2024-10-10', amount: 340.00, status: 'paid', reimbursed_amount: 255.00, provider_pseudo: 'PRS-0031', insured_pseudo: 'ASS-004217', lines: [
    { code: 'CSC', label: 'Consultation cardiologie', quantity: 1, unit_price: 55, amount: 55 },
    { code: 'ETT', label: 'Échocardiographie', quantity: 1, unit_price: 95, amount: 95 },
    { code: 'HOL', label: 'Holter ECG 24h', quantity: 1, unit_price: 190, amount: 190 },
  ]},
  { id: 'FAC-2024-1043', date: '2024-10-11', amount: 78.00, status: 'accepted', reimbursed_amount: 58.50, provider_pseudo: 'PRS-0052', insured_pseudo: 'ASS-004217', lines: [
    { code: 'CSG', label: 'Consultation générale', quantity: 1, unit_price: 28, amount: 28 },
    { code: 'BIO', label: 'Bilan biologique', quantity: 1, unit_price: 50, amount: 50 },
  ]},
  { id: 'FAC-2024-1044', date: '2024-10-12', amount: 1250.00, status: 'reviewing', reimbursed_amount: 0, provider_pseudo: 'PRS-0078', insured_pseudo: 'ASS-004218', lines: [
    { code: 'IRM', label: 'IRM articulaire', quantity: 1, unit_price: 320, amount: 320 },
    { code: 'KIN', label: 'Séance kinésithérapie', quantity: 15, unit_price: 62, amount: 930, suspicious: true },
  ]},
  { id: 'FAC-2024-1045', date: '2024-10-09', amount: 45.00, status: 'received', reimbursed_amount: 0, provider_pseudo: 'PRS-0031', insured_pseudo: 'ASS-004219' },
  { id: 'FAC-2024-1046', date: '2024-10-08', amount: 890.00, status: 'rejected', reimbursed_amount: 0, provider_pseudo: 'PRS-0102', insured_pseudo: 'ASS-004220' },
  { id: 'FAC-2024-1047', date: '2024-10-07', amount: 210.00, status: 'paid', reimbursed_amount: 157.50, provider_pseudo: 'PRS-0052', insured_pseudo: 'ASS-004221' },
  { id: 'FAC-2024-1048', date: '2024-10-06', amount: 520.00, status: 'paid', reimbursed_amount: 390.00, provider_pseudo: 'PRS-0031', insured_pseudo: 'ASS-004222' },
];

export const mockAlerts: Alert[] = [
  { id: 'ALT-001', invoice_id: 'FAC-2024-1044', score: 0.92, amount: 1250.00, provider_pseudo: 'PRS-0078', insured_pseudo: 'ASS-004218', created_at: '2024-10-12T09:30:00Z', status: 'pending', type: 'surconsommation' },
  { id: 'ALT-002', invoice_id: 'FAC-2024-1041', score: 0.85, amount: 640.00, provider_pseudo: 'PRS-0102', insured_pseudo: 'ASS-004220', created_at: '2024-10-11T14:20:00Z', status: 'pending', type: 'tarification' },
  { id: 'ALT-003', invoice_id: 'FAC-2024-1038', score: 0.71, amount: 380.00, provider_pseudo: 'PRS-0102', insured_pseudo: 'ASS-004223', created_at: '2024-10-10T11:00:00Z', status: 'pending', type: 'doublon_prescription' },
  { id: 'ALT-004', invoice_id: 'FAC-2024-1035', score: 0.58, amount: 220.00, provider_pseudo: 'PRS-0055', insured_pseudo: 'ASS-004224', created_at: '2024-10-09T16:45:00Z', status: 'pending', type: 'inadequation_prescription' },
  { id: 'ALT-005', invoice_id: 'FAC-2024-1033', score: 0.89, amount: 910.00, provider_pseudo: 'PRS-0078', insured_pseudo: 'ASS-004225', created_at: '2024-10-08T08:15:00Z', status: 'validated', type: 'tarification' },
  { id: 'ALT-006', invoice_id: 'FAC-2024-1029', score: 0.43, amount: 150.00, provider_pseudo: 'PRS-0052', insured_pseudo: 'ASS-004226', created_at: '2024-10-07T10:30:00Z', status: 'rejected', type: 'doublon_prescription' },
  { id: 'ALT-007', invoice_id: 'FAC-2024-1027', score: 0.76, amount: 450.00, provider_pseudo: 'PRS-0102', insured_pseudo: 'ASS-004227', created_at: '2024-10-06T13:00:00Z', status: 'pending', type: 'surconsommation' },
];

export const mockAlertDetail: AlertDetail = {
  ...mockAlerts[0],
  top_factors: [
    { feature: 'unit_price_ratio', label_fr: 'Tarif 3,2 fois supérieur à la moyenne de l\'acte', impact: 0.34, direction: 'positive' },
    { feature: 'quantity_anomaly', label_fr: 'Quantité 15 séances (norme: 5-8)', impact: 0.28, direction: 'positive' },
    { feature: 'provider_flag_rate', label_fr: 'Taux d\'alerte du prestataire: 18%', impact: 0.19, direction: 'positive' },
    { feature: 'duplicate_prescription', label_fr: 'Prescription similaire il y a 5 jours', impact: 0.15, direction: 'positive' },
    { feature: 'age_consistency', label_fr: 'Âge compatible avec la pathologie', impact: -0.08, direction: 'negative' },
  ],
  prescription_flags: ['Doublon de prescription détecté', 'Prescription incohérente avec la pathologie'],
  invoice_lines: [
    { code: 'IRM', label: 'IRM articulaire', quantity: 1, unit_price: 320, amount: 320 },
    { code: 'KIN', label: 'Séance kinésithérapie', quantity: 15, unit_price: 62, amount: 930, suspicious: true },
  ],
  provider_history: [
    { ts: '2024-09-28T10:00:00Z', decision: 'validated', actor_pseudo: 'GST-0008', score: 0.88 },
    { ts: '2024-08-15T14:30:00Z', decision: 'rejected', actor_pseudo: 'GST-0011', score: 0.52 },
    { ts: '2024-07-02T09:15:00Z', decision: 'validated', actor_pseudo: 'GST-0008', score: 0.91 },
  ],
};

export const mockConversations: Conversation[] = [
  {
    id: 'CONV-001',
    title: 'Plafond dentaire',
    last_message: 'Votre plafond de remboursement dentaire est de 300 EUR par semestre...',
    updated_at: '2024-10-12T10:30:00Z',
    messages: [
      {
        id: 'msg-1', role: 'user', content: 'Quel est mon plafond de remboursement dentaire ?', timestamp: '2024-10-12T10:25:00Z',
      },
      {
        id: 'msg-2', role: 'assistant', content: 'Votre plafond de remboursement dentaire est de **300 EUR par semestre** pour les soins conservateurs (détartrage, soins, dévitalisation). Pour l\'orthodontie, le plafond est de 600 EUR par année civile.\n\nCe plafond est réinitialisé au 1er janvier de chaque année.', timestamp: '2024-10-12T10:25:30Z',
        sources: [
          { document: 'Contrat Santé Plus', page: 12, excerpt: 'Plafond dentaire soins conservateurs: 300 EUR/semestre. Orthodontie: 600 EUR/an. Réinitialisation au 1er janvier.' },
        ],
        feedback: 'up',
      },
    ],
  },
  {
    id: 'CONV-002',
    title: 'Dossier septembre',
    last_message: 'Votre dossier du 12 septembre est actuellement en cours de traitement...',
    updated_at: '2024-10-11T15:00:00Z',
    messages: [
      {
        id: 'msg-3', role: 'user', content: 'Où en est mon dossier du 12 septembre ?', timestamp: '2024-10-11T14:55:00Z',
      },
      {
        id: 'msg-4', role: 'assistant', content: 'Votre dossier du **12 septembre 2024** (réf. FAC-2024-1018) est actuellement **en cours de contrôle**.\n\nIl a été réceptionné le 12/09 et est en phase de vérification. Le remboursement est généralement effectué sous 5 à 10 jours ouvrés après acceptation.', timestamp: '2024-10-11T14:55:30Z',
        sources: [
          { document: 'Contrat Santé Plus', page: 8, excerpt: 'Délai de traitement standard: 5-10 jours ouvrés après acceptation de la facture.' },
        ],
        feedback: null,
      },
    ],
  },
];

export const mockKPIData: KPIData = {
  invoices_processed: 2847,
  amount_saved: 142300,
  detection_rate: 0.127,
  alerts_pending: 34,
  series: [
    { date: 'S1', invoices: 412, alerts: 38, saved: 18200 },
    { date: 'S2', invoices: 389, alerts: 41, saved: 21500 },
    { date: 'S3', invoices: 445, alerts: 52, saved: 28100 },
    { date: 'S4', invoices: 401, alerts: 35, saved: 19800 },
    { date: 'S5', invoices: 468, alerts: 48, saved: 26200 },
    { date: 'S6', invoices: 432, alerts: 44, saved: 28500 },
    { date: 'S7', invoices: 300, alerts: 34, saved: 0 },
  ],
};

export const mockServiceStatus: ServiceStatus = {
  api: 'ok',
  database: 'ok',
  model: 'degraded',
  n8n: 'ok',
  vector_db: 'ok',
};

export const mockSystemMetrics: SystemMetrics = {
  latency_p95_ms: 142,
  requests_per_min: 38,
  error_rate: 0.012,
  drift_psi: 0.083,
  series: Array.from({ length: 24 }, (_, i) => ({
    date: `${String(i).padStart(2, '0')}:00`,
    latency: 100 + Math.random() * 80,
    requests: 20 + Math.random() * 40,
    errors: Math.random() * 3,
    psi: 0.05 + Math.random() * 0.06,
  })),
};

export const mockModelVersions: ModelVersion[] = [
  { version: 'v2.3.0', created_at: '2024-10-01', recall: 0.91, precision: 0.87, status: 'active' },
  { version: 'v2.2.1', created_at: '2024-09-01', recall: 0.88, precision: 0.84, status: 'archived' },
  { version: 'v2.2.0', created_at: '2024-08-15', recall: 0.86, precision: 0.89, status: 'archived' },
  { version: 'v2.1.0', created_at: '2024-07-01', recall: 0.82, precision: 0.85, status: 'archived' },
  { version: 'v1.9.0', created_at: '2024-05-01', recall: 0.79, precision: 0.81, status: 'archived' },
];

export const mockAuditLog: AuditLogEntry[] = [
  { ts: '2024-10-12T09:45:00Z', actor_pseudo: 'GST-0012', action: 'Décision alerte validée', object: 'ALT-001', model_version: 'v2.3.0' },
  { ts: '2024-10-12T08:30:00Z', actor_pseudo: 'ADM-0001', action: 'Modèle activé', object: 'v2.3.0', model_version: 'v2.3.0' },
  { ts: '2024-10-11T16:20:00Z', actor_pseudo: 'GST-0008', action: 'Décision alerte rejetée', object: 'ALT-006', model_version: 'v2.3.0' },
  { ts: '2024-10-11T14:00:00Z', actor_pseudo: 'ADM-0001', action: 'Seuil d\'alerte modifié', object: '0.80 → 0.75', model_version: 'v2.3.0' },
  { ts: '2024-10-10T11:15:00Z', actor_pseudo: 'PRS-0031', action: 'Facture déposée', object: 'FAC-2024-1042', model_version: 'v2.3.0' },
  { ts: '2024-10-10T08:00:00Z', actor_pseudo: 'ADM-0001', action: 'Canal Slack configuré', object: '#alerts-fraud', model_version: 'v2.3.0' },
];

export const mockAdminSettings: AdminSettings = {
  alert_threshold: 0.80,
  channels: {
    slack: { enabled: true, webhook: 'https://hooks.slack.com/services/xxx' },
    email: { enabled: false, address: '' },
  },
};

export const mockInvoiceResult: InvoiceSubmissionResult = {
  invoice_id: 'FAC-2024-1049',
  status: 'accepted',
  errors: [],
};

export const mockChatResponse = (message: string): { answer: string; sources: { document: string; page: number; excerpt: string }[] } => {
  const lower = message.toLowerCase();
  if (lower.includes('plafond') || lower.includes('dentaire')) {
    return {
      answer: 'Votre plafond de remboursement dentaire est de **300 EUR par semestre** pour les soins conservateurs (détartrage, soins, dévitalisation). Pour l\'orthodontie, le plafond est de 600 EUR par année civile.\n\nCe plafond est réinitialisé au 1er janvier de chaque année.',
      sources: [{ document: 'Contrat Santé Plus', page: 12, excerpt: 'Plafond dentaire soins conservateurs: 300 EUR/semestre. Orthodontie: 600 EUR/an.' }],
    };
  }
  if (lower.includes('dossier') || lower.includes('septembre') || lower.includes('etat') || lower.includes('état')) {
    return {
      answer: 'Votre dossier du **12 septembre 2024** (réf. FAC-2024-1018) est actuellement **en cours de contrôle**.\n\nIl a été réceptionné le 12/09 et est en phase de vérification. Le remboursement est généralement effectué sous 5 à 10 jours ouvrés après acceptation.',
      sources: [{ document: 'Contrat Santé Plus', page: 8, excerpt: 'Délai de traitement standard: 5-10 jours ouvrés après acceptation.' }],
    };
  }
  if (lower.includes('exclu') || lower.includes('exclusion')) {
    return {
      answer: 'Les éléments suivants sont **exclus** de votre contrat:\n\n- Médecine douce (acupuncture, homéopathie, ostéopathie hors prescription)\n- Chirurgie esthétique non reconstructrice\n- Cures thermales (sauf convention spécifique)\n- Actes expérimentaux\n\nPour plus de détails, consultez l\'article 7 de votre contrat.',
      sources: [{ document: 'Contrat Santé Plus', page: 24, excerpt: 'Article 7 - Exclusions: médecine douce, chirurgie esthétique non reconstructrice, cures thermales, actes expérimentaux.' }],
    };
  }
  return {
    answer: 'Je peux vous renseigner sur votre contrat, vos remboursements, l\'état de vos dossiers et les exclusions de garanties. N\'hésitez pas à me poser une question plus précise.',
    sources: [],
  };
};
