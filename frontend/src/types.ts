export type ScoreComponent = {
  key: string
  label: string
  score: number
  weight: number
  explanation: string
}

export type Evidence = {
  id: string
  title: string
  source: string
  excerpt: string
  metric: string
}

export type MetricPoint = {
  month: string
  opportunity: number
  capacity_gw: number
  demand_index: number
}

export type MarketOverview = {
  market: string
  score: number
  recommendation: string
  last_updated: string
  components: ScoreComponent[]
  metrics: MetricPoint[]
  evidence: Evidence[]
}

export type ScenarioInput = {
  subsidy_change: number
  demand_change: number
  grid_risk_change: number
  weather_change: number
}

export type ScenarioResult = {
  score: number
  delta: number
  recommendation: string
  component_scores: ScoreComponent[]
  explanation: string
}

export type SimulationResult = {
  iterations: number
  p10: number
  p50: number
  p90: number
  probability_research: number
  explanation: string
}

export type SensitivityItem = {
  key: string
  label: string
  positive_delta: number
  negative_delta: number
  impact: number
}

export type SensitivityResult = {
  baseline_score: number
  perturbation: number
  items: SensitivityItem[]
}

export type NewsItem = {
  id: string
  title: string
  category: string
  impact: 'low' | 'medium' | 'high'
  summary: string
  why: string
  source: string
  published_at: string
  acknowledged: boolean
  url?: string | null
}

export type PublicDataSource = {
  id: string
  name: string
  kind: 'energy' | 'weather'
  refresh_mode: 'manual' | 'scheduled'
  status: 'seed' | 'ready' | 'live' | 'degraded'
  note: string
  last_checked_at: string | null
  last_success_at: string | null
  observation_label: string
}

export type DataRefreshResult = {
  status: 'live' | 'degraded'
  owid: {
    country: string
    records: number
    latest_year: number
    solar_capacity_gw: number | null
    solar_electricity_twh: number
  } | null
  weather: {
    days: number
    average_temperature_c: number
    average_radiation_mj_m2: number
  } | null
  message: string
}

export type NewsRefreshResult = {
  status: 'live' | 'degraded'
  added: number
  message: string
  notifications_previewed: number
  notifications_sent: number
}

export type NewsPollingStatus = {
  enabled: boolean
  interval_seconds: number
}

export type SubscriptionInput = {
  email: string
  country: string
  topic: string
  frequency: 'immediate' | 'daily'
  min_impact: 'medium' | 'high'
}

export type Subscription = SubscriptionInput & {
  id: string
  created_at: string
}

export type DecisionCardInput = {
  title: string
  verdict: 'research' | 'watch' | 'hold'
  rationale: string
  evidence_ids: string[]
  owner: string
  review_date: string
}

export type DecisionCard = DecisionCardInput & {
  id: string
  created_at: string
}

export type DecisionReviewQueue = {
  overdue: DecisionCard[]
  due_today: DecisionCard[]
  upcoming: DecisionCard[]
}

export type DecisionReviewTrigger = {
  news: NewsItem
  evidence_ids: string[]
  cards: DecisionCard[]
}

export type DecisionReadinessCheck = {
  key: 'evidence' | 'source_freshness' | 'audit_trace'
  label: string
  status: 'pass' | 'caution' | 'missing'
  detail: string
  score: number
  max_score: number
}

export type DecisionReadiness = {
  score: number
  status: 'ready' | 'caution' | 'not_ready'
  next_action: string
  checks: DecisionReadinessCheck[]
}

export type DecisionReviewInput = {
  outcome: 'maintain' | 'adjust' | 'retire'
  note: string
}

export type DecisionReview = DecisionReviewInput & {
  id: string
  decision_card_id: string
  created_at: string
}

export type DemoSeedResult = {
  card: DecisionCard
  created: boolean
}

export type ResearchRuntime = {
  id: string
  mode: 'ollama' | 'fallback'
  model: string | null
  latency_ms: number
  evidence_ids: string[]
  created_at: string
}

export type ResearchRun = ResearchRuntime & {
  question: string
  score: number
  recommendation: string
  answer: string | null
}

export type ResearchObservability = {
  sample_size: number
  p50_latency_ms: number | null
  p95_latency_ms: number | null
  fallback_rate: number | null
  evidence_coverage: number | null
  last_run_at: string | null
}

export type StreamEvent =
  | { type: 'status'; payload: { label: string } }
  | { type: 'token'; payload: { text: string } }
  | { type: 'citations'; payload: { items: Evidence[] } }
  | { type: 'done'; payload: { score: number; recommendation: string; runtime: ResearchRuntime } }

export type MarketPackStatus = 'draft' | 'published' | 'archived'

export type MarketPackComponentInput = {
  key: string
  label: string
  base_score: number
  weight: number
}

export type MarketPackSummary = {
  id: string
  version: number
  status: MarketPackStatus
  name: string
  country: string
  sector: string
  change_note: string
  created_at: string
  published_at: string | null
}

export type MarketPackDetail = MarketPackSummary & {
  components: MarketPackComponentInput[]
}

export type MarketPackDraftInput = {
  name: string
  country: string
  sector: string
  change_note: string
  components: MarketPackComponentInput[]
}

export type MarketPackExport = {
  format_version: 1
  exported_at: string
  source: MarketPackSummary
  template: MarketPackDraftInput
}

export type MarketPackImportInput = {
  pack_id: string
  template: MarketPackDraftInput
}

export type MarketPackPreview = ScenarioResult & {
  pack_id: string
  version: number
  status: MarketPackStatus
  mode: 'sandbox'
}

export type CountryProfile = {
  id: 'de' | 'es' | 'fr' | 'ae' | 'sa'
  name: string
  display_name: string
  market_label: string
  market_pack_id: string
  latitude: number
  longitude: number
  timezone: string
  news_query: string
}

export type CountryWorkspace = {
  profile: CountryProfile
  market_pack: MarketPackDetail
  overview: MarketOverview
  sources: PublicDataSource[]
  news: NewsItem[]
}

export type CountryRefreshResult = {
  profile_id: string
  data: DataRefreshResult
  news: NewsRefreshResult
}

export type ResearchReport = {
  id: string
  profile_id: string
  market_pack_id: string
  market_pack_version: number
  score: number
  recommendation: string
  markdown: string
  created_at: string
  available_formats: Array<'docx' | 'pdf'>
}

export type ReportEmailResult = {
  mode: 'preview' | 'sent' | 'failed'
  subject: string
  message: string
  attachments: string[]
}

export type FactorStatus = 'observed' | 'derived' | 'assumption' | 'insufficient'

export type FactorItem = {
  key: string
  label: string
  score: number
  base_score: number
  contribution: number
  status: FactorStatus
  coverage_ratio: number
  missing_ratio: number
  freshness_label: string
  source_ids: string[]
  evidence_ids: string[]
  explanation: string
}

export type FactorSnapshot = {
  id: string
  profile_id: CountryProfile['id']
  market_pack_id: string
  market_pack_version: number
  captured_at: string
  items: FactorItem[]
}

export type ImpactMatrix = {
  profile_id: CountryProfile['id']
  captured_at: string
  items: FactorItem[]
}

export type EvidenceItem = {
  id: string
  profile_id: CountryProfile['id']
  title: string
  source: string
  url: string | null
  summary: string
  excerpt: string
  published_at: string | null
  language: string
  category: string
  event_type: string
  impact_direction: 'positive' | 'negative' | 'mixed' | 'unknown'
  impact_factors: string[]
  confidence: number
  extraction_mode: 'rules' | 'ollama' | 'manual'
  acknowledged: boolean
  created_at: string
}

export type ProjectStage = 'screening' | 'due_diligence' | 'review' | 'admitted' | 'on_hold' | 'rejected'
export type TaskPriority = 'blocker' | 'high' | 'normal'
export type TaskStatus = 'open' | 'in_progress' | 'done' | 'not_applicable'

export type ProjectCreateInput = {
  name: string
  profile_id: CountryProfile['id']
  owner: string
  capacity_mw?: number | null
  target_cod?: string | null
}

export type ProjectOpportunity = ProjectCreateInput & {
  id: string
  stage: ProjectStage
  decision_note: string | null
  created_at: string
  updated_at: string
}

export type ProjectUpdateInput = {
  stage?: ProjectStage
  owner?: string
  decision_note?: string
}

export type DueDiligenceTask = {
  id: string
  project_id: string
  profile_id: CountryProfile['id']
  factor_key: string
  title: string
  priority: TaskPriority
  status: TaskStatus
  owner: string
  due_date: string
  evidence_ids: string[]
  assessment_id: string | null
  completion_note: string | null
  created_at: string
  updated_at: string
}

export type AdmissionAssessment = {
  id: string
  project_id: string
  profile_id: CountryProfile['id']
  factor_snapshot_id: string
  verdict: 'ready_for_review' | 'needs_due_diligence' | 'not_ready'
  risk_level: 'low' | 'medium' | 'high'
  blockers: string[]
  task_ids: string[]
  summary: string
  created_at: string
}
