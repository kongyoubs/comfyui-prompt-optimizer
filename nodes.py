# -*- coding: utf-8 -*-
"""
主节点：Prompt Optimizer
一个节点搞定 生图/生视频/音乐/图像反推 的提示词优化，
内部通过可插拔适配器（core/adapters）按 model_type 分发。

输入:
    text          原始提示词
    mode          优化 / 反推 / 反推+优化
    model_type    auto / image / video / music（auto 按关键字自动识别）
    target_model  可选：目标生图/视频/音乐模型名
    image         可选：IMAGE 张量（反推或多图参考，取前 N 张）
    max_images    最多取前几张图（1-8）
    provider      选择 API 中转站（providers.json 里的 name）
    language      zh / en / both（优化结果语言）
    max_tokens    输出长度上限
    temperature   采样温度

输出:
    positive      优化后的正向提示词（caption 模式=反推描述）
    negative      负面提示词（仅 image 适配器产出；无则 empty）
    caption       反推描述（仅反推相关模式产出）
    raw           LLM 原始返回
"""
import folder_paths  # noqa: F401  （确保 ComfyUI 环境变量已加载）

from .core import client as api_client
from .core import image_utils
from .core.adapters import get_adapter, auto_detect_adapter, ADAPTER_CHOICES


# 常量列表（ComfyUI 下拉选项）
MODE_CHOICES = ["optimize", "caption", "both"]
MODEL_TYPE_CHOICES = [("auto", "自动识别"), *ADAPTER_CHOICES]
LANGUAGE_CHOICES = [
    ("zh", "中文"),
    ("en", "英文"),
    ("both", "中英双输出"),
]


class PromptOptimizerNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "输入原始提示词，例如：一只戴贝雷帽的橘猫，水彩风格",
                }),
                "mode": (MODE_CHOICES, {"default": "optimize"}),
                "model_type": (MODEL_TYPE_CHOICES, {"default": "auto"}),
            },
            "optional": {
                "target_model": ("STRING", {
                    "default": "",
                    "placeholder": "可选：FLUX.1-dev / Wan2.1 / MusicGen / Qwen-Image…",
                }),
                "image": ("IMAGE",),
                "max_images": ("INT", {"default": 1, "min": 1, "max": 8, "step": 1}),
                "provider": (api_client.provider_names(), {"default": api_client.provider_names()[0] if api_client.provider_names() else ""}),
                "language": (LANGUAGE_CHOICES, {"default": "zh"}),
                "max_tokens": ("INT", {"default": 2048, "min": 256, "max": 8192, "step": 256}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "caption", "raw")
    FUNCTION = "process"
    CATEGORY = "Prompt Optimizer"

    def process(self, text, mode="optimize", model_type="auto", target_model="",
                image=None, max_images=1, provider="", language="zh",
                max_tokens=2048, temperature=0.7):
        text = str(text or "").strip()
        mode = str(mode or "optimize")

        # ---- 确定适配器类型 ----
        adapter_id = str(model_type or "auto")
        if adapter_id == "auto":
            adapter_id = auto_detect_adapter(text) or "image"

        # ---- 图片转 data URI（供反推）----
        data_urls = []
        if image is not None:
            total = int(getattr(image, "shape", [0])[0]) if hasattr(image, "shape") else 0
            count = min(total or 0, int(max_images or 1))
            for i in range(count):
                url = image_utils.tensor_to_data_url(image, index=i)
                if url:
                    data_urls.append(url)

        # ---- 是否需要反推（caption 模式 或 both 模式或 adapter=caption）----
        need_caption = mode in ("caption", "both") or adapter_id == "caption"
        need_optimize = mode in ("optimize", "both") or adapter_id != "caption"

        caption = ""
        positive = ""
        negative = ""
        raw = ""

        # ---- 反推：先用 VLM 描述图片 ----
        if need_caption:
            if not data_urls:
                raise RuntimeError("反推模式需要连接 image 输入（IMAGE 张量）")
            cap_adapter = get_adapter("caption", language=language)
            sys_p, user_content = cap_adapter.build_messages(text, target_model, data_urls)
            caption = api_client.chat_completion(
                provider,
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_content}],
                model_type="vision",
                max_tokens=max_tokens,
                temperature=temperature,
            )
            raw += f"【反推】\n{caption}\n"

        # ---- 优化：用 LLM 优化提示词 ----
        if need_optimize:
            adapter = get_adapter(adapter_id, language=language)
            sys_p, user_content = adapter.build_messages(text, target_model, data_urls)
            result = api_client.chat_completion(
                provider,
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_content}],
                model_type="chat",
                max_tokens=max_tokens,
                temperature=temperature,
            )
            raw += f"【优化】\n{result}\n"
            positive, negative = _split_positive_negative(result, adapter_id, language)

        # ---- 兜底：既无反推也无优化（空输入）----
        if not caption and not positive:
            positive = text or ""

        return (positive, negative, caption, raw.strip())


def _split_positive_negative(result, adapter_id, language):
    """从 LLM 输出中拆出正向/负面提示词。
    优先解析 JSON（{"positive":..., "negative":...}），回退到文本标记解析。
    """
    result = str(result or "").strip()
    positive = result
    negative = ""

    # ---- 1. 尝试 JSON 解析 ----
    parsed = _try_parse_json(result)
    if parsed:
        pos = parsed.get("positive") or parsed.get("positive_prompt") or parsed.get("prompt")
        neg = parsed.get("negative") or parsed.get("negative_prompt")
        if pos is not None and isinstance(pos, str) and pos.strip():
            positive = pos.strip()
            negative = (neg or "").strip()
            # 负面为 empty/none 时置空
            if negative.lower() in ("empty", "none", "无", "无负面提示词"):
                negative = ""
            return positive, negative

    # ---- 2. 文本标记解析（回退）----
    for marker in ("【负面提示词】", "[Negative Prompt]", "负面提示词：", "Negative:"):
        idx = result.find(marker)
        if idx > 0:
            positive = result[:idx].strip()
            negative = result[idx + len(marker):].strip()
            break

    # 清理正向上可能残留的标题
    for title in ("【正向提示词】", "[Positive Prompt]", "正向提示词："):
        if positive.startswith(title):
            positive = positive[len(title):].strip()
            break

    # 去掉负面里的 "empty" / "无"
    if negative.lower() in ("empty", "none", "无", "无负面提示词"):
        negative = ""

    return positive, negative


def _try_parse_json(text):
    """尝试把文本解析为 JSON dict；支持被 ```json 代码块包裹的情况。"""
    import json
    import re
    if not text:
        return None
    s = text.strip()
    # 去除 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
    if m:
        s = m.group(1)
    else:
        # 提取第一个 { ... } 对象
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            s = s[start:end + 1]
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


NODE_CLASS_MAPPINGS = {
    "PromptOptimizer": PromptOptimizerNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptOptimizer": "提示词优化（生图/视频/音乐/反推）",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
