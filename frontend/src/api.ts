/**
 * Cliente HTTP da API GenomAI.
 *
 * Todas as requisições enviam o cabeçalho `X-GenomAI-Persona`. O backend é a
 * fonte de verdade das permissões: esconder um botão no frontend é apenas
 * conveniência de UX, nunca a barreira de segurança.
 */

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const PERSONA_STORAGE_KEY = "genomai.persona";
export const PERSONA_IDS = ["leitor", "analista", "desenvolvedor", "administrador"] as const;
export type PersonaId = (typeof PERSONA_IDS)[number];

/** Lê a persona escolhida pelo usuário, com fallback seguro. */
export function getStoredPersona(): PersonaId {
  if (typeof window === "undefined") return "analista";
  const stored = window.localStorage.getItem(PERSONA_STORAGE_KEY);
  return (PERSONA_IDS as readonly string[]).includes(stored ?? "") ? (stored as PersonaId) : "analista";
}

let currentPersona: PersonaId = getStoredPersona();

/** Atualiza a persona usada nas próximas requisições e persiste a escolha. */
export function setStoredPersona(persona: PersonaId): void {
  currentPersona = persona;
  if (typeof window !== "undefined") window.localStorage.setItem(PERSONA_STORAGE_KEY, persona);
}

export type TableSummary = {
  name: string;
  schema: string;
  columns_count: number;
  primary_key: string[];
  foreign_keys_count: number;
};

export type ColumnInfo = {
  name: string;
  type: string;
  nullable: boolean;
  default?: string | null;
  is_primary_key: boolean;
};

export type TableInfo = {
  name: string;
  schema: string;
  columns: ColumnInfo[];
  primary_key: string[];
  foreign_keys: {
    constrained_columns: string[];
    referred_table: string;
    referred_schema: string;
    referred_columns: string[];
  }[];
  indexes: { name: string; column_names: string[]; unique: boolean }[];
};

export type TableRows = {
  table: string;
  schema: string;
  columns: ColumnInfo[];
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
};

export type TableRelationship = {
  constraint_name: string;
  source_table: string;
  source_schema: string;
  source_columns: string[];
  target_table: string;
  target_schema: string;
  target_columns: string[];
};

export type TableRelationships = {
  table: string;
  schema: string;
  outbound: TableRelationship[];
  inbound: TableRelationship[];
};

export type Metrics = {
  tables_total: number;
  tables_with_basic_metadata: number;
  metadata_coverage_percent: number;
  tables_without_primary_key: number;
  pending_suggestions: number;
  partially_approved_suggestions: number;
  total_suggestions: number;
  approved_suggestions: number;
  rejected_suggestions: number;
  reviewed_suggestions: number;
  review_rate_percent: number;
  note: string;
};

export type Recommendation = {
  severity: "low" | "medium" | "high";
  table: string;
  category: string;
  message: string;
  suggested_sql?: string | null;
  evidence?: string | null;
};

export type SuggestionStatus = "pending" | "approved" | "rejected" | "partially_approved";

export type Suggestion = {
  id: number;
  table: string;
  kind: string;
  column_name: string | null;
  description: string;
  confidence: number;
  status: SuggestionStatus;
  rationale: string;
  suggested_sql: string | null;
  version: number;
  previous_status: string | null;
  review_comment: string;
  reviewed_by: string | null;
  edited_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  reviewed_at: string | null;
  applied_at: string | null;
  applied_by: string | null;
  apply_error: string | null;
  revision_count: number;
};

export type SuggestionEdit = {
  table?: string;
  kind?: string;
  column_name?: string | null;
  description?: string;
  confidence?: number;
  rationale?: string;
  suggested_sql?: string | null;
  comment?: string;
  reopen?: boolean;
};

export type SuggestionRevision = {
  id: number;
  suggestion_id: number;
  version: number;
  table: string;
  kind: string;
  column_name: string | null;
  description: string;
  confidence: number;
  status: SuggestionStatus;
  rationale: string;
  suggested_sql: string | null;
  edited_by: string;
  comment: string;
  created_at: string;
};

export type ApplyPreview = {
  suggestion_id: number;
  action: string;
  sql: string | null;
  can_apply: boolean;
  blockers: string[];
  warnings: string[];
};

export type ApplyResult = {
  suggestion_id: number;
  action: string;
  success: boolean;
  sql: string | null;
  error: string | null;
  applied_at: string | null;
  applied_by: string | null;
  log_id: number | null;
};

export type ApplyLog = {
  id: number;
  suggestion_id: number | null;
  persona: string;
  action: string;
  sql_text: string;
  success: boolean;
  error: string | null;
  duration_ms: number | null;
  created_at: string;
};

export type PersonaInfo = {
  id: PersonaId;
  label: string;
  description: string;
  capabilities: string[];
};

export type StorageInfo = {
  analyzed: {
    dialect: string;
    schema: string;
    read_only: boolean;
    excluded_tables: string[];
  };
  app_store: {
    backend: string;
    schema: string | null;
    persistent: boolean;
    remote: boolean;
    location: string;
    isolation: string;
    tables: string[];
    available: boolean;
    error?: string;
  };
  isolation: {
    separate_connection: boolean;
    separate_storage: boolean;
    separate_schema: boolean;
    ai_receives_only_safe_metadata: boolean;
    same_connection_string: boolean;
    valid: boolean;
    error: string | null;
    warnings: string[];
  };
  ai: {
    enabled: boolean;
    provider: string;
    model: string;
    payload_policy: string;
    write_access: boolean;
    applies_changes: boolean;
  };
};

export type PrivacyPolicy = {
  policy: string;
  allowed_fields: string[];
  never_sent: string[];
  sensitive_categories: string[];
  mask_sensitive_identifiers: boolean;
  redact_digit_runs: boolean;
  excluded_tables: string[];
  audit: string;
};

export type AiPayloadPreview = {
  payload: {
    schema_name: string;
    tables: {
      name: string;
      columns: {
        name: string;
        type: string;
        nullable: boolean;
        is_primary_key: boolean;
        sensitive: boolean;
        sensitivity_category: string | null;
      }[];
      primary_key: string[];
      foreign_keys: unknown[];
      indexes: unknown[];
    }[];
    policy: string;
  };
  report: {
    tables_included: number;
    tables_excluded: number;
    columns_included: number;
    sensitive_columns: number;
    redacted_identifiers: number;
    removed_fields: number;
    masked_sensitive_identifiers: boolean;
    excluded_table_names: string[];
    notice: string;
  };
  sha256: string;
  policy: PrivacyPolicy;
};

export type AiAnalysisResult = {
  summary: string;
  suggestions_created: number;
  duplicates_skipped: number;
  suggestions: Suggestion[];
  human_review_required: boolean;
  database_changes_applied: boolean;
  privacy: {
    policy: string;
    payload_sha256: string;
    tables_sent: number;
    columns_sent: number;
    sensitive_columns_flagged: number;
    redacted_identifiers: number;
    excluded_tables: string[];
    records_sent: number;
    defaults_sent: number;
  };
};

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-GenomAI-Persona": currentPersona,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    let message = `Falha ao consultar a API (${response.status}).`;
    if (typeof detail === "string") message = detail;
    else if (detail && typeof detail === "object" && Array.isArray(detail.blockers)) {
      message = detail.blockers.join(" ");
    } else if (Array.isArray(detail) && detail.length) {
      message = detail.map((item) => item.msg ?? String(item)).join("; ");
    }
    throw new ApiError(response.status, message, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; database: string; engine: string }>("/health"),
  metrics: () => request<Metrics>("/api/v1/dashboard/metrics"),
  tables: (q = "") =>
    request<{ count: number; items: TableSummary[] }>(
      `/api/v1/catalog/tables${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),
  table: (name: string) => request<TableInfo>(`/api/v1/catalog/tables/${encodeURIComponent(name)}`),
  rows: (name: string, limit = 25, offset = 0) =>
    request<TableRows>(
      `/api/v1/catalog/tables/${encodeURIComponent(name)}/rows?limit=${limit}&offset=${offset}`,
    ),
  relationships: (name: string) =>
    request<TableRelationships>(`/api/v1/catalog/tables/${encodeURIComponent(name)}/relationships`),
  analyze: () =>
    request<{ summary: string; tables_analyzed: number; recommendations: Recommendation[] }>(
      "/api/v1/advisor/analyze",
    ),
  aiAnalyze: () => request<AiAnalysisResult>("/api/v1/advisor/ai-analyze", { method: "POST" }),

  personas: () => request<PersonaInfo[]>("/api/v1/personas"),
  storage: () => request<StorageInfo>("/api/v1/system/storage"),
  privacyPolicy: () => request<PrivacyPolicy>("/api/v1/privacy/policy"),
  aiPayload: () => request<AiPayloadPreview>("/api/v1/privacy/ai-payload"),

  suggestions: (status: string, params: { table?: string; q?: string } = {}) => {
    const search = new URLSearchParams({ status });
    if (params.table) search.set("table", params.table);
    if (params.q) search.set("q", params.q);
    return request<Suggestion[]>(`/api/v1/suggestions?${search.toString()}`);
  },
  createSuggestion: (body: {
    table: string;
    kind: string;
    column_name?: string | null;
    description: string;
    confidence: number;
    rationale: string;
    suggested_sql?: string | null;
  }) => request<Suggestion>("/api/v1/suggestions", { method: "POST", body: JSON.stringify(body) }),
  editSuggestion: (id: number, body: SuggestionEdit) =>
    request<Suggestion>(`/api/v1/suggestions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  review: (id: number, decision: SuggestionStatus, comment = "") =>
    request<{ id: number; status: string; comment: string; reviewed_by: string | null }>(
      `/api/v1/suggestions/${id}/review`,
      { method: "POST", body: JSON.stringify({ decision, comment }) },
    ),
  revisions: (id: number) => request<SuggestionRevision[]>(`/api/v1/suggestions/${id}/revisions`),
  applyPreview: (id: number) =>
    request<ApplyPreview>(`/api/v1/suggestions/${id}/apply-preview`),
  apply: (id: number) =>
    request<ApplyResult>(`/api/v1/suggestions/${id}/apply`, { method: "POST" }),
  applyLogs: (suggestionId?: number) =>
    request<ApplyLog[]>(
      `/api/v1/apply-logs${suggestionId ? `?suggestion_id=${suggestionId}` : ""}`,
    ),
};
