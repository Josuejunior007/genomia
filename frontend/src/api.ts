const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export type TableSummary = {
  name: string; schema: string; columns_count: number; primary_key: string[]; foreign_keys_count: number
}
export type ColumnInfo = { name: string; type: string; nullable: boolean; default?: string | null; is_primary_key: boolean }
export type TableInfo = {
  name: string; schema: string; columns: ColumnInfo[]; primary_key: string[]
  foreign_keys: { constrained_columns: string[]; referred_table: string; referred_schema: string; referred_columns: string[] }[]
  indexes: { name: string; column_names: string[]; unique: boolean }[]
}
export type Metrics = {
  tables_total: number; tables_with_basic_metadata: number; metadata_coverage_percent: number
  tables_without_primary_key: number; pending_suggestions: number; total_suggestions: number
  approved_suggestions: number; rejected_suggestions: number; reviewed_suggestions: number; review_rate_percent: number; note: string
}
export type Recommendation = { severity: 'low' | 'medium' | 'high'; table: string; category: string; message: string; suggested_sql?: string | null; evidence?: string | null }
export type Suggestion = { id: number; table: string; kind: string; description: string; confidence: number; status: string; rationale: string }
export type AiAnalysisResult = { summary: string; suggestions_created: number; suggestions: Suggestion[]; human_review_required: boolean; database_changes_applied: boolean }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `Falha ao consultar a API (${response.status}).`
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; database: string; engine: string }>('/health'),
  metrics: () => request<Metrics>('/api/v1/dashboard/metrics'),
  tables: (q = '') => request<{ count: number; items: TableSummary[] }>(`/api/v1/catalog/tables${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  table: (name: string) => request<TableInfo>(`/api/v1/catalog/tables/${encodeURIComponent(name)}`),
  analyze: () => request<{ summary: string; tables_analyzed: number; recommendations: Recommendation[] }>('/api/v1/advisor/analyze'),
  aiAnalyze: () => request<AiAnalysisResult>('/api/v1/advisor/ai-analyze', { method: 'POST' }),
  suggestions: (status: string) => request<Suggestion[]>(`/api/v1/suggestions?status=${status}`),
  review: (id: number, decision: 'approved' | 'rejected') => request(`/api/v1/suggestions/${id}/review`, {
    method: 'POST', body: JSON.stringify({ decision, comment: '' }),
  }),
}
