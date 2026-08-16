# -*- coding: utf-8 -*-
"""生视频提示词优化适配器 — Wan2.x / HunyuanVideo / LTX-Video / H3 等。"""
from .base import BaseAdapter


class VideoAdapter(BaseAdapter):
    adapter_id = "video"
    display_name = "生视频优化"

    def build_messages(self, text, target_model="", data_urls=None):
        model_hint = f"目标视频模型: {target_model}。" if target_model else ""

        system = self._make_system(
            "你是一名专业的 AI 视频生成提示词工程师，擅长把想法扩写成适合文生视频模型的高质量提示词。",
            "规则：\n"
            "1. 视频提示词必须包含：主体与动作、场景与背景、镜头语言（景别：远景/全景/中景/近景/特写；机位运动：推/拉/摇/移/跟/升降）、"
            "时间节奏（开场-发展-高潮-收尾）、光线与氛围、画风与质感；\n"
            "2. 动作描述要具体（谁 + 做什么 + 怎么做），避免抽象形容词堆叠；\n"
            "3. 强调运动连续性：物体的位移、人物的姿态变化、光影的流动都要描述；\n"
            "4. 若目标模型有专门格式（如 MiniMax H3 的 T2VA/I2VA/FL2VA 等），按对应格式组织；\n"
            "5. 输出格式：先输出【视频提示词】（可直接粘贴给视频模型），再输出【分镜要点】（3-5 条简短要点，供参考）。",
            model_hint,
            self._lang_hint(),
        )

        user = f"请优化以下视频生成提示词：\n{text}"
        return system, user
