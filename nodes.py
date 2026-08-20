# -*- coding: utf-8 -*-
"""
主节点：Prompt Optimizer
一个节点搞定 生图/生视频/音乐/图像反推 的提示词优化，
内部通过可插拔适配器（core/adapters）按 model_type 分发。

输入:
    text          原始提示词
    mode          优化 / 反推 / 反推+优化
    model_type    auto / image / video / music（auto 按关键字自动识别）
    image         可选：IMAGE 张量（反推或多图参考，取前 N 张）
    max_images    最多取前几张图（1-8）
    skill         选择 skills/ 目录下的 skill（下拉，可自定义扩展）
    provider      选择 API 中转站（providers.json 里的 name）
    language      zh / en / both（优化结果语言）
    max_tokens    输出长度上限
    temperature   采样温度

输出:
    positive      主提示词输出：
                    - 优化模式：优化后的正向提示词（生图/视频/音乐）
                    - 反推模式：图片反推描述（与 caption 相同）
                    - 编辑模式：图生图编辑提示词
                    - 空输入：原样返回 text
    negative      负面提示词（仅 image 适配器产出；SD 系用，FLUX 系为空；其余模式为空）
    caption       图片反推描述（仅 mode=caption/both 或 caption 类型 skill 时有值）
    raw           LLM 原始返回全文，含【反推】【优化】各段；
                  执行 provider 配置动作时前置追加【配置】日志（排错用）
"""
import folder_paths  # noqa: F401  （确保 ComfyUI 环境变量已加载）

from .core import client as api_client
from .core import image_utils
from .core import skill_loader
from .core.adapters import get_adapter, auto_detect_adapter, ADAPTER_CHOICES


# 常量列表（ComfyUI 下拉选项）
# 注意：带显示名的选项用 [value, 显示名] list，不能用 tuple ——
# ComfyUI 前端保存 combo 时序列化为数组，tuple 会导致后端 "Value not in list" 校验失败。
MODE_CHOICES = [
    ["optimize", "提示词优化"],
    ["caption", "图像反推"],
    ["both", "提示词优化和图像反推"],
]
# 注意：带显示名的选项用 [value, 显示名] list，不能用 tuple ——
# ComfyUI 前端保存 combo 时序列化为数组，tuple 会导致后端 "Value not in list" 校验失败。
MODEL_TYPE_CHOICES = [["auto", "自动识别"], *ADAPTER_CHOICES]
LANGUAGE_CHOICES = [
    ["zh", "中文"],
    ["en", "英文"],
    ["both", "中英双输出"],
]
# skill 下拉：无 + 扫描 skills/ 目录得到的全部 skill
SKILL_CHOICES = [["none", "不使用 skill"]] + skill_loader.skill_choices()
# provider 配置动作下拉（持久化到 providers.json）
PROVIDER_ACTION_CHOICES = [
    ["none", "无操作"],
    ["save", "保存配置到文件"],
    ["delete", "删除所选 provider"],
    ["reload", "重载 providers.json"],
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
                "image": ("IMAGE",),
                "max_images": ("INT", {"default": 1, "min": 1, "max": 8, "step": 1}),
                "skill": (SKILL_CHOICES, {"default": "none"}),
                "provider": (api_client.provider_names(), {
                    "default": api_client.provider_names()[0] if api_client.provider_names() else ""
                }),
                "language": (LANGUAGE_CHOICES, {"default": "zh"}),
                "max_tokens": ("INT", {"default": 2048, "min": 256, "max": 8192, "step": 256}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                # ---- Provider 配置（节点界面直填，持久化到 providers.json）----
                "provider_action": (PROVIDER_ACTION_CHOICES, {"default": "none"}),
                "provider_name": ("STRING", {
                    "default": "",
                    "placeholder": "Provider 名称（保存/删除用，如 DeepSeek）",
                }),
                "base_url": ("STRING", {
                    "default": "",
                    "placeholder": "https://api.deepseek.com/v1（以 /v1 结尾）",
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "sk-xxxx（保存后写入 providers.json）",
                }),
                "chat_model": ("STRING", {
                    "default": "",
                    "placeholder": "gpt-4o / deepseek-chat / Qwen/Qwen3-235B-A22B",
                }),
                "vision_model": ("STRING", {
                    "default": "",
                    "placeholder": "gpt-4o / qwen-vl-max（看图用，留空=chat_model）",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("正向提示词", "反向提示词", "图像反推", "原始输出")
    FUNCTION = "process"
    CATEGORY = "Prompt Optimizer"

    def process(self, text, mode="optimize", model_type="auto",
                image=None, max_images=1, skill="none", provider="", language="zh",
                max_tokens=2048, temperature=0.7,
                provider_action="none", provider_name="", base_url="",
                api_key="", chat_model="", vision_model=""):
        text = str(text or "").strip()
        # ComfyUI 前端把 combo 选中项序列化为 [value, 显示名] 数组传给节点，
        # 这里统一规范化为字符串（字符串输入原样通过）。
        mode = _combo_value(mode, "optimize")
        model_type = _combo_value(model_type, "auto")
        skill_id = _combo_value(skill, "none")
        language = _combo_value(language, "zh")
        provider = _combo_value(provider, "")
        provider_action = _combo_value(provider_action, "none")

        # ---- 处理 Provider 配置动作（写回 providers.json，持久化）----
        config_log = _handle_provider_action(
            provider_action, provider, provider_name,
            base_url, api_key, chat_model, vision_model,
        )

        # ---- 确定适配器类型 ----
        adapter_id = str(model_type or "auto")
        if adapter_id == "auto":
            adapter_id = auto_detect_adapter(text) or "image"

        # skill：若选中，覆盖 adapter_id 为 skill 声明的类型，并准备 skill 规则
        skill_rules = ""
        skill_type = ""
        if skill_id != "none":
            sk = skill_loader.get_skill(skill_id)
            if sk:
                adapter_id = sk["type"]
                skill_rules = sk["rules"]
                skill_type = sk["type"]

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
        need_optimize = bool(text) and (mode in ("optimize", "both") or adapter_id not in ("caption",))

        # 编辑模式：需要图片输入
        if adapter_id == "edit" and not data_urls:
            raise RuntimeError("图像编辑模式需要连接 image 输入（IMAGE 张量）")

        caption = ""
        positive = ""
        negative = ""
        raw = ""

        # ---- 反推：先用 VLM 描述图片 ----
        if need_caption:
            if not data_urls:
                raise RuntimeError("反推模式需要连接 image 输入（IMAGE 张量）")
            cap_adapter = get_adapter("caption", language=language)
            sys_p, user_content = cap_adapter.build_messages(text, data_urls=data_urls)
            # caption 类型 skill 的规则注入到反推分支（否则在纯 caption 模式下会被忽略）
            if skill_type == "caption" and skill_rules:
                sys_p = f"{sys_p}\n\n【必须遵循以下 skill 规则生成描述】\n\n{skill_rules}"
            caption = api_client.chat_completion(
                provider,
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_content}],
                model_type="vision",
                max_tokens=max_tokens,
                temperature=temperature,
            )
            raw += f"【反推】\n{caption}\n"
            # 反推结果同时输出到 positive（README 输出表约定：caption 模式下
            # positive = 图片反推描述），便于直接接入文生图提示词链路；
            # mode=both 时会被后面的优化结果覆盖。
            if not positive:
                positive = caption

        # ---- 优化：用 LLM 优化提示词 ----
        if need_optimize:
            adapter = get_adapter(adapter_id, language=language)
            sys_p, user_content = adapter.build_messages(text, data_urls=data_urls)
            # 注入 skill 规则：把 skill 内容追加到 system prompt
            if skill_rules:
                sys_p = f"{sys_p}\n\n【必须遵循以下 skill 规则生成提示词】\n\n{skill_rules}"
            # 编辑/反推类需要 vision 模型看图片，其余用 chat 模型
            use_model_type = "vision" if adapter_id in ("edit",) else "chat"
            result = api_client.chat_completion(
                provider,
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_content}],
                model_type=use_model_type,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            raw += f"【优化】\n{result}\n"
            positive, negative = _split_positive_negative(result, adapter_id, language)

        # ---- 兜底：既无反推也无优化（空输入）----
        if not caption and not positive:
            positive = text or ""

        if config_log:
            raw = (config_log + "\n" + raw).strip()

        return (positive, negative, caption, raw.strip())


def _combo_value(v, default=""):
    """ComfyUI 前端把 combo 选中项序列化为 [value, 显示名] 数组传给节点函数，
    这里统一取第一项字符串；纯字符串输入原样返回。"""
    if isinstance(v, (list, tuple)):
        return str(v[0]) if v and v[0] is not None else default
    if v is None:
        return default
    return str(v)


def _handle_provider_action(action, provider, provider_name, base_url,
                            api_key, chat_model, vision_model):
    """
    处理节点上的 provider 配置动作，写回 providers.json（持久化）。
    返回操作日志字符串；无操作时返回 ""。
    """
    action = str(action or "none")
    if action == "none":
        return ""

    try:
        if action == "save":
            # 未填 provider_name 时沿用当前下拉选中的 provider（更新场景）
            name = (provider_name or "").strip() or (provider or "").strip()
            _, log = api_client.save_provider(
                name, base_url, api_key, chat_model, vision_model)
            return f"【配置】{log}\n（已写入 providers.json，重启不丢失；下拉列表已动态刷新）"
        if action == "delete":
            name = (provider_name or "").strip() or (provider or "").strip()
            log = api_client.delete_provider(name)
            return f"【配置】{log}"
        if action == "reload":
            api_client.load_providers(force=True)
            return f"【配置】已强制重载 providers.json，当前可用: {', '.join(api_client.provider_names()) or '（空）'}"
        return f"【配置】未知动作: {action}"
    except Exception as exc:
        return f"【配置操作失败】{exc}"


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
