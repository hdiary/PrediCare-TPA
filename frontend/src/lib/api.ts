import type {
  AuthResponse,
  RegisterPayload,
  Role,
  Invoice,
  Alert,
  AlertDetail,
  PrescriptionAlert,
  KPIData,
  ServiceStatus,
  SystemMetrics,
  ModelVersion,
  AuditLogEntry,
  AdminSettings,
  Conversation,
  InvoiceSubmissionResult,
} from "./types";

import {
  MOCK_ACCOUNTS,
  mockInvoices,
  mockAlerts,
  mockAlertDetail,
  mockPrescriptionAlerts,
  mockProviderConversations,
  mockKPIData,
  mockServiceStatus,
  mockSystemMetrics,
  mockModelVersions,
  mockAuditLog,
  mockAdminSettings,
  mockConversations,
  mockInvoiceResult,
  mockChatResponse,
} from "./mockData";

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";
export const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === "true";
const USE_MOCK_CHAT =
  USE_MOCK_AUTH || import.meta.env.VITE_USE_MOCK_CHAT === "true";
const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000")
  .replace(/\/+$/, "");

interface BackendUser {
  user_id: number;
  email: string;
  role: string;
  assure_id: string | null;
  prestataire_id: string | null;
}

const FRONTEND_ROLE: Record<string, Role> = {
  professionnel_sante: "provider",
  assure: "insured",
  gestionnaire: "manager",
  administrateur: "admin",
};

function mapBackendUser(user: BackendUser) {
  const role = FRONTEND_ROLE[user.role];
  if (!role) throw new Error("Rôle utilisateur non pris en charge");
  return {
    role,
    display_name: user.email,
    pseudonym: user.assure_id || user.prestataire_id || user.email,
    email: user.email,
  };
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("predicare_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

let refreshInFlight: Promise<boolean> | null = null;

function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    const refreshToken = localStorage.getItem("predicare_refresh_token");
    if (!refreshToken) return Promise.resolve(false);
    refreshInFlight = fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (response) => {
        if (!response.ok) return false;
        const tokens = (await response.json()) as {
          access_token: string;
          refresh_token: string;
        };
        localStorage.setItem("predicare_token", tokens.access_token);
        localStorage.setItem("predicare_refresh_token", tokens.refresh_token);
        return true;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const send = () => fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options.headers,
    },
  });
  const accessToken = localStorage.getItem("predicare_token");
  let res = await send();
  if (
    res.status === 401 &&
    !["/auth/login", "/auth/token", "/auth/refresh"].includes(path) &&
    localStorage.getItem("predicare_refresh_token")
  ) {
    if (
      localStorage.getItem("predicare_token") !== accessToken ||
      await refreshAccessToken()
    ) {
      res = await fetch(`${BASE_URL}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
          ...options.headers,
        },
      });
    }
  }
  if (res.status === 401) {
    localStorage.removeItem("predicare_token");
    localStorage.removeItem("predicare_refresh_token");
    window.location.href = "/login";
    throw new Error("Session expirée");
  }
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Accès refusé");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Erreur ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  async login(email: string, password: string): Promise<AuthResponse> {
    if (USE_MOCK_AUTH) {
      await delay(600);
      const account = MOCK_ACCOUNTS.find(
        (a) => a.email === email && a.password === password,
      );
      if (!account) throw new Error("Email ou mot de passe incorrect");
      return {
        access_token: "mock-jwt-" + account.role,
        role: account.role,
        display_name: account.display_name,
        pseudonym: account.pseudonym,
      };
    }
    const data = await request<{
      access_token: string;
      refresh_token: string;
      user: BackendUser;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    return {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      ...mapBackendUser(data.user),
    };
  },

  async logout(): Promise<void> {
    if (USE_MOCK_AUTH) return;
    await request<void>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({
        refresh_token: localStorage.getItem("predicare_refresh_token"),
      }),
    });
  },

  async getMe(): Promise<{
    role: Role;
    display_name: string;
    pseudonym: string;
    email: string;
  }> {
    if (USE_MOCK_AUTH) {
      await delay(200);
      const token = localStorage.getItem("predicare_token");
      const account = MOCK_ACCOUNTS.find((a) => "mock-jwt-" + a.role === token);
      if (!account) throw new Error("Non authentifié");
      return {
        role: account.role,
        display_name: account.display_name,
        pseudonym: account.pseudonym,
        email: account.email,
      };
    }
    const user = await request<BackendUser>("/auth/me");
    return mapBackendUser(user);
  },

  async getInvoices(filters?: {
    mine?: boolean;
    status?: string;
    page?: number;
  }): Promise<{ items: Invoice[]; total: number }> {
    if (USE_MOCKS) {
      await delay(400);
      let items = [...mockInvoices];
      if (filters?.status && filters.status !== "all") {
        items = items.filter((i) => i.status === filters.status);
      }
      return { items, total: items.length };
    }
    const params = new URLSearchParams();
    if (filters?.mine) params.set("mine", "true");
    if (filters?.status && filters.status !== "all")
      params.set("status", filters.status);
    if (filters?.page) params.set("page", String(filters.page));
    return request(`/invoices?${params}`);
  },

  async submitInvoice(
    data: FormData | Record<string, unknown>,
  ): Promise<InvoiceSubmissionResult> {
    if (USE_MOCKS) {
      await delay(1200);
      return mockInvoiceResult;
    }
    if (data instanceof FormData) {
      const res = await fetch(`${BASE_URL}/invoices`, {
        method: "POST",
        headers: { ...authHeaders() },
        body: data,
      });
      if (!res.ok) throw new Error("Erreur lors du dépôt");
      return res.json();
    }
    return request("/invoices", { method: "POST", body: JSON.stringify(data) });
  },

  async getAlerts(filters?: {
    status?: string;
    minScore?: number;
    page?: number;
  }): Promise<{ items: Alert[]; total: number }> {
    if (USE_MOCKS) {
      await delay(400);
      let items = [...mockAlerts];
      if (filters?.status && filters.status !== "all") {
        items = items.filter((a) => a.status === filters.status);
      }
      if (filters?.minScore) {
        items = items.filter((a) => a.score >= (filters.minScore || 0));
      }
      return { items, total: items.length };
    }
    const params = new URLSearchParams();
    if (filters?.status && filters.status !== "all")
      params.set("status", filters.status);
    if (filters?.minScore) params.set("min_score", String(filters.minScore));
    return request(`/alerts?${params}`);
  },

  async uploadPrescriptionScan(invoiceId: string, scan: File): Promise<void> {
    if (USE_MOCKS) {
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

  // ---- Comptes : routes publiques (sans jeton) ----
  async register(payload: RegisterPayload): Promise<{ status: "pending" }> {
    if (USE_MOCKS) {
      await delay(900);
      // Réponse identique que l'e-mail existe déjà ou non : on ne révèle pas quels comptes existent.
      return { status: "pending" };
    }
    return request("/auth/register", { method: "POST", body: JSON.stringify(payload) });
  },

  async requestPasswordReset(email: string): Promise<void> {
    if (USE_MOCKS) {
      await delay(700);
      return;
    }
    await request("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
  },

  async resetPassword(token: string, password: string): Promise<void> {
    if (USE_MOCKS) {
      await delay(700);
      if (token === "expire") throw new Error("Ce lien a expiré ou a déjà été utilisé. Refaites une demande.");
      return;
    }
    await request("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) });
  },

  async getPrescriptionAlerts(filters?: {
    rule?: string;
    minSeverity?: number;
  }): Promise<{ items: PrescriptionAlert[]; total: number }> {
    if (USE_MOCKS) {
      await delay(400);
      let items = [...mockPrescriptionAlerts];
      if (filters?.rule && filters.rule !== "all") {
        items = items.filter((a) => a.rule === filters.rule);
      }
      if (filters?.minSeverity) {
        items = items.filter((a) => a.severity >= (filters.minSeverity || 0));
      }
      return { items, total: items.length };
    }
    const params = new URLSearchParams();
    if (filters?.rule && filters.rule !== "all") params.set("rule", filters.rule);
    if (filters?.minSeverity) params.set("min_severity", String(filters.minSeverity));
    return request(`/prescription-alerts?${params}`);
  },

  async getAlertDetail(id: string): Promise<AlertDetail> {
    if (USE_MOCKS) {
      await delay(500);
      return { ...mockAlertDetail, id };
    }
    return request(`/alerts/${id}`);
  },

  async decideAlert(
    id: string,
    decision: "validate" | "reject",
    comment: string,
  ): Promise<{ id: string; status: string; decided_at: string }> {
    if (USE_MOCKS) {
      await delay(800);
      return {
        id,
        status: decision === "validate" ? "validated" : "rejected",
        decided_at: new Date().toISOString(),
      };
    }
    return request(`/alerts/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, comment }),
    });
  },

  async getKPIs(period?: string): Promise<KPIData> {
    if (USE_MOCKS) {
      await delay(500);
      return mockKPIData;
    }
    return request(`/kpis${period ? `?period=${period}` : ""}`);
  },

  async getServiceStatus(): Promise<ServiceStatus> {
    if (USE_MOCKS) {
      await delay(300);
      return mockServiceStatus;
    }
    return request("/admin/health");
  },

  async getSystemMetrics(period?: string): Promise<SystemMetrics> {
    if (USE_MOCKS) {
      await delay(500);
      return mockSystemMetrics;
    }
    return request(`/admin/metrics${period ? `?period=${period}` : ""}`);
  },

  async getModelVersions(): Promise<{
    active: string;
    versions: ModelVersion[];
  }> {
    if (USE_MOCKS) {
      await delay(400);
      return { active: "v2.3.0", versions: mockModelVersions };
    }
    return request("/admin/models");
  },

  async activateModel(version: string): Promise<{ active: string }> {
    if (USE_MOCKS) {
      await delay(800);
      return { active: version };
    }
    return request(`/admin/models/${version}/activate`, { method: "POST" });
  },

  async getAuditLog(filters?: {
    action?: string;
    actor?: string;
  }): Promise<{ items: AuditLogEntry[] }> {
    if (USE_MOCKS) {
      await delay(400);
      return { items: mockAuditLog };
    }
    const params = new URLSearchParams();
    if (filters?.action) params.set("action", filters.action);
    if (filters?.actor) params.set("actor", filters.actor);
    return request(`/admin/audit-log?${params}`);
  },

  async getAdminSettings(): Promise<AdminSettings> {
    if (USE_MOCKS) {
      await delay(300);
      return mockAdminSettings;
    }
    return request("/admin/settings");
  },

  async updateAdminSettings(settings: AdminSettings): Promise<AdminSettings> {
    if (USE_MOCKS) {
      await delay(600);
      return settings;
    }
    return request("/admin/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  },

  async getConversations(role?: Role): Promise<{ conversations: Conversation[] }> {
    if (USE_MOCK_CHAT) {
      await delay(300);
      return { conversations: role === "provider" ? mockProviderConversations : mockConversations };
    }
    return request("/chat/history");
  },

  async sendMessage(
    conversationId: string | null,
    message: string,
    role?: Role,
  ): Promise<{
    conversation_id: string;
    answer: string;
    sources: { document: string; page: number; excerpt: string }[];
  }> {
    if (USE_MOCK_CHAT) {
      await delay(1000);
      const resp = mockChatResponse(message, role);
      return {
        conversation_id: conversationId || "CONV-NEW",
        answer: resp.answer,
        sources: resp.sources,
      };
    }
    return request("/chat", {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId, message }),
    });
  },
};
