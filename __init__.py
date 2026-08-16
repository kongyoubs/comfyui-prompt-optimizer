# -*- coding: utf-8 -*-
"""
ComfyUI Prompt Optimizer
一个节点完成生图/生视频/音乐提示词优化 + 图像反推。
引擎为 OpenAI 兼容 API（支持任意中转站），适配器可插拔。
"""
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
