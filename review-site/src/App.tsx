import { Flower2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type View = 'home' | 'news' | 'story' | 'collection' | 'inquire'
type Block =
  | { type: 'h2'; text: string }
  | { type: 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'image'; alt: string; src: string }
  | { type: 'sources'; items: Array<{ label: string; href: string }> }

type Article = { title: string; subtitle: string; blocks: Block[] }
type EditionArticle = {
  title: string
  chinese_characters: number
  source_count: number
  image_count: number
}
type EditionSummary = {
  edition_date: string
  articles: { wechat: EditionArticle; woshipm: EditionArticle }
}
type ArchiveIndex = { editions: string[] }
type ClaimStatus = 'supported' | 'partial' | 'conflicting' | 'unverified'
type ResearchClaim = { text: string; status: ClaimStatus; evidence_urls: string[] }
type ResearchItem = {
  rank: number
  title: string
  event_time: string
  summary: string
  why_it_matters: string
  risk_note: string
  source_urls: string[]
  claims: ResearchClaim[]
}
type ReferenceMaterial = {
  title: string
  url: string
  purpose: string
  status: Exclude<ClaimStatus, 'conflicting'>
}
type ResearchTopic = {
  platform: 'wechat' | 'woshipm'
  title: string
  angle: string
  audience_decision: string
  new_value: string
}
type ResearchBundle = {
  edition_date: string
  digest_title: string
  executive_summary: string
  items: ResearchItem[]
  reference_materials: ReferenceMaterial[]
  topics: ResearchTopic[]
}
type ResearchState =
  | { status: 'loading' }
  | { status: 'empty' }
  | { status: 'error' }
  | { status: 'ready'; data: ResearchBundle }

const entrance = 'cubic-bezier(0.16, 1, 0.3, 1)'
const overlayEase = 'cubic-bezier(0.76, 0, 0.24, 1)'
const base = import.meta.env.BASE_URL
const claimLabels: Record<ClaimStatus, string> = {
  supported: '已核实',
  partial: '部分支持',
  conflicting: '存在冲突',
  unverified: '未核实',
}
const claimStyles: Record<ClaimStatus, string> = {
  supported: 'bg-[#dce8d8] text-[#31512d]',
  partial: 'bg-[#eee2c7] text-[#72551d]',
  conflicting: 'bg-[#ecd5d0] text-[#7b3025]',
  unverified: 'bg-black/10 text-black/55',
}

function isResearchBundle(value: unknown): value is ResearchBundle {
  if (!value || typeof value !== 'object') return false
  const bundle = value as Partial<ResearchBundle>
  return typeof bundle.edition_date === 'string'
    && typeof bundle.digest_title === 'string'
    && typeof bundle.executive_summary === 'string'
    && Array.isArray(bundle.reference_materials)
    && bundle.reference_materials.every((candidate) => {
      if (!candidate || typeof candidate !== 'object') return false
      const material = candidate as Partial<ReferenceMaterial>
      return typeof material.title === 'string'
        && typeof material.url === 'string'
        && typeof material.purpose === 'string'
        && (material.status === 'supported' || material.status === 'partial' || material.status === 'unverified')
    })
    && Array.isArray(bundle.topics)
    && bundle.topics.every((candidate) => {
      if (!candidate || typeof candidate !== 'object') return false
      const topic = candidate as Partial<ResearchTopic>
      return (topic.platform === 'wechat' || topic.platform === 'woshipm')
        && typeof topic.title === 'string'
        && typeof topic.angle === 'string'
        && typeof topic.audience_decision === 'string'
        && typeof topic.new_value === 'string'
    })
    && Array.isArray(bundle.items)
    && bundle.items.every((candidate) => {
      if (!candidate || typeof candidate !== 'object') return false
      const item = candidate as Partial<ResearchItem>
      return typeof item.rank === 'number'
        && typeof item.title === 'string'
        && typeof item.event_time === 'string'
        && typeof item.summary === 'string'
        && typeof item.why_it_matters === 'string'
        && typeof item.risk_note === 'string'
        && Array.isArray(item.source_urls)
        && item.source_urls.every((url) => typeof url === 'string')
        && Array.isArray(item.claims)
        && item.claims.every((claimCandidate) => {
          if (!claimCandidate || typeof claimCandidate !== 'object') return false
          const claim = claimCandidate as Partial<ResearchClaim>
          return typeof claim.text === 'string'
            && typeof claim.status === 'string'
            && claim.status in claimLabels
            && Array.isArray(claim.evidence_urls)
            && claim.evidence_urls.every((url) => typeof url === 'string')
        })
    })
}

function sourceHost(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function isArchiveIndex(value: unknown): value is ArchiveIndex {
  if (!value || typeof value !== 'object') return false
  const archive = value as Partial<ArchiveIndex>
  return Array.isArray(archive.editions)
    && archive.editions.every((edition) => /^\d{4}-\d{2}-\d{2}$/.test(edition))
}

function formatEditionDate(value: string) {
  const [year, month, day] = value.split('-')
  return `${year}年${Number(month)}月${Number(day)}日`
}

function ArchivePicker({
  editions,
  current,
  onChange,
}: {
  editions: string[]
  current: string
  onChange: (edition: string) => void
}) {
  if (!editions.length) return null
  return (
    <label className="flex items-center gap-2 rounded-full border border-white/20 px-4 py-2 text-white/70">
      <span className="text-xs font-medium uppercase tracking-[0.14em]">历史日期</span>
      <select
        aria-label="查看历史日期"
        value={editions.includes(current) ? current : editions[0]}
        onChange={(event) => onChange(event.target.value)}
        className="max-w-[9.5rem] cursor-pointer bg-black text-sm text-white outline-none"
      >
        {editions.map((edition) => (
          <option key={edition} value={edition}>{formatEditionDate(edition)}</option>
        ))}
      </select>
    </label>
  )
}

function formatEventTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: value.includes('T') ? '2-digit' : undefined,
    minute: value.includes('T') ? '2-digit' : undefined,
  }).format(date)
}

function displayDigestTitle(value: string) {
  const normalized = value.replace(/^AI\s*资讯日报\s*[｜|:：-]?\s*/i, '')
  return normalized === value ? value : `SignalBloom 本期信号｜${normalized}`
}

function itemStatus(item: ResearchItem): ClaimStatus {
  if (item.claims.some((claim) => claim.status === 'conflicting')) return 'conflicting'
  if (item.claims.some((claim) => claim.status === 'unverified')) return 'unverified'
  if (item.claims.some((claim) => claim.status === 'partial')) return 'partial'
  return 'supported'
}

function parseArticle(markdown: string): Article {
  const lines = markdown.split(/\r?\n/)
  const title = lines.find((line) => line.startsWith('# '))?.slice(2).trim() ?? ''
  const titleIndex = lines.findIndex((line) => line.startsWith('# '))
  const subtitle = lines.slice(titleIndex + 1).find((line) => line.trim())?.trim() ?? ''
  const blocks: Block[] = []
  let paragraph: string[] = []
  let sources: Array<{ label: string; href: string }> = []
  let inSources = false

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'p', text: paragraph.join(' ') })
    paragraph = []
  }
  const flushSources = () => {
    if (sources.length) blocks.push({ type: 'sources', items: sources })
    sources = []
  }

  for (const rawLine of lines.slice(titleIndex + 1)) {
    const line = rawLine.trim()
    if (!line || line === subtitle) {
      flushParagraph()
      continue
    }
    if (line === '## 关键来源') {
      flushParagraph()
      inSources = true
      continue
    }
    if (inSources) {
      const link = line.match(/^- \[([^\]]+)]\((https?:\/\/[^)]+)\)$/)
      if (link) sources.push({ label: link[1], href: link[2] })
      continue
    }
    const image = line.match(/^!\[([^\]]*)]\(([^)]+)\)$/)
    if (image) {
      flushParagraph()
      blocks.push({ type: 'image', alt: image[1], src: `${base}${image[2].replace(/^\.\//, '')}` })
      continue
    }
    if (line.startsWith('### ')) {
      flushParagraph()
      blocks.push({ type: 'h3', text: line.slice(4) })
      continue
    }
    if (line.startsWith('## ')) {
      flushParagraph()
      blocks.push({ type: 'h2', text: line.slice(3) })
      continue
    }
    paragraph.push(line)
  }
  flushParagraph()
  flushSources()
  return { title, subtitle, blocks }
}

function Hero({ visible }: { visible: boolean }) {
  const reveal = visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
  return (
    <section className="relative flex h-screen w-full items-end justify-center overflow-hidden">
      <div
        className={`absolute inset-0 transition-all duration-[1400ms] ${visible ? 'scale-100 opacity-100' : 'scale-105 opacity-0'}`}
        style={{ transitionTimingFunction: entrance }}
      >
        <video
          src={`${base}hero-flower.mp4`}
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 h-full w-full object-cover"
        />
      </div>
      <div className="relative z-10 mx-auto max-w-4xl px-6 pb-16 text-center md:pb-24">
        <h1
          className={`font-instrument mb-5 text-[2.5rem] leading-[0.95] text-white transition-all duration-900 sm:text-5xl md:mb-6 md:text-6xl lg:text-7xl ${reveal}`}
          style={{ transitionDelay: visible ? '400ms' : '0ms', transitionTimingFunction: entrance }}
        >
          让真正值得读的<br className="hidden sm:block" /> 信号开花
        </h1>
        <p
          className={`mx-auto mb-8 max-w-md text-base text-white/70 transition-all duration-900 md:mb-10 md:text-lg ${reveal}`}
          style={{ transitionDelay: visible ? '600ms' : '0ms', transitionTimingFunction: entrance }}
        >
          SignalBloom 从信息筛选、事实核验走到双平台成稿。
        </p>
        <a
          href="#today"
          className={`inline-block rounded-full bg-white px-8 py-3.5 text-sm font-medium text-black transition-all duration-900 hover:bg-white/90 md:text-base ${reveal}`}
          style={{ transitionDelay: visible ? '800ms' : '0ms', transitionTimingFunction: entrance }}
        >
          查看本地内容
        </a>
      </div>
    </section>
  )
}

function TodayContent({ go, research }: { go: (view: View) => void; research: ResearchBundle | null }) {
  const [summary, setSummary] = useState<EditionSummary | null>(null)

  useEffect(() => {
    let active = true
    fetch(`${base}edition.json`)
      .then((response) => {
        if (!response.ok) throw new Error('Unable to load edition summary')
        return response.json() as Promise<EditionSummary>
      })
      .then((value) => {
        if (active && value.edition_date && value.articles?.wechat && value.articles?.woshipm) {
          setSummary(value)
        }
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  if (!summary && !research) {
    return (
      <section id="today" className="flex min-h-screen scroll-mt-20 items-center bg-[#f4f1e8] px-6 py-24 text-[#171717] md:px-10">
        <div className="mx-auto w-full max-w-5xl border-t border-black/15 pt-10">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">私有内容区</p>
          <h2 className="mt-6 max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">尚未生成本地编辑包</h2>
          <p className="mt-7 max-w-2xl text-base leading-8 text-black/55 md:text-lg">
            公开仓库只包含功能代码。运行 SignalBloom 后，文章、配图、证据包和质检结果会写入当前用户的本地 outputs 目录，不会上传到 Git。
          </p>
          <code className="mt-8 inline-block bg-black px-5 py-3 text-sm text-white">./scripts/run_today.sh</code>
        </div>
      </section>
    )
  }

  const metrics = (article: EditionArticle) =>
    `${article.chinese_characters} 个汉字 · ${article.source_count} 个关键来源 · ${article.image_count} 张配图`
  const editions = summary ? [
    {
      eyebrow: '微信公众号',
      title: summary.articles.wechat.title,
      metrics: metrics(summary.articles.wechat),
      view: 'story' as View,
      action: '查看公众号预览',
    },
    {
      eyebrow: '人人都是产品经理',
      title: summary.articles.woshipm.title,
      metrics: metrics(summary.articles.woshipm),
      view: 'collection' as View,
      action: '查看产品经理预览',
    },
  ] : []
  const editionDate = research?.edition_date ?? summary?.edition_date ?? ''
  const researchSources = research
    ? new Set(research.items.flatMap((item) => item.source_urls)).size
    : 0

  return (
    <section id="today" className="min-h-screen scroll-mt-20 bg-[#f4f1e8] px-6 py-24 text-[#171717] md:px-10 md:py-32">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-8 border-b border-black/15 pb-12 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.24em] text-black/45">{editionDate.replace(/-/g, '.')} · 本地内容工作台</p>
            <h2 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">先看本期发生了什么，再决定写什么</h2>
          </div>
          <p className="max-w-md text-base leading-8 text-black/55">SignalBloom 先交付去重、排序和核验后的资讯结果，两篇平台文章是这份研究包的下游产物。</p>
        </div>

        {research && (
          <article className="mt-10 grid gap-10 bg-black p-7 text-white md:grid-cols-[1fr_auto] md:items-end md:p-10">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-white/45">本期资讯 · {research.items.length} 条入选 · {researchSources} 个来源</p>
              <h3 className="mt-6 max-w-4xl text-3xl font-semibold leading-tight tracking-tight md:text-5xl">{displayDigestTitle(research.digest_title)}</h3>
              <p className="mt-6 max-w-4xl text-base leading-8 text-white/60">{research.executive_summary}</p>
            </div>
            <button
              type="button"
              onClick={() => go('news')}
              className="self-start rounded-full bg-white px-6 py-3 text-sm font-medium text-black transition hover:bg-white/90 md:self-end"
            >
              查看全部资讯与证据
            </button>
          </article>
        )}

        {summary && <p className="mb-5 mt-16 text-xs font-semibold uppercase tracking-[0.22em] text-black/40">平台内容输出</p>}
        <div className="grid gap-5 md:grid-cols-2">
          {editions.map((edition) => (
            <article key={edition.eyebrow} className="flex min-h-[360px] flex-col justify-between bg-black p-7 text-white md:p-10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-white/45">{edition.eyebrow}</p>
                <h3 className="mt-6 text-3xl font-semibold leading-tight tracking-tight md:text-4xl">{edition.title}</h3>
                <p className="mt-6 text-sm leading-7 text-white/50">{edition.metrics}</p>
              </div>
              <button
                type="button"
                onClick={() => go(edition.view)}
                className="mt-10 self-start rounded-full bg-white px-6 py-3 text-sm font-medium text-black transition hover:bg-white/90"
              >
                {edition.action}
              </button>
            </article>
          ))}
        </div>

        <div className="mt-20 border-t border-black/15 pt-10">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-black/40">本期处理链路</p>
          <p className="mt-5 text-xl font-medium leading-relaxed md:text-3xl">人工提供线索 → 去重与筛选 → 事实核验 → 平台选题 → Human Writing 长文 → 配图与预览</p>
        </div>
      </div>
    </section>
  )
}

function DailyNews({ state, go, onRetry }: { state: ResearchState; go: (view: View) => void; onRetry: () => void }) {
  if (state.status !== 'ready') {
    const copy = {
      loading: {
        eyebrow: '正在读取',
        title: '正在打开本地资讯包',
        body: '正在从当前审核目录读取 research_bundle.json。',
      },
      empty: {
        eyebrow: '私有内容区',
        title: '尚未生成本地资讯包',
        body: '运行 SignalBloom 后，本次搜索、去重和核验后的资讯会出现在这里。公开仓库不附带任何用户资讯。',
      },
      error: {
        eyebrow: '读取失败',
        title: '资讯包存在，但当前无法读取',
        body: '请检查 research_bundle.json 是否为完整 JSON，并通过本地 HTTP 服务打开 review.html。',
      },
    }[state.status]
    return (
      <main className="flex min-h-screen items-center bg-[#f4f1e8] px-6 py-28 text-[#171717] md:px-10">
        <div className="mx-auto w-full max-w-5xl border-t border-black/15 pt-10">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">{copy.eyebrow}</p>
          <h1 className="mt-6 max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">{copy.title}</h1>
          <p className="mt-7 max-w-2xl text-base leading-8 text-black/55 md:text-lg">{copy.body}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            {state.status === 'error' && <button type="button" onClick={onRetry} className="rounded-full bg-black px-6 py-3 text-sm font-medium text-white">重新读取</button>}
            {state.status !== 'loading' && <button type="button" onClick={() => go('home')} className="rounded-full border border-black/20 px-6 py-3 text-sm font-medium text-black">返回工作台</button>}
          </div>
        </div>
      </main>
    )
  }

  const bundle = state.data
  const items = [...bundle.items].sort((left, right) => left.rank - right.rank)
  const claims = items.flatMap((item) => item.claims)
  const sourceCount = new Set(items.flatMap((item) => item.source_urls)).size
  const supportedCount = claims.filter((claim) => claim.status === 'supported').length
  const metrics = [
    ['入选资讯', items.length],
    ['事实主张', claims.length],
    ['去重来源', sourceCount],
    ['已核实主张', supportedCount],
  ]

  return (
    <main className="min-h-screen bg-[#f4f1e8] px-6 pb-28 pt-28 text-[#171717] md:px-10 md:pt-36">
      <div className="mx-auto max-w-6xl">
        <header className="grid gap-10 border-b border-black/15 pb-14 lg:grid-cols-[0.7fr_1.3fr] lg:gap-20">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">{bundle.edition_date.replace(/-/g, '.')} · 本期资讯</p>
            <h1 className="mt-6 text-5xl font-semibold leading-[0.95] tracking-tight md:text-7xl">这期搜到了什么</h1>
          </div>
          <div className="lg:pt-9">
            <h2 className="text-2xl font-semibold leading-tight tracking-tight md:text-4xl">{displayDigestTitle(bundle.digest_title)}</h2>
            <p className="mt-6 text-base leading-8 text-black/60 md:text-lg">{bundle.executive_summary}</p>
          </div>
        </header>

        <section aria-label="资讯统计" className="grid grid-cols-2 border-b border-black/15 md:grid-cols-4">
          {metrics.map(([label, value]) => (
            <div key={label} className="border-black/15 py-7 odd:border-r md:border-r md:px-6 md:first:pl-0 md:last:border-r-0">
              <p className="font-instrument text-4xl md:text-5xl">{value}</p>
              <p className="mt-2 text-xs font-semibold uppercase tracking-[0.18em] text-black/40">{label}</p>
            </div>
          ))}
        </section>

        <div className="flex flex-col gap-5 pb-8 pt-16 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-black/40">按编辑优先级排序</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight md:text-5xl">{items.length} 条值得今天关注的信号</h2>
          </div>
          <p className="max-w-md text-sm leading-7 text-black/50">产品影响和风险边界始终展开，事实主张与原始来源可按需查看。</p>
        </div>

        <ol className="list-none">
          {items.map((item) => {
            const verification = itemStatus(item)
            return (
              <li key={`${item.rank}-${item.title}`} className="border-t border-black/15 py-10 md:py-14">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-baseline gap-4">
                    <span className="font-instrument text-4xl text-black/35">{String(item.rank).padStart(2, '0')}</span>
                    <time className="text-xs font-semibold uppercase tracking-[0.18em] text-black/40" dateTime={item.event_time}>{formatEventTime(item.event_time)}</time>
                  </div>
                  <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${claimStyles[verification]}`}>{claimLabels[verification]}</span>
                </div>

                <div className="mt-7 grid gap-8 md:grid-cols-[1.45fr_0.85fr] md:gap-12">
                  <div>
                    <h3 className="text-3xl font-semibold leading-tight tracking-tight md:text-5xl">{item.title}</h3>
                    <p className="mt-6 text-base leading-8 text-black/65 md:text-lg">{item.summary}</p>
                  </div>
                  <div className="grid gap-4">
                    <section className="bg-black p-6 text-white">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/40">产品判断</p>
                      <p className="mt-4 text-sm leading-7 text-white/75">{item.why_it_matters}</p>
                    </section>
                    <section className="border border-[#b66a57]/25 bg-[#efe2dc] p-6">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7b3025]/60">边界与风险</p>
                      <p className="mt-4 text-sm leading-7 text-[#5f3028]">{item.risk_note}</p>
                    </section>
                  </div>
                </div>

                <details className="group mt-8 border-t border-black/15 pt-5">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-semibold text-black/65">
                    <span>来源与事实核验 · {item.claims.length} 条主张 · {item.source_urls.length} 个来源</span>
                    <span aria-hidden="true" className="text-xl font-normal transition group-open:rotate-45">+</span>
                  </summary>
                  <div className="mt-7 grid gap-10 md:grid-cols-[1.4fr_0.6fr]">
                    <div className="grid gap-4">
                      {item.claims.map((claim, index) => (
                        <article key={`${claim.text}-${index}`} className="border-l border-black/20 pl-5">
                          <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-semibold ${claimStyles[claim.status]}`}>{claimLabels[claim.status]}</span>
                          <p className="mt-3 text-sm leading-7 text-black/70">{claim.text}</p>
                          {claim.evidence_urls.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
                              {claim.evidence_urls.map((url, evidenceIndex) => (
                                <a key={`${url}-${evidenceIndex}`} href={url} target="_blank" rel="noreferrer" className="text-xs text-black/45 underline underline-offset-4">证据 {evidenceIndex + 1}</a>
                              ))}
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/40">原始来源</p>
                      <ul className="mt-4 grid gap-3">
                        {item.source_urls.map((url, index) => (
                          <li key={`${url}-${index}`}><a href={url} target="_blank" rel="noreferrer" className="break-all text-sm leading-6 text-black/60 underline underline-offset-4">{sourceHost(url)}</a></li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </details>
              </li>
            )
          })}
        </ol>

        {(bundle.reference_materials.length > 0 || bundle.topics.length > 0) && (
          <section className="grid gap-5 border-t border-black/15 pt-12 md:grid-cols-2">
            {bundle.reference_materials.length > 0 && (
              <details className="bg-white p-6 md:p-8">
                <summary className="cursor-pointer text-lg font-semibold">补充研究材料 · {bundle.reference_materials.length}</summary>
                <ul className="mt-6 grid gap-5">
                  {bundle.reference_materials.map((material) => (
                    <li key={material.url}>
                      <a href={material.url} target="_blank" rel="noreferrer" className="font-semibold underline underline-offset-4">{material.title}</a>
                      <p className="mt-2 text-sm leading-7 text-black/55">{material.purpose}</p>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {bundle.topics.length > 0 && (
              <details className="bg-black p-6 text-white md:p-8">
                <summary className="cursor-pointer text-lg font-semibold">基于这些资讯生成的选题 · {bundle.topics.length}</summary>
                <div className="mt-6 grid gap-7">
                  {bundle.topics.map((topic) => (
                    <article key={topic.platform}>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/40">{topic.platform === 'wechat' ? '微信公众号' : '人人都是产品经理'}</p>
                      <h3 className="mt-2 text-xl font-semibold">{topic.title}</h3>
                      <p className="mt-3 text-sm leading-7 text-white/60">{topic.angle}</p>
                      <p className="mt-2 text-sm leading-7 text-white/60">读者决策：{topic.audience_decision}</p>
                      <p className="mt-2 text-sm leading-7 text-white/60">新增价值：{topic.new_value}</p>
                    </article>
                  ))}
                </div>
              </details>
            )}
          </section>
        )}

        <section className="mt-16 flex flex-col justify-between gap-6 border-t border-black/15 pt-10 md:flex-row md:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/40">下游内容</p>
            <p className="mt-3 text-xl font-semibold">这份资讯包已分别转化为两个平台选题。</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => go('story')} className="rounded-full bg-black px-6 py-3 text-sm font-medium text-white">公众号预览</button>
            <button type="button" onClick={() => go('collection')} className="rounded-full border border-black/20 px-6 py-3 text-sm font-medium text-black">产品经理文章</button>
          </div>
        </section>
      </div>
    </main>
  )
}

function ArticlePreview({ platform, source, onHome }: { platform: string; source: string; onHome: () => void }) {
  const [article, setArticle] = useState<Article | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle')
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setArticle(null)
    setLoadError(false)
    fetch(`${base}articles/${source}`)
      .then((response) => {
        if (!response.ok) throw new Error(`Unable to load ${source}`)
        return response.text()
      })
      .then((text) => setArticle(parseArticle(text)))
      .catch(() => setLoadError(true))
  }, [source])

  const copyArticle = async () => {
    if (!bodyRef.current) return
    const sourceRoot = bodyRef.current
    const cloneRoot = sourceRoot.cloneNode(true) as HTMLElement
    const sourceNodes = [sourceRoot, ...sourceRoot.querySelectorAll<HTMLElement>('*')]
    const cloneNodes = [cloneRoot, ...cloneRoot.querySelectorAll<HTMLElement>('*')]
    const portableProperties = [
      'color', 'font-family', 'font-size', 'font-style', 'font-weight', 'letter-spacing',
      'line-height', 'list-style-type', 'margin', 'text-align', 'text-decoration',
      'text-underline-offset',
    ]

    sourceNodes.forEach((node, index) => {
      const computed = window.getComputedStyle(node)
      portableProperties.forEach((property) => {
        cloneNodes[index].style.setProperty(property, computed.getPropertyValue(property))
      })
    })
    cloneRoot.querySelector('header > p')?.remove()
    cloneRoot.querySelectorAll('figure').forEach((figure, index) => {
      const placeholder = document.createElement('p')
      const alt = figure.querySelector('img')?.alt || '文章配图'
      placeholder.textContent = `【配图 ${index + 1}｜${alt}，请按网页预览位置上传本地图片】`
      placeholder.style.cssText = 'color:#666;font-size:14px;line-height:1.8;margin:32px 0;text-align:center;'
      figure.replaceWith(placeholder)
    })

    const html = cloneRoot.innerHTML
    const text = [...cloneRoot.querySelectorAll('h1, h2, h3, p, li')]
      .map((node) => node.textContent?.trim() || '')
      .filter(Boolean)
      .join('\n\n')
    try {
      if ('ClipboardItem' in window && navigator.clipboard?.write) {
        await navigator.clipboard.write([
          new ClipboardItem({
            'text/html': new Blob([html], { type: 'text/html' }),
            'text/plain': new Blob([text], { type: 'text/plain' }),
          }),
        ])
      } else {
        await navigator.clipboard.writeText(text)
      }
      setCopyStatus('copied')
    } catch {
      setCopyStatus('failed')
    }
    window.setTimeout(() => setCopyStatus('idle'), 1800)
  }

  if (loadError) {
    return (
      <main className="min-h-screen bg-black pt-28 text-center text-white/60">
        <p>当前没有本地文章。公开仓库不附带任何用户生成内容。</p>
        <button type="button" onClick={onHome} className="mt-5 rounded-full border border-white/20 px-5 py-2 text-sm text-white">返回工作台</button>
      </main>
    )
  }
  if (!article) return <main className="min-h-screen bg-black pt-28 text-center text-white/60">Loading</main>

  return (
    <main className="min-h-screen bg-black px-4 pb-24 pt-28 md:px-8 md:pt-36">
      <div className="mx-auto mb-8 flex max-w-[820px] flex-col gap-4 text-white sm:flex-row sm:items-center sm:justify-between">
        <div>
          <span className="text-xs uppercase tracking-[0.24em] text-white/50">{platform}</span>
          <p className="mt-1 text-xs text-white/40">配图已在网页就位，复制后请按占位提示上传本地图片</p>
        </div>
        <button
          type="button"
          onClick={copyArticle}
          className="self-start rounded-full border border-white/20 px-5 py-2 text-sm text-white/90 transition hover:bg-white/10 sm:self-auto"
        >
          {copyStatus === 'copied' ? '已复制' : copyStatus === 'failed' ? '请手动选中复制' : '复制排版正文'}
        </button>
      </div>
      <article ref={bodyRef} className="article-sheet mx-auto max-w-[820px] bg-[#f4f1e8] px-6 py-12 text-[#171717] sm:px-10 md:px-16 md:py-20">
        <header className="mb-12 border-b border-black/15 pb-10">
          <p className="mb-5 text-xs uppercase tracking-[0.22em] text-black/45">SignalBloom · 编辑预览</p>
          <h1 className="text-3xl font-semibold leading-tight tracking-tight md:text-5xl">{article.title}</h1>
          <p className="mt-5 text-base leading-8 text-black/60 md:text-lg">{article.subtitle}</p>
        </header>
        <div className="article-copy">
          {article.blocks.map((block, index) => {
            if (block.type === 'h2') return <h2 key={index}>{block.text}</h2>
            if (block.type === 'h3') return <h3 key={index}>{block.text}</h3>
            if (block.type === 'p') return <p key={index}>{block.text}</p>
            if (block.type === 'image') {
              return (
                <figure key={index}>
                  <img src={block.src} alt={block.alt} />
                  <figcaption>{block.alt}</figcaption>
                </figure>
              )
            }
            return (
              <section key={index} className="sources">
                <h2>关键来源</h2>
                <ul>
                  {block.items.map((item) => (
                    <li key={item.href}><a href={item.href} target="_blank" rel="noreferrer">{item.label}</a></li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      </article>
    </main>
  )
}

function ReviewSummary({ go }: { go: (view: View) => void }) {
  return (
    <main className="flex min-h-screen items-center bg-black px-6 pb-16 pt-28 text-white md:px-10 md:pt-36">
      <div className="mx-auto w-full max-w-5xl">
        <p className="mb-6 text-xs uppercase tracking-[0.26em] text-white/45">投稿前质量门</p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight md:text-7xl">事实、来源、字数与图片，全部在发布前停下来检查。</h1>
        <p className="mt-8 max-w-2xl text-base leading-8 text-white/55 md:text-lg">每次运行的具体质检结果只保存在当前用户的本地编辑包中，公开代码仓库不保存稿件、配图、证据包或运行日志。</p>
        <div className="mt-12 flex flex-wrap gap-3">
          <button onClick={() => go('story')} className="rounded-full bg-white px-7 py-3 text-sm font-medium text-black">公众号预览</button>
          <button onClick={() => go('collection')} className="rounded-full border border-white/20 px-7 py-3 text-sm font-medium text-white">产品经理文章预览</button>
        </div>
      </div>
    </main>
  )
}

export default function App() {
  const [mounted, setMounted] = useState(false)
  const [heroVisible, setHeroVisible] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [view, setView] = useState<View>('home')
  const [researchState, setResearchState] = useState<ResearchState>({ status: 'loading' })
  const [researchRequest, setResearchRequest] = useState(0)
  const [archive, setArchive] = useState<ArchiveIndex | null>(null)

  useEffect(() => {
    const mountTimer = window.setTimeout(() => setMounted(true), 100)
    const heroTimer = window.setTimeout(() => setHeroVisible(true), 300)
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll)
    return () => {
      window.clearTimeout(mountTimer)
      window.clearTimeout(heroTimer)
      window.removeEventListener('scroll', onScroll)
    }
  }, [])

  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [menuOpen])

  useEffect(() => {
    let active = true
    setResearchState({ status: 'loading' })
    fetch(`${base}research_bundle.json`)
      .then(async (response) => {
        if (response.status === 404 || !response.headers.get('content-type')?.includes('json')) {
          if (active) setResearchState({ status: 'empty' })
          return
        }
        if (!response.ok) throw new Error('Unable to load research bundle')
        const value: unknown = await response.json()
        if (!isResearchBundle(value)) throw new Error('Invalid research bundle')
        if (active) setResearchState({ status: 'ready', data: value })
      })
      .catch(() => {
        if (active) setResearchState({ status: 'error' })
      })
    return () => { active = false }
  }, [researchRequest])

  useEffect(() => {
    let active = true
    fetch(new URL('../archive.json', window.location.href), { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error('Unable to load archive index')
        return response.json() as Promise<unknown>
      })
      .then((value) => {
        if (active && isArchiveIndex(value)) setArchive(value)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  const navigate = (next: View) => {
    setMenuOpen(false)
    setView(next)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  const navItems: Array<{ label: string; view: View }> = [
    { label: '内容工作台', view: 'home' },
    { label: '本期资讯', view: 'news' },
    { label: '公众号预览', view: 'story' },
    { label: '产品经理预览', view: 'collection' },
    { label: '质量门说明', view: 'inquire' },
  ]
  const pathEdition = window.location.pathname.match(/\/(\d{4}-\d{2}-\d{2})\//)?.[1] ?? ''
  const currentEdition = researchState.status === 'ready'
    ? researchState.data.edition_date
    : pathEdition
  const openEdition = (edition: string) => {
    if (!archive?.editions.includes(edition) || edition === currentEdition) return
    window.location.assign(new URL(`../${edition}/review.html`, window.location.href))
  }
  const enter = mounted ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'

  return (
    <div className="min-h-screen bg-black">
      <nav className={`fixed left-0 top-0 z-50 w-full transition-all duration-500 ${scrolled || view !== 'home' ? 'bg-black/90 backdrop-blur-md' : 'bg-transparent'}`}>
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-6 md:h-20 md:px-10">
          <a href="#" onClick={(event) => { event.preventDefault(); navigate('home') }} className={`z-50 text-xl font-semibold tracking-tight text-white transition-all duration-700 md:text-2xl ${enter}`} style={{ transitionTimingFunction: entrance }}>SignalBloom</a>
          <div className={`hidden items-center gap-3 transition-all duration-700 md:flex ${enter}`} style={{ transitionDelay: mounted ? '200ms' : '0ms', transitionTimingFunction: entrance }}>
            <button
              type="button"
              onClick={() => setMenuOpen((value) => !value)}
              className="rounded-full border border-white/20 px-5 py-2 text-sm text-white/90 transition hover:bg-white/10"
            >
              {menuOpen ? '关闭' : '查看内容'}
            </button>
            <ArchivePicker editions={archive?.editions ?? []} current={currentEdition} onChange={openEdition} />
          </div>
          <Flower2 aria-label="SignalBloom" className={`z-50 hidden h-8 w-8 text-white transition-all duration-700 md:block ${enter}`} strokeWidth={1.6} style={{ transitionDelay: mounted ? '400ms' : '0ms', transitionTimingFunction: entrance }} />
          <button
            type="button"
            aria-label="Toggle menu"
            onClick={() => setMenuOpen((value) => !value)}
            className={`z-50 flex h-8 w-8 flex-col items-center justify-center gap-1.5 transition-all duration-700 md:hidden ${enter}`}
            style={{ transitionDelay: mounted ? '200ms' : '0ms', transitionTimingFunction: entrance }}
          >
            <span className={`h-[2px] w-6 bg-white transition-transform duration-500 ${menuOpen ? 'translate-y-[4px] rotate-45' : ''}`} style={{ transitionTimingFunction: overlayEase }} />
            <span className={`h-[2px] w-6 bg-white transition-transform duration-500 ${menuOpen ? '-translate-y-[4px] -rotate-45' : ''}`} style={{ transitionTimingFunction: overlayEase }} />
          </button>
        </div>
      </nav>

      <div className={`fixed inset-0 z-40 flex flex-col items-center justify-center bg-black transition-all duration-700 ${menuOpen ? 'visible opacity-100' : 'invisible opacity-0'}`} style={{ transitionTimingFunction: overlayEase }}>
        <div className="flex flex-col items-center gap-8 text-center">
          {navItems.map((item, index) => (
            <a
              key={item.label}
              href="#"
              onClick={(event) => { event.preventDefault(); navigate(item.view) }}
              className={`font-instrument text-4xl text-white transition-all duration-[600ms] hover:opacity-60 md:text-6xl ${menuOpen ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`}
              style={{ transitionDelay: menuOpen ? `${150 + index * 80}ms` : '0ms', transitionTimingFunction: overlayEase }}
            >
              {item.label}
            </a>
          ))}
          {archive && archive.editions.length > 0 && (
            <div className={`mt-4 transition-all duration-[600ms] ${menuOpen ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`} style={{ transitionDelay: menuOpen ? `${150 + navItems.length * 80}ms` : '0ms', transitionTimingFunction: overlayEase }}>
              <ArchivePicker editions={archive.editions} current={currentEdition} onChange={openEdition} />
            </div>
          )}
        </div>
      </div>

      {view === 'home' && <><Hero visible={heroVisible} /><TodayContent go={navigate} research={researchState.status === 'ready' ? researchState.data : null} /></>}
      {view === 'news' && <DailyNews state={researchState} go={navigate} onRetry={() => setResearchRequest((value) => value + 1)} />}
      {view === 'story' && <ArticlePreview platform="微信公众号预览" source="wechat.md" onHome={() => navigate('home')} />}
      {view === 'collection' && <ArticlePreview platform="人人都是产品经理预览" source="woshipm.md" onHome={() => navigate('home')} />}
      {view === 'inquire' && <ReviewSummary go={navigate} />}
    </div>
  )
}
