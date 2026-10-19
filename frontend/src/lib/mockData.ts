import type {
  UserRow,
  Alert,
  PrescriptionAlert,
  AlertDetail,
  Conversation,
  Invoice,
  InvoiceSubmissionResult,
  ModelVersion,
  AuditLogEntry,
  AdminSettings,
  ServiceStatus,
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

export const mockServiceStatus: ServiceStatus = {
  api: 'ok',
  database: 'ok',
  model: 'degraded',
  n8n: 'ok',
  vector_db: 'ok',
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
  extended_rule_enabled: false,
  channels: {
    slack: { enabled: true, channel: '#alertes-fraude' },
    email: { enabled: false, address: '' },
  },
};

export const mockInvoiceResult: InvoiceSubmissionResult = {
  invoice_id: 'FAC-2024-1049',
  status: 'accepted',
  errors: [],
};

const mockProviderChatResponse = (lower: string): { answer: string; sources: { document: string; page: number; excerpt: string }[] } => {
  if (lower.includes('rejet')) {
    return {
      answer: "Votre dernière facture a été **rejetée** pour le motif suivant : *numéro d'ordonnance manquant pour un acte soumis à prescription*.\n\nVous pouvez la corriger depuis **Mes factures** en ajoutant l'ordonnance, puis la redéposer.",
      sources: [],
    };
  }
  if (lower.includes('facture') || lower.includes('dossier') || lower.includes('fac-')) {
    return {
      answer: 'Votre facture **FAC-2024-1018** est actuellement **en cours de contrôle**.\n\nElle a été réceptionnée et passe les vérifications automatiques. Vous serez prévenu dès qu\'elle est acceptée ou si une correction est demandée.',
      sources: [],
    };
  }
  if (lower.includes('justificatif') || lower.includes('ordonnance') || lower.includes('prescription') || lower.includes('pièce') || lower.includes('piece')) {
    return {
      answer: 'Pour un acte soumis à prescription, joignez à la facture :\n\n- le **numéro et la date de l\'ordonnance**\n- l\'identité du **prescripteur**\n- le scan de l\'ordonnance si vous l\'avez (facultatif)\n\nUne ordonnance expirée ou ne couvrant pas les lignes facturées sera signalée au contrôle.',
      sources: [{ document: 'Guide Réseau de Soins National', page: 6, excerpt: 'Les actes et produits soumis à prescription doivent être accompagnés de l\'ordonnance correspondante, valide à la date du soin.' }],
    };
  }
  if (lower.includes('tarif') || lower.includes('consultation') || lower.includes('barème') || lower.includes('bareme')) {
    return {
      answer: 'Le **tarif de référence** d\'une consultation de médecine générale figure au barème des actes, avec un **tarif maximum** à ne pas dépasser. Au-delà, la facture est signalée.\n\nPrécisez l\'acte pour obtenir le tarif exact.',
      sources: [{ document: 'Barème de Référence des Actes', page: 3, excerpt: 'Pour chaque acte : tarif minimum, tarif de référence et tarif maximum.' }],
    };
  }
  return {
    answer: 'Je peux vous renseigner sur l\'état de vos factures, les motifs de rejet, les pièces à fournir et le barème des actes. N\'hésitez pas à me poser une question plus précise.',
    sources: [],
  };
};

export const mockProviderConversations: Conversation[] = [
  {
    id: 'CONV-P01',
    title: 'Facture rejetée',
    last_message: 'Votre dernière facture a été rejetée pour le motif suivant...',
    updated_at: '2024-10-14T09:10:00Z',
    messages: [
      { id: 'pmsg-1', role: 'user', content: 'Pourquoi ma dernière facture a-t-elle été rejetée ?', timestamp: '2024-10-14T09:05:00Z' },
      {
        id: 'pmsg-2', role: 'assistant',
        content: "Votre dernière facture a été **rejetée** pour le motif suivant : *numéro d'ordonnance manquant pour un acte soumis à prescription*.\n\nVous pouvez la corriger depuis **Mes factures** en ajoutant l'ordonnance, puis la redéposer.",
        timestamp: '2024-10-14T09:10:00Z', feedback: 'up',
      },
    ],
  },
  {
    id: 'CONV-P02',
    title: 'Tarif d\'une consultation',
    last_message: 'Le tarif de référence d\'une consultation de médecine générale figure au barème...',
    updated_at: '2024-10-09T15:40:00Z',
    messages: [
      { id: 'pmsg-3', role: 'user', content: 'Quel est le tarif de référence d\'une consultation ?', timestamp: '2024-10-09T15:35:00Z' },
      {
        id: 'pmsg-4', role: 'assistant',
        content: 'Le **tarif de référence** d\'une consultation de médecine générale figure au barème des actes, avec un **tarif maximum** à ne pas dépasser. Au-delà, la facture est signalée.\n\nPrécisez l\'acte pour obtenir le tarif exact.',
        sources: [{ document: 'Barème de Référence des Actes', page: 3, excerpt: 'Pour chaque acte : tarif minimum, tarif de référence et tarif maximum.' }],
        timestamp: '2024-10-09T15:40:00Z', feedback: null,
      },
    ],
  },
];

export const mockChatResponse = (message: string, role?: 'insured' | 'provider' | string): { answer: string; sources: { document: string; page: number; excerpt: string }[] } => {
  const lower = message.toLowerCase();
  if (role === 'provider') return mockProviderChatResponse(lower);
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

export const mockPrescriptionAlerts: PrescriptionAlert[] = [
  { id: 'PRA-001', prescription_id: 'ORD-0041872', rule: 'ORDONNANCE_ANTIDATEE', severity: 3, detail: "prescrite le 2025-12-05, avant l'adhésion du 2025-12-13", diagnosis: 'Hypertension artérielle', prescription_date: '2025-12-05', prescriber_pseudo: 'PRS-0078', insured_pseudo: 'ASS-004218' },
  { id: 'PRA-002', prescription_id: 'ORD-0038110', rule: 'PRESCRIPTEUR_RADIE', severity: 3, detail: 'prescripteur déconventionné à la date de prescription', diagnosis: 'Diabète de type 2', prescription_date: '2026-03-14', prescriber_pseudo: 'PRS-0102', insured_pseudo: 'ASS-004220' },
  { id: 'PRA-003', prescription_id: 'ORD-0029954', rule: 'ORDONNANCE_FALSIFIEE', severity: 3, detail: 'MED-0042 : quantité 9 (max observé 2)', diagnosis: 'Douleur lombaire', prescription_date: '2026-05-21', prescriber_pseudo: 'PRS-0055', insured_pseudo: 'ASS-004223' },
  { id: 'PRA-004', prescription_id: 'ORD-0044301', rule: 'DOUBLON_PRESCRIPTION', severity: 2, detail: 'mêmes lignes déjà prescrites il y a 3 j (autre prescripteur)', diagnosis: 'Infection respiratoire', prescription_date: '2026-06-02', prescriber_pseudo: 'PRS-0052', insured_pseudo: 'ASS-004224' },
  { id: 'PRA-005', prescription_id: 'ORD-0044298', rule: 'DOUBLON_PRESCRIPTION', severity: 2, detail: 'mêmes lignes déjà prescrites il y a 1 j (même prescripteur)', diagnosis: 'Gastrite', prescription_date: '2026-06-02', prescriber_pseudo: 'PRS-0078', insured_pseudo: 'ASS-004225' },
  { id: 'PRA-006', prescription_id: 'ORD-0036677', rule: 'INADEQUATION_DIAGNOSTIC', severity: 2, detail: "LAB-GE, LAB-ECBU jamais prescrit pour « Rhinite allergique »", diagnosis: 'Rhinite allergique', prescription_date: '2026-04-08', prescriber_pseudo: 'PRS-0102', insured_pseudo: 'ASS-004226' },
  { id: 'PRA-007', prescription_id: 'ORD-0040215', rule: 'PRESCRIPTEUR_INCOMPATIBLE', severity: 2, detail: 'PEDIATRIE : « Trouble anxieux » hors de son champ habituel', diagnosis: 'Trouble anxieux', prescription_date: '2026-02-17', prescriber_pseudo: 'PRS-0063', insured_pseudo: 'ASS-004227' },
];

export const mockUserRows: UserRow[] = [
  ...MOCK_ACCOUNTS.map((acc) => ({
    pseudonym: acc.pseudonym, display_name: acc.display_name, role: acc.role, email: acc.email, status: 'active' as const,
  })),
  { pseudonym: 'GST-0008', display_name: 'Gestionnaire A', role: 'manager', email: 'gst8@predicare.fr', status: 'active' },
  { pseudonym: 'GST-0011', display_name: 'Gestionnaire B', role: 'manager', email: 'gst11@predicare.fr', status: 'inactive' },
  { pseudonym: 'PRS-0052', display_name: 'Praticien B', role: 'provider', email: 'prs52@predicare.fr', status: 'active' },
  { pseudonym: 'PRS-0078', display_name: 'Praticien C', role: 'provider', email: 'prs78@predicare.fr', status: 'active' },
  { pseudonym: 'ASS-004218', display_name: 'Assuré B', role: 'insured', email: 'ass4218@predicare.fr', status: 'active' },
  { pseudonym: 'ASS-004219', display_name: 'Assuré C', role: 'insured', email: 'ass4219@predicare.fr', status: 'active' },
];
