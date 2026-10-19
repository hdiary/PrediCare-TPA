/**
 * Couche d'accès à l'API PrediCare TPA (backend FastAPI).
 *
 * - Le frontend parle en anglais (types.ts) ; l'API parle en français (rôles, champs). Toute la
 *   traduction est faite ICI, pour que les pages n'aient pas à la connaître.
 * - Les fonctions pas encore disponibles côté backend restent simulées (mockData.ts). La liste est
 *   réglée par VITE_MOCKS : "all" (tout simulé, démo hors-ligne), "none" (rien de simulé), ou une
 *   liste de fonctions séparées par des virgules. Par défaut : kpis,metrics,models,chat.
 */
import type {
  AuthResponse,
  Role,
  Invoice,
  Alert,
  AlertDetail,
  AlertStatus,
  AlertType,
  KPIData,
  ServiceStatus,
  ServiceState,
  SystemMetrics,
  ModelVersion,
  AuditLogEntry,
  AdminSettings,
  Conversation,
  InvoiceSubmissionResult,
  UserRow,
  PrescriptionAlert,
  RegisterPayload,
} from "./types";

import {
  MOCK_ACCOUNTS,
  mockInvoices,
  mockAlerts,
  mockAlertDetail,
  mockKPIData,
  mockServiceStatus,
  mockSystemMetrics,
  mockModelVersions,
  mockAuditLog,
  mockAdminSettings,
  mockConversations,
  mockInvoiceResult,
  mockChatResponse,
  mockUserRows,
  mockPrescriptionAlerts,
  mockProviderConversations,
} from "./mockData";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** En développement et en production, "/api" est redirigé vers le backend (vite.config.ts, nginx.conf). */
export const BASE_URL: string = import.meta.env.VITE_API_URL || "/api";

export type Feature =
  | "auth" | "alerts" | "invoices" | "settings" | "audit" | "users"
  | "health" | "kpis" | "metrics" | "models" | "chat" | "prescriptions" | "register" | "password";

const DEFAULT_MOCKS = "kpis,metrics,models,chat,prescriptions,register,password";
const mockedFeatures = new Set(
  String(import.meta.env.VITE_MOCKS || DEFAULT_MOCKS)
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s && s !== "none"),
);

export function isMock(feature: Feature): boolean {
  return mockedFeatures.has("all") || mockedFeatures.has(feature);
}

/** Fonctions simulées en ce moment (affichées dans le bandeau « données de démonstration »). */
export function mockedFeatureList(): Feature[] {
  const all: Feature[] = ["auth", "alerts", "invoices", "settings", "audit", "users", "health",
    "kpis", "metrics", "models", "chat", "prescriptions", "register", "password"];
  return all.filter(isMock);
}

const TOKEN_KEY = "predicare_token";
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Appels HTTP
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  /** Erreurs de validation par champ (rejet d'une facture, requête invalide). */
  errors: { field: string; message: string; code?: string }[];
  constructor(message: string, status: number, errors: ApiError["errors"] = []) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Extrait un message lisible et les erreurs par champ d'une réponse d'erreur du backend. */
function parseErrorBody(body: unknown, status: number): ApiError {
  const b = (body ?? {}) as {
    detail?: unknown; erreurs?: { code: string; champ: string; message: string }[];
    errors?: { field: string; message: string }[];
  };
  const errors: ApiError["errors"] = [];
  if (Array.isArray(b.erreurs)) {
    // Facture rejetée : codes du contrat de données (section 9.1)
    for (const e of b.erreurs) errors.push({ field: e.champ, message: e.message, code: e.code });
  } else if (Array.isArray(b.errors)) {
    for (const e of b.errors) errors.push({ field: e.field, message: e.message });
  }
  const message = typeof b.detail === "string" ? b.detail : `Erreur ${status}`;
  return new ApiError(message, status, errors);
}

async function request<T>(path: string, options: RequestInit = {}, opts: { auth?: boolean } = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(opts.auth === false ? {} : authHeaders()),
      ...options.headers,
    },
  });
  if (res.status === 401 && opts.auth !== false) {
    localStorage.removeItem(TOKEN_KEY);
    window.location.href = "/login";
    throw new ApiError("Session expirée", 401);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = parseErrorBody(body, res.status);
    if (res.status === 403 && err.message === `Erreur 403`) err.message = "Accès refusé";
    throw err;
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Traductions API (français) -> frontend
// ---------------------------------------------------------------------------

interface ApiUser {
  user_id: number; email: string; role: string; assure_id?: string | null; prestataire_id?: string | null;
}

const ROLE_FROM_API: Record<string, Role> = {
  assure: "insured",
  professionnel_sante: "provider",
  gestionnaire: "manager",
  administrateur: "admin",
};
const ROLE_PREFIX: Record<Role, string> = { insured: "ASS", provider: "PRE", manager: "GST", admin: "ADM" };

/** Le frontend affiche un pseudonyme : identifiant métier si le compte en a un, sinon RÔLE-numéro. */
function mapUser(u: ApiUser): { role: Role; display_name: string; pseudonym: string; email: string } {
  const role = ROLE_FROM_API[u.role];
  if (!role) throw new Error(`Rôle inconnu : ${u.role}`);
  const pseudonym = u.assure_id || u.prestataire_id || `${ROLE_PREFIX[role]}-${String(u.user_id).padStart(4, "0")}`;
  const local = u.email.split("@")[0];
  return { role, pseudonym, email: u.email, display_name: local.charAt(0).toUpperCase() + local.slice(1) };
}

let cachedMe: { pseudonym: string; role: Role } | null = null;

async function currentUser() {
  if (!cachedMe) {
    const me = mapUser(await request<ApiUser>("/auth/me"));
    cachedMe = { pseudonym: me.pseudonym, role: me.role };
  }
  return cachedMe;
}

const DECISION_TO_STATUS: Record<string, AlertStatus> = {
  fraude_confirmee: "validated",
  faux_positif: "rejected",
  a_investiguer: "investigating",
};

const INVOICE_STATUS_FROM_API: Record<string, Invoice["status"]> = {
  EN_COURS: "reviewing",
  PAYEE: "paid",
  REJETEE: "rejected",
};
const INVOICE_STATUS_TO_API: Record<string, string | null> = {
  reviewing: "EN_COURS", paid: "PAYEE", rejected: "REJETEE",
  received: null, accepted: null, // statuts sans équivalent côté backend
};

/** Le backend ne classe pas encore les alertes par type : toute alerte du modèle est de type « tarification ». */
function alertTypeOf(a: { type_alerte?: string | null }): AlertType {
  const known: AlertType[] = ["tarification", "doublon_prescription", "inadequation_prescription", "surconsommation"];
  return known.includes(a.type_alerte as AlertType) ? (a.type_alerte as AlertType) : "tarification";
}

/** « ecart_prix_moyen » -> « Écart prix moyen » (pas de dictionnaire fourni par le modèle). */
function prettyFeature(name: string): string {
  const s = name.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

interface ApiLine {
  code: string; libelle?: string | null; quantite: number; prix_unitaire: number; montant: number;
}
const mapLine = (l: ApiLine) => ({
  code: l.code, label: l.libelle || l.code, quantity: l.quantite, unit_price: l.prix_unitaire, amount: l.montant,
});

interface ApiAlertSummary {
  facture_id: string; score: number; date: string; montant_total?: number | null;
  prestataire_id?: string | null; assure_id?: string | null; derniere_decision?: string | null;
}
const mapAlertSummary = (a: ApiAlertSummary): Alert => ({
  id: a.facture_id,
  invoice_id: a.facture_id,
  score: a.score,
  amount: a.montant_total ?? 0,
  provider_pseudo: a.prestataire_id ?? "—",
  insured_pseudo: a.assure_id ?? "—",
  created_at: a.date,
  status: a.derniere_decision ? DECISION_TO_STATUS[a.derniere_decision] ?? "pending" : "pending",
  type: alertTypeOf({}),
});

const AUDIT_LABELS: Record<string, string> = {
  prediction: "Prédiction de facture",
  decision: "Décision gestionnaire",
  facture_rejetee: "Facture rejetée",
  erreur_prediction: "Erreur de prédiction (facture)",
  modele_charge: "Chargement du modèle",
  acces_identite: "Accès à une identité (alerte)",
  config_modifiee: "Modification du seuil / de la configuration",
};

function newFactureId(): string {
  const n = crypto.getRandomValues(new Uint32Array(1))[0] % 10_000_000;
  return `FAC-9${String(n).padStart(7, "0")}`; // plage FAC-9xxxxxxx réservée aux factures déposées
}

// ---------------------------------------------------------------------------
// API publique utilisée par les pages
// ---------------------------------------------------------------------------

export const api = {
  async login(email: string, password: string): Promise<AuthResponse> {
    if (isMock("auth")) {
      await delay(600);
      const account = MOCK_ACCOUNTS.find((a) => a.email === email && a.password === password);
      if (!account) throw new Error("Email ou mot de passe incorrect");
      return {
        access_token: "mock-jwt-" + account.role,
        role: account.role,
        display_name: account.display_name,
        pseudonym: account.pseudonym,
      };
    }
    try {
      const data = await request<{ access_token: string; user: ApiUser }>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ email, password }) },
        { auth: false },
      );
      const u = mapUser(data.user);
      cachedMe = { pseudonym: u.pseudonym, role: u.role };
      return { access_token: data.access_token, role: u.role, display_name: u.display_name, pseudonym: u.pseudonym };
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) throw new Error("Email ou mot de passe incorrect");
      throw e;
    }
  },

  async getMe(): Promise<{ role: Role; display_name: string; pseudonym: string; email: string }> {
    if (isMock("auth")) {
      await delay(200);
      const token = localStorage.getItem(TOKEN_KEY);
      const account = MOCK_ACCOUNTS.find((a) => "mock-jwt-" + a.role === token);
      if (!account) throw new Error("Non authentifié");
      return { role: account.role, display_name: account.display_name, pseudonym: account.pseudonym, email: account.email };
    }
    const me = mapUser(await request<ApiUser>("/auth/me"));
    cachedMe = { pseudonym: me.pseudonym, role: me.role };
    return me;
  },

  /** Factures dans le périmètre du compte (prestataire : les siennes ; assuré : les siennes ; gestionnaire : toutes). */
  async getInvoices(filters?: { mine?: boolean; status?: string; page?: number }): Promise<{ items: Invoice[]; total: number }> {
    if (isMock("invoices")) {
      await delay(400);
      let items = [...mockInvoices];
      if (filters?.status && filters.status !== "all") items = items.filter((i) => i.status === filters.status);
      return { items, total: items.length };
    }
    const params = new URLSearchParams({ limit: "200" });
    if (filters?.status && filters.status !== "all") {
      const apiStatus = INVOICE_STATUS_TO_API[filters.status];
      if (!apiStatus) return { items: [], total: 0 };
      params.set("statut", apiStatus);
    }
    const data = await request<{
      items: {
        facture_id: string; date_soin: string; montant_total: number; montant_pris_en_charge?: number | null;
        statut: string; prestataire_id: string; assure_id: string; lignes: ApiLine[];
      }[];
      total: number;
    }>(`/invoices?${params}`);
    return {
      total: data.total,
      items: data.items.map((f) => ({
        id: f.facture_id,
        date: f.date_soin,
        amount: f.montant_total,
        status: INVOICE_STATUS_FROM_API[f.statut] ?? "reviewing",
        reimbursed_amount: f.montant_pris_en_charge ?? 0,
        provider_pseudo: f.prestataire_id,
        insured_pseudo: f.assure_id,
        lines: f.lignes.map(mapLine),
      })),
    };
  },

  /**
   * Dépôt d'une facture (POST /predict).
   * - Saisie manuelle : objet { insured_pseudo, care_date, care_time, contract_id, invoice_number, invoice_type, lines }.
   * - Fichier : seul le JSON (contrat de données, section 11.1) est accepté par l'API.
   * Une facture rejetée par la validation n'est PAS une erreur technique : on renvoie status "rejected" avec les motifs.
   */
  async submitInvoice(data: FormData | Record<string, unknown>): Promise<InvoiceSubmissionResult> {
    if (isMock("invoices")) {
      await delay(1200);
      return mockInvoiceResult;
    }
    const me = await currentUser();
    let payload: Record<string, unknown>;
    if (data instanceof FormData) {
      const file = data.get("file");
      if (!(file instanceof File) || !/\.json$/i.test(file.name)) {
        throw new Error("Format non pris en charge : déposez un fichier JSON ou utilisez la saisie manuelle.");
      }
      try {
        payload = JSON.parse(await file.text());
      } catch {
        throw new Error("Le fichier JSON est illisible.");
      }
      if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
        throw new Error("Le fichier JSON doit contenir un objet facture.");
      }
      // ordonnance saisie dans le formulaire (champ « prescription », JSON) : seul son numéro est transmis
      const rx = data.get("prescription");
      if (typeof rx === "string" && rx && !payload.ordonnance_id) {
        try {
          payload.ordonnance_id = (JSON.parse(rx) as { prescription_id?: string }).prescription_id;
        } catch { /* champ facultatif illisible : ignoré */ }
      }
    } else {
      const d = data as {
        insured_pseudo: string; care_date: string; care_time?: string; contract_id: string;
        invoice_number: string; invoice_type: string;
        lines: { code: string; label?: string; quantity: number; unit_price: number }[];
        prescription?: { prescription_id?: string };
      };
      payload = {
        numero_facture: d.invoice_number,
        assure_id: d.insured_pseudo.trim(),
        contrat_id: d.contract_id.trim(),
        type_facture: d.invoice_type,
        date_soin: d.care_date,
        heure_soin: d.care_time || "08:00",
        devise: "MGA",
        lignes: d.lines.map((l) => ({ code: l.code.trim(), quantite: l.quantity, prix_unitaire: l.unit_price })),
      };
      // L'API ne stocke que le numéro d'ordonnance (date, prescripteur et diagnostic ne sont pas encore acceptés).
      if (d.prescription?.prescription_id) payload.ordonnance_id = d.prescription.prescription_id.trim();
    }
    if (me.role === "provider") payload.prestataire_id = me.pseudonym;
    const generated = !payload.facture_id;

    for (let attempt = 0; attempt < 2; attempt++) {
      if (generated) payload.facture_id = newFactureId();
      try {
        const r = await request<{ facture_id: string }>("/predict", { method: "POST", body: JSON.stringify(payload) });
        return { invoice_id: r.facture_id, status: "accepted", errors: [] };
      } catch (e) {
        if (!(e instanceof ApiError) || ![403, 409, 422].includes(e.status)) throw e;
        const doublon = e.errors.some((x) => x.code === "FACTURE_DEJA_ENREGISTREE");
        if (doublon && generated && attempt === 0) continue; // collision d'identifiant : on retire un autre numéro
        return {
          invoice_id: String(payload.facture_id ?? "—"),
          status: "rejected",
          errors: e.errors.length ? e.errors.map((x) => ({ field: x.field, message: x.message })) : [{ field: "", message: e.message }],
        };
      }
    }
    throw new Error("Dépôt impossible");
  },

  /** Scan de l'ordonnance : pas encore de route côté backend (simulé par défaut). */
  async uploadPrescriptionScan(invoiceId: string, scan: File): Promise<void> {
    if (isMock("prescriptions")) {
      await delay(500);
      return;
    }
    const formData = new FormData();
    formData.append("scan", scan);
    const res = await fetch(`${BASE_URL}/invoices/${encodeURIComponent(invoiceId)}/prescription-scan`, {
      method: "POST",
      headers: { ...authHeaders() },
      body: formData,
    });
    if (!res.ok) throw new Error("Erreur lors de l'envoi de l'ordonnance");
  },

  // ---- Comptes : routes publiques (sans jeton), pas encore de routes côté backend ----
  async register(payload: RegisterPayload): Promise<{ status: "pending" }> {
    if (isMock("register")) {
      await delay(900);
      // Réponse identique que l'e-mail existe déjà ou non : on ne révèle pas quels comptes existent.
      return { status: "pending" };
    }
    return request("/auth/register", { method: "POST", body: JSON.stringify(payload) }, { auth: false });
  },

  async requestPasswordReset(email: string): Promise<void> {
    if (isMock("password")) {
      await delay(700);
      return;
    }
    await request("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }, { auth: false });
  },

  async resetPassword(token: string, password: string): Promise<void> {
    if (isMock("password")) {
      await delay(700);
      if (token === "expire") throw new Error("Ce lien a expiré ou a déjà été utilisé. Refaites une demande.");
      return;
    }
    await request("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) }, { auth: false });
  },

  /** Alertes de prescription (règles de backend/ml/prescription_rules.py, pas encore exposées par l'API). */
  async getPrescriptionAlerts(filters?: { rule?: string; minSeverity?: number }): Promise<{ items: PrescriptionAlert[]; total: number }> {
    if (isMock("prescriptions")) {
      await delay(400);
      let items = [...mockPrescriptionAlerts];
      if (filters?.rule && filters.rule !== "all") items = items.filter((x) => x.rule === filters.rule);
      if (filters?.minSeverity) items = items.filter((x) => x.severity >= (filters.minSeverity || 0));
      return { items, total: items.length };
    }
    const params = new URLSearchParams();
    if (filters?.rule && filters.rule !== "all") params.set("rule", filters.rule);
    if (filters?.minSeverity) params.set("min_severity", String(filters.minSeverity));
    return request(`/prescription-alerts?${params}`);
  },

  async getAlerts(filters?: { status?: string; minScore?: number; page?: number }): Promise<{ items: Alert[]; total: number }> {
    if (isMock("alerts")) {
      await delay(400);
      let items = [...mockAlerts];
      if (filters?.status && filters.status !== "all") items = items.filter((a) => a.status === filters.status);
      if (filters?.minScore) items = items.filter((a) => a.score >= (filters.minScore || 0));
      return { items, total: items.length };
    }
    // Le backend sait filtrer « en attente / traitées / toutes » ; les 3 états de décision se filtrent ici.
    const statut = filters?.status === "pending" ? "en_attente" : "toutes";
    const rows = await request<ApiAlertSummary[]>(`/alerts?statut=${statut}&limit=200`);
    let items = rows.map(mapAlertSummary);
    if (filters?.status && filters.status !== "all") items = items.filter((a) => a.status === filters.status);
    if (filters?.minScore) items = items.filter((a) => a.score >= (filters.minScore || 0));
    return { items, total: items.length };
  },

  async getAlertDetail(id: string): Promise<AlertDetail> {
    if (isMock("alerts")) {
      await delay(500);
      return { ...mockAlertDetail, id };
    }
    const d = await request<{
      prediction: { facture_id: string; score: number; date: string };
      shap: { top?: { variable: string; valeur?: number | string | null; contribution: number }[] } | null;
      decisions: { decision: string; date_decision: string; gestionnaire_id: number }[];
      facture: { prestataire_id: string; assure_id: string; montant_total: number } | null;
      lignes: ApiLine[];
      historique_prestataire: { facture_id: string; score: number; decision: string; date_decision: string; gestionnaire_id: number }[];
    }>(`/alerts/${encodeURIComponent(id)}`);
    const last = d.decisions[0]?.decision;
    return {
      id: d.prediction.facture_id,
      invoice_id: d.prediction.facture_id,
      score: d.prediction.score,
      amount: d.facture?.montant_total ?? 0,
      provider_pseudo: d.facture?.prestataire_id ?? "—",
      insured_pseudo: d.facture?.assure_id ?? "—",
      created_at: d.prediction.date,
      status: last ? DECISION_TO_STATUS[last] ?? "pending" : "pending",
      type: alertTypeOf({}),
      top_factors: (d.shap?.top ?? []).map((f) => ({
        feature: f.variable,
        label_fr: prettyFeature(f.variable) + (f.valeur !== null && f.valeur !== undefined ? ` (${f.valeur})` : ""),
        impact: f.contribution,
        direction: f.contribution >= 0 ? "positive" : "negative",
      })),
      prescription_flags: [], // règles de prescription (P2) pas encore branchées côté backend
      invoice_lines: d.lignes.map(mapLine),
      provider_history: d.historique_prestataire.map((h) => ({
        ts: h.date_decision,
        decision: (DECISION_TO_STATUS[h.decision] ?? "rejected") as "validated" | "rejected" | "investigating",
        actor_pseudo: `GST-${String(h.gestionnaire_id).padStart(4, "0")}`,
        score: h.score,
      })),
    };
  },

  /** `amount` : montant de la facture ; une fraude confirmée est comptée comme montant économisé. */
  async decideAlert(
    id: string,
    decision: "validate" | "reject",
    comment: string,
    amount?: number,
  ): Promise<{ id: string; status: string; decided_at: string }> {
    if (isMock("alerts")) {
      await delay(800);
      return { id, status: decision === "validate" ? "validated" : "rejected", decided_at: new Date().toISOString() };
    }
    const fraude = decision === "validate";
    const r = await request<{ facture_id: string; decision: string; date_decision: string }>(
      `/alerts/${encodeURIComponent(id)}/decision`,
      {
        method: "POST",
        body: JSON.stringify({
          decision: fraude ? "fraude_confirmee" : "faux_positif",
          commentaire: comment || null,
          montant_economise: fraude && amount !== undefined ? Math.round(amount) : null,
        }),
      },
    );
    return { id: r.facture_id, status: DECISION_TO_STATUS[r.decision] ?? "pending", decided_at: r.date_decision };
  },

  async getKPIs(period?: string): Promise<KPIData> {
    if (isMock("kpis")) {
      await delay(500);
      return mockKPIData;
    }
    return request(`/kpis${period ? `?period=${period}` : ""}`);
  },

  /** États des services : l'API et la base viennent de /health ; n8n et la base vectorielle ne sont pas encore sondés. */
  async getServiceStatus(): Promise<ServiceStatus> {
    if (isMock("health")) {
      await delay(300);
      return mockServiceStatus;
    }
    const unknown: ServiceState = "unknown";
    try {
      const res = await fetch(`${BASE_URL}/health`);
      const h = (await res.json()) as { checks?: Record<string, string> };
      const checks = h.checks ?? {};
      return {
        api: "ok",
        database: checks.database === "ok" ? "ok" : "down",
        model: checks.model === "ok" ? "ok" : "down",
        n8n: unknown,
        vector_db: unknown,
      };
    } catch {
      return { api: "down", database: unknown, model: unknown, n8n: unknown, vector_db: unknown };
    }
  },

  async getSystemMetrics(period?: string): Promise<SystemMetrics> {
    if (isMock("metrics")) {
      await delay(500);
      return mockSystemMetrics;
    }
    return request(`/admin/metrics${period ? `?period=${period}` : ""}`);
  },

  async getModelVersions(): Promise<{ active: string; versions: ModelVersion[] }> {
    if (isMock("models")) {
      await delay(400);
      return { active: "v2.3.0", versions: mockModelVersions };
    }
    return request("/admin/models");
  },

  async activateModel(version: string): Promise<{ active: string }> {
    if (isMock("models")) {
      await delay(800);
      return { active: version };
    }
    return request(`/admin/models/${version}/activate`, { method: "POST" });
  },

  async getAuditLog(filters?: { action?: string; actor?: string }): Promise<{ items: AuditLogEntry[] }> {
    if (isMock("audit")) {
      await delay(400);
      return { items: mockAuditLog };
    }
    const rows = await request<{ ts: string; event_type: string; actor: string; entity: string; model_version?: string | null }[]>(
      "/admin/audit-log?limit=500",
    );
    let items = rows.map((r) => ({
      ts: r.ts,
      actor_pseudo: r.actor,
      action: AUDIT_LABELS[r.event_type] ?? r.event_type,
      object: r.entity,
      model_version: r.model_version ?? "—",
    }));
    if (filters?.action) items = items.filter((i) => i.action.toLowerCase().includes(filters.action!.toLowerCase()));
    if (filters?.actor) items = items.filter((i) => i.actor_pseudo.toLowerCase().includes(filters.actor!.toLowerCase()));
    return { items };
  },

  async getAdminSettings(): Promise<AdminSettings> {
    if (isMock("settings")) {
      await delay(300);
      return mockAdminSettings;
    }
    const s = await request<{
      alert_threshold: number; slack_enabled: boolean; slack_channel: string;
      email_enabled: boolean; email_recipients: string;
    }>("/admin/settings");
    return {
      alert_threshold: s.alert_threshold,
      channels: {
        slack: { enabled: s.slack_enabled, webhook: s.slack_channel },
        email: { enabled: s.email_enabled, address: s.email_recipients },
      },
    };
  },

  async updateAdminSettings(settings: AdminSettings): Promise<AdminSettings> {
    if (isMock("settings")) {
      await delay(600);
      return settings;
    }
    try {
      await request("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({
          alert_threshold: settings.alert_threshold,
          slack_enabled: settings.channels.slack.enabled,
          slack_channel: settings.channels.slack.webhook,
          email_enabled: settings.channels.email.enabled,
          email_recipients: settings.channels.email.address,
        }),
      });
    } catch (e) {
      // 422 : afficher le motif précis (ex. adresse e-mail invalide) plutôt qu'un message générique
      if (e instanceof ApiError && e.status === 422 && e.errors.length) throw new Error(e.errors[0].message);
      throw e;
    }
    return settings;
  },

  async getUsers(): Promise<UserRow[]> {
    if (isMock("users")) {
      await delay(300);
      return mockUserRows;
    }
    const rows = await request<(ApiUser & { is_active: boolean })[]>("/admin/users");
    return rows.map((r) => {
      const u = mapUser(r);
      return { pseudonym: u.pseudonym, display_name: u.display_name, role: u.role, email: u.email, status: r.is_active ? "active" : "inactive" };
    });
  },

  async getConversations(role?: Role): Promise<{ conversations: Conversation[] }> {
    if (isMock("chat")) {
      await delay(300);
      return { conversations: role === "provider" ? mockProviderConversations : mockConversations };
    }
    return request("/chat/history");
  },

  async sendMessage(
    conversationId: string | null,
    message: string,
    role?: Role,
  ): Promise<{ conversation_id: string; answer: string; sources: { document: string; page: number; excerpt: string }[] }> {
    if (isMock("chat")) {
      await delay(1000);
      const resp = mockChatResponse(message, role);
      return { conversation_id: conversationId || "CONV-NEW", answer: resp.answer, sources: resp.sources };
    }
    return request("/chat", { method: "POST", body: JSON.stringify({ conversation_id: conversationId, message }) });
  },
};
