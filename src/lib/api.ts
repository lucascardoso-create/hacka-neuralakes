export type RunMode = 'fixture' | 'replay' | 'live'

export type FlowNodePayload = {
  id: string
  label: string
  connector?: string
  operation?: string
  position?: { x: number; y: number }
}

export type ApiError = Error & {
  status?: number
  code?: string
}

export type CaseInput = {
  title: string
  represented_side: string
  success_definition: string
  target_stage: string
  target_claim_id: string | null
  as_of_date: string
  text?: string
  document_ids?: string[]
}

export type Run = {
  id: string
  status: string
  current_step?: string
  progress?: { completed?: number; total?: number }
  result_ref?: string | null
  blockers?: Array<{ code?: string; message_safe?: string }>
}

export type Event = {
  event_id: string
  sequence: number
  timestamp: string
  run_id: string
  step_id?: string
  kind: string
  status: string
  message_safe?: string
  metrics_delta?: Record<string, number | string | null>
}

export type AnalysisResult = {
  repetitividade?: number | null
  exito?: number | null
  abstention_reasons?: string[]
  evidence_ids?: string[]
  calibration_status?: string
  provenance?: Record<string, unknown>
  analysis?: {
    synthetic: boolean
    demand: string
    methodology: string
    comparisons: Array<{ id: string; score: number; result: string; reason: string }>
    conclusion: string
  }
}

export type Connector = {
  id: string
  plugin_id?: string
  configured?: boolean
  mode_supported?: RunMode[]
  capabilities?: string[]
}

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim()
const baseUrl = (configuredApiUrl || '/v1').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    let body: { error?: { code?: string; message?: string } } = {}
    try {
      body = await response.json()
    } catch {
      // Keep the HTTP status when the backend returned no JSON envelope.
    }
    const error = new Error(body.error?.message || `Backend respondeu ${response.status}`) as ApiError
    error.status = response.status
    error.code = body.error?.code
    throw error
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  baseUrl,
  listConnectors: () => request<Connector[]>('/connectors'),
  createCase: (body: CaseInput) => request<{ id: string }>('/cases', {
    method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: JSON.stringify(body),
  }),
  startRun: (caseId: string, mode: RunMode, nodes: FlowNodePayload[], edges: Array<[string, string]>) => request<{ id: string; status_url?: string }>(`/cases/${caseId}/runs`, {
    method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: JSON.stringify({ mode, policy_version: 'v0.1', budget: { max_provider_calls: 12 }, nodes, edges }),
  }),
  testNode: (body: { node_id: string; connector?: string; operation?: string; mode: RunMode }) => request<{ status: string; message_safe: string; output?: Record<string, unknown> }>('/nodes/test', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  getRun: (runId: string) => request<Run>(`/runs/${runId}`),
  getEvents: (runId: string, cursor?: number) => request<{ events: Event[]; next_cursor?: number }>(
    `/runs/${runId}/events?after=${cursor || 0}&limit=100`,
  ),
  getResult: (runId: string) => request<AnalysisResult>(`/runs/${runId}/result`),
  cancelRun: (runId: string) => request<void>(`/runs/${runId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason: 'cancelled_by_user' }),
  }),
}
