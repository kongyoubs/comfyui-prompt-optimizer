# -*- coding: utf-8 -*-
"""
OpenAI 兼容 API 客户端 — 支持任意中转站 / OpenAI / DeepSeek / 魔搭 / Ollama 等。

配置读取自插件目录下 providers.json（可配置多个 provider，运行时可切换）。
所有 provider 必须兼容 OpenAI Chat Completions 协议：
    POST {base_url}/chat/completions
    Authorization: Bearer {api_key}
"""
import json
import os
import threading

import requests

# 请求超时（秒）
REQUEST_TIMEOUT = 300

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
                    temperature=0.7, timeout=None, extra=None):
    """
    调用一次 chat completion。

    messages: OpenAI 格式消息列表，如
        [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
            {"type": "text", "text": "描述这张图"}
        ]}]

    返回: 助手回复文本。失败抛出 RuntimeError。
    """
    provider = get_provider(provider_name)
    if not provider:
        raise RuntimeError(f"未找到 API provider: {provider_name}")

    base_url = str(provider.get("base_url") or "").strip().rstrip("/")
    api_key = str(provider.get("api_key") or "").strip()
    model = _resolve_model(provider, model_type)

    if not base_url:
        raise RuntimeError(f"provider [{provider_name}] 缺少 base_url")
    if not api_key:
        raise RuntimeError(f"provider [{provider_name}] 缺少 api_key")

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
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            body[k] = v

    try:
        resp = requests.post(url, json=body, headers=headers,
                             timeout=timeout or REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise RuntimeError(f"请求超时（{timeout or REQUEST_TIMEOUT}s）: {url}")
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"网络错误: {exc}")

    if resp.status_code != 200:
        detail = resp.text[:500]
        raise RuntimeError(f"API 错误({resp.status_code}): {detail}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"API 返回格式异常: {exc} | {resp.text[:300]}")

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
