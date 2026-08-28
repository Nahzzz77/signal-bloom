import { Flower2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type View = 'home' | 'story' | 'collection' | 'inquire'
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

const entrance = 'cubic-bezier(0.16, 1, 0.3, 1)'
const overlayEase = 'cubic-bezier(0.76, 0, 0.24, 1)'
const base = import.meta.env.BASE_URL

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

function TodayContent({ go }: { go: (view: View) => void }) {
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

  if (!summary) {
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
  const editions = [
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
  ]

  return (
    <section id="today" className="min-h-screen scroll-mt-20 bg-[#f4f1e8] px-6 py-24 text-[#171717] md:px-10 md:py-32">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-8 border-b border-black/15 pb-12 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.24em] text-black/45">{summary.edition_date.replace(/-/g, '.')} · 今日编辑包</p>
            <h2 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">从线索到成稿，本次内容已经整理完毕</h2>
          </div>
          <p className="max-w-md text-base leading-8 text-black/55">两篇长文均超过六千汉字，五张配图已放入对应段落，不含无法直接发布的 Markdown 表格。</p>
        </div>

        <div className="mt-10 grid gap-5 md:grid-cols-2">
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
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-black/40">今日处理链路</p>
          <p className="mt-5 text-xl font-medium leading-relaxed md:text-3xl">人工提供线索 → 去重与筛选 → 事实核验 → 平台选题 → Human Writing 长文 → 配图与预览</p>
        </div>
      </div>
    </section>
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

  const navigate = (next: View) => {
    setMenuOpen(false)
    setView(next)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  const navItems: Array<{ label: string; view: View }> = [
    { label: '内容工作台', view: 'home' },
    { label: '公众号预览', view: 'story' },
    { label: '产品经理预览', view: 'collection' },
    { label: '质量门说明', view: 'inquire' },
  ]
  const enter = mounted ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'

  return (
    <div className="min-h-screen bg-black">
      <nav className={`fixed left-0 top-0 z-50 w-full transition-all duration-500 ${scrolled ? 'bg-black/80 backdrop-blur-md' : 'bg-transparent'}`}>
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-6 md:h-20 md:px-10">
          <a href="#" onClick={(event) => { event.preventDefault(); navigate('home') }} className={`z-50 text-xl font-semibold tracking-tight text-white transition-all duration-700 md:text-2xl ${enter}`} style={{ transitionTimingFunction: entrance }}>SignalBloom</a>
          <button
            type="button"
            onClick={() => setMenuOpen((value) => !value)}
            className={`hidden items-center gap-2 rounded-full border border-white/20 px-5 py-2 text-sm text-white/90 transition-all duration-700 hover:bg-white/10 md:flex ${enter}`}
            style={{ transitionDelay: mounted ? '200ms' : '0ms', transitionTimingFunction: entrance }}
          >
            {menuOpen ? '关闭' : '查看内容'}
          </button>
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
        </div>
      </div>

      {view === 'home' && <><Hero visible={heroVisible} /><TodayContent go={navigate} /></>}
      {view === 'story' && <ArticlePreview platform="微信公众号预览" source="wechat.md" onHome={() => navigate('home')} />}
      {view === 'collection' && <ArticlePreview platform="人人都是产品经理预览" source="woshipm.md" onHome={() => navigate('home')} />}
      {view === 'inquire' && <ReviewSummary go={navigate} />}
    </div>
  )
}
