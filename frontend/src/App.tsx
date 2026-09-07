import { FormEvent, useEffect, useMemo, useState } from 'react'
import { api, streamResearch } from './lib/api'
import type { AdmissionAssessment, CountryProfile, DecisionCard, DecisionReadiness, DecisionReview, DecisionReviewQueue, DecisionReviewTrigger, DueDiligenceTask, Evidence, EvidenceItem, FactorSnapshot, ImpactMatrix, MarketOverview, MarketPackComponentInput, MarketPackDetail, MarketPackDraftInput, MarketPackPreview, MarketPackSummary, NewsItem, NewsPollingStatus, ProjectOpportunity, ProjectStage, PublicDataSource, ReportEmailResult, ResearchObservability, ResearchReport, ResearchRun, ScenarioInput, ScenarioResult, SensitivityResult, SimulationResult, StreamEvent, TaskStatus } from './types'

const defaultScenario: ScenarioInput = {
  subsidy_change: 0,
  demand_change: 0,
  grid_risk_change: 0,
  weather_change: 0,
}

const scrollSectionIds = ['overview', 'projects', 'market-packs', 'research', 'signals', 'sources'] as const
type ScrollSectionId = typeof scrollSectionIds[number]

const emptyMarketPackDraft: MarketPackDraftInput = {
  name: 'Germany Photovoltaic Entry Research',
  country: 'Germany',
  sector: 'Photovoltaic',
  change_note: 'Create a reviewed configuration change before publishing.',
  components: [],
}

const formatDelta = (delta: number) => `${delta > 0 ? '+' : ''}${delta.toFixed(1)}`
const shortDate = (value: string) => new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(new Date(value))
const newsTimestamp = (value: string) => {
  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}
const orderNewsForReview = (items: NewsItem[]) => [...items].sort((left, right) => (
  Number(left.acknowledged) - Number(right.acknowledged)
  || newsTimestamp(right.published_at) - newsTimestamp(left.published_at)
))
const dateTimeLabel = (value: string | null) => value
  ? new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
  : '尚未刷新'
const runtimeLabel = (run: ResearchRun) => run.mode === 'ollama' ? `Ollama · ${run.model ?? '本地模型'}` : '受控规则降级'
const rateLabel = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(0)}%`
const readinessLabel = (status: DecisionReadiness['status']) => ({ ready: '可以人工决策', caution: '需要补充复核', not_ready: '尚未就绪' })[status]
const newsPollingLabel = (status: NewsPollingStatus | null) => {
  if (!status) return '读取轮询配置…'
  if (!status.enabled) return '后台刷新已关闭'
  return status.interval_seconds % 60 === 0
    ? `后台 ${status.interval_seconds / 60} 分钟刷新`
    : `后台 ${status.interval_seconds} 秒刷新`
}

function TrendChart({ overview }: { overview: MarketOverview }) {
  const points = overview.metrics
  const width = 600
  const height = 190
  const values = points.map((point) => point.opportunity)
  const min = Math.min(...values) - 2
  const max = Math.max(...values) + 2
  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width
      const y = height - ((point.opportunity - min) / (max - min)) * height
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <div className="chart-wrap" aria-label="市场机会评分趋势图">
      <div className="chart-meta"><span>机会评分 · 10 个月趋势</span><strong>{points.at(-1)?.opportunity.toFixed(1)}</strong></div>
      <svg viewBox={`0 0 ${width} ${height + 28}`} className="trend-chart" role="img">
        {[0.25, 0.5, 0.75].map((line) => <line key={line} x1="0" x2={width} y1={height * line} y2={height * line} className="grid-line" />)}
        <path d={path} className="trend-line" />
        {points.map((point, index) => {
          const x = (index / (points.length - 1)) * width
          const y = height - ((point.opportunity - min) / (max - min)) * height
          return <circle key={point.month} cx={x} cy={y} r="4" className="trend-dot"><title>{`${point.month}: ${point.opportunity}`}</title></circle>
        })}
      </svg>
      <div className="chart-axis"><span>{points[0]?.month}</span><span>{points.at(-1)?.month}</span></div>
    </div>
  )
}

function ScoreRing({ score }: { score: number }) {
  return (
    <div className="score-ring" style={{ '--score': `${score * 3.6}deg` } as React.CSSProperties}>
      <div><strong>{score.toFixed(1)}</strong><span>/ 100</span></div>
    </div>
  )
}

function App() {
  const [countries, setCountries] = useState<CountryProfile[]>([])
  const [selectedCountryId, setSelectedCountryId] = useState<CountryProfile['id']>('de')
  const [isLoadingCountry, setIsLoadingCountry] = useState(false)
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [reportMessage, setReportMessage] = useState('')
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const [reportEmailResult, setReportEmailResult] = useState<ReportEmailResult | null>(null)
  const [isSendingReport, setIsSendingReport] = useState(false)
  const [overview, setOverview] = useState<MarketOverview | null>(null)
  const [news, setNews] = useState<NewsItem[]>([])
  const [newsPollingStatus, setNewsPollingStatus] = useState<NewsPollingStatus | null>(null)
  const [sources, setSources] = useState<PublicDataSource[]>([])
  const [featureSnapshot, setFeatureSnapshot] = useState<FactorSnapshot | null>(null)
  const [impactMatrix, setImpactMatrix] = useState<ImpactMatrix | null>(null)
  const [evidenceTimeline, setEvidenceTimeline] = useState<EvidenceItem[]>([])
  const [evidenceFactorFilter, setEvidenceFactorFilter] = useState('all')
  const [evidenceStateFilter, setEvidenceStateFilter] = useState<'all' | 'confirmed' | 'pending'>('all')
  const [isRefreshingFeatures, setIsRefreshingFeatures] = useState(false)
  const [projects, setProjects] = useState<ProjectOpportunity[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [projectTasks, setProjectTasks] = useState<DueDiligenceTask[]>([])
  const [projectAssessment, setProjectAssessment] = useState<AdmissionAssessment | null>(null)
  const [projectName, setProjectName] = useState('')
  const [projectOwner, setProjectOwner] = useState('Development Desk')
  const [projectCapacity, setProjectCapacity] = useState('')
  const [projectTargetCod, setProjectTargetCod] = useState('')
  const [projectDecisionNote, setProjectDecisionNote] = useState('')
  const [projectMessage, setProjectMessage] = useState('')
  const [isCreatingProject, setIsCreatingProject] = useState(false)
  const [isAssessingProject, setIsAssessingProject] = useState(false)
  const [marketPacks, setMarketPacks] = useState<MarketPackSummary[]>([])
  const [marketPackDetail, setMarketPackDetail] = useState<MarketPackDetail | null>(null)
  const [marketPackDraft, setMarketPackDraft] = useState<MarketPackDraftInput>(emptyMarketPackDraft)
  const [marketPackMessage, setMarketPackMessage] = useState('')
  const [isSavingMarketPack, setIsSavingMarketPack] = useState(false)
  const [isPublishingMarketPack, setIsPublishingMarketPack] = useState(false)
  const [marketPackPreview, setMarketPackPreview] = useState<MarketPackPreview | null>(null)
  const [isPreviewingMarketPack, setIsPreviewingMarketPack] = useState(false)
  const [importPackId, setImportPackId] = useState('fr-pv')
  const [importTemplateText, setImportTemplateText] = useState('')
  const [isImportingMarketPack, setIsImportingMarketPack] = useState(false)
  const [decisionCards, setDecisionCards] = useState<DecisionCard[]>([])
  const [decisionReviewQueue, setDecisionReviewQueue] = useState<DecisionReviewQueue>({ overdue: [], due_today: [], upcoming: [] })
  const [decisionReviewTriggers, setDecisionReviewTriggers] = useState<DecisionReviewTrigger[]>([])
  const [decisionReadiness, setDecisionReadiness] = useState<DecisionReadiness | null>(null)
  const [decisionReviews, setDecisionReviews] = useState<Record<string, DecisionReview[]>>({})
  const [researchRuns, setResearchRuns] = useState<ResearchRun[]>([])
  const [researchObservability, setResearchObservability] = useState<ResearchObservability | null>(null)
  const [scenario, setScenario] = useState<ScenarioInput>(defaultScenario)
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null)
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null)
  const [sensitivityResult, setSensitivityResult] = useState<SensitivityResult | null>(null)
  const [question, setQuestion] = useState('德国光伏市场未来一年是否仍应优先进入？主要风险是什么？')
  const [researchText, setResearchText] = useState('')
  const [researchStatus, setResearchStatus] = useState('准备就绪')
  const [citations, setCitations] = useState<Evidence[]>([])
  const [isResearching, setIsResearching] = useState(false)
  const [email, setEmail] = useState('demo@example.com')
  const [emailMessage, setEmailMessage] = useState('')
  const [refreshMessage, setRefreshMessage] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSeedingDemo, setIsSeedingDemo] = useState(false)
  const [newsRefreshMessage, setNewsRefreshMessage] = useState('')
  const [isRefreshingNews, setIsRefreshingNews] = useState(false)
  const [subscriptionMessage, setSubscriptionMessage] = useState('')
  const [decisionVerdict, setDecisionVerdict] = useState<'research' | 'watch' | 'hold'>('watch')
  const [reviewDate, setReviewDate] = useState('2026-09-17')
  const [decisionMessage, setDecisionMessage] = useState('')
  const [reviewingCardId, setReviewingCardId] = useState<string | null>(null)
  const [reviewOutcome, setReviewOutcome] = useState<'maintain' | 'adjust' | 'retire'>('maintain')
  const [reviewNote, setReviewNote] = useState('')
  const [reviewMessage, setReviewMessage] = useState('')
  const [snapshotCardId, setSnapshotCardId] = useState<string | null>(null)
  const [evidenceSnapshots, setEvidenceSnapshots] = useState<Record<string, Evidence[]>>({})
  const [error, setError] = useState('')
  const [activeSection, setActiveSection] = useState<ScrollSectionId>('overview')

  const activeScore = scenarioResult?.score ?? overview?.score ?? 0
  const activeRecommendation = scenarioResult?.recommendation ?? overview?.recommendation ?? '加载中'
  const components = scenarioResult?.component_scores ?? overview?.components ?? []

  const scenarioChanged = useMemo(() => Object.values(scenario).some((value) => value !== 0), [scenario])
  const marketPackWeightTotal = useMemo(() => marketPackDraft.components.reduce((total, component) => total + Number(component.weight || 0), 0), [marketPackDraft.components])
  const canPublishSelectedMarketPack = marketPackDetail?.id === 'de-pv' && marketPackDetail.status === 'draft'
  const visibleEvidence = useMemo(() => evidenceTimeline.filter((item) => (
    (evidenceFactorFilter === 'all' || item.impact_factors.includes(evidenceFactorFilter))
    && (evidenceStateFilter === 'all' || (evidenceStateFilter === 'confirmed' ? item.acknowledged : !item.acknowledged))
  )), [evidenceFactorFilter, evidenceStateFilter, evidenceTimeline])
  const unconfirmedNewsCount = useMemo(() => news.filter((item) => !item.acknowledged).length, [news])
  const orderedNews = useMemo(() => orderNewsForReview(news), [news])
  const selectedProject = useMemo(() => projects.find((project) => project.id === selectedProjectId) ?? null, [projects, selectedProjectId])
  const openBlockers = useMemo(() => projectTasks.filter((task) => task.priority === 'blocker' && ['open', 'in_progress'].includes(task.status)), [projectTasks])

  async function loadCountryEvidence(profileId: CountryProfile['id']) {
    const [snapshot, matrix, timeline] = await Promise.all([
      api.countryFeatures(profileId),
      api.countryImpactMatrix(profileId),
      api.countryEvidenceTimeline(profileId),
    ])
    setFeatureSnapshot(snapshot)
    setImpactMatrix(matrix)
    setEvidenceTimeline(timeline)
  }

  async function loadProjectWorkbench(profileId: CountryProfile['id'], projectId = selectedProjectId) {
    const items = await api.projects(profileId)
    setProjects(items)
    const selected = projectId && items.some((item) => item.id === projectId) ? projectId : (items[0]?.id ?? null)
    setSelectedProjectId(selected)
    setProjectAssessment(null)
    setProjectDecisionNote(items.find((item) => item.id === selected)?.decision_note ?? '')
    setProjectTasks(selected ? await api.projectTasks(selected) : [])
  }

  async function loadDecisionReviews(cards: DecisionCard[]) {
    const entries = await Promise.all(cards.map(async (card) => [card.id, await api.decisionReviews(card.id)] as const))
    setDecisionReviews(Object.fromEntries(entries))
  }

  async function loadData() {
    try {
      const [market, items, pollingStatus, publicSources, packs, cards, reviewQueue, reviewTriggers, runs, observability, readiness] = await Promise.all([api.overview(), api.news(), api.newsPollingStatus(), api.sources(), api.marketPacks(), api.decisionCards(), api.decisionReviewQueue(), api.decisionReviewTriggers(), api.researchRuns(), api.researchObservability(), api.decisionReadiness()])
      setOverview(market)
      setNews(items)
      setNewsPollingStatus(pollingStatus)
      setSources(publicSources)
      setMarketPacks(packs)
      setDecisionCards(cards)
      setDecisionReviewQueue(reviewQueue)
      setDecisionReviewTriggers(reviewTriggers)
      await loadDecisionReviews(cards)
      setResearchRuns(runs)
      setResearchObservability(observability)
      setDecisionReadiness(readiness)
      const activePack = packs.find((pack) => pack.status === 'published') ?? packs[0]
      if (activePack) {
        const detail = await api.marketPackVersion(activePack.id, activePack.version)
        setMarketPackDetail(detail)
        setMarketPackDraft({ name: detail.name, country: detail.country, sector: detail.sector, change_note: detail.change_note, components: detail.components })
      }
      setError('')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '无法连接 AtlasIQ API')
    }
  }

  useEffect(() => {
    void loadData()
    void Promise.all([api.countries(), api.countryWorkspace('de'), loadCountryEvidence('de')]).then(([profiles, workspace]) => {
      setCountries(profiles)
      setOverview(workspace.overview)
      setNews(workspace.news)
      setSources(workspace.sources)
      setMarketPackDetail(workspace.market_pack)
      setMarketPackDraft({ name: workspace.market_pack.name, country: workspace.market_pack.country, sector: workspace.market_pack.sector, change_note: workspace.market_pack.change_note, components: workspace.market_pack.components })
    }).catch(() => undefined)
    void loadProjectWorkbench('de').catch(() => undefined)
    const timer = window.setInterval(() => void Promise.all([api.news(), api.decisionReviewTriggers()]).then(([items, triggers]) => { setNews(items); setDecisionReviewTriggers(triggers) }).catch(() => undefined), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const sections = scrollSectionIds
      .map((sectionId) => document.getElementById(sectionId))
      .filter((section): section is HTMLElement => section !== null)
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>('.sidebar nav a[href^="#"]'))

    const handleLinkClick = (event: MouseEvent) => {
      const sectionId = (event.currentTarget as HTMLAnchorElement).getAttribute('href')?.slice(1)
      if (sectionId && scrollSectionIds.includes(sectionId as ScrollSectionId)) {
        setActiveSection(sectionId as ScrollSectionId)
      }
    }

    const observer = new IntersectionObserver((entries) => {
      const activeEntry = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => Math.abs(left.boundingClientRect.top - window.innerHeight * 0.28) - Math.abs(right.boundingClientRect.top - window.innerHeight * 0.28))[0]
      if (activeEntry && scrollSectionIds.includes(activeEntry.target.id as ScrollSectionId)) {
        setActiveSection(activeEntry.target.id as ScrollSectionId)
      }
    }, { rootMargin: '-18% 0px -55% 0px', threshold: [0, 0.1, 0.35] })

    sections.forEach((section) => observer.observe(section))
    links.forEach((link) => link.addEventListener('click', handleLinkClick))
    return () => {
      observer.disconnect()
      links.forEach((link) => link.removeEventListener('click', handleLinkClick))
    }
  }, [])

  useEffect(() => {
    document.querySelectorAll<HTMLAnchorElement>('.sidebar nav a[href^="#"]').forEach((link) => {
      const isActive = link.getAttribute('href') === `#${activeSection}`
      link.classList.toggle('active', isActive)
      if (isActive) link.setAttribute('aria-current', 'location')
      else link.removeAttribute('aria-current')
    })
  }, [activeSection])

  async function runScenario() {
    try {
      const [result, simulation, sensitivity] = await Promise.all([api.countryScenario(selectedCountryId, scenario), api.countrySimulation(selectedCountryId, scenario), api.countrySensitivity(selectedCountryId, scenario)])
      setScenarioResult(result)
      setSimulationResult(simulation)
      setSensitivityResult(sensitivity)
    } catch (scenarioError) {
      setError(scenarioError instanceof Error ? scenarioError.message : '情景计算失败')
    }
  }

  async function selectMarketPackVersion(pack: MarketPackSummary) {
    try {
      const detail = await api.marketPackVersion(pack.id, pack.version)
      setMarketPackDetail(detail)
      setMarketPackDraft({ name: detail.name, country: detail.country, sector: detail.sector, change_note: detail.change_note, components: detail.components })
      setMarketPackPreview(null)
      setMarketPackMessage(`已加载 v${detail.version}；编辑后会创建新草稿，不会改写该版本。`)
    } catch (marketPackError) {
      setMarketPackMessage(marketPackError instanceof Error ? marketPackError.message : '读取配置版本失败')
    }
  }

  function updateMarketPackComponent(index: number, field: keyof MarketPackComponentInput, value: string) {
    setMarketPackDraft((current) => ({
      ...current,
      components: current.components.map((component, componentIndex) => componentIndex === index
        ? { ...component, [field]: field === 'base_score' || field === 'weight' ? Number(value) : value }
        : component),
    }))
  }

  function addMarketPackComponent() {
    setMarketPackDraft((current) => ({ ...current, components: [...current.components, { key: `factor_${current.components.length + 1}`, label: 'New factor', base_score: 60, weight: 0.05 }] }))
  }

  async function saveMarketPackDraft() {
    if (Math.abs(marketPackWeightTotal - 1) > 0.0001) {
      setMarketPackMessage(`当前权重为 ${(marketPackWeightTotal * 100).toFixed(1)}%，请调整为 100% 后再保存。`)
      return
    }
    setIsSavingMarketPack(true)
    try {
      const packId = marketPackDetail?.id ?? 'de-pv'
      const saved = await api.createMarketPackDraft(packId, marketPackDraft)
      const [packs, detail] = await Promise.all([api.marketPacks(), api.marketPackVersion(saved.id, saved.version)])
      setMarketPacks(packs)
      setMarketPackDetail(detail)
      setMarketPackMessage(`草稿 v${saved.version} 已保存。它不会影响当前评分，待你显式发布。`)
      setMarketPackPreview(null)
    } catch (marketPackError) {
      setMarketPackMessage(marketPackError instanceof Error ? marketPackError.message : '保存配置草稿失败')
    } finally {
      setIsSavingMarketPack(false)
    }
  }

  async function publishSelectedMarketPack() {
    if (!marketPackDetail || marketPackDetail.status !== 'draft') return
    setIsPublishingMarketPack(true)
    try {
      const published = await api.publishMarketPack(marketPackDetail.id, marketPackDetail.version)
      const [packs, detail, market] = await Promise.all([api.marketPacks(), api.marketPackVersion(published.id, published.version), api.overview()])
      setMarketPacks(packs)
      setMarketPackDetail(detail)
      setOverview(market)
      setScenarioResult(null)
      setSimulationResult(null)
      setSensitivityResult(null)
      setMarketPackMessage(`已发布 v${published.version}。总览评分已切换到新的已发布配置。`)
      setMarketPackPreview(null)
    } catch (marketPackError) {
      setMarketPackMessage(marketPackError instanceof Error ? marketPackError.message : '发布配置版本失败')
    } finally {
      setIsPublishingMarketPack(false)
    }
  }

  async function previewSelectedMarketPack() {
    if (!marketPackDetail) return
    setIsPreviewingMarketPack(true)
    try {
      const preview = await api.previewMarketPack(marketPackDetail.id, marketPackDetail.version, scenario)
      setMarketPackPreview(preview)
      setMarketPackMessage(`已在沙盒运行 ${preview.pack_id} v${preview.version}；没有写入或发布任何配置。`)
    } catch (marketPackError) {
      setMarketPackMessage(marketPackError instanceof Error ? marketPackError.message : '沙盒预览失败')
    } finally {
      setIsPreviewingMarketPack(false)
    }
  }

  async function exportSelectedMarketPack() {
    if (!marketPackDetail) return
    try {
      const exported = await api.exportMarketPack(marketPackDetail.id, marketPackDetail.version)
      const downloadUrl = URL.createObjectURL(new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json;charset=utf-8' }))
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `atlasiq-${marketPackDetail.id}-v${marketPackDetail.version}-template.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(downloadUrl)
      setMarketPackMessage(`v${marketPackDetail.version} 模板已导出，可在其他市场包中导入为草稿。`)
    } catch (marketPackError) {
      setMarketPackMessage(marketPackError instanceof Error ? marketPackError.message : '导出配置模板失败')
    }
  }

  async function importMarketPackTemplate() {
    if (!/^[a-z][a-z0-9-]*$/.test(importPackId)) {
      setMarketPackMessage('目标市场包 ID 需以小写字母开头，只能包含小写字母、数字和短横线。')
      return
    }
    try {
      const parsed: unknown = JSON.parse(importTemplateText)
      const candidate = typeof parsed === 'object' && parsed !== null && 'template' in parsed
        ? (parsed as { template?: unknown }).template
        : parsed
      const isCompleteTemplate = typeof candidate === 'object'
        && candidate !== null
        && typeof (candidate as Record<string, unknown>).name === 'string'
        && typeof (candidate as Record<string, unknown>).country === 'string'
        && typeof (candidate as Record<string, unknown>).sector === 'string'
        && typeof (candidate as Record<string, unknown>).change_note === 'string'
        && Array.isArray((candidate as Record<string, unknown>).components)
      if (!isCompleteTemplate) throw new Error('模板缺少名称、国家、赛道、变更说明或评分组件。')
      const template = candidate as MarketPackDraftInput
      setIsImportingMarketPack(true)
      const saved = await api.importMarketPack({ pack_id: importPackId, template })
      const [packs, detail] = await Promise.all([api.marketPacks(), api.marketPackVersion(saved.id, saved.version)])
      setMarketPacks(packs)
      setMarketPackDetail(detail)
      setMarketPackDraft({ name: detail.name, country: detail.country, sector: detail.sector, change_note: detail.change_note, components: detail.components })
      setMarketPackPreview(null)
      setMarketPackMessage(`模板已导入为 ${saved.id} v${saved.version} 草稿；请完成本地审阅后再发布。`)
    } catch (marketPackError) {
      setMarketPackMessage(marketPackError instanceof Error ? marketPackError.message : '模板格式不正确，未创建草稿。')
    } finally {
      setIsImportingMarketPack(false)
    }
  }

  async function refreshPublicData() {
    setIsRefreshing(true)
    setRefreshMessage('正在读取该国家的公开能源、天气与新闻信号…')
    try {
      const result = await api.refreshCountry(selectedCountryId)
      const workspace = await api.countryWorkspace(selectedCountryId)
      setRefreshMessage(result.data.status === 'live' ? `${result.data.message} ${result.news.message}` : `降级模式：${result.data.message}`)
      setOverview(workspace.overview)
      setSources(workspace.sources)
      setNews(workspace.news)
      const snapshot = await api.refreshCountryFeatures(selectedCountryId)
      setFeatureSnapshot(snapshot)
      setImpactMatrix(await api.countryImpactMatrix(selectedCountryId))
      setEvidenceTimeline(await api.countryEvidenceTimeline(selectedCountryId))
      const readiness = await api.decisionReadiness()
      setDecisionReadiness(readiness)
    } catch (refreshError) {
      setRefreshMessage(refreshError instanceof Error ? refreshError.message : '公开数据刷新失败')
    } finally {
      setIsRefreshing(false)
    }
  }

  async function selectCountry(profileId: CountryProfile['id']) {
    setIsLoadingCountry(true)
    try {
      const workspace = await api.countryWorkspace(profileId)
      setSelectedCountryId(profileId)
      setOverview(workspace.overview)
      setSources(workspace.sources)
      setNews(workspace.news)
      await loadCountryEvidence(profileId)
      await loadProjectWorkbench(profileId, null)
      setMarketPackDetail(workspace.market_pack)
      setMarketPackDraft({ name: workspace.market_pack.name, country: workspace.market_pack.country, sector: workspace.market_pack.sector, change_note: workspace.market_pack.change_note, components: workspace.market_pack.components })
      setScenarioResult(null)
      setSimulationResult(null)
      setSensitivityResult(null)
      setReport(null)
      setReportEmailResult(null)
      setReportMessage(`已切换至 ${workspace.profile.name}。评分、数据状态和新闻信号均按国家隔离。`)
    } catch (countryError) {
      setError(countryError instanceof Error ? countryError.message : '切换国家工作台失败')
    } finally {
      setIsLoadingCountry(false)
    }
  }

  async function generateReport() {
    setIsGeneratingReport(true)
    try {
      const created = await api.createResearchReport(selectedCountryId, scenario)
      setReport(created)
      setReportEmailResult(null)
      setReportMessage(`报告 ${created.id} 已在本地生成，可下载 Word 或 PDF。`)
    } catch (reportError) {
      setReportMessage(reportError instanceof Error ? reportError.message : '报告生成失败')
    } finally {
      setIsGeneratingReport(false)
    }
  }

  async function deliverReport(send: boolean) {
    if (!report) return
    setIsSendingReport(true)
    try {
      const result = send
        ? await api.sendReportEmail(report.id, email, ['docx', 'pdf'])
        : await api.previewReportEmail(report.id, email, ['docx', 'pdf'])
      setReportEmailResult(result)
    } catch (reportEmailError) {
      setReportMessage(reportEmailError instanceof Error ? reportEmailError.message : '报告邮件操作失败')
    } finally {
      setIsSendingReport(false)
    }
  }

  async function seedDemoWorkspace() {
    setIsSeedingDemo(true)
    try {
      const result = await api.seedDemo()
      await loadData()
      setRefreshMessage(result.created ? '已加载本地演示样本：决策卡、复盘记录与并网信号均已就绪。' : '演示样本已存在，已刷新到最新本地状态。')
    } catch (seedError) {
      setError(seedError instanceof Error ? seedError.message : '加载演示样本失败')
    } finally {
      setIsSeedingDemo(false)
    }
  }

  async function askResearch(event: FormEvent) {
    event.preventDefault()
    if (question.trim().length < 8 || isResearching) return
    setResearchText('')
    setCitations([])
    setResearchStatus('已提交研究任务')
    setIsResearching(true)
    try {
      await streamResearch(question, scenario, selectedCountryId, (event: StreamEvent) => {
        if (event.type === 'status') setResearchStatus(event.payload.label)
        if (event.type === 'token') setResearchText((current) => current + event.payload.text)
        if (event.type === 'citations') setCitations(event.payload.items)
        if (event.type === 'done') {
          setResearchStatus(`完成 · ${event.payload.recommendation} ${event.payload.score.toFixed(1)} 分`)
          setDecisionVerdict(event.payload.recommendation === '积极研究' ? 'research' : event.payload.recommendation === '暂缓进入' ? 'hold' : 'watch')
          setDecisionMessage(`已按透明评分结果预填“${event.payload.recommendation}”；保存前仍可由你修改。`)
        }
      })
      void Promise.all([api.researchRuns(), api.researchObservability(), api.decisionReadiness()])
        .then(([runs, observability, readiness]) => {
          setResearchRuns(runs)
          setResearchObservability(observability)
          setDecisionReadiness(readiness)
        })
        .catch(() => undefined)
    } catch (researchError) {
      setResearchStatus('生成失败')
      setError(researchError instanceof Error ? researchError.message : '研究服务暂时不可用')
    } finally {
      setIsResearching(false)
    }
  }

  async function acknowledge(id: string) {
    try {
      await api.acknowledge(id)
      setNews((items) => items.map((item) => item.id === id ? { ...item, acknowledged: true } : item))
      setDecisionReviewTriggers(await api.decisionReviewTriggers())
    } catch (ackError) {
      setError(ackError instanceof Error ? ackError.message : '确认动态失败')
    }
  }

  async function refreshFeatureEvidence() {
    setIsRefreshingFeatures(true)
    try {
      const snapshot = await api.refreshCountryFeatures(selectedCountryId)
      setFeatureSnapshot(snapshot)
      setImpactMatrix(await api.countryImpactMatrix(selectedCountryId))
      setSources(await api.sources(selectedCountryId))
    } catch (featureError) {
      setError(featureError instanceof Error ? featureError.message : '特征数据刷新失败')
    } finally {
      setIsRefreshingFeatures(false)
    }
  }

  async function confirmEvidence(evidenceId: string) {
    try {
      await api.acknowledgeCountryEvidence(selectedCountryId, evidenceId)
      await loadCountryEvidence(selectedCountryId)
      await loadProjectWorkbench(selectedCountryId)
    } catch (evidenceError) {
      setError(evidenceError instanceof Error ? evidenceError.message : '证据确认失败')
    }
  }

  async function createProject() {
    if (projectName.trim().length < 3) {
      setProjectMessage('请填写至少 3 个字符的项目名称。')
      return
    }
    setIsCreatingProject(true)
    try {
      const created = await api.createProject({
        name: projectName.trim(),
        profile_id: selectedCountryId,
        owner: projectOwner.trim() || 'Development Desk',
        capacity_mw: projectCapacity ? Number(projectCapacity) : null,
        target_cod: projectTargetCod || null,
      })
      setProjectName('')
      setProjectCapacity('')
      setProjectTargetCod('')
      setProjectMessage(`已创建 ${created.name}。下一步运行准入评估，生成尽调任务。`)
      await loadProjectWorkbench(selectedCountryId, created.id)
    } catch (projectError) {
      setProjectMessage(projectError instanceof Error ? projectError.message : '创建项目失败')
    } finally {
      setIsCreatingProject(false)
    }
  }

  async function selectProject(projectId: string) {
    const project = projects.find((item) => item.id === projectId)
    setSelectedProjectId(projectId)
    setProjectAssessment(null)
    setProjectDecisionNote(project?.decision_note ?? '')
    try {
      setProjectTasks(await api.projectTasks(projectId))
    } catch (projectError) {
      setError(projectError instanceof Error ? projectError.message : '读取项目尽调任务失败')
    }
  }

  async function assessSelectedProject() {
    if (!selectedProject) return
    setIsAssessingProject(true)
    try {
      const assessment = await api.assessProject(selectedProject.id)
      setProjectAssessment(assessment)
      setProjectTasks(await api.projectTasks(selectedProject.id))
      setProjectMessage(assessment.verdict === 'ready_for_review' ? '准入门槛已满足，可进入人工评审。' : `已生成评估：${assessment.blockers.length} 个 blocker 需要处理。`)
    } catch (projectError) {
      setProjectMessage(projectError instanceof Error ? projectError.message : '运行准入评估失败')
    } finally {
      setIsAssessingProject(false)
    }
  }

  async function updateTaskStatus(task: DueDiligenceTask, status: TaskStatus) {
    if (!selectedProject) return
    try {
      const updated = await api.updateProjectTask(selectedProject.id, task.id, status, status === 'done' ? 'Marked complete by project owner.' : undefined)
      setProjectTasks((items) => items.map((item) => item.id === updated.id ? updated : item))
    } catch (projectError) {
      setProjectMessage(projectError instanceof Error ? projectError.message : '更新尽调任务失败')
    }
  }

  async function transitionProject(stage: ProjectStage) {
    if (!selectedProject) return
    try {
      const updated = await api.updateProject(selectedProject.id, { stage, decision_note: projectDecisionNote || undefined })
      setProjects((items) => items.map((item) => item.id === updated.id ? updated : item))
      setProjectDecisionNote(updated.decision_note ?? '')
      setProjectMessage(`项目阶段已更新为 ${updated.stage}。`)
    } catch (projectError) {
      setProjectMessage(projectError instanceof Error ? projectError.message : '项目阶段更新失败')
    }
  }

  async function downloadProjectBriefing() {
    if (!selectedProject) return
    try {
      const briefing = await api.projectBriefing(selectedProject.id)
      const url = URL.createObjectURL(new Blob([briefing], { type: 'text/markdown;charset=utf-8' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `atlasiq-${selectedProject.id}-admission-briefing.md`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (projectError) {
      setProjectMessage(projectError instanceof Error ? projectError.message : '导出项目简报失败')
    }
  }

  async function refreshNews() {
    setIsRefreshingNews(true)
    setNewsRefreshMessage('正在读取配置化公开 RSS…')
    try {
      const result = await api.refreshNews()
      const deliveryNote = result.notifications_sent > 0
        ? ` 已发送 ${result.notifications_sent} 封邮件。`
        : result.notifications_previewed > 0
          ? ` 已生成 ${result.notifications_previewed} 条安全预览。`
          : ''
      setNewsRefreshMessage(result.message + deliveryNote)
      setNews(await api.news())
    } catch (newsError) {
      setNewsRefreshMessage(newsError instanceof Error ? newsError.message : '新闻刷新失败')
    } finally {
      setIsRefreshingNews(false)
    }
  }

  async function previewEmail() {
    try {
      const result = await api.previewEmail(email)
      setEmailMessage(`${result.mode === 'sent' ? '已发送' : '安全预览'}：${result.message}`)
    } catch (emailError) {
      setEmailMessage(emailError instanceof Error ? emailError.message : '邮件预览失败')
    }
  }

  async function subscribeToSignals() {
    try {
      const subscription = await api.subscribe({
        email,
        country: 'Germany',
        topic: 'photovoltaic',
        frequency: 'immediate',
        min_impact: 'medium',
      })
      setSubscriptionMessage(`已保存订阅 ${subscription.id}：中高优先级动态将进入邮件投递流程。`)
    } catch (subscriptionError) {
      setSubscriptionMessage(subscriptionError instanceof Error ? subscriptionError.message : '订阅保存失败')
    }
  }

  async function saveDecisionCard() {
    if (researchText.trim().length < 8) {
      setDecisionMessage('请先完成一次研究问答，再保存决策卡。')
      return
    }
    try {
      const card = await api.saveDecisionCard({
        title: question.slice(0, 120),
        verdict: decisionVerdict,
        rationale: researchText,
        evidence_ids: citations.map((item) => item.id),
        owner: 'Strategy Desk',
        review_date: reviewDate,
      })
      const reviewQueue = await api.decisionReviewQueue()
      setDecisionCards((items) => [card, ...items])
      setDecisionReviewQueue(reviewQueue)
      setDecisionReviews((items) => ({ ...items, [card.id]: [] }))
      setDecisionMessage('决策卡已保存，可在复盘时查看原始判断与证据。')
    } catch (decisionError) {
      setDecisionMessage(decisionError instanceof Error ? decisionError.message : '保存决策卡失败')
    }
  }

  async function saveDecisionReview(cardId: string) {
    if (reviewNote.trim().length < 8) {
      setReviewMessage('请填写至少 8 个字符的复盘说明。')
      return
    }
    try {
      const created = await api.createDecisionReview(cardId, { outcome: reviewOutcome, note: reviewNote.trim() })
      setDecisionReviews((items) => ({ ...items, [cardId]: [created, ...(items[cardId] ?? [])] }))
      setReviewingCardId(null)
      setReviewNote('')
      setReviewOutcome('maintain')
      setReviewMessage('复盘记录已保存；原始判断与市场评分未被自动改写。')
    } catch (reviewError) {
      setReviewMessage(reviewError instanceof Error ? reviewError.message : '保存复盘记录失败')
    }
  }

  async function exportDecisionBriefing(card: DecisionCard) {
    try {
      const markdown = await api.decisionBriefing(card.id)
      const downloadUrl = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }))
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `atlasiq-${card.id}.md`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(downloadUrl)
      setReviewMessage('决策简报已下载为 Markdown，可直接用于团队同步或面试演示。')
    } catch (exportError) {
      setReviewMessage(exportError instanceof Error ? exportError.message : '导出决策简报失败')
    }
  }

  async function toggleEvidenceSnapshot(card: DecisionCard) {
    if (snapshotCardId === card.id) { setSnapshotCardId(null); return }
    try {
      const snapshots = evidenceSnapshots[card.id] ?? await api.decisionEvidenceSnapshot(card.id)
      setEvidenceSnapshots((items) => ({ ...items, [card.id]: snapshots }))
      setSnapshotCardId(card.id)
    } catch (snapshotError) {
      setReviewMessage(snapshotError instanceof Error ? snapshotError.message : '读取证据快照失败')
    }
  }

  if (!overview) {
    return <main className="loading-shell"><div className="pulse-logo">A</div><p>{error || '正在打开 AtlasIQ…'}</p></main>
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">A</div><span>Atlas<span>IQ</span></span></div>
        <nav>
          <a className="active" href="#overview"><span>◉</span> 当前市场判断</a>
          <a href="#projects"><span>↗</span> 项目推进与待办</a>
          <a href="#market-packs"><span>≡</span> 评分规则与版本</a>
          <a href="#research"><span>✦</span> 带证据的研究结论</a>
          <a href="#signals"><span>◌</span> 需要确认的市场变化 {unconfirmedNewsCount > 0 && <b>{unconfirmedNewsCount}</b>}</a>
          <a href="#sources"><span>▤</span> 数据与来源</a>
        </nav>
        <div className="sidebar-note"><span className="dot" /> 本地优先模式<br /><small>不使用付费 AI API</small></div>
        <div className="analyst"><div className="avatar">S</div><div><strong>Strategy Desk</strong><small>Germany watchlist</small></div></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p className="eyebrow">MARKET ENTRY WORKSPACE / MULTI-COUNTRY</p><h1>{overview.market} <span className="live-pill"><i /> 持续监测</span></h1></div>
          <div className="top-actions"><button className="quiet-btn" onClick={() => void seedDemoWorkspace()} disabled={isSeedingDemo}>{isSeedingDemo ? '加载示例…' : '加载面试示例'}</button><button className="quiet-btn" onClick={() => void refreshPublicData()} disabled={isRefreshing}>{isRefreshing ? '读取公开数据…' : '刷新数据'}</button><button className="primary-btn" onClick={() => document.getElementById('research')?.scrollIntoView({ behavior: 'smooth' })}>生成研究结论 <span>→</span></button></div>
        </header>

        {error && <div className="error-banner">{error}<button onClick={() => setError('')}>×</button></div>}
        {refreshMessage && <div className="refresh-banner"><span>数据刷新</span>{refreshMessage}<button onClick={() => setRefreshMessage('')}>×</button></div>}

        <section className="country-report-panel panel">
          <div className="country-report-heading"><div><span>从市场判断到项目动作</span><h2>选择市场，查看判断并生成汇报材料</h2><p>切换市场后，数据、动态、判断依据、评分规则和项目机会会同步切换；需要沟通时再按需生成报告。</p></div><label>选择市场<select value={selectedCountryId} onChange={(event) => void selectCountry(event.target.value as CountryProfile['id'])} disabled={isLoadingCountry}>{countries.map((country) => <option key={country.id} value={country.id}>{country.display_name}</option>)}</select></label></div>
          <div className="country-report-meta"><span>Market Pack · {marketPackDetail?.id} v{marketPackDetail?.version}</span><span>数据源 · OWID / Open-Meteo / RSS-GDELT</span><span>实时状态 · {sources.some((source) => source.status === 'degraded') ? '部分降级' : '可按需刷新'}</span></div>
          <div className="country-report-actions"><button className="secondary-btn" onClick={() => void refreshPublicData()} disabled={isRefreshing || isLoadingCountry}>{isRefreshing ? '刷新中…' : '更新该市场信息'}</button><button className="primary-btn" onClick={() => void generateReport()} disabled={isGeneratingReport}>{isGeneratingReport ? '生成中…' : '生成汇报摘要'}</button></div>
          {reportMessage && <p className="country-report-message">{reportMessage}</p>}
          {report && <div className="report-delivery"><div><strong>{report.id}</strong><small>{new Date(report.created_at).toLocaleString('zh-CN')} · {report.recommendation} · {report.score.toFixed(1)} 分</small></div><div className="report-links"><a href={api.reportDownloadUrl(report.id, 'docx')}>下载 Word</a><a href={api.reportDownloadUrl(report.id, 'pdf')}>下载 PDF</a></div><div className="report-email"><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="接收邮箱" /><button className="secondary-btn" onClick={() => void deliverReport(false)} disabled={isSendingReport}>邮件预览</button><button className="primary-btn" onClick={() => void deliverReport(true)} disabled={isSendingReport}>{isSendingReport ? '处理中…' : '确认发送'}</button></div>{reportEmailResult && <p className={`report-email-message ${reportEmailResult.mode}`}>{reportEmailResult.mode === 'preview' ? '安全预览' : reportEmailResult.mode === 'sent' ? '已发送' : '发送失败'}：{reportEmailResult.message}（{reportEmailResult.attachments.join('、')}）</p>}</div>}
        </section>

        <section id="overview" className="hero-grid">
          <article className="score-card panel">
            <div className="panel-label">当前市场判断 <span>用于排定研究与项目优先级</span></div>
            <div className="score-content"><ScoreRing score={activeScore} /><div><p className="recommendation">{activeRecommendation}</p><h2>{scenarioChanged ? '调整假设后的判断' : '建议继续研究，并优先核验关键风险'}</h2><p>这是帮助团队安排下一步工作的市场判断，不替代投资、并网、工程或法律决策。</p></div></div>
            <div className="score-footer"><span>最近更新 · {new Date(overview.last_updated).toLocaleString('zh-CN')}</span><button onClick={() => setScenario(defaultScenario)}>重置假设</button></div>
          </article>
          <article className="insight-card panel"><div className="panel-label">本轮优先核验 <span className="accent">{overview.evidence.length} 条依据</span></div><h3>先核验并网、政策和项目经济性，再决定是否投入更多尽调资源。</h3><p>当这三项证据不足时，不应只因市场评分较高就推进项目。</p><div className="evidence-chip"><span>✓</span> 判断已关联 {overview.evidence.length} 条可追溯依据</div></article>
        </section>

        <section className="overview-grid">
          <article className="panel trend-panel"><TrendChart overview={overview} /></article>
          <article className="panel metrics-panel"><div className="panel-label">评分拆解 <span>权重 × 得分</span></div>{components.map((component) => <div className="metric-row" key={component.key}><div><span>{component.label}</span><small>{Math.round(component.weight * 100)}% 权重</small></div><div className="metric-track"><i style={{ width: `${component.score}%` }} /></div><strong>{component.score.toFixed(0)}</strong></div>)}</article>
        </section>

        <section className="evidence-workbench panel" aria-label="市场影响矩阵与证据时间线">
          <div className="section-heading">
            <div><p className="eyebrow">MARKET JUDGMENT / EVIDENCE</p><h2>市场判断依据</h2><p>这里回答“为什么这么判断”：八个维度分别展示数据覆盖、来源、更新时间和影响解释。未确认的信息只作为待核验线索，不会自动改变判断。</p></div>
            <button className="secondary-btn" onClick={() => void refreshFeatureEvidence()} disabled={isRefreshingFeatures}>{isRefreshingFeatures ? '更新依据中…' : '更新公开数据依据'}</button>
          </div>
          <div className="feature-coverage">
            <div><span>本次判断依据</span><strong>{featureSnapshot ? shortDate(featureSnapshot.captured_at) : '等待加载'}</strong></div>
            <div><span>当前评分规则</span><strong>{featureSnapshot ? `${featureSnapshot.market_pack_id} v${featureSnapshot.market_pack_version}` : '—'}</strong></div>
            <div><span>有真实观测的维度</span><strong>{impactMatrix?.items.filter((item) => item.status === 'observed').length ?? 0} / 8</strong></div>
            <div><span>待核验的文本依据</span><strong>{evidenceTimeline.length}</strong></div>
          </div>
          <div className="impact-matrix">
            {(impactMatrix?.items ?? []).map((item) => <article className={`factor-cell ${item.status}`} key={item.key}>
              <div className="factor-cell-top"><span className={`factor-status ${item.status}`}>{item.status}</span><strong>{item.score.toFixed(0)}</strong></div>
              <h3>{item.label}</h3>
              <div className="coverage-bar"><i style={{ width: `${item.coverage_ratio * 100}%` }} /></div>
              <small>覆盖 {(item.coverage_ratio * 100).toFixed(0)}% · {item.freshness_label}</small>
              <p>{item.explanation}</p>
              <footer><span>{item.source_ids.length ? item.source_ids.join(' / ') : '无结构化来源'}</span><em>{item.evidence_ids.length} 条证据</em></footer>
            </article>)}
          </div>
          <div className="evidence-timeline-heading">
            <div><span>证据变化时间线</span><small>优先确认会改变项目判断的信号；只保存公开标题、摘要与短摘录，不镜像文章全文。</small></div>
            <div className="evidence-filters">
              <select value={evidenceFactorFilter} onChange={(event) => setEvidenceFactorFilter(event.target.value)}><option value="all">全部因素</option>{(impactMatrix?.items ?? []).map((item) => <option value={item.key} key={item.key}>{item.label}</option>)}</select>
              <select value={evidenceStateFilter} onChange={(event) => setEvidenceStateFilter(event.target.value as typeof evidenceStateFilter)}><option value="all">全部状态</option><option value="pending">待确认</option><option value="confirmed">已确认</option></select>
            </div>
          </div>
          <div className="evidence-timeline">
            {visibleEvidence.length === 0 && <p className="evidence-empty">当前筛选没有已入库的文本证据。刷新公开新闻后，系统会按规则提取事件字段。</p>}
            {visibleEvidence.map((item) => <article className={`evidence-event ${item.acknowledged ? 'confirmed' : 'pending'}`} key={item.id}>
              <div className={`direction ${item.impact_direction}`}>{item.impact_direction === 'positive' ? '↑' : item.impact_direction === 'negative' ? '↓' : '↔'}</div>
              <div className="evidence-event-copy"><div><small>{shortDate(item.published_at ?? item.created_at)} · {item.source} · {item.extraction_mode}</small><em>{item.acknowledged ? '已确认' : '待确认'}</em></div><h3>{item.title}</h3><p>{item.excerpt || item.summary}</p><footer><span>{item.event_type}</span>{item.impact_factors.map((factor) => <b key={factor}>{factor}</b>)}<small>置信度 {(item.confidence * 100).toFixed(0)}%</small></footer>{item.url && <a href={item.url} target="_blank" rel="noreferrer">查看公开来源 ↗</a>}</div>
              {!item.acknowledged && <button className="ack-btn" onClick={() => void confirmEvidence(item.id)}>确认并触发复核</button>}
            </article>)}
          </div>
        </section>

        <section id="projects" className="project-workbench panel" aria-label="海外项目准入与尽调工作台">
          <div className="section-heading"><div><p className="eyebrow">PROJECT ACTIONS / HUMAN DECISION</p><h2>项目推进与待办</h2><p>先创建项目机会，再运行准入评估；系统会列出必须补齐的阻塞项和责任人。只有 blocker 关闭后，项目才能提交人工评审。</p></div><div className="project-counter"><span>该市场项目</span><strong>{projects.length}</strong></div></div>
          <div className="project-create">
            <label>项目名称<input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="例如 Almería 120MW 光伏项目" /></label>
            <label>负责人<input value={projectOwner} onChange={(event) => setProjectOwner(event.target.value)} /></label>
            <label>容量 MW<input type="number" min="1" value={projectCapacity} onChange={(event) => setProjectCapacity(event.target.value)} placeholder="120" /></label>
            <label>目标 COD<input type="date" value={projectTargetCod} onChange={(event) => setProjectTargetCod(event.target.value)} /></label>
            <button className="primary-btn" onClick={() => void createProject()} disabled={isCreatingProject}>{isCreatingProject ? '创建中…' : '创建并开始推进'} <span>→</span></button>
          </div>
          <div className="project-layout">
            <aside className="project-rail"><div className="project-rail-heading"><span>当前项目机会</span><small>仅显示所选市场</small></div>{projects.length === 0 ? <p>还没有项目。创建一条项目机会后，才能把国家研究变成可分配的尽调动作。</p> : projects.map((project) => <button key={project.id} className={`project-row ${selectedProjectId === project.id ? 'selected' : ''}`} onClick={() => void selectProject(project.id)}><span className={`stage-dot ${project.stage}`} /><div><strong>{project.name}</strong><small>{project.owner} · {project.capacity_mw ? `${project.capacity_mw} MW` : '容量待补充'}</small></div><em>{project.stage}</em></button>)}</aside>
            <article className="project-detail">
              {!selectedProject ? <p className="project-empty">从左侧选择或新建一个项目机会。</p> : <>
                <div className="project-detail-heading"><div><span>{selectedProject.profile_id.toUpperCase()} · {selectedProject.id}</span><h3>{selectedProject.name}</h3><small>{selectedProject.owner} · 目标 COD {selectedProject.target_cod || '待定义'} · 创建 {shortDate(selectedProject.created_at)}</small></div><div className={`project-stage ${selectedProject.stage}`}>{selectedProject.stage}</div></div>
                <div className="project-actions"><button className="secondary-btn" onClick={() => void assessSelectedProject()} disabled={isAssessingProject}>{isAssessingProject ? '评估中…' : '1. 检查能否推进'}</button><button className="secondary-btn" onClick={() => void transitionProject('due_diligence')}>2. 进入尽调</button><button className="secondary-btn" onClick={() => void transitionProject('review')} disabled={openBlockers.length > 0}>3. 提交人工评审</button><button className="text-btn" onClick={() => void downloadProjectBriefing()}>导出汇报简报 ↓</button></div>
                {projectAssessment && <div className={`assessment-card ${projectAssessment.verdict}`}><div><span>ADMISSION ASSESSMENT</span><strong>{projectAssessment.verdict === 'ready_for_review' ? '可进入人工评审' : projectAssessment.verdict === 'needs_due_diligence' ? '需补充尽调' : '暂不具备准入条件'}</strong><small>风险 {projectAssessment.risk_level} · 特征快照 {projectAssessment.factor_snapshot_id}</small></div><p>{projectAssessment.summary}</p>{projectAssessment.blockers.length > 0 && <div className="assessment-blockers">{projectAssessment.blockers.map((blocker) => <b key={blocker}>BLOCKER · {blocker}</b>)}</div>}</div>}
                <div className="project-stage-control"><label>人工决策说明<textarea value={projectDecisionNote} onChange={(event) => setProjectDecisionNote(event.target.value)} placeholder="例如：经并网与政策材料复核后，提交投资委员会评审。" /></label><div><button className="mini-btn" onClick={() => void transitionProject('on_hold')}>暂缓</button><button className="mini-btn" onClick={() => void transitionProject('rejected')}>淘汰</button><button className="primary-btn" onClick={() => void transitionProject('admitted')} disabled={openBlockers.length > 0 || !projectDecisionNote.trim()}>人工准入</button></div></div>
                <div className="task-heading"><div><span>你现在需要处理的事项</span><strong>{openBlockers.length} 个 blocker 尚未关闭</strong></div><small>系统只负责提醒与分配；完成、暂缓或推进都必须由责任人明确操作。</small></div>
                <div className="task-list">{projectTasks.length === 0 ? <p className="project-empty">先点击“检查能否推进”，系统才会按八个关键维度生成可追溯的尽调任务。</p> : projectTasks.map((task) => <article className={`project-task ${task.priority} ${task.status}`} key={task.id}><div className="task-priority">{task.priority === 'blocker' ? '!' : task.priority === 'high' ? '↑' : '·'}</div><div><div><span>{task.priority.toUpperCase()} · {task.factor_key}</span><em>{task.status}</em></div><h4>{task.title}</h4><p>负责人：{task.owner} · 截止：{task.due_date}{task.evidence_ids.length > 0 ? ` · 证据 ${task.evidence_ids.join(' / ')}` : ''}</p>{task.completion_note && <small>{task.completion_note}</small>}</div>{task.status !== 'done' && task.status !== 'not_applicable' && <div className="task-actions"><button className="text-btn" onClick={() => void updateTaskStatus(task, 'in_progress')}>开始处理</button><button className="mini-btn" onClick={() => void updateTaskStatus(task, 'done')}>标记完成</button></div>}</article>)}</div>
              </>}
            </article>
          </div>
          {projectMessage && <p className="project-message">{projectMessage}</p>}
        </section>

        <section id="market-packs" className="market-pack-panel panel">
          <div className="section-heading"><div><p className="eyebrow">SCORING GOVERNANCE / VERSIONED</p><h2>评分规则与版本</h2><p>当业务团队需要调整市场判断口径时，在这里修改维度、权重和基准分。先保存草稿、核验影响，再由人工发布；历史判断不会被覆盖。</p></div><div className="market-pack-status"><span>当前使用规则</span><strong>{marketPackDetail ? `v${marketPackDetail.version} · ${marketPackDetail.status}` : '读取中'}</strong></div></div>
          <div className="market-pack-grid">
            <article className="market-pack-editor">
              <div className="market-pack-meta"><label>名称<input value={marketPackDraft.name} onChange={(event) => setMarketPackDraft((current) => ({ ...current, name: event.target.value }))} /></label><label>国家<input value={marketPackDraft.country} onChange={(event) => setMarketPackDraft((current) => ({ ...current, country: event.target.value }))} /></label><label>赛道<input value={marketPackDraft.sector} onChange={(event) => setMarketPackDraft((current) => ({ ...current, sector: event.target.value }))} /></label></div>
              <div className="market-pack-components"><div className="market-pack-components-heading"><div><span>市场判断维度</span><small>权重合计 {(marketPackWeightTotal * 100).toFixed(1)}%</small></div><button className="text-btn" type="button" onClick={addMarketPackComponent}>+ 添加判断维度</button></div>{marketPackDraft.components.map((component, index) => <div className="market-pack-component" key={`${component.key}-${index}`}><input aria-label={`组件 ${index + 1} 键`} value={component.key} onChange={(event) => updateMarketPackComponent(index, 'key', event.target.value)} /><input aria-label={`组件 ${index + 1} 名称`} value={component.label} onChange={(event) => updateMarketPackComponent(index, 'label', event.target.value)} /><input aria-label={`组件 ${index + 1} 基准分`} type="number" min="0" max="100" value={component.base_score} onChange={(event) => updateMarketPackComponent(index, 'base_score', event.target.value)} /><label><input aria-label={`组件 ${index + 1} 权重`} type="number" min="0.01" max="1" step="0.01" value={component.weight} onChange={(event) => updateMarketPackComponent(index, 'weight', event.target.value)} /><span>{(component.weight * 100).toFixed(0)}%</span></label><button className="remove-component" type="button" disabled={marketPackDraft.components.length === 1} onClick={() => setMarketPackDraft((current) => ({ ...current, components: current.components.filter((_, componentIndex) => componentIndex !== index) }))}>×</button></div>)}</div>
              <label className="market-pack-note">变更说明<textarea value={marketPackDraft.change_note} onChange={(event) => setMarketPackDraft((current) => ({ ...current, change_note: event.target.value }))} /></label>
              <div className="market-pack-actions"><button className="secondary-btn" onClick={() => void saveMarketPackDraft()} disabled={isSavingMarketPack}>{isSavingMarketPack ? '保存中…' : '1. 保存为草稿'}</button><button className="secondary-btn" onClick={() => void previewSelectedMarketPack()} disabled={isPreviewingMarketPack || !marketPackDetail}>{isPreviewingMarketPack ? '计算中…' : '2. 预览影响'}</button>{canPublishSelectedMarketPack && <button className="primary-btn" onClick={() => void publishSelectedMarketPack()} disabled={isPublishingMarketPack}>{isPublishingMarketPack ? '发布中…' : `3. 发布 v${marketPackDetail?.version}`} <span>→</span></button>}<button className="text-btn" onClick={() => void exportSelectedMarketPack()}>导出规则模板</button></div>
              {marketPackDetail?.status === 'draft' && marketPackDetail.id !== 'de-pv' && <p className="market-pack-boundary">该模板已保存为可复用草稿；待为该国家/赛道绑定独立数据源后，才会开放发布到实时总览。</p>}
              {marketPackMessage && <p className="market-pack-message">{marketPackMessage}</p>}
              {marketPackPreview && <aside className="market-pack-preview"><div><span>SANDBOX RESULT</span><strong>{marketPackPreview.score.toFixed(1)} / 100</strong></div><p>{marketPackPreview.recommendation} · 相对基线 {formatDelta(marketPackPreview.delta)} 分</p><small>已复用当前情景假设；该结果不影响实时总览或任何已发布版本。</small></aside>}
              <details className="market-pack-import"><summary>复用其他市场的评分规则</summary><div><label>目标市场包 ID<input value={importPackId} onChange={(event) => setImportPackId(event.target.value)} placeholder="例如 fr-pv" /></label><label>规则模板 JSON<textarea value={importTemplateText} onChange={(event) => setImportTemplateText(event.target.value)} placeholder="粘贴 AtlasIQ 导出的规则模板" /></label><button className="secondary-btn" onClick={() => void importMarketPackTemplate()} disabled={isImportingMarketPack || !importTemplateText.trim()}>{isImportingMarketPack ? '导入中…' : '导入为草稿'}</button></div></details>
            </article>
            <aside className="market-pack-ledger"><div className="ledger-heading"><span>VERSION LEDGER</span><small>可追溯、不可覆盖</small></div>{marketPacks.slice(0, 8).map((pack) => <button className={`pack-version ${marketPackDetail?.id === pack.id && marketPackDetail.version === pack.version ? 'selected' : ''}`} key={`${pack.id}-${pack.version}`} onClick={() => void selectMarketPackVersion(pack)}><div><strong>v{pack.version}</strong><span className={`pack-status ${pack.status}`}>{pack.status === 'published' ? '已发布' : pack.status === 'draft' ? '草稿' : '已归档'}</span></div><p>{pack.change_note}</p><small>{dateTimeLabel(pack.published_at ?? pack.created_at)}</small></button>)}</aside>
          </div>
        </section>

        <section className="scenario-panel panel">
          <div className="section-heading"><div><p className="eyebrow">TEST THE ASSUMPTIONS</p><h2>关键假设影响</h2><p>不确定补贴、需求、并网或资源条件时，先在这里测试影响幅度，再决定优先补哪一份材料。</p></div><button className="quiet-btn" onClick={() => void runScenario()}>测试影响 <span>↗</span></button></div>
          <div className="sliders">
            {([
              ['subsidy_change', '补贴支持变化', '政策强度'],
              ['demand_change', '市场需求变化', '需求水平'],
              ['grid_risk_change', '并网风险变化', '执行风险'],
              ['weather_change', '资源条件变化', '辐照条件'],
            ] as const).map(([key, label, hint]) => <label className="slider-control" key={key}><div><span>{label}</span><small>{hint}</small><strong>{formatDelta(scenario[key])}%</strong></div><input type="range" min="-30" max="30" value={scenario[key]} onChange={(event) => setScenario({ ...scenario, [key]: Number(event.target.value) })} /></label>)}
          </div>
          {scenarioResult && <div className="scenario-result"><span>调整后的市场判断</span><strong>{scenarioResult.recommendation}</strong><p>{scenarioResult.explanation}</p></div>}
          {simulationResult && <div className="simulation-strip"><div><span>P10</span><strong>{simulationResult.p10.toFixed(1)}</strong></div><div><span>P50</span><strong>{simulationResult.p50.toFixed(1)}</strong></div><div><span>P90</span><strong>{simulationResult.p90.toFixed(1)}</strong></div><div className="probability"><span>积极研究概率</span><strong>{(simulationResult.probability_research * 100).toFixed(1)}%</strong></div><p>{simulationResult.explanation}</p></div>}
          {sensitivityResult && <div className="sensitivity-panel"><div className="sensitivity-heading"><div><span>ONE-AT-A-TIME SENSITIVITY</span><strong>优先验证影响最大的假设</strong></div><small>在当前情景下逐项 ±{sensitivityResult.perturbation} 个百分点，其余假设保持不变</small></div>{sensitivityResult.items.map((item, index) => <div className="sensitivity-row" key={item.key}><div><b>{index + 1}</b><span>{item.label}</span><small>最大影响 {item.impact.toFixed(1)} 分</small></div><div><em className={item.positive_delta >= 0 ? 'positive' : 'negative'}>+{sensitivityResult.perturbation}pp {formatDelta(item.positive_delta)}</em><em className={item.negative_delta >= 0 ? 'positive' : 'negative'}>−{sensitivityResult.perturbation}pp {formatDelta(item.negative_delta)}</em></div></div>)}</div>}
        </section>

        <section id="research" className="research-grid">
          <article className="research-panel panel"><div className="section-heading"><div><p className="eyebrow">AI HELPS EXPLAIN, PEOPLE DECIDE</p><h2>生成带证据的研究结论</h2></div><span className={isResearching ? 'status running' : 'status'}>{isResearching ? '生成中' : researchStatus}</span></div><form onSubmit={askResearch}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} aria-label="研究问题" /><div className="form-footer"><span>输入一个具体业务问题；AI 只会组织已检索的指标和证据，不会替你做准入或投资决策。</span><button className="primary-btn" disabled={isResearching}>{isResearching ? '正在整理…' : '生成带证据的结论'} <span>→</span></button></div></form><div className="research-output">{researchText ? <p>{researchText}</p> : <p className="placeholder">例如：德国光伏市场现在最需要补齐哪项尽调证据？系统会先运行受控分析，再生成可回看的研究结论。</p>}</div>{citations.length > 0 && <div className="citations"><p>这份结论引用的依据</p>{citations.map((citation) => <div key={citation.id} className="citation"><b>[{citation.id}]</b><div><strong>{citation.title}</strong><span>{citation.source}</span></div></div>)}</div>}{researchRuns[0] && <div className="run-audit"><div className="run-audit-heading"><span>AI 运行记录</span><small>本地保存最近记录，便于回看依据与响应质量</small></div>{researchObservability && researchObservability.sample_size > 0 && <div className="quality-grid"><div><span>样本</span><strong>{researchObservability.sample_size}</strong></div><div><span>P50</span><strong>{researchObservability.p50_latency_ms ?? '—'} ms</strong></div><div><span>P95</span><strong>{researchObservability.p95_latency_ms ?? '—'} ms</strong></div><div><span>降级率</span><strong>{rateLabel(researchObservability.fallback_rate)}</strong></div><div><span>证据覆盖</span><strong>{rateLabel(researchObservability.evidence_coverage)}</strong></div></div>}{researchRuns.slice(0, 2).map((run) => <div className="run-record" key={run.id}><div><strong>{runtimeLabel(run)}</strong><small>{dateTimeLabel(run.created_at)} · {run.latency_ms} ms · {run.evidence_ids.join(' / ')}</small>{run.answer && <button className="text-btn" onClick={() => { setQuestion(run.question); setResearchText(run.answer ?? ''); setResearchStatus('已回看本地保存的历史报告') }}>回看该结论</button>}</div><em>{run.recommendation} {run.score.toFixed(1)}</em></div>)}</div>}</article>
          <article id="sources" className="sources-panel panel"><div className="panel-label">数据与来源 <span>知道结论来自哪里</span></div>{sources.map((source) => <div className="source-card" key={source.id}><div className="source-icon">{source.kind === 'energy' ? 'EN' : 'WX'}</div><div><strong>{source.name} <em className={`source-status ${source.status}`}>{source.status}</em></strong><p>{source.note}</p><small>{source.observation_label} · 上次检查 {dateTimeLabel(source.last_checked_at)} · 上次成功 {dateTimeLabel(source.last_success_at)}</small></div></div>)}<button className="source-link" onClick={() => void refreshPublicData()}>更新已配置的公开数据 →</button></article>
        </section>

        <section className="decision-panel panel">
          <div className="section-heading"><div><p className="eyebrow">DECISION LOOP / HUMAN OWNED</p><h2>保存判断并设置复盘</h2><p>把本次判断、引用依据、负责人和下一次复盘日期放在一起；市场变化出现后，团队能回到当时的依据重新核验。</p></div><button className="primary-btn" onClick={() => void saveDecisionCard()}>保存判断并安排复盘 <span>→</span></button></div>
          <div className="decision-controls"><label>判断<select value={decisionVerdict} onChange={(event) => setDecisionVerdict(event.target.value as typeof decisionVerdict)}><option value="research">积极研究</option><option value="watch">持续观察</option><option value="hold">暂缓进入</option></select></label><label>复盘日期<input type="date" value={reviewDate} onChange={(event) => setReviewDate(event.target.value)} /></label><div className="decision-hint"><span>负责人</span><strong>Strategy Desk</strong><small>证据：{citations.length > 0 ? citations.map((item) => item.id).join(' · ') : '等待研究结果'}</small></div></div>
          {decisionReadiness && <aside className={`readiness-gate ${decisionReadiness.status}`} aria-label="决策就绪度">
            <div className="readiness-summary"><div><span>DECISION READINESS</span><strong>{readinessLabel(decisionReadiness.status)}</strong></div><b>{decisionReadiness.score}<small>/ 100</small></b></div>
            <p>{decisionReadiness.next_action}</p>
            <div className="readiness-checks">{decisionReadiness.checks.map((check) => <div className={`readiness-check ${check.status}`} key={check.key}><i>{check.status === 'pass' ? '✓' : check.status === 'caution' ? '!' : '—'}</i><div><strong>{check.label}</strong><span>{check.detail}</span></div><em>{check.score}/{check.max_score}</em></div>)}</div>
          </aside>}
          {decisionMessage && <p className="decision-message">{decisionMessage}</p>}
          {reviewMessage && <p className="decision-message">{reviewMessage}</p>}
          <div className="review-queue" aria-label="决策复盘提醒"><div className="review-queue-heading"><div><span>接下来需要回看的判断</span><strong>让每次判断回到当时的证据与后续结果中复核</strong></div><small>按设定的复盘日期自动分组</small></div><div className="review-summary"><div className={decisionReviewQueue.overdue.length > 0 ? 'review-count urgent' : 'review-count'}><span>已逾期</span><strong>{decisionReviewQueue.overdue.length}</strong></div><div className={decisionReviewQueue.due_today.length > 0 ? 'review-count today' : 'review-count'}><span>今天要回看</span><strong>{decisionReviewQueue.due_today.length}</strong></div><div className="review-count"><span>未来 7 天</span><strong>{decisionReviewQueue.upcoming.length}</strong></div></div>{[...decisionReviewQueue.overdue, ...decisionReviewQueue.due_today, ...decisionReviewQueue.upcoming].length > 0 ? <div className="review-items">{decisionReviewQueue.overdue.slice(0, 1).map((card) => <p key={card.id}><em>逾期</em>{card.title}<small>{card.review_date}</small></p>)}{decisionReviewQueue.due_today.slice(0, 1).map((card) => <p key={card.id}><em>今天</em>{card.title}<small>{card.review_date}</small></p>)}{decisionReviewQueue.upcoming.slice(0, 1).map((card) => <p key={card.id}><em>待办</em>{card.title}<small>{card.review_date}</small></p>)}</div> : <p className="review-empty">未来 7 天没有待回看的判断；保存判断时可以设置复盘日期。</p>}</div>
          {decisionReviewTriggers.length > 0 && <div className="signal-review-alert" aria-label="市场信号触发的复盘提醒"><div><span>CONFIRMED SIGNAL → REVIEW</span><strong>已确认的中高优先级信号涉及现有决策假设</strong></div><small>系统不会自动修改判断，只提示重新核验。</small>{decisionReviewTriggers.slice(0, 2).map((trigger) => <p key={trigger.news.id}><em>{trigger.news.category}</em><span>{trigger.news.title}</span><small>关联 {trigger.cards.map((card) => card.title).join(' / ')} · 证据 {trigger.evidence_ids.join(' / ')}</small></p>)}</div>}
          <div className="decision-history">{decisionCards.length === 0 ? <p>暂无已保存决策。完成一次研究后可创建第一张决策卡。</p> : decisionCards.slice(0, 3).map((card) => { const latestReview = decisionReviews[card.id]?.[0]; const snapshots = evidenceSnapshots[card.id] ?? []; return <article key={card.id} className="decision-card"><span className={`verdict ${card.verdict}`}>{card.verdict === 'research' ? '积极研究' : card.verdict === 'watch' ? '持续观察' : '暂缓进入'}</span><div><h3>{card.title}</h3><p>{card.rationale.slice(0, 150)}{card.rationale.length > 150 ? '…' : ''}</p><small>{card.owner} · 复盘 {card.review_date} · {card.evidence_ids.join(' / ') || '无引用'}</small>{snapshotCardId === card.id && <div className="evidence-snapshot">{snapshots.map((item) => <div key={item.id}><b>[{item.id}] {item.title}</b><small>{item.source} · {item.metric}</small><p>{item.excerpt}</p></div>)}</div>}{latestReview && <div className={`review-result ${latestReview.outcome}`}><strong>{latestReview.outcome === 'maintain' ? '复盘：维持判断' : latestReview.outcome === 'adjust' ? '复盘：调整判断' : '复盘：终止跟踪'}</strong><p>{latestReview.note}</p><small>{dateTimeLabel(latestReview.created_at)}</small></div>}{reviewingCardId === card.id ? <div className="review-action"><select value={reviewOutcome} onChange={(event) => setReviewOutcome(event.target.value as typeof reviewOutcome)}><option value="maintain">维持判断</option><option value="adjust">调整判断</option><option value="retire">终止跟踪</option></select><textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="填写本次复盘的证据、变化或下一步…" aria-label="复盘说明" /><div><button className="mini-btn" onClick={() => void saveDecisionReview(card.id)}>保存复盘</button><button className="text-btn" onClick={() => { setReviewingCardId(null); setReviewNote('') }}>取消</button></div></div> : <div className="card-actions"><button className="text-btn" onClick={() => void toggleEvidenceSnapshot(card)}>{snapshotCardId === card.id ? '收起证据快照' : '查看证据快照'}</button><button className="text-btn record-review" onClick={() => { setReviewingCardId(card.id); setReviewMessage('') }}>记录复盘 →</button><button className="text-btn" onClick={() => void exportDecisionBriefing(card)}>导出简报 ↓</button></div>}</div></article>})}</div>
        </section>

        <section id="signals" className="signals-grid">
          <article className="news-panel panel"><div className="section-heading"><div><p className="eyebrow">MARKET CHANGE / REVIEW FIRST</p><h2>需要你确认的市场变化</h2><p>只把可能影响现有判断或项目推进的公开信息放到这里；确认后会留下依据，并提醒相关项目或判断重新核验。</p></div><div className="news-actions"><span className="freshness"><i /> {newsPollingLabel(newsPollingStatus)}</span><button className="mini-btn" onClick={() => void refreshNews()} disabled={isRefreshingNews}>{isRefreshingNews ? '刷新中…' : '更新动态'}</button></div></div>{newsRefreshMessage && <p className="news-refresh-message">{newsRefreshMessage}</p>}{orderedNews.map((item) => <article className={`news-item ${item.acknowledged ? 'acknowledged' : ''}`} key={item.id}><div className={`impact impact-${item.impact}`}><span>{item.impact === 'medium' ? '!' : '·'}</span></div><div className="news-copy"><div><small>{item.category} · {shortDate(item.published_at)}</small>{item.acknowledged && <em>已确认</em>}</div><h3>{item.title}</h3><p>{item.summary}</p><strong>可能影响：{item.why}</strong>{item.url && <a href={item.url} target="_blank" rel="noreferrer">查看原始来源 ↗</a>}</div>{!item.acknowledged && <button className="ack-btn" onClick={() => void acknowledge(item.id)}>确认并纳入复核</button>}</article>)}</article>
          <article className="notify-panel panel"><p className="eyebrow">EMAIL NOTIFICATION</p><h2>把重要变化送到负责人邮箱</h2><p>仅当公开信息匹配规则并超过阈值时才推送。未配置 SMTP 时只保存安全预览，不会发送真实邮件。</p><label>接收提醒的邮箱<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><button className="primary-btn full" onClick={() => void subscribeToSignals()}>订阅需要关注的变化 <span>→</span></button><button className="secondary-btn full" onClick={() => void previewEmail()}>预览邮件内容</button>{subscriptionMessage && <div className="email-message">{subscriptionMessage}</div>}{emailMessage && <div className="email-message">{emailMessage}</div>}<div className="notify-rule"><span>当前提醒规则</span><strong>德国 · 光伏 · 即时 · 中高优先级</strong></div></article>
        </section>

        <footer>AtlasIQ MVP · 本地优先 · 所有市场结论须由分析师复核</footer>
      </section>
    </main>
  )
}

export default App
