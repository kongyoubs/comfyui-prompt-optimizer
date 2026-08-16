# ComfyUI Prompt Optimizer

一个节点搞定 **生图 / 生视频 / 音乐** 提示词优化 + **图像反推**。
引擎使用 **OpenAI 兼容 API**（支持任意中转站、DeepSeek、魔搭、Ollama 等），
适配器可插拔，新增模型类型无需改节点。

> 设计参考 [comfyUI-llama-TE](https://github.com/tl2012tl/comfyUI-llama-TE) 的图片预处理与节点风格，
> 但改为 API 引擎（无需本地 LLM/GPU），并扩展为"一个节点 + 可插拔适配器"结构。

## 特性

- 🎬 **MiniMax H3 官方视频 skill**：内置 13 个官方视频预设（T2VA/I2VA/FL2VA/L2VA/Ref2VA + 8 个风格化短片），下拉即选
- 🎵 **MiniMax Music3 官方音乐 skill**：内置音乐描述重写规则（含风格路由）
- 📂 **skills 目录自定义**：`skills/` 下每个文件夹是一个 skill，新增 skill 零代码改动
- 🌐 **任意中转站**：`providers.json` 配置多个 API，节点内下拉切换
- 🌍 **中英可选**：中文 / 英文 / 中英双输出
- 🧩 **可插拔适配器**：加新模型类型 = 在 `core/adapters/` 加一个文件

## Skill 目录（可扩展）

节点的 `skill` 下拉自动扫描插件根目录下的 `skills/` 文件夹，每个子文件夹是一个 skill。内置 14 个 MiniMax 官方 skill（[MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3) 视频 + [MiniMax-Music3](https://github.com/MiniMax-AI/MiniMax-Music3) 音乐）。

### 目录规范

```
skills/
    <skill-id>/                # skill 唯一标识（文件夹名）
        SKILL.md               # 必需：frontmatter 声明 name / type / description
        references/            # 可选：额外的规则文件（.md/.txt 按文件名拼接）
```

`SKILL.md` 格式：

```markdown
---
name: 我的生图风格
type: image        # image / video / music / caption
description: 用这种风格优化生图提示词
---
（正文规则，会被注入 LLM 的 system prompt……）
```

`type` 决定走哪个适配器（image/video/music/caption）。选中 skill 后，节点会把 SKILL.md 正文 + references 里所有规则注入 system prompt，生成符合该规范的提示词。

### 内置 skill 一览

| 预设 | 类型 | 说明 |
|---|---|---|
| H3 文生视频 (T2VA) | video | 纯文本生成完整视听时间线 |
| H3 首帧生视频 (I2VA) | video | 从首帧图向后发展 |
| H3 首尾帧生视频 (FL2VA) | video | 描述首尾帧之间的连续路径 |
| H3 尾帧生视频 (L2VA) | video | 推断开头并收敛到尾帧 |
| H3 全参考生视频 (Ref2VA) | video | 六段式全参考重写 |
| H3 3D动画短片 / 品牌宣传片 / 双人游戏开场 / 手绘实拍 / 极简产品广告 / MV字幕 / 纸拼贴 / 纸艺定格 | video | 8 个风格化视频生成 skill |
| Music3 音乐描述重写 | music | 结构化音乐 caption（Global Metadata / Vocal / Arrangement） |

### 新增自定义 skill

只需两步：

1. 在 `skills/` 下建一个文件夹，如 `skills/my-style/`
2. 写一个 `SKILL.md`（含上面的 frontmatter）

重启 ComfyUI，节点的 `skill` 下拉就会出现你的 skill，无需改任何代码。

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
