# -*- coding: utf-8 -*-
"""音乐生成提示词优化适配器 — MusicGen / AudioLDM / Stable Audio 等。"""
from .base import BaseAdapter


class MusicAdapter(BaseAdapter):
    adapter_id = "music"
    display_name = "音乐优化"

    def build_messages(self, text, target_model="", data_urls=None):
        model_hint = f"目标音乐模型: {target_model}。" if target_model else ""

        system = self._make_system(
            "你是一名专业的 AI 音乐生成提示词工程师，擅长把想法转成适合音乐生成模型的描述。",
            "规则：\n"
            "1. 音乐提示词必须覆盖：曲风/流派、情绪氛围、速度 BPM、主要乐器、结构（前奏-主歌-副歌-桥段-尾声）、"
            "人声类型（有/无、男女声、和声）、音色质感；\n"
            "2. 使用可被音乐模型理解的描述性语言，如 'upbeat electronic dance music with a driving four-on-the-floor beat, bright synth leads, 128 BPM'；\n"
            "3. 若目标模型是 MusicGen：输出一句自然语言描述即可（模型直接用文本生成音频）；\n"
            "4. 若目标模型是 AudioLDM / Stable Audio：可同时给出标签式描述和长句描述；\n"
            "5. 输出格式：先输出【音乐提示词】（可直接用于生成），再输出【参数建议】（BPM、时长、风格标签）。",
            model_hint,
            self._lang_hint(),
        )

        user = f"请优化以下音乐生成描述：\n{text}"
        return system, user
