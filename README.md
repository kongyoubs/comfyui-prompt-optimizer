# ComfyUI Prompt Optimizer

一个节点搞定 **生图 / 生视频 / 音乐** 提示词优化 + **图像反推**。
引擎使用 **OpenAI 兼容 API**（支持任意中转站、DeepSeek、魔搭、Ollama 等），
适配器可插拔，新增模型类型无需改节点。

> 设计参考 [comfyUI-llama-TE](https://github.com/tl2012tl/comfyUI-llama-TE) 的图片预处理与节点风格，
> 但改为 API 引擎（无需本地 LLM/GPU），并扩展为"一个节点 + 可插拔适配器"结构。

## 特性

- 🖼️ **生图优化**：FLUX 系自然语言描述 + 无负面词；SDXL/SD3 系 tag 风格 + 负面提示词
- 🎬 **生视频优化**：补运动描述、镜头语言（景别/运镜）、时间节奏、光线氛围
- 🎵 **音乐优化**：曲风/情绪/BPM/乐器/结构/人声全覆盖
- 👁️ **图像反推**：VLM 读取图片 → 详细文字描述（可反向用于生图）
- 🎬 **MiniMax H3 官方视频 skill**：内置 13 个官方视频预设（T2VA/I2VA/FL2VA/L2VA/Ref2VA + 8 个风格化短片），下拉即选
- 🎵 **MiniMax Music3 官方音乐 skill**：内置音乐描述重写规则（含风格路由）
- 🌐 **任意中转站**：`providers.json` 配置多个 API，节点内下拉切换
- 🌍 **中英可选**：中文 / 英文 / 中英双输出
- 🧩 **可插拔适配器**：加新模型类型 = 在 `core/adapters/` 加一个文件

## 官方预设（MiniMax）

节点 `official` 参数提供 14 个内置官方预设，来源 [MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3) 和 [MiniMax-Music3](https://github.com/MiniMax-AI/MiniMax-Music3)：

| 预设 | 说明 |
|---|---|
| H3 文生视频 (T2VA) | 纯文本生成完整视听时间线 |
| H3 首帧生视频 (I2VA) | 从首帧图向后发展 |
| H3 首尾帧生视频 (FL2VA) | 描述首尾帧之间的连续路径 |
| H3 尾帧生视频 (L2VA) | 推断开头并收敛到尾帧 |
| H3 全参考生视频 (Ref2VA) | 六段式全参考重写 |
| H3 3D动画短片 / 品牌宣传片 / 双人游戏开场 / 手绘实拍 / 极简产品广告 / MV字幕 / 纸拼贴 / 纸艺定格 | 8 个风格化视频生成 skill |
| Music3 音乐描述重写 | 结构化音乐 caption（Global Metadata / Vocal / Arrangement） |

选中官方预设后，节点会把对应 skill 的完整规则注入 system prompt，生成符合 MiniMax 官方格式的提示词。

## 安装

1. 把本目录放到 ComfyUI 的 `custom_nodes`：

```text
ComfyUI/custom_nodes/comfyui-prompt-optimizer/
```

2. 复制 `providers.example.json` 为 `providers.json`，填入你的 API 配置：

```json
{
  "providers": [
    {
      "name": "我的中转站",
      "base_url": "https://api.xxx.com/v1",
      "api_key": "sk-xxxx",
      "chat_model": "gpt-4o",
      "vision_model": "gpt-4o"
    }
  ]
}
```

- `base_url`：OpenAI 兼容地址（以 `/v1` 结尾）
- `chat_model`：普通 LLM（提示词优化用）
- `vision_model`：多模态 VLM（图像反推用，可填 `qwen-vl-max`、`gpt-4o` 等）
- 支持配置多个，节点里下拉切换

3. 重启 ComfyUI。依赖：`requests` + `Pillow`（ComfyUI 已自带）。

## 使用

节点分类：**Prompt Optimizer** → **提示词优化（生图/视频/音乐/反推）**

### 参数

| 参数 | 说明 |
|---|---|
| `text` | 原始提示词 |
| `mode` | `optimize` 优化 / `caption` 反推 / `both` 反推+优化 |
| `model_type` | `auto` 自动识别 / `image` / `video` / `music` |
| `target_model` | 可选：目标模型名（如 FLUX.1-dev、Wan2.1） |
| `image` | 可选 IMAGE 输入（反推/图生图用，最多 8 张） |
| `max_images` | 取前几张图（1-8） |
| `provider` | 选哪个 API 中转站 |
| `language` | 中文 / 英文 / 中英双输出 |
| `max_tokens` / `temperature` | 采样参数 |

### 输出

| 输出 | 说明 |
|---|---|
| `positive` | 优化后的正向提示词 / 反推描述 |
| `negative` | 负面提示词（仅生图适配器；无则空） |
| `caption` | 反推描述（仅反推相关模式） |
| `raw` | LLM 原始返回（调试用） |

### 典型工作流

```
原始提示词 → [提示词优化] → positive → [FLUX.1-dev] → 出图
                                    → negative → [SDXL] → 出图

图片 → [提示词优化(mode=caption)] → caption → [文生图] → 复刻图片风格

"一只猫在雨中奔跑，电影感" → [提示词优化(model_type=video)] → [Wan2.1] → 生视频
```

## 扩展：新增适配器

在 `core/adapters/` 新增一个文件，继承 `BaseAdapter`：

```python
from .base import BaseAdapter

class MyAdapter(BaseAdapter):
    adapter_id = "my_type"
    display_name = "我的类型"

    def build_messages(self, text, target_model="", data_urls=None):
        system = "..."
        return system, f"请优化：{text}"
```

然后在 `core/adapters/__init__.py` 的 `ADAPTERS` / `ADAPTER_CHOICES` 注册即可，节点无需改动。

## 文件结构

```text
comfyui-prompt-optimizer/
├── __init__.py          # 节点注册
├── nodes.py             # 主节点定义
├── providers.example.json
├── core/
│   ├── client.py        # OpenAI 兼容 API 客户端（多中转站）
│   ├── image_utils.py   # 图片缩放+JPEG→data URI（参照 TE）
│   └── adapters/
│       ├── base.py      # 适配器基类
│       ├── image.py     # 生图优化
│       ├── video.py     # 生视频优化
│       ├── music.py     # 音乐优化
│       └── caption.py   # 图像反推
└── README.md
```

## 常见问题

- **反推没输出**：确认 `mode` 选了 caption/both、`image` 已连接、`vision_model` 是 VLM。
- **提示缺少 provider**：检查 `providers.json` 是否创建、`base_url` 是否以 `/v1` 结尾。
- **中文乱码**：确保插件文件保存为 UTF-8（本项目全部 UTF-8）。
- **慢**：反推+优化一次会调用两次 API；拆开用 `mode` 单选可减少等待。

> 测试：SSH 推送通道验证（2026-08-16 15:31）
