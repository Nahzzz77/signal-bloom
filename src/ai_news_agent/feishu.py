from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import fcntl


API_BASE = "https://open.feishu.cn/open-apis"
MAX_POST_BYTES = 50_000
MAX_REQUEST_ATTEMPTS = 3
STATUS_LABELS = {
    "supported": "已核实",
    "partial": "部分支持",
    "conflicting": "存在冲突",
    "unverified": "未核实",
}


class FeishuError(RuntimeError):
    pass


def _request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    query: dict | None = None,
) -> dict:
    url = f"{API_BASE}{path}"
    if query:
        url += "?" + urlencode(query)
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, headers=headers, method=method)
    for attempt in range(MAX_REQUEST_ATTEMPTS):
        try:
            with urlopen(request, timeout=20) as response:
                value = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            retryable = exc.code == 408 or exc.code == 425 or exc.code == 429 or exc.code >= 500
            if retryable and attempt < MAX_REQUEST_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            try:
                value = json.loads(exc.read().decode("utf-8"))
                detail = f"{value.get('code', exc.code)}: {value.get('msg', exc.reason)}"
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = f"HTTP {exc.code}: {exc.reason}"
            raise FeishuError(f"飞书 API 请求失败（{detail}）") from None
        except URLError as exc:
            if attempt < MAX_REQUEST_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            raise FeishuError(f"无法连接飞书 API（{exc.reason}）") from None
        except json.JSONDecodeError:
            raise FeishuError("飞书 API 返回了无法解析的响应") from None
    else:  # pragma: no cover - the loop either breaks or raises above.
        raise FeishuError("飞书 API 请求未完成")
    if not isinstance(value, dict):
        raise FeishuError("飞书 API 返回格式不正确")
    if value.get("code", 0) != 0:
        raise FeishuError(f"飞书 API {value.get('code')}: {value.get('msg', '未知错误')}")
    return value


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    value = _request_json(
        "POST",
        "/auth/v3/tenant_access_token/internal",
        payload={"app_id": app_id, "app_secret": app_secret},
    )
    token = value.get("tenant_access_token")
    if not token:
        raise FeishuError("飞书未返回 tenant_access_token")
    return str(token)


def list_chats(token: str) -> list[dict]:
    chats: list[dict] = []
    page_token = ""
    while True:
        query = {"page_size": 100}
        if page_token:
            query["page_token"] = page_token
        data = _request_json("GET", "/im/v1/chats", token=token, query=query).get("data", {})
        chats.extend(data.get("items", []))
        if not data.get("has_more"):
            return chats
        page_token = str(data.get("page_token", ""))
        if not page_token:
            raise FeishuError("飞书群列表声明还有下一页，但没有返回 page_token")


def find_chat_id(chats: list[dict], chat_name: str) -> str:
    matches = [str(chat.get("chat_id")) for chat in chats if chat.get("name") == chat_name]
    if not matches:
        raise FeishuError(f"机器人所在群里没有找到「{chat_name}」")
    if len(matches) > 1:
        raise FeishuError(f"机器人所在群里有 {len(matches)} 个同名的「{chat_name}」，请先将群改为唯一名称")
    return matches[0]


def _status_text(claims: list[dict]) -> str:
    counts = Counter(claim.get("status", "unverified") for claim in claims)
    return " · ".join(
        f"{label} {counts[status]}" for status, label in STATUS_LABELS.items() if counts[status]
    )


def _source_row(urls: list[str]) -> list[dict]:
    row: list[dict] = [{"tag": "text", "text": "来源  "}]
    for index, url in enumerate(urls, start=1):
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise FeishuError(f"资讯包含有非法来源链接：{url}")
        if index > 1:
            row.append({"tag": "text", "text": "  ·  "})
        row.append({"tag": "a", "text": f"来源 {index}", "href": url})
    return row


def build_post(bundle: dict) -> dict:
    items = bundle.get("items")
    if not isinstance(items, list) or not items:
        raise FeishuError("资讯包没有可同步的条目")
    all_claims = [claim for item in items for claim in item.get("claims", [])]
    content: list[list[dict]] = [
        [{"tag": "text", "text": str(bundle.get("executive_summary", ""))}],
        [
            {
                "tag": "text",
                "text": f"共 {len(items)} 条资讯｜{_status_text(all_claims) or '暂无核验状态'}",
            }
        ],
    ]
    for item in sorted(items, key=lambda value: value.get("rank", 0)):
        claims = item.get("claims", [])
        content.extend(
            [
                [
                    {
                        "tag": "text",
                        "text": f"\n{item.get('rank', '')}. {item.get('title', '')}",
                        "style": ["bold"],
                    }
                ],
                [
                    {
                        "tag": "text",
                        "text": f"{item.get('event_time', '')}  ·  {_status_text(claims) or '未标注核验状态'}",
                    }
                ],
                [{"tag": "text", "text": str(item.get("summary", ""))}],
                [{"tag": "text", "text": f"产品判断  {item.get('why_it_matters', '')}"}],
                [{"tag": "text", "text": f"边界与风险  {item.get('risk_note', '')}"}],
                _source_row(item.get("source_urls", [])),
            ]
        )
    return {
        "zh_cn": {
            "title": f"SignalBloom 今日 AI 资讯 · {bundle.get('edition_date', '')}",
            "content": content,
        }
    }


def send_post(token: str, chat_id: str, post: dict, delivery_uuid: str) -> dict:
    value = _request_json(
        "POST",
        "/im/v1/messages",
        token=token,
        query={"receive_id_type": "chat_id"},
        payload={
            "receive_id": chat_id,
            "msg_type": "post",
            "content": json.dumps(post, ensure_ascii=False, separators=(",", ":")),
            "uuid": delivery_uuid,
        },
    )
    return value.get("data", {})


def _decode_json(path: Path, raw: bytes) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeishuError(f"{path.name} 不是有效 JSON（第 {exc.lineno} 行）") from None
    if not isinstance(value, dict):
        raise FeishuError(f"{path.name} 顶层必须是 JSON 对象")
    return value


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise FeishuError(f"缺少本地文件：{path.name}")
    return _decode_json(path, path.read_bytes())


def _write_receipt(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def _delivery_lock(output_dir: Path):
    """Serialize all non-dry-run delivery attempts for one edition."""
    lock_path = output_dir / ".feishu_delivery.lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sync_output(
    output_dir: Path,
    *,
    app_id: str,
    app_secret: str,
    chat_name: str,
    dry_run: bool = False,
) -> dict:
    output_dir = output_dir.resolve()
    bundle_path = output_dir / "research_bundle.json"
    if not bundle_path.is_file():
        raise FeishuError("缺少本地文件：research_bundle.json")
    bundle_bytes = bundle_path.read_bytes()
    bundle = _decode_json(bundle_path, bundle_bytes)
    qa_path = output_dir / "qa_report.json"
    qa_bytes = qa_path.read_bytes() if qa_path.is_file() else b""
    qa = _decode_json(qa_path, qa_bytes) if qa_bytes else _load_json(qa_path)
    research_errors = qa.get("research", {}).get("errors")
    if not isinstance(research_errors, list):
        raise FeishuError("qa_report.json 缺少 research.errors 校验结果")
    if research_errors:
        raise FeishuError(f"资讯研究仍有 {len(research_errors)} 个硬错误，拒绝同步到飞书")
    # Feishu receives the research digest only.  Article and Human Writing
    # errors are kept in the QA report for the local editorial workflow, but
    # they must not block delivery of an otherwise verified news bundle.
    bundle_hash = hashlib.sha256(bundle_bytes).hexdigest()
    manifest = _load_json(output_dir / "manifest.json")
    recorded_hash = next(
        (
            artifact.get("sha256")
            for artifact in manifest.get("artifacts", [])
            if artifact.get("path") == "research_bundle.json"
        ),
        None,
    )
    if recorded_hash != bundle_hash:
        raise FeishuError("当前资讯包与 Manifest 中已质检的版本不一致，请先重新运行质检")
    recorded_qa_hash = next(
        (
            artifact.get("sha256")
            for artifact in manifest.get("artifacts", [])
            if artifact.get("path") == "qa_report.json"
        ),
        None,
    )
    if recorded_qa_hash and recorded_qa_hash != hashlib.sha256(qa_bytes).hexdigest():
        raise FeishuError("当前 QA 报告与 Manifest 中已质检的版本不一致，请先重新运行质检")
    post = build_post(bundle)
    post_bytes = json.dumps(post, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    content_bytes = len(post_bytes)
    if content_bytes > MAX_POST_BYTES:
        raise FeishuError(
            f"飞书富文本达到 {content_bytes} 字节，超过当前 {MAX_POST_BYTES} 字节的安全上限"
        )
    message_hash = hashlib.sha256(post_bytes).hexdigest()
    if dry_run:
        return {
            "status": "dry_run",
            "chat_name": chat_name,
            "edition_date": bundle.get("edition_date"),
            "item_count": len(bundle.get("items", [])),
            "content_bytes": content_bytes,
            "bundle_sha256": bundle_hash,
            "message_sha256": message_hash,
        }

    receipt_path = output_dir / "feishu_delivery.json"
    # Codex's backup task and macOS launchd can fire close together.  Hold a
    # cross-process lock across the receipt check and API call so only one
    # sender can claim this edition at a time.
    with _delivery_lock(output_dir):
        if not app_id or not app_secret:
            raise FeishuError("缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
        token = get_tenant_access_token(app_id, app_secret)
        chat_id = find_chat_id(list_chats(token), chat_name)
        if receipt_path.is_file():
            receipt = _load_json(receipt_path)
            same_target = receipt.get("app_id") == app_id and receipt.get("chat_id") == chat_id
            if receipt.get("status") == "sending":
                raise FeishuError("上一次飞书投递在发送中中断，请先到目标群确认是否已送达")
            if (
                receipt.get("status") == "succeeded"
                and receipt.get("message_sha256") == message_hash
                and same_target
            ):
                return {**receipt, "skipped": True}

        delivery_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"signalbloom:{app_id}:{chat_id}:{message_hash}"))
        pending = {
            "status": "sending",
            "edition_date": bundle.get("edition_date"),
            "app_id": app_id,
            "chat_name": chat_name,
            "chat_id": chat_id,
            "delivery_uuid": delivery_uuid,
            "bundle_sha256": bundle_hash,
            "message_sha256": message_hash,
            "attempted_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_receipt(receipt_path, pending)
        try:
            message = send_post(token, chat_id, post, delivery_uuid)
        except FeishuError:
            _write_receipt(
                receipt_path,
                {**pending, "status": "failed", "failed_at": datetime.now(timezone.utc).isoformat()},
            )
            raise
        message_id = message.get("message_id")
        if not message_id:
            raise FeishuError("飞书返回成功，但没有 message_id")
        receipt = {
            "status": "succeeded",
            "edition_date": bundle.get("edition_date"),
            "app_id": app_id,
            "chat_name": chat_name,
            "chat_id": chat_id,
            "message_id": message_id,
            "delivery_uuid": delivery_uuid,
            "bundle_sha256": bundle_hash,
            "message_sha256": message_hash,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_receipt(receipt_path, receipt)
        return receipt
