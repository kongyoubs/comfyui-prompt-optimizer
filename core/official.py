# -*- coding: utf-8 -*-
"""
官方 skill 加载器 — 读取 core/official/ 下内置的 MiniMax 官方 skill 文件，
把它们作为提示词优化的"规则来源"注入 system prompt。

目录结构:
    core/official/
        h3/                    # MiniMax H3 视频生成
            SKILL.md           # 核心提示词编写规则
            base-en.txt        # T2VA/I2VA/FL2VA/L2VA 提示词结构
            ref-en.txt         # Ref2VA 全参考模式结构
            styles/*.md        # 8 个风格化视频 skill（中文版）
        music3/                # MiniMax Music3 音乐生成
            SKILL.md           # 音乐描述重写工作流
            genre-router.md    # 风格路由规则
"""
import os

_OFFICIAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "official")

# 官方预设列表：(预设id, 显示名, 类型, 规则文件相对路径列表)
# 类型: video / music
OFFICIAL_PRESETS = [
    # ---- H3 视频 ----
    ("h3_t2va", "H3 文生视频 (T2VA)", "video", ["h3/SKILL.md", "h3/base-en.txt"]),
    ("h3_i2va", "H3 首帧生视频 (I2VA)", "video", ["h3/SKILL.md", "h3/base-en.txt"]),
    ("h3_fl2va", "H3 首尾帧生视频 (FL2VA)", "video", ["h3/SKILL.md", "h3/base-en.txt"]),
    ("h3_l2va", "H3 尾帧生视频 (L2VA)", "video", ["h3/SKILL.md", "h3/base-en.txt"]),
    ("h3_ref2va", "H3 全参考生视频 (Ref2VA)", "video", ["h3/SKILL.md", "h3/ref-en.txt"]),
    ("h3_3d_animation", "H3 3D动画短片", "video", ["h3/styles/3d-animation-short-generator.md"]),
    ("h3_brand_promo", "H3 品牌宣传片", "video", ["h3/styles/brand-promo-video-generator.md"]),
    ("h3_coop_game", "H3 双人游戏开场", "video", ["h3/styles/co-op-game-intro-generator.md"]),
    ("h3_handdrawn", "H3 手绘实拍融合", "video", ["h3/styles/handdrawn-live-video-generator.md"]),
    ("h3_product_ad", "H3 极简产品广告", "video", ["h3/styles/minimalist-product-ad-generator.md"]),
    ("h3_mv_subtitle", "H3 音乐MV字幕", "video", ["h3/styles/music-video-subtitle-generator.md"]),
    ("h3_paper_collage", "H3 纸拼贴讲解动画", "video", ["h3/styles/paper-collage-explainer-generator.md"]),
    ("h3_papercraft", "H3 纸艺定格科普", "video", ["h3/styles/papercraft-stop-motion-explainer.md"]),
    # ---- Music3 音乐 ----
    ("music3_rewriter", "Music3 音乐描述重写", "music", ["music3/SKILL.md", "music3/genre-router.md"]),
]


def get_preset(preset_id):
    """按预设 id 返回 (显示名, 类型, 规则文本)；未知返回 None。"""
    for pid, label, ptype, paths in OFFICIAL_PRESETS:
        if pid == preset_id:
            rules = _load_rules(paths)
            return label, ptype, rules
    return None


def _load_rules(rel_paths):
    """读取多个规则文件，拼接为一段完整规则文本。"""
    chunks = []
    for rel in rel_paths:
        full = os.path.join(_OFFICIAL_DIR, rel.replace("/", os.sep))
        if os.path.exists(full):
            try:
                with open(full, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    chunks.append(content)
            except Exception as exc:
                print(f"[prompt-optimizer] 读取官方规则失败 {rel}: {exc}")
    return "\n\n".join(chunks)


def official_choices():
    """返回节点下拉用的 [(id, 显示名)] 列表。"""
    return [(pid, label) for pid, label, _ptype, _paths in OFFICIAL_PRESETS]


def preset_type(preset_id):
    """返回预设的类型（video/music），未知返回 None。"""
    for pid, _label, ptype, _paths in OFFICIAL_PRESETS:
        if pid == preset_id:
            return ptype
    return None
