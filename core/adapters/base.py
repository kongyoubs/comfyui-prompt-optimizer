# -*- coding: utf-8 -*-
"""
适配器基类 — 定义提示词优化适配器的接口。
新增模型类型 = 继承 BaseAdapter 实现 build_messages()。
"""
from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """提示词优化适配器基类。"""

    #: 适配器标识：image / video / music / caption
    adapter_id = "base"
    #: 显示名
    display_name = "基础"

    def __init__(self, language="zh"):
        """
        language: 'zh' 输出中文提示词；'en' 输出英文提示词；'both' 中英双输出。
        """
        self.language = language

    @abstractmethod
    def build_messages(self, text, target_model="", data_urls=None):
        """
        构造发送给 LLM 的消息列表。

        参数:
            text:        原始提示词
            target_model: 目标模型名（可选，如 FLUX.1-dev）
            data_urls:   图片 data URI 列表（仅 caption 适配器使用）

        返回:
            (system_prompt, user_content)
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 通用辅助
    # ------------------------------------------------------------------
    def _lang_hint(self):
        """输出语言指令片段。"""
        if self.language == "en":
            return "Output only in English."
        if self.language == "both":
            return (
                "Output BOTH an English version and a Chinese version, "
                "labeled 'EN:' and 'ZH:' respectively."
            )
        return "使用简体中文输出。"

    def _make_system(self, *sections):
        """拼接系统提示词。"""
        parts = [s for s in sections if s]
        return "\n\n".join(parts)
