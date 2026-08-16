# -*- coding: utf-8 -*-
"""
check_api.py — 验证 providers.json 里的 API 是否可用。

用法:
    python check_api.py [--config providers.json 路径]

功能:
    1. 读取 providers.json（默认取插件目录下）
    2. 逐个 provider 测试 chat_model 的连通性（发一条极简消息）
    3. 可选 --test-vision 测试 vision_model 连通性
    4. 输出每个 provider 的 可用/不可用 及错误原因

退出码: 0=全部可用, 1=存在不可用
"""
import argparse
import json
import os
import sys


def load_providers(config_path):
    if not os.path.exists(config_path):
        print(f"[错误] 找不到配置文件: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    providers = data.get("providers", [])
    if not providers:
        print("[错误] providers.json 里没有 provider")
        sys.exit(1)
    return providers


def test_chat(provider, timeout=30):
    """测试 chat_model：发一条 'ping' 消息，返回 (ok, 信息)。"""
    import requests
    base_url = str(provider.get("base_url") or "").strip().rstrip("/")
    api_key = str(provider.get("api_key") or "").strip()
    model = provider.get("chat_model") or provider.get("vision_model") or "gpt-4o"

    if not base_url or not api_key:
        return False, "缺少 base_url 或 api_key"

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
    except Exception as exc:
        return False, f"网络错误: {exc}"

    if resp.status_code == 200:
        return True, f"OK (model={model})"
    return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


def test_vision(provider, timeout=60):
    """测试 vision_model：发一张 1x1 像素图，返回 (ok, 信息)。"""
    import base64
    import requests
    base_url = str(provider.get("base_url") or "").strip().rstrip("/")
    api_key = str(provider.get("api_key") or "").strip()
    model = provider.get("vision_model") or provider.get("chat_model") or "gpt-4o"

    if not base_url or not api_key:
        return False, "缺少 base_url 或 api_key"

    # 1x1 红色像素 PNG
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    data_url = f"data:image/png;base64,{png_b64}"

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": "这张图是什么颜色？"},
                    ],
                }],
                "max_tokens": 20,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
    except Exception as exc:
        return False, f"网络错误: {exc}"

    if resp.status_code == 200:
        return True, f"OK (vision model={model})"
    return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


def main():
    parser = argparse.ArgumentParser(description="验证 providers.json 里的 API 可用性")
    parser.add_argument("--config", default=None, help="providers.json 路径（默认插件目录下）")
    parser.add_argument("--test-vision", action="store_true", help="同时测试 vision_model（会多发请求）")
    args = parser.parse_args()

    if args.config:
        config_path = args.config
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(here), "providers.json")

    providers = load_providers(config_path)
    print(f"配置文件: {config_path}\n")

    all_ok = True
    for p in providers:
        name = p.get("name", "(未命名)")
        ok, msg = test_chat(p)
        status = "[OK]   可用" if ok else "[FAIL] 不可用"
        if not ok:
            all_ok = False
        print(f"{status}  [{name}]  chat: {msg}")
        if args.test_vision:
            vok, vmsg = test_vision(p)
            vstatus = "[OK]   可用" if vok else "[FAIL] 不可用"
            if not vok:
                all_ok = False
            print(f"{vstatus}  [{name}]  vision: {vmsg}")
        print()

    print("=" * 50)
    if all_ok:
        print("全部 provider 可用 [OK]")
        sys.exit(0)
    else:
        print("存在不可用的 provider [FAIL]，请检查上面的错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
