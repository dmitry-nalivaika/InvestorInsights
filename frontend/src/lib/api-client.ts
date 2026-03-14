// filepath: frontend/src/lib/api-client.ts
/**
 * Typed API client for the InvestorInsights backend.
 *
 * All endpoints return typed responses. Errors throw `ApiError`.
 */

// ── Types ───────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body?: unknown,
  ) {
    super(`API ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ── Company types ───────────────────────────────────────────────

export interface Company {
  id: string;
  ticker: string;
  name: string;
  cik: string | null;
  sector: string | null;
  industry: string | null;
  description: string | null;
  doc_count?: number;
  latest_filing_date?: string | null;
  readiness_pct?: number | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyDetail extends Company {
  documents_summary?: {
    total: number;
    by_status: Record<string, number>;
    by_type: Record<string, number>;
    year_range: { min: number; max: number } | null;
  };
  financials_summary?: {
    periods_available: number;
    year_range: { min: number; max: number } | null;
  };
  recent_sessions?: ChatSession[];
}

export interface CompanyCreate {
  ticker: string;
  name?: string;
  cik?: string;
  sector?: string;
  industry?: string;
}

// ── Document types ──────────────────────────────────────────────

export interface Document {
  id: string;
  company_id: string;
  doc_type: string;
  fiscal_year: number;
  fiscal_quarter: number | null;
  filing_date: string;
  period_end_date: string;
  status: string;
  page_count: number | null;
  sec_accession: string | null;
  source_url: string | null;
  created_at: string;
  updated_at: string;
}

// ── Chat types ──────────────────────────────────────────────────

export interface ChatSession {
  id: string;
  company_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  created_at: string;
}

export interface ChatSource {
  chunk_id: string;
  doc_type: string;
  fiscal_year: number;
  section_title?: string;
  score: number;
  text_preview?: string;
}

// ── Analysis types ──────────────────────────────────────────────

export interface AnalysisProfile {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AnalysisProfileDetail extends AnalysisProfile {
  criteria: AnalysisCriterion[];
}

export interface AnalysisCriterion {
  id: string;
  profile_id: string;
  name: string;
  category: string;
  description: string | null;
  formula: string;
  is_custom_formula: boolean;
  comparison: string;
  threshold_value: number | null;
  threshold_low: number | null;
  threshold_high: number | null;
  weight: number;
  lookback_years: number;
  enabled: boolean;
  sort_order: number;
  created_at: string;
}

export interface AnalysisResult {
  id: string;
  company_id: string;
  company_ticker: string | null;
  company_name: string | null;
  profile_id: string;
  profile_version: number;
  run_at: string;
  overall_score: number;
  max_score: number;
  pct_score: number;
  grade: string;
  criteria_count: number;
  passed_count: number;
  failed_count: number;
  criteria_results: CriteriaResultItem[];
  summary: string | null;
  created_at: string;
}

export interface CriteriaResultItem {
  criteria_name: string;
  category: string;
  formula: string;
  values_by_year: Record<string, number | null>;
  latest_value: number | null;
  threshold: string;
  passed: boolean;
  weighted_score: number;
  trend: string | null;
  note: string | null;
}

export interface FormulaInfo {
  name: string;
  category: string;
  description: string;
  required_fields: string[];
  example: string | null;
}

// Comparison types
export interface ComparisonRanking {
  rank: number;
  company_id: string;
  company_ticker: string | null;
  company_name: string | null;
  result_id: string;
  overall_score: number;
  max_score: number;
  pct_score: number;
  grade: string;
  passed_count: number;
  failed_count: number;
  criteria_count: number;
  status: "scored" | "no_data";
  criteria_results: {
    criteria_name: string;
    category: string;
    formula: string;
    latest_value: number | null;
    threshold: string;
    passed: boolean;
    has_data: boolean;
    weighted_score: number;
    weight: number;
    trend: string | null;
    values_by_year: Record<string, number | null>;
  }[];
  summary: string | null;
}

export interface ComparisonResponse {
  profile_id: string;
  profile_name: string;
  companies_count: number;
  criteria_names: string[];
  rankings: ComparisonRanking[];
}

// ── Financial types ─────────────────────────────────────────────

export interface FinancialPeriod {
  fiscal_year: number;
  fiscal_quarter: number | null;
  period_end_date: string;
  income_statement: Record<string, number | null>;
  balance_sheet: Record<string, number | null>;
  cash_flow: Record<string, number | null>;
}

// ── Client ──────────────────────────────────────────────────────

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

function getApiKey(): string {
  return process.env.NEXT_PUBLIC_API_KEY ?? "";
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${API_PREFIX}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-API-Key": getApiKey(),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    throw new ApiError(res.status, res.statusText, body);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ── Companies ───────────────────────────────────────────────────

export const companiesApi = {
  list(params?: {
    search?: string;
    sector?: string;
    sort_by?: string;
    sort_order?: string;
    limit?: number;
    offset?: number;
  }) {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) qs.set(k, String(v));
      });
    }
    const q = qs.toString();
    return request<PaginatedResponse<Company>>(
      `/companies${q ? `?${q}` : ""}`,
    );
  },

  get(id: string) {
    return request<CompanyDetail>(`/companies/${id}`);
  },

  create(data: CompanyCreate) {
    return request<Company>("/companies", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update(id: string, data: Partial<CompanyCreate>) {
    return request<Company>(`/companies/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete(id: string) {
    return request<void>(`/companies/${id}?confirm=true`, {
      method: "DELETE",
    });
  },
};

// ── Documents ───────────────────────────────────────────────────

export const documentsApi = {
  list(companyId: string, params?: Record<string, string | number>) {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) qs.set(k, String(v));
      });
    }
    const q = qs.toString();
    return request<PaginatedResponse<Document>>(
      `/companies/${companyId}/documents${q ? `?${q}` : ""}`,
    );
  },

  fetchSec(companyId: string, data?: { filing_types?: string[]; years_back?: number }) {
    return request<{ task_id: string; message: string; estimated_filings: number }>(
      `/companies/${companyId}/documents/fetch-sec`,
      { method: "POST", body: JSON.stringify(data ?? {}) },
    );
  },

  retry(companyId: string, documentId: string) {
    return request<{ message: string }>(
      `/companies/${companyId}/documents/${documentId}/retry`,
      { method: "POST" },
    );
  },

  delete(companyId: string, documentId: string) {
    return request<void>(
      `/companies/${companyId}/documents/${documentId}?confirm=true`,
      { method: "DELETE" },
    );
  },
};

// ── Chat ────────────────────────────────────────────────────────

export const chatApi = {
  listSessions(companyId: string, params?: { limit?: number; offset?: number }) {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) qs.set(k, String(v));
      });
    }
    const q = qs.toString();
    return request<PaginatedResponse<ChatSession>>(
      `/companies/${companyId}/chat/sessions${q ? `?${q}` : ""}`,
    );
  },

  getSession(companyId: string, sessionId: string) {
    return request<{ session: ChatSession; messages: ChatMessage[] }>(
      `/companies/${companyId}/chat/sessions/${sessionId}`,
    );
  },

  deleteSession(companyId: string, sessionId: string) {
    return request<void>(
      `/companies/${companyId}/chat/sessions/${sessionId}`,
      { method: "DELETE" },
    );
  },

  /** Returns the streaming URL — caller handles SSE parsing. */
  streamUrl(companyId: string) {
    return `${BASE_URL}${API_PREFIX}/companies/${companyId}/chat`;
  },
};

// ── Analysis ────────────────────────────────────────────────────

export const analysisApi = {
  // Profiles
  listProfiles() {
    return request<PaginatedResponse<AnalysisProfile>>("/analysis/profiles");
  },

  getProfile(id: string) {
    return request<AnalysisProfileDetail>(`/analysis/profiles/${id}`);
  },

  createProfile(data: {
    name: string;
    description?: string;
    is_default?: boolean;
    criteria: Omit<AnalysisCriterion, "id" | "profile_id" | "created_at">[];
  }) {
    return request<AnalysisProfileDetail>("/analysis/profiles", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateProfile(
    id: string,
    data: {
      name?: string;
      description?: string;
      is_default?: boolean;
      criteria?: Omit<AnalysisCriterion, "id" | "profile_id" | "created_at">[];
    },
  ) {
    return request<AnalysisProfileDetail>(`/analysis/profiles/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  deleteProfile(id: string) {
    return request<void>(`/analysis/profiles/${id}`, { method: "DELETE" });
  },

  // Run
  runAnalysis(data: {
    company_ids: string[];
    profile_id: string;
    generate_summary?: boolean;
  }) {
    return request<{ results: AnalysisResult[] }>("/analysis/run", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Results
  listResults(params?: {
    company_id?: string;
    profile_id?: string;
    limit?: number;
    offset?: number;
  }) {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) qs.set(k, String(v));
      });
    }
    const q = qs.toString();
    return request<PaginatedResponse<AnalysisResult>>(
      `/analysis/results${q ? `?${q}` : ""}`,
    );
  },

  getResult(id: string) {
    return request<AnalysisResult>(`/analysis/results/${id}`);
  },

  exportResult(id: string) {
    return request<AnalysisResult>(`/analysis/results/${id}/export`);
  },

  // Formulas
  listFormulas() {
    return request<{ formulas: FormulaInfo[] }>("/analysis/formulas");
  },

  // Comparison
  compare(data: {
    company_ids: string[];
    profile_id: string;
    generate_summary?: boolean;
  }) {
    return request<ComparisonResponse>("/analysis/compare", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

// ── Financials ──────────────────────────────────────────────────

export const financialsApi = {
  get(
    companyId: string,
    params?: { period?: string; start_year?: number; end_year?: number },
  ) {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) qs.set(k, String(v));
      });
    }
    const q = qs.toString();
    return request<{ company_id: string; periods: FinancialPeriod[] }>(
      `/companies/${companyId}/financials${q ? `?${q}` : ""}`,
    );
  },

  exportCsvUrl(companyId: string, params?: { period?: string }) {
    const qs = new URLSearchParams();
    if (params?.period) qs.set("period", params.period);
    qs.set("api_key", getApiKey());
    return `${BASE_URL}${API_PREFIX}/companies/${companyId}/financials/export?${qs}`;
  },
};

// ── Health ──────────────────────────────────────────────────────

export const healthApi = {
  check() {
    return request<{
      status: string;
      components: Record<string, string>;
      version: string;
      uptime_seconds: number;
    }>("/health");
  },
};
