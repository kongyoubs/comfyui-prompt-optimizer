# -*- coding: utf-8 -*-
"""图像编辑适配器 — 用 VLM 理解参考图 + 修改指令，生成图生图编辑提示词。"""
from .base import BaseAdapter


class EditAdapter(BaseAdapter):
    adapter_id = "edit"
    display_name = "图像编辑"

    def build_messages(self, text, target_model="", data_urls=None):
        model_hint = f"目标编辑模型: {target_model}。" if target_model else ""

        system = (
            "你是一名专业的 AI 图像编辑提示词工程师。用户会提供一张参考图和一个修改要求，"
            "你需要先理解图片内容，再生成一个清晰的图生图编辑提示词。\n"
            "规则：\n"
            "1. 编辑提示词应描述【期望的改变】，而不是重述整张图（如\"把背景换成星空\"、\"让角色穿上红色外套\"）；\n"
            "2. 保留参考图中不需要修改的主体特征（人物身份、构图、风格等）；\n"
            "3. 若修改要求涉及风格转换（如\"转成水彩画\"），用自然语言描述目标风格；\n"
            "4. 若目标模型是 FLUX 系列：用自然语言完整句子描述编辑结果，不输出负面提示词；\n"
            "5. 若目标模型是 SD 系图生图：可补充负面提示词（保留原图主体，避免变形）。\n"
            + model_hint
        )

        lang = self.language
        lang_note = {
            "zh": "使用简体中文输出编辑提示词。",
            "en": "Output the edit prompt in English.",
            "both": "Output the edit prompt in English, then Chinese (EN: / ZH:).",
        }.get(lang, "使用简体中文输出编辑提示词。")
        system += "\n" + lang_note

        # 用户消息：图片在前，修改要求在后
        user_text = f"请基于这张参考图，根据以下修改要求生成图生图编辑提示词：\n{text}"
        user_content = [{"type": "text", "text": user_text}]
        for url in (data_urls or []):
            if url:
                user_content.insert(0, {"type": "image_url", "image_url": {"url": url}})
        return system, user_content
