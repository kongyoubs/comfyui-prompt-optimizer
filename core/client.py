# -*- coding: utf-8 -*-
"""
OpenAI 兼容 API 客户端 — 支持任意中转站 / OpenAI / DeepSeek / 魔搭 / Ollama 等。

配置读取自插件目录下 providers.json（可配置多个 provider，运行时可切换）。
所有 provider 必须兼容 OpenAI Chat Completions 协议：
    POST {base_url}/chat/completions
    Authorization: Bearer {api_key}

特性：
- 请求自动重试（指数退避，网络错误/5xx 时触发）
- 多 provider 故障转移（当前 provider 失败时自动尝试下一个）
- 可选 response_format json（结构化输出）
"""
import json
import os
import random
import threading
import time

import requests

# 请求超时（秒）
REQUEST_TIMEOUT = 300
# 默认重试次数
DEFAULT_RETRIES = 2
# 重试基础退避时间（秒）
RETRY_BASE_DELAY = 1.5

_lock = threading.Lock()
_cache_providers = None


def get_providers_path():
    """providers.json 与 core/ 同级（即插件根目录）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "providers.json")


def _default_providers():
    return {
        "providers": [
            {
                "name": "示例中转站（请修改）",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-你的key",
                "chat_model": "gpt-4o",
                "vision_model": "gpt-4o",
            }
        ]
    }


def load_providers(force=False):
    """读取 providers.json；文件缺失或损坏时返回示例配置。"""
    global _cache_providers
    with _lock:
        if _cache_providers is not None and not force:
            return _cache_providers
        path = get_providers_path()
        data = _default_providers()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and isinstance(loaded.get("providers"), list):
                    data = loaded
            except Exception as exc:
                print(f"[prompt-optimizer] providers.json 解析失败，使用默认配置: {exc}")
        _cache_providers = data
        return data


def provider_names():
    """返回所有可用的 provider 名称列表。"""
    data = load_providers()
    return [p.get("name", f"provider-{i}") for i, p in enumerate(data.get("providers", []))]


def get_provider(name):
    """按名称取 provider 配置；找不到时返回第一个。"""
    data = load_providers()
    providers = data.get("providers", [])
    for p in providers:
        if p.get("name") == name:
            return p
    return providers[0] if providers else None


def _resolve_model(provider, model_type):
    """model_type: 'chat' 或 'vision'。分别对应 providers.json 里的 chat_model / vision_model。"""
    if not provider:
        return None
    if model_type == "vision":
        return provider.get("vision_model") or provider.get("chat_model") or "gpt-4o"
    return provider.get("chat_model") or "gpt-4o"


def chat_completion(provider_name, messages, *, model_type="chat", max_tokens=2048,
                    temperature=0.7, timeout=None, extra=None, retries=None,
                    json_mode=False, failover=True):
    """
    调用一次 chat completion。

    messages: OpenAI 格式消息列表，如
        [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
            {"type": "text", "text": "描述这张图"}
        ]}]

    参数:
        retries:   每个 provider 的重试次数（None 用 DEFAULT_RETRIES）
        json_mode: 请求 LLM 返回 JSON（response_format），失败自动回退
        failover:  当前 provider 失败时是否自动切换到下一个 provider

    返回: 助手回复文本。所有 provider 都失败时抛出 RuntimeError。
    """
    provider = get_provider(provider_name)
    if not provider:
        raise RuntimeError(f"未找到 API provider: {provider_name}")

    # 构造候选 provider 列表（当前在前，其余按序跟随，用于故障转移）
    data = load_providers()
    all_providers = data.get("providers", [])
    candidates = [p for p in all_providers if p.get("name") == provider.get("name")]
    candidates += [p for p in all_providers if p.get("name") != provider.get("name")]
    if not candidates:
        candidates = [provider]

    attempt_count = retries if retries is not None else DEFAULT_RETRIES
    last_error = None

    for prov in candidates:
        for attempt in range(attempt_count + 1):
            try:
                return _chat_once(prov, messages, model_type=model_type,
                                  max_tokens=max_tokens, temperature=temperature,
                                  timeout=timeout, extra=extra, json_mode=json_mode)
            except _RetryableError as exc:
                last_error = exc
                if attempt < attempt_count:
                    delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    continue
                # 该 provider 重试耗尽，若允许故障转移则跳出内层换下一个
                break
            except RuntimeError as exc:
                # 非可重试错误（如 4xx 参数错误），立即换下一个 provider
                last_error = exc
                break
        if not failover:
            break

    raise RuntimeError(f"所有 provider 均调用失败，最后错误: {last_error}")


class _RetryableError(RuntimeError):
    """可重试的错误（网络问题 / 5xx / 超时）。"""


def _chat_once(provider, messages, *, model_type, max_tokens, temperature,
               timeout, extra, json_mode):
    base_url = str(provider.get("base_url") or "").strip().rstrip("/")
    api_key = str(provider.get("api_key") or "").strip()
    model = _resolve_model(provider, model_type)

    if not base_url:
        raise RuntimeError(f"provider [{provider.get('name')}] 缺少 base_url")
    if not api_key:
        raise RuntimeError(f"provider [{provider.get('name')}] 缺少 api_key")

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            body[k] = v

    try:
        resp = requests.post(url, json=body, headers=headers,
                             timeout=timeout or REQUEST_TIMEOUT)
    except requests.exceptions.Timeout as exc:
        raise _RetryableError(f"请求超时（{timeout or REQUEST_TIMEOUT}s）: {url}") from exc
    except requests.exceptions.RequestException as exc:
        raise _RetryableError(f"网络错误: {exc}") from exc

    # 5xx / 429 视为可重试
    if resp.status_code >= 500 or resp.status_code == 429:
        raise _RetryableError(f"API 服务端错误({resp.status_code}): {resp.text[:300]}")

    if resp.status_code != 200:
        # 4xx 视为不可重试
        detail = resp.text[:500]
        raise RuntimeError(f"API 错误({resp.status_code}): {detail}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"API 返回格式异常: {exc} | {resp.text[:300]}") from exc

    if isinstance(content, list):
        # 部分模型返回分段 content
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text") or item.get("content") or "")
            else:
                parts.append(str(item))
        content = "\n".join(p for p in parts if p)
    return str(content or "").strip()


def list_models(provider_name):
    """可选：列出中转站可用模型（GET /models）。"""
    provider = get_provider(provider_name)
    if not provider:
        return []
    base_url = str(provider.get("base_url") or "").strip().rstrip("/")
    api_key = str(provider.get("api_key") or "").strip()
    if not base_url:
        return []
    try:
        resp = requests.get(f"{base_url}/models",
                            headers={"Authorization": f"Bearer {api_key}"},
                            timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return [m.get("id") for m in data.get("data", []) if m.get("id")]
    except Exception:
        pass
    return []
