/**
 * Typed API client + TanStack Query hooks.
 *
 * Every endpoint of the FastAPI service has exactly one hook here.
 * Request and response shapes come from `./types.ts`, which is regenerated
 * from `/api/openapi.json` via `npm run gen:api` — so editing this file
 * by hand is not how types should drift; they should drift via the
 * backend OpenAPI spec.
 *
 * No state-management library. TanStack Query owns server state. Local UI
 * state goes in component `useState`. Filter selections live in the URL.
 */
import { useQuery } from '@tanstack/react-query'
import type { components } from './types'

type Schemas = components['schemas']

// ─── Domain type re-exports (component code imports from here, not types.ts)

export type FeedbackSummary = Schemas['FeedbackSummary']
export type FeedbackDetail = Schemas['FeedbackDetail']
export type ClassificationSummary = Schemas['ClassificationSummary']
export type CitationSummary = Schemas['CitationSummary']
export type DraftSummary = Schemas['DraftSummary']
export type DraftListItem = Schemas['DraftListItem']
export type DraftDetail = Schemas['DraftDetail']
export type SpikeSummary = Schemas['SpikeSummary']
export type SpikeDetail = Schemas['SpikeDetail']
export type SpikeFeedbacksResponse = Schemas['SpikeFeedbacksResponse']
export type KnowledgeSourceHealth = Schemas['KnowledgeSourceHealth']
export type KnowledgeSourcesResponse = Schemas['KnowledgeSourcesResponse']
export type VolumeResponse = Schemas['VolumeResponse']
export type VolumeBucket = Schemas['VolumeBucket']
export type CategoriesResponse = Schemas['CategoriesResponse']
export type CategoryCount = Schemas['CategoryCount']
export type AppResponse = Schemas['AppResponse']
export type HealthResponse = Schemas['HealthResponse']
export type AuditLogItem = Schemas['AuditLogItem']

// ─── Filter shape used by most list endpoints

export type ScopeFilters = {
  app?: string
  platform?: string
  channel?: string
  since?: string
  limit?: number
}

// ─── Low-level fetch wrapper

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(
      `GET ${path} → HTTP ${response.status}${detail ? `: ${detail}` : ''}`,
    )
  }
  return response.json() as Promise<T>
}

function buildQuery(params: Record<string, unknown>): string {
  const pairs: string[] = []
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    pairs.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
  }
  return pairs.length ? `?${pairs.join('&')}` : ''
}

// ─── Hooks (auto-refresh intervals match the plan: section 10)

/** GET /api/health */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => get<HealthResponse>('/api/health'),
    refetchInterval: 60_000,
  })
}

/** GET /api/apps */
export function useApps() {
  return useQuery({
    queryKey: ['apps'],
    queryFn: () => get<AppResponse[]>('/api/apps'),
    staleTime: 5 * 60_000,
  })
}

/** GET /api/feedback?... */
export function useFeedbackList(filters: ScopeFilters) {
  return useQuery({
    queryKey: ['feedback', filters],
    queryFn: () =>
      get<FeedbackSummary[]>(`/api/feedback${buildQuery(filters)}`),
    refetchInterval: 30_000,
  })
}

/** GET /api/feedback/{feedback_id} */
export function useFeedbackDetail(feedbackId: string | null) {
  return useQuery({
    queryKey: ['feedback', feedbackId],
    queryFn: () => get<FeedbackDetail>(`/api/feedback/${feedbackId}`),
    enabled: Boolean(feedbackId),
  })
}

/** GET /api/drafts?... */
export type DraftFilters = ScopeFilters & { status?: string }

export function useDrafts(filters: DraftFilters) {
  return useQuery({
    queryKey: ['drafts', filters],
    queryFn: () =>
      get<DraftListItem[]>(`/api/drafts${buildQuery(filters)}`),
    refetchInterval: 30_000,
  })
}

/** GET /api/drafts/{draft_id} */
export function useDraftDetail(draftId: string | null) {
  return useQuery({
    queryKey: ['draft', draftId],
    queryFn: () => get<DraftDetail>(`/api/drafts/${draftId}`),
    enabled: Boolean(draftId),
  })
}

/** GET /api/spikes?... */
export type SpikeFilters = {
  app?: string
  active?: boolean
  since?: string
  limit?: number
}

export function useSpikes(filters: SpikeFilters) {
  return useQuery({
    queryKey: ['spikes', filters],
    queryFn: () => get<SpikeSummary[]>(`/api/spikes${buildQuery(filters)}`),
    refetchInterval: 30_000,
  })
}

/** GET /api/spikes/{spike_id}/feedbacks */
export function useSpikeFeedbacks(spikeId: string | null) {
  return useQuery({
    queryKey: ['spike-feedbacks', spikeId],
    queryFn: () =>
      get<SpikeFeedbacksResponse>(`/api/spikes/${spikeId}/feedbacks`),
    enabled: Boolean(spikeId),
  })
}

/** GET /api/knowledge/sources */
export function useKnowledgeSources() {
  return useQuery({
    queryKey: ['knowledge-sources'],
    queryFn: () => get<KnowledgeSourcesResponse>('/api/knowledge/sources'),
    refetchInterval: 60_000,
  })
}

/** GET /api/analytics/volume */
export type AnalyticsFilters = {
  range_days?: number
  app?: string
  platform?: string
  channel?: string
}

export function useVolume(filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ['volume', filters],
    queryFn: () => get<VolumeResponse>(`/api/analytics/volume${buildQuery(filters)}`),
    refetchInterval: 5 * 60_000,
  })
}

/** GET /api/analytics/categories */
export function useCategoryMix(filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ['categories', filters],
    queryFn: () =>
      get<CategoriesResponse>(`/api/analytics/categories${buildQuery(filters)}`),
    refetchInterval: 5 * 60_000,
  })
}

/** GET /api/audit */
export type AuditFilters = {
  actor?: string
  since?: string
  limit?: number
}

export function useAuditLog(filters: AuditFilters) {
  return useQuery({
    queryKey: ['audit', filters],
    queryFn: () => get<AuditLogItem[]>(`/api/audit${buildQuery(filters)}`),
    refetchInterval: 30_000,
  })
}
