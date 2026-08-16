# -*- coding: utf-8 -*-
"""图像反推适配器 — 用 VLM（多模态模型）把图片描述成文本。"""
from .base import BaseAdapter


class CaptionAdapter(BaseAdapter):
    adapter_id = "caption"
    display_name = "图像反推"

    def build_messages(self, text, target_model="", data_urls=None):
        # 反推总是输出英文描述（生图提示词友好），语言选项对纯反推影响小，
        # 但仍尊重语言选择：zh 输出中文描述。
        lang_note = {
            "zh": "使用简体中文描述图片内容。",
            "en": "Describe the image in English.",
            "both": "Describe the image in English, then in Chinese (EN: / ZH:).",
        }.get(self.language, "使用简体中文描述图片内容。")

        system = (
            "你是一名专业的图像描述助手。请详细、准确地描述图片内容，"
            "包括：主体、场景、构图、光线、色彩、风格、质感、细节、文字内容（如有）。\n"
            + lang_note
        )

        # 用户消息：图片在前、文字指令在后（OpenAI 多模态格式）
        extra = f"\n\n补充要求（可选，原样转述）：{text}" if text else ""
        user_content = [
            {"type": "text", "text": f"请描述这张图片。{extra}"},
        ]
        # 图片 data URI 列表在最前面（image_url 优先，text 在后符合多数 VLM 要求）
        for url in (data_urls or []):
            if url:
                user_content.insert(0, {"type": "image_url", "image_url": {"url": url}})
        return system, user_content
