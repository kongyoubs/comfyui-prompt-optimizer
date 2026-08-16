# -*- coding: utf-8 -*-
"""
Skill 加载器 — 目录驱动的 skill 扫描。

skills/ 目录规范:
    skills/
        <skill-id>/
            SKILL.md        # 必需：frontmatter 声明 name / type / description
            references/     # 可选：额外的规则文件（.md / .txt 按文件名排序后拼接）

SKILL.md frontmatter 示例:
    ---
    name: H3 文生视频 (T2VA)
    type: video            # image / video / music / caption
    description: 用 H3 官方规范生成视频提示词
    ---
    （正文规则……）

用户新增 skill = 在 skills/ 下建一个文件夹 + 写 SKILL.md，重启 ComfyUI 即自动出现，
无需改任何代码。
"""
import os
import re

_SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")

# 合法的 type 值（对应适配器）
_VALID_TYPES = {"image", "video", "music", "caption"}


def _parse_frontmatter(text):
    """解析 SKILL.md 顶部的 --- frontmatter ---，返回 (字段dict, 正文)。"""
    fm = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            kv = re.match(r"^([\w-]+)\s*:\s*(.*)$", line.strip())
            if kv:
                fm[kv.group(1)] = kv.group(2).strip()
    return fm, body.strip()


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as exc:
        print(f"[prompt-optimizer] 读取失败 {path}: {exc}")
        return ""


def scan_skills():
    """扫描 skills/ 目录，返回 skill 列表。

    返回: [
        {"id": "h3-t2va", "name": "H3 文生视频 (T2VA)", "type": "video", "rules": "...", "description": "..."},
        ...
    ]
    按 id 排序，保证下拉顺序稳定。
    """
    skills = []
    if not os.path.isdir(_SKILLS_DIR):
        return skills

    for entry in sorted(os.listdir(_SKILLS_DIR)):
        skill_dir = os.path.join(_SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.exists(skill_md):
            continue

        fm, body = _parse_frontmatter(_read_text(skill_md))
        skill_type = fm.get("type", "").strip().lower()
        if skill_type not in _VALID_TYPES:
            skill_type = "video"  # 默认按视频处理

        # 组装规则文本：正文 + references/*
        chunks = [body] if body else []
        ref_dir = os.path.join(skill_dir, "references")
        if os.path.isdir(ref_dir):
            for ref_name in sorted(os.listdir(ref_dir)):
                ref_path = os.path.join(ref_dir, ref_name)
                if os.path.isfile(ref_path) and ref_name.lower().endswith((".md", ".txt")):
                    content = _read_text(ref_path)
                    if content:
                        chunks.append(content)

        rules = "\n\n".join(c for c in chunks if c)
        if not rules:
            continue  # 空规则跳过

        skills.append({
            "id": entry,
            "name": fm.get("name", entry),
            "type": skill_type,
            "description": fm.get("description", ""),
            "rules": rules,
        })

    return skills


def get_skill(skill_id):
    """按 id 返回单个 skill；未知返回 None。"""
    for s in scan_skills():
        if s["id"] == skill_id:
            return s
    return None


def skill_choices():
    """返回节点下拉用的 [(id, 显示名)] 列表。"""
    return [(s["id"], s["name"]) for s in scan_skills()]


def skill_types():
    """返回 {id: type} 映射。"""
    return {s["id"]: s["type"] for s in scan_skills()}
