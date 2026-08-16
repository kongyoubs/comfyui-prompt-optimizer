---
name: comfyui-prompt-optimizer
description: ComfyUI 提示词优化节点（节点名 PromptOptimizer）。一个节点完成生图/生视频/音乐的提示词优化，以及图像反推（VLM 图生文）。引擎为 OpenAI 兼容 API（支持任意中转站/DeepSeek/魔搭/Ollama），适配器可插拔。当用户需要为 ComfyUI 工作流优化提示词、把简单想法扩写成高质量生图/视频/音乐提示词、或对图片做反推描述时使用。
---

# ComfyUI Prompt Optimizer

一个 ComfyUI 自定义节点，把用户简单的想法扩写成**适配特定模型的高质量提示词**，支持生图、生视频、音乐三大类，以及图像反推。

## 何时使用

- 用户要在 ComfyUI 里优化/扩写生图提示词（FLUX/SDXL/SD3 等）
- 用户要优化生视频提示词（补镜头语言、运动描述）
- 用户要优化音乐生成提示词（曲风/BPM/乐器/结构）
- 用户要对图片做反推（VLM 图生文，得到可复用的描述）
- 用户提到"提示词优化节点"、"PromptOptimizer"、"prompt 扩写"

## 项目结构

```
comfyui-prompt-optimizer/
├── __init__.py           # 节点注册
├── nodes.py              # 主节点 PromptOptimizer
├── providers.json        # API 配置（用户自建，git 忽略）
├── providers.example.json
├── core/
│   ├── client.py         # OpenAI 兼容客户端（重试/故障转移/JSON模式）
│   ├── image_utils.py    # 图片缩放+JPEG→data URI
│   └── adapters/         # 可插拔适配器
│       ├── base.py       # 适配器基类
│       ├── image.py      # 生图优化
│       ├── video.py      # 生视频优化
│       ├── music.py      # 音乐优化
│       └── caption.py    # 图像反推
└── README.md
```

## 安装与配置

### 安装

把仓库 clone 到 ComfyUI 的 `custom_nodes`：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/kongyoubs/comfyui-prompt-optimizer.git
```

### 配置 API（providers.json）

复制 `providers.example.json` 为 `providers.json`，填入中转站信息：

```json
{
  "providers": [
    {
      "name": "我的中转站",
      "base_url": "https://api.example.com/v1",
      "api_key": "sk-xxxx",
      "chat_model": "gpt-4o",
      "vision_model": "qwen-vl-max"
    }
  ]
}
```

字段说明：
- `name`：节点下拉里显示的名字（可配多个，运行时可切换）
- `base_url`：OpenAI 兼容地址（以 `/v1` 结尾）
- `api_key`：API 密钥
- `chat_model`：普通 LLM（提示词优化用）
- `vision_model`：多模态 VLM（图像反推用）

配置完成后重启 ComfyUI。

## 节点用法

节点：**Prompt Optimizer**（分类：Prompt Optimizer → 提示词优化）

### 输入参数

| 参数 | 说明 |
|---|---|
| `text` | 原始提示词 |
| `mode` | `optimize` 优化 / `caption` 反推 / `both` 反推+优化 |
| `model_type` | `auto` 自动识别 / `image` / `video` / `music` |
| `target_model` | 可选：目标模型名（FLUX.1-dev、Wan2.1、MusicGen…） |
| `image` | 可选 IMAGE 输入（反推/图生图，最多 8 张） |
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
原始提示词 → [PromptOptimizer] → positive → [FLUX.1-dev] → 出图
                                → negative → [SDXL] → 出图

图片 → [PromptOptimizer(mode=caption)] → caption → [文生图] → 复刻图片

"一只猫雨中奔跑，电影感" → [PromptOptimizer(model_type=video)] → [Wan2.1] → 生视频
```

## 适配器机制（可插拔）

4 个内置适配器，按 `model_type` 分发：

| 适配器 | 用途 | 关键差异 |
|---|---|---|
| `image` | 生图 | FLUX 自然语言+无负面；SD 系 tag+负面词 |
| `video` | 生视频 | 补运动/镜头语言/时间节奏 |
| `music` | 音乐 | 曲风/情绪/BPM/乐器/结构 |
| `caption` | 反推 | 用 VLM 纯描述，不优化 |

**新增适配器** = 在 `core/adapters/` 加一个继承 `BaseAdapter` 的文件，然后在 `core/adapters/__init__.py` 的 `ADAPTERS` / `ADAPTER_CHOICES` 注册。节点代码无需改动。

## 辅助工具

本 skill 附带 `check_api.py`，用于验证 providers.json 里的 API 是否可用：

```bash
python <SKILL_DIR>/scripts/check_api.py --config <插件目录>/providers.json
```

## 注意事项

- 反推需要 `vision_model` 是 VLM；优化用 `chat_model`
- `both` 模式会调用两次 API（先反推再优化），可先用 `caption` 验证反推再连优化
- API 客户端内置重试（指数退避）和多 provider 故障转移，单个中转站挂掉会自动切换
- 图片预处理参照 comfyUI-llama-TE：最大边 1024 等比缩放 + 优化 JPEG 90 编码
