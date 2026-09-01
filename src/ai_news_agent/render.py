from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import urlsplit


def render_digest(bundle: dict) -> str:
    lines = [
        f"# {bundle['digest_title']}",
        "",
        f"日期 {bundle['edition_date']}",
        "",
        bundle["executive_summary"],
        "",
    ]
    for item in bundle.get("items", []):
        lines.extend(
            [
                f"## {item['rank']}. {item['title']}",
                "",
                f"发生时间 {item['event_time']}",
                "",
                item["summary"],
                "",
                f"产品影响 {item['why_it_matters']}",
                "",
                f"风险边界 {item['risk_note']}",
                "",
                "事实核验",
                "",
            ]
        )
        for claim in item.get("claims", []):
            links = "、".join(claim.get("evidence_urls", [])) or "无"
            lines.append(f"- [{claim['status']}] {claim['text']} 证据 {links}")
        lines.extend(["", "关键来源", ""])
        lines.extend(f"- {url}" for url in item.get("source_urls", []))
        lines.append("")
    if bundle.get("reference_materials"):
        lines.extend(["## 补充参考材料", ""])
        for material in bundle["reference_materials"]:
            lines.append(
                f"- [{material['status']}] {material['title']}  {material['purpose']}  {material['url']}"
            )
        lines.append("")
    lines.extend(["## 今日平台选题", ""])
    for topic in bundle.get("topics", []):
        lines.extend(
            [
                f"### {topic['platform']}  {topic['title']}",
                "",
                topic["angle"],
                "",
                f"读者要做的决定 {topic['audience_decision']}",
                "",
                f"本稿新增价值 {topic['new_value']}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_article(article: dict) -> str:
    if article.get("status") == "blocked":
        reason = article.get("blocking_reason") or "当前阶段未生成可审核正文。"
        missing = article.get("missing_evidence") or []
        lines = ["# 本轮稿件未生成", "", "当前稿件被质量门阻塞，禁止发布。", "", f"阻塞原因 {reason}"]
        if missing:
            lines.extend(["", "需要补充", ""])
            lines.extend(f"- {item}" for item in missing)
        return "\n".join(lines).strip() + "\n"
    lines = [f"# {article['title']}", ""]
    if article.get("subtitle"):
        lines.extend([article["subtitle"], ""])
    lines.extend([article["body_markdown"].strip(), "", "## 编辑交接", ""])
    lines.extend(
        [
            f"摘要 {article['summary']}",
            "",
            f"AI 内容标识提醒 {article['ai_disclosure_note']}",
            "",
        ]
    )
    for note in article.get("editor_notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines).strip() + "\n"


def _safe_link(url: str) -> str:
    escaped = html.escape(url)
    parts = urlsplit(url)
    if parts.scheme in {"http", "https"} and parts.netloc:
        return f'<a href="{escaped}" target="_blank" rel="noreferrer">{escaped}</a>'
    return f"<code>{escaped}</code>"


def _article_panel(title: str, article: dict, qa: dict) -> str:
    body = html.escape(str(article.get("body_markdown") or "当前没有可审核正文。"))
    sources = "".join(f"<li>{_safe_link(url)}</li>" for url in article.get("source_urls", []))
    return f"""
    <section class="panel">
      <div class="eyebrow">{html.escape(title)}</div>
      <h2>{html.escape(str(article.get('title') or '本轮稿件未生成'))}</h2>
      <p class="subtitle">{html.escape(str(article.get('subtitle') or ''))}</p>
      <pre class="article">{body}</pre>
      <h3>关键来源</h3><ul>{sources}</ul>
      <h3>机器质检</h3><pre>{html.escape(json.dumps(qa, ensure_ascii=False, indent=2))}</pre>
    </section>
    """


def render_review_html(bundle: dict, articles: dict[str, dict], qa: dict) -> str:
    rows: list[str] = []
    for item in bundle.get("items", []):
        claims = "".join(
            "<li><strong>"
            + html.escape(claim.get("status", ""))
            + "</strong> "
            + html.escape(claim.get("text", ""))
            + "<br>"
            + " · ".join(_safe_link(url) for url in claim.get("evidence_urls", []))
            + "</li>"
            for claim in item.get("claims", [])
        )
        sources = " · ".join(_safe_link(url) for url in item.get("source_urls", []))
        rows.append(
            f"<tr><td>{item['rank']}</td><td><strong>{html.escape(item['title'])}</strong>"
            f"<p>{html.escape(item['summary'])}</p><small>{sources}</small></td>"
            f"<td>{html.escape(item['why_it_matters'])}<p class='risk'>风险边界 {html.escape(item['risk_note'])}</p></td>"
            f"<td><ul>{claims}</ul></td></tr>"
        )
    item_rows = "".join(rows)
    topics = "".join(
        f"<article><h3>{html.escape(topic['platform'])} · {html.escape(topic['title'])}</h3>"
        f"<p>{html.escape(topic['angle'])}</p><p><strong>读者决策</strong> {html.escape(topic['audience_decision'])}</p>"
        f"<p><strong>新增价值</strong> {html.escape(topic['new_value'])}</p></article>"
        for topic in bundle.get("topics", [])
    )
    status = "通过机器硬检查" if qa.get("passed") else "存在硬错误，不能直接发布"
    status_class = "pass" if qa.get("passed") else "fail"
    panels = _article_panel("微信公众号", articles["wechat"], qa["articles"]["wechat"])
    panels += _article_panel("人人都是产品经理", articles["woshipm"], qa["articles"]["woshipm"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(bundle['digest_title'])} 验收页</title>
  <style>
    :root {{ color-scheme: light; --ink:#17212b; --muted:#667085; --line:#d9e0e7; --paper:#fff; --bg:#f3f6f8; --brand:#126b5d; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; }}
    main {{ max-width:1180px; margin:0 auto; padding:40px 24px 80px; }}
    header {{ background:#102c2a; color:white; padding:32px; border-radius:18px; box-shadow:0 12px 32px #102c2a20; }}
    header h1 {{ margin:4px 0 8px; font-size:34px; }}
    .eyebrow {{ color:#61b9aa; font-size:12px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
    .status {{ display:inline-block; margin-top:16px; padding:7px 12px; border-radius:999px; font-weight:700; }}
    .status.pass {{ background:#d7f4e8; color:#126b5d; }} .status.fail {{ background:#ffe0e0; color:#9d2424; }}
    .panel {{ margin-top:24px; padding:28px; background:var(--paper); border:1px solid var(--line); border-radius:16px; }}
    h2 {{ margin:4px 0 6px; font-size:27px; }} h3 {{ margin-top:28px; }} .subtitle {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:12px; text-align:left; vertical-align:top; border-bottom:1px solid var(--line); }}
    pre {{ white-space:pre-wrap; word-break:break-word; background:#f7f8fa; border:1px solid var(--line); border-radius:10px; padding:16px; overflow:auto; }}
    .article {{ background:white; font:16px/1.9 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; }}
    .risk {{ color:#9d3a24; }} small {{ color:var(--muted); }} td ul {{ margin:0; padding-left:20px; }}
    a {{ color:var(--brand); }}
  </style>
</head>
<body><main>
  <header><div class="eyebrow">AI NEWS AGENT · {html.escape(bundle['edition_date'])}</div><h1>{html.escape(bundle['digest_title'])}</h1><p>{html.escape(bundle['executive_summary'])}</p><span class="status {status_class}">{status}</span></header>
  <section class="panel"><div class="eyebrow">每日总览</div><h2>入选资讯、风险与证据</h2><table><thead><tr><th>#</th><th>事件与来源</th><th>产品影响与边界</th><th>逐条事实</th></tr></thead><tbody>{item_rows}</tbody></table></section>
  <section class="panel"><div class="eyebrow">平台差异</div><h2>两个独立选题</h2>{topics}</section>
  {panels}
  <section class="panel"><div class="eyebrow">人工终审</div><h2>发布前必须完成</h2><ol>{''.join(f'<li>{html.escape(item)}</li>' for item in qa['manual_review_required'])}</ol></section>
</main></body></html>"""


def write_json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
