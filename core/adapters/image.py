# -*- coding: utf-8 -*-
"""生图提示词优化适配器 — FLUX / SDXL / SD3 / Qwen-Image 等。"""
from .base import BaseAdapter


class ImageAdapter(BaseAdapter):
    adapter_id = "image"
    display_name = "生图优化"

    def build_messages(self, text, target_model="", data_urls=None):
        model_hint = f"目标生图模型: {target_model}。" if target_model else ""

        system = self._make_system(
            "你是一名专业的 AI 绘画提示词工程师，擅长把用户简单的想法扩写成高质量、结构化的生图提示词。",
            "规则：\n"
            "1. 分析主体、环境、光线、构图、风格、质感、细节六个维度，逐项补全；\n"
            "2. 若目标模型是 FLUX 系列（FLUX.1-dev / schnell / kontext 等）：使用自然语言完整句子描述，不使用逗号分隔的 tag 堆叠，不输出负面提示词；\n"
            "3. 若目标模型是 SDXL / SD3 / SD1.5 等：使用英文逗号分隔的 tag 风格（如 masterpiece, best quality, highly detailed），并给出负面提示词（如 lowres, bad anatomy, blurry, watermark）；\n"
            "4. 保留用户原词中的关键主体与专有名词，不擅自删改；\n"
            "5. 输出格式：先输出【正向提示词】，再输出【负面提示词】（无负面要求时负面提示词输出 empty）。",
            model_hint,
            self._lang_hint(),
        )

        user = f"请优化以下生图提示词：\n{text}"
        return system, user
