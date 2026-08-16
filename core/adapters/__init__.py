# -*- coding: utf-8 -*-
"""适配器注册表 — 按 model_type 选择适配器。"""
from .image import ImageAdapter
from .video import VideoAdapter
from .music import MusicAdapter
from .caption import CaptionAdapter

#: 适配器注册表：id -> 适配器类
ADAPTERS = {
    "image": ImageAdapter,
    "video": VideoAdapter,
    "music": MusicAdapter,
    "caption": CaptionAdapter,
}

#: 节点下拉显示名 -> id
ADAPTER_CHOICES = [
    ("image", "生图优化"),
    ("video", "生视频优化"),
    ("music", "音乐优化"),
    ("caption", "图像反推"),
]

#: 自动识别关键字（文本出现时优先匹配的适配器）
AUTO_KEYWORDS = [
    ("video", ("视频", "镜头", "运镜", "分镜", "动画", "video", "shot", "camera", "motion", "t2v", "i2v", "h3", "wan", "hunyuan", "ltx")),
    ("music", ("音乐", "旋律", "曲风", "节奏", "bpm", "music", "song", "audio", "melody", "beat", "instrumental")),
    ("image", ("画", "图", "插画", "海报", "壁纸", "照片", "image", "photo", "art", "illustration", "painting", "portrait")),
]


def get_adapter(adapter_id, language="zh"):
    """按 id 获取适配器实例。"""
    cls = ADAPTERS.get(adapter_id)
    if cls is None:
        cls = ImageAdapter
    return cls(language=language)


def auto_detect_adapter(text):
    """
    根据文本自动判断最可能的适配器。
    返回: ('image'|'video'|'music'|None)
    """
    if not text:
        return None
    lowered = text.lower()
    scores = {}
    for adapter_id, keywords in AUTO_KEYWORDS:
        score = sum(1 for kw in keywords if kw in lowered)
        if score:
            scores[adapter_id] = scores.get(adapter_id, 0) + score
    if not scores:
        return None
    return max(scores.items(), key=lambda kv: kv[1])[0]
