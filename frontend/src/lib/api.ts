import type {
  DataRefreshResult,
  DemoSeedResult,
  DecisionCard,
  DecisionCardInput,
  DecisionReadiness,
  DecisionReview,
  DecisionReviewInput,
  DecisionReviewQueue,
  DecisionReviewTrigger,
  Evidence,
  EvidenceItem,
  FactorSnapshot,
  ImpactMatrix,
  MarketOverview,
  MarketPackDetail,
  MarketPackDraftInput,
  MarketPackExport,
  MarketPackImportInput,
  MarketPackPreview,
  MarketPackSummary,
  NewsItem,
  NewsPollingStatus,
  NewsRefreshResult,
  PublicDataSource,
  ResearchObservability,
  ResearchRun,
  ScenarioInput,
  ScenarioResult,
  SensitivityResult,
  SimulationResult,
  StreamEvent,
  Subscription,
  SubscriptionInput,
  CountryProfile,
  CountryRefreshResult,
  CountryWorkspace,
  ResearchReport,
  ReportEmailResult,
  ProjectOpportunity,
  ProjectCreateInput,
  ProjectUpdateInput,
  AdmissionAssessment,
  DueDiligenceTask,
  TaskStatus,
} from '../types'

const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  })
  if (!response.ok) {
    const details = await response.text()
    throw new Error(details || `请求失败：${response.status}`)
  }
  return response.json() as Promise<T>
}

async function requestText(path: string, options?: RequestInit): Promise<string> {
  const response = await fetch(`${baseUrl}${path}`, options)
  if (!response.ok) {
    const details = await response.text()
    throw new Error(details || `Request failed: ${response.status}`)
  }
  return response.text()
}

export const api = {
  countries: () => request<CountryProfile[]>('/countries'),
  countryWorkspace: (profileId: string) => request<CountryWorkspace>(`/countries/${profileId}/workspace`),
  refreshCountry: (profileId: string) => request<CountryRefreshResult>(`/countries/${profileId}/refresh`, { method: 'POST' }),
  projects: (profileId?: string) => request<ProjectOpportunity[]>(`/projects${profileId ? `?profile_id=${profileId}` : ''}`),
  createProject: (payload: ProjectCreateInput) => request<ProjectOpportunity>('/projects', { method: 'POST', body: JSON.stringify(payload) }),
  updateProject: (projectId: string, payload: ProjectUpdateInput) => request<ProjectOpportunity>(`/projects/${projectId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  assessProject: (projectId: string) => request<AdmissionAssessment>(`/projects/${projectId}/assessments`, { method: 'POST' }),
  projectTasks: (projectId: string) => request<DueDiligenceTask[]>(`/projects/${projectId}/tasks`),
  updateProjectTask: (projectId: string, taskId: string, status: TaskStatus, completion_note?: string) =>
    request<DueDiligenceTask>(`/projects/${projectId}/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify({ status, completion_note }) }),
  projectBriefing: (projectId: string) => requestText(`/projects/${projectId}/briefing`),
  countryFeatures: (profileId: string) => request<FactorSnapshot>(`/countries/${profileId}/features`),
  refreshCountryFeatures: (profileId: string) => request<FactorSnapshot>(`/countries/${profileId}/features/refresh`, { method: 'POST' }),
  countryImpactMatrix: (profileId: string) => request<ImpactMatrix>(`/countries/${profileId}/impact-matrix`),
  countryEvidence: (profileId: string) => request<EvidenceItem[]>(`/countries/${profileId}/evidence`),
  countryEvidenceTimeline: (profileId: string) => request<EvidenceItem[]>(`/countries/${profileId}/evidence/timeline`),
  acknowledgeCountryEvidence: (profileId: string, evidenceId: string) =>
    request<EvidenceItem>(`/countries/${profileId}/evidence/${evidenceId}/acknowledge`, { method: 'POST' }),
  countryScenario: (profileId: string, scenario: ScenarioInput) => request<ScenarioResult>(`/countries/${profileId}/scenarios`, { method: 'POST', body: JSON.stringify(scenario) }),
  countrySimulation: (profileId: string, scenario: ScenarioInput) => request<SimulationResult>(`/countries/${profileId}/simulations`, { method: 'POST', body: JSON.stringify(scenario) }),
  countrySensitivity: (profileId: string, scenario: ScenarioInput) => request<SensitivityResult>(`/countries/${profileId}/sensitivity`, { method: 'POST', body: JSON.stringify(scenario) }),
  createResearchReport: (profileId: string, scenario: ScenarioInput) => request<ResearchReport>(`/countries/${profileId}/research-report`, { method: 'POST', body: JSON.stringify(scenario) }),
  reportDownloadUrl: (reportId: string, format: 'docx' | 'pdf') => `${baseUrl}/reports/${reportId}/download?format=${format}`,
  previewReportEmail: (reportId: string, email: string, formats: Array<'docx' | 'pdf'>) => request<ReportEmailResult>(`/reports/${reportId}/email-preview`, { method: 'POST', body: JSON.stringify({ email, formats }) }),
  sendReportEmail: (reportId: string, email: string, formats: Array<'docx' | 'pdf'>) => request<ReportEmailResult>(`/reports/${reportId}/send-email`, { method: 'POST', body: JSON.stringify({ email, formats }) }),
  overview: () => request<MarketOverview>('/market/overview'),
  marketPacks: () => request<MarketPackSummary[]>('/market-packs'),
  marketPackVersion: (packId: string, version: number) => request<MarketPackDetail>(`/market-packs/${packId}/versions/${version}`),
  createMarketPackDraft: (packId: string, draft: MarketPackDraftInput) =>
    request<MarketPackSummary>(`/market-packs/${packId}/drafts`, { method: 'POST', body: JSON.stringify(draft) }),
  publishMarketPack: (packId: string, version: number) =>
    request<MarketPackSummary>(`/market-packs/${packId}/versions/${version}/publish`, { method: 'POST' }),
  exportMarketPack: (packId: string, version: number) => request<MarketPackExport>(`/market-packs/${packId}/versions/${version}/export`),
  importMarketPack: (payload: MarketPackImportInput) =>
    request<MarketPackSummary>('/market-packs/imports', { method: 'POST', body: JSON.stringify(payload) }),
  previewMarketPack: (packId: string, version: number, scenario: ScenarioInput) =>
    request<MarketPackPreview>(`/market-packs/${packId}/versions/${version}/preview`, { method: 'POST', body: JSON.stringify(scenario) }),
  scenario: (scenario: ScenarioInput) =>
    request<ScenarioResult>('/market/scenarios', { method: 'POST', body: JSON.stringify(scenario) }),
  simulate: (scenario: ScenarioInput) =>
    request<SimulationResult>('/market/simulations', { method: 'POST', body: JSON.stringify(scenario) }),
  sensitivity: (scenario: ScenarioInput) =>
    request<SensitivityResult>('/market/sensitivity', { method: 'POST', body: JSON.stringify(scenario) }),
  seedDemo: () => request<DemoSeedResult>('/demo/seed', { method: 'POST' }),
  decisionReadiness: () => request<DecisionReadiness>('/decision-readiness'),
  news: () => request<NewsItem[]>('/news'),
  refreshNews: () => request<NewsRefreshResult>('/news/refresh', { method: 'POST' }),
  newsPollingStatus: () => request<NewsPollingStatus>('/news/polling-status'),
  subscribe: (subscription: SubscriptionInput) => request<Subscription>('/subscriptions', { method: 'POST', body: JSON.stringify(subscription) }),
  decisionCards: () => request<DecisionCard[]>('/decision-cards'),
  decisionReviewQueue: () => request<DecisionReviewQueue>('/decision-cards/review-queue'),
  decisionReviewTriggers: () => request<DecisionReviewTrigger[]>('/decision-cards/review-triggers'),
  decisionReviews: (cardId: string) => request<DecisionReview[]>(`/decision-cards/${cardId}/reviews`),
  decisionEvidenceSnapshot: (cardId: string) => request<Evidence[]>(`/decision-cards/${cardId}/evidence-snapshot`),
  createDecisionReview: (cardId: string, review: DecisionReviewInput) => request<DecisionReview>(`/decision-cards/${cardId}/reviews`, { method: 'POST', body: JSON.stringify(review) }),
  decisionBriefing: (cardId: string) => requestText(`/decision-cards/${cardId}/briefing`),
  saveDecisionCard: (card: DecisionCardInput) => request<DecisionCard>('/decision-cards', { method: 'POST', body: JSON.stringify(card) }),
  researchObservability: () => request<ResearchObservability>('/research/observability'),
  researchRuns: () => request<ResearchRun[]>('/research/runs'),
  sources: (profileId = 'de') => request<PublicDataSource[]>(`/data-sources?profile_id=${profileId}`),
  refreshData: () => request<DataRefreshResult>('/data/refresh', { method: 'POST' }),
  acknowledge: (id: string) => request<{ id: string; acknowledged: boolean }>(`/news/${id}/acknowledge`, { method: 'POST' }),
  previewEmail: (email: string) =>
    request<EmailPreviewResult>('/notifications/test-email', { method: 'POST', body: JSON.stringify({ email }) }),
}

export type EmailPreviewResult = {
  mode: 'preview' | 'sent'
  subject: string
  message: string
}

export async function streamResearch(
  question: string,
  scenario: ScenarioInput,
  profileId: CountryProfile['id'],
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${baseUrl}/research/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, scenario, profile_id: profileId }),
  })
  if (!response.ok || !response.body) throw new Error('研究服务暂时不可用')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const eventMatch = block.match(/^event: (.+)$/m)
      const dataMatch = block.match(/^data: (.+)$/m)
      if (!eventMatch || !dataMatch) continue
      onEvent({ type: eventMatch[1] as StreamEvent['type'], payload: JSON.parse(dataMatch[1]) } as StreamEvent)
    }
    if (done) break
  }
}
