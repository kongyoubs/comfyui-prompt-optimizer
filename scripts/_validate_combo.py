# -*- coding: utf-8 -*-
"""临时验证脚本：模拟 ComfyUI 的 combo 校验逻辑（execution.py: val in combo_options）。

用法: <comfy-python> scripts/_validate_combo.py <插件目录>
"""
import importlib.util
import os
import sys
import types

plugin_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, plugin_dir)  # 同 ComfyUI：加载 custom_node 时会把插件目录加入 sys.path

# ---- folder_paths stub（本机非 ComfyUI 环境）----
try:
    import folder_paths  # noqa
except ImportError:
    folder_paths = types.ModuleType("folder_paths")
    sys.modules["folder_paths"] = folder_paths

# ---- 用 ComfyUI 同款方式加载插件包 ----
spec = importlib.util.spec_from_file_location(
    "comfyui_prompt_optimizer_test",
    os.path.join(plugin_dir, "__init__.py"),
    submodule_search_locations=[plugin_dir],
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

from core.adapters import ADAPTER_CHOICES  # noqa
from core import skill_loader  # noqa
# nodes 已作为包成员被 __init__.py 导入，从包命名空间取
node_mod = sys.modules[spec.name + ".nodes"]
MODEL_TYPE_CHOICES = node_mod.MODEL_TYPE_CHOICES
LANGUAGE_CHOICES = node_mod.LANGUAGE_CHOICES
SKILL_CHOICES = node_mod.SKILL_CHOICES
PROVIDER_ACTION_CHOICES = node_mod.PROVIDER_ACTION_CHOICES
MODE_CHOICES = node_mod.MODE_CHOICES

# 前端保存到工作流的典型数组值（就是报错日志里的样子）
cases = [
    ("mode", "optimize", MODE_CHOICES),
    ("model_type", ["image", "生图优化"], MODEL_TYPE_CHOICES),
    ("model_type", ["auto", "自动识别"], MODEL_TYPE_CHOICES),
    ("model_type", ["video", "生视频优化"], MODEL_TYPE_CHOICES),
    ("language", ["zh", "中文"], LANGUAGE_CHOICES),
    ("language", ["en", "英文"], LANGUAGE_CHOICES),
    ("skill", ["image-zimage", "Z-image 生图提示词"], SKILL_CHOICES),
    ("skill", ["none", "不使用 skill"], SKILL_CHOICES),
    ("provider_action", ["save", "保存配置到文件"], PROVIDER_ACTION_CHOICES),
    ("provider_action", ["reload", "重载 providers.json"], PROVIDER_ACTION_CHOICES),
]

allok = True
for name, val, opts in cases:
    ok = val in opts
    allok = allok and ok
    print(f'{"OK  " if ok else "FAIL"} {name}: {val!r} in combo_options -> {ok}')

# 纯字符串值也要能过（用户手改 JSON 为字符串的情况）
extra = [
    ("model_type_str", "image", MODEL_TYPE_CHOICES),
    ("language_str", "zh", LANGUAGE_CHOICES),
    ("skill_str", "image-zimage", SKILL_CHOICES),
]
for name, val, opts in extra:
    ok = val in opts
    allok = allok and ok
    print(f'{"OK  " if ok else "FAIL"} {name}: {val!r} in combo_options -> {ok}')

# ---- 模拟 process()：前端传数组值时，节点必须取到正确的字符串 ----
print()
print("=== process() 数组值模拟 ===")
# stub API：不真发请求（注意：必须替换 nodes 引用的同一个 client 模块）
api_client = node_mod.api_client
calls = {}

def fake_chat(provider, messages, model_type="chat", **kw):
    calls["provider"] = provider
    calls["model_type"] = model_type
    sys_prompt = messages[0]["content"]
    calls["skill_injected"] = "Z-image 生图提示词" in sys_prompt or "画质前缀" in sys_prompt
    return '{"positive": "masterpiece, best quality, 8k, sharp focus, 橘猫", "negative": ""}'

api_client.chat_completion = fake_chat

node_cls = node_mod.PromptOptimizerNode
# 前端保存的数组值
positive, negative, caption, raw = node_cls().process(
    text="一只戴贝雷帽的橘猫，水彩风格",
    mode=["optimize", "优化"],
    model_type=["image", "生图优化"],
    skill=["image-zimage", "Z-image 生图提示词"],
    provider="DeepSeek",
    language=["en", "英文"],
    provider_action=["none", "无操作"],
)
print(f"provider 收到: {calls.get('provider')!r}")
print(f"model_type 收到: {calls.get('model_type')!r} (应为 chat)")
print(f"skill 规则已注入: {calls.get('skill_injected')}")
print(f"positive: {positive!r}")
print(f"negative: {negative!r}")

p_ok = ("橘猫" in positive) and calls.get("provider") == "DeepSeek" and calls.get("skill_injected")
allok = allok and p_ok
print(f'{"OK  " if p_ok else "FAIL"} process() 数组值处理')

# ---- 模拟 caption 反推模式：positive 必须等于反推描述 ----
print()
print("=== caption 模式模拟 ===")
import numpy as np

class FakeImage:
    shape = (1, 8, 8, 3)
    def __getitem__(self, i):
        return self
    def cpu(self):
        return self
    def numpy(self):
        return np.zeros((8, 8, 3), dtype=np.float32)

calls2 = {}
def fake_chat2(provider, messages, model_type="chat", **kw):
    calls2["provider"] = provider
    calls2["model_type"] = model_type
    calls2["has_image"] = any(
        (isinstance(m, dict) and m.get("type") == "image_url") or
        (isinstance(m, list) and any(isinstance(x, dict) and x.get("type") == "image_url" for x in m))
        for msg in messages for m in (msg["content"] if isinstance(msg.get("content"), list) else [msg.get("content")])
    )
    return "a cute cat sitting on a windowsill, warm light"

api_client.chat_completion = fake_chat2
pos2, neg2, cap2, raw2 = node_cls().process(
    text="",
    mode=["caption", "图像反推"],
    model_type=["caption", "图像反推"],
    skill=["caption-golden-reverse", "图片精细反推"],
    provider="ky-modelscope",
    language=["zh", "中文"],
    image=FakeImage(),
    provider_action=["none", "无操作"],
)
print(f"provider: {calls2.get('provider')!r}  模型类型: {calls2.get('model_type')!r} (应为 vision)")
print(f"图片已发送: {calls2.get('has_image')}")
print(f"positive: {pos2!r}")
print(f"caption:  {cap2!r}")
c_ok = (calls2.get("model_type") == "vision") and calls2.get("has_image") and pos2 == cap2 == "a cute cat sitting on a windowsill, warm light"
allok = allok and c_ok
print(f'{"OK  " if c_ok else "FAIL"} caption 模式 positive=caption')

print()
print("ALL PASS" if allok else "SOME FAILED")
sys.exit(0 if allok else 1)
