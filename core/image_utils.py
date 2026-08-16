# -*- coding: utf-8 -*-
"""
图片预处理：把 ComfyUI 的 IMAGE 张量或本地图片文件转为 data URI，
供多模态（VLM）模型做图像反推。

参照 comfyUI-llama-TE 的做法：
1. 按最大边长等比缩放（默认 1024）
2. RGBA 透明底合成白底
3. 优化 JPEG(quality=90, progressive) 编码
4. 转 data:image/jpeg;base64,...
"""
import base64
import io
import os

import numpy as np
from PIL import Image

# 输入图片 JPEG 质量
JPEG_QUALITY = 90
# 默认最大边长
DEFAULT_MAX_EDGE = 1024


def resize_to_max_edge(pil_image, max_edge):
    """等比缩放到最大边长不超过 max_edge；max_edge<=0 时不缩放。"""
    if max_edge <= 0:
        return pil_image
    w, h = pil_image.size
    long_edge = max(w, h)
    if long_edge <= max_edge:
        return pil_image
    scale = max_edge / float(long_edge)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return pil_image.resize((new_w, new_h), resample=Image.BICUBIC)


def encode_pil_to_jpeg(pil_image, quality=JPEG_QUALITY):
    """RGBA 透明底合成白底后编码为 JPEG bytes。"""
    if pil_image.mode in ("RGBA", "LA") or "transparency" in pil_image.info:
        rgba = pil_image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        pil_image = background.convert("RGB")
    elif pil_image.mode not in ("RGB", "L"):
        pil_image = pil_image.convert("RGB")

    buf = io.BytesIO()
    try:
        pil_image.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    except Exception:
        buf = io.BytesIO()
        pil_image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def tensor_to_data_url(comfy_image, index=0, max_edge=DEFAULT_MAX_EDGE):
    """
    把 ComfyUI 的 IMAGE 张量（B,H,W,C 的 float32 0~1）的第 index 张
    转为 data URI。失败返回空字符串。
    """
    try:
        if comfy_image is None:
            return ""
        img_np = np.clip(255.0 * comfy_image[index].cpu().numpy(), 0, 255).astype(np.uint8)
        pil_image = Image.fromarray(img_np, mode="RGB")
        pil_image = resize_to_max_edge(pil_image, max_edge)
        image_bytes = encode_pil_to_jpeg(pil_image)
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        return f"data:image/jpeg;base64,{image_b64}"
    except Exception as exc:
        print(f"[prompt-optimizer] tensor 转 data URI 失败: {exc}")
        return ""


def file_to_data_url(file_path, max_edge=DEFAULT_MAX_EDGE):
    """本地图片文件转 data URI（自动缩放 + JPEG 编码）。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到图片文件: {file_path}")
    with Image.open(file_path) as pil:
        pil = resize_to_max_edge(pil, max_edge)
        image_bytes = encode_pil_to_jpeg(pil)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{image_b64}"


def build_vision_content(data_urls, text):
    """
    构建多模态 content 数组：
        [{"type":"image_url","image_url":{"url":data_url}}, ..., {"type":"text","text":text}]
    """
    content = []
    for url in data_urls:
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})
    if text:
        content.append({"type": "text", "text": text})
    return content
