# ComfyUI Prompt Optimizer

一个节点搞定 **生图 / 生视频 / 音乐** 提示词优化 + **图像反推** + **图像编辑**。
引擎使用 **OpenAI 兼容 API**（支持任意中转站、DeepSeek、魔搭、Ollama 等），
内置 **34 个 skill**（含 MiniMax 官方视频/音乐 skill + 主流模型专属提示词模板），
适配器与 skill 均可插拔扩展，新增能力零代码改动。

> 设计参考 [comfyUI-llama-TE](https://github.com/tl2012tl/comfyUI-llama-TE) 的图片预处理与节点风格，
> 但改为 API 引擎（无需本地 LLM/GPU），并扩展为"一个节点 + 可插拔适配器 + 目录驱动 skill"结构。

## 特性

- 🖼️ **生图优化**：FLUX 系自然语言 + 无负面词；SD 系 tag 风格 + 负面提示词；Z-image/Krea/Qwen 等模型专属写法
- 🎬 **生视频优化**：补运动描述、镜头语言、时间节奏；含电影分镜、九宫格/25宫格漫剧分镜、运镜库
- 🎵 **音乐优化**：曲风/情绪/BPM/乐器/结构，含 MiniMax Music3 官方结构化重写
- 👁️ **图像反推**：VLM 读取图片 → 详细描述（含普通反推、JSON 结构化反推）
- ✏️ **图像编辑**：参考图 + 修改指令 → 生成图生图编辑提示词（FLUX.2 Klein / Qwen-Edit）
- 📂 **目录驱动 skill**：`skills/` 下每个文件夹是一个 skill，新增 skill 零代码改动
- 🌐 **任意中转站**：`providers.json` 配置多个 API，节点内下拉切换，含重试与故障转移
- 🌍 **中英可选**：中文 / 英文 / 中英双输出
- 🧩 **可插拔适配器**：加新模型类型 = 在 `core/adapters/` 加一个文件

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

字段说明：

| 字段 | 说明 |
|---|---|
| `name` | provider 显示名（节点下拉里切换） |
| `base_url` | OpenAI 兼容地址（以 `/v1` 结尾） |
| `api_key` | API 密钥 |
| `chat_model` | 普通 LLM（提示词优化用） |
| `vision_model` | 多模态 VLM（图像反推/编辑用，可填 `qwen-vl-max`、`gpt-4o` 等） |

- 支持配置多个 provider，节点里下拉切换；单个失败自动切换到下一个。
- 可填的 provider 示例：OpenAI、DeepSeek、魔搭（`https://api-inference.modelscope.cn/v1`）、Ollama（`http://localhost:11434/v1`）、各类中转站。

3. 重启 ComfyUI。依赖：`requests` + `Pillow`（ComfyUI 已自带）。

## 使用

节点分类：**Prompt Optimizer** → **提示词优化（生图/视频/音乐/反推/编辑）**

### 参数

| 参数 | 说明 |
|---|---|
| `text` | 原始提示词 / 修改指令（编辑时） |
| `mode` | `optimize` 优化 / `caption` 反推 / `both` 反推+优化 |
| `model_type` | `auto` 自动识别 / `image` / `video` / `music` / `caption` / `edit` |
| `target_model` | 可选：目标模型名（FLUX.1-dev、Wan2.1、MusicGen…） |
| `image` | 可选 IMAGE 输入（反推/编辑用，最多 8 张） |
| `max_images` | 取前几张图（1-8） |
| `skill` | 选择 `skills/` 目录下的 skill（34 个内置，可自定义扩展） |
| `provider` | 选哪个 API 中转站 |
| `language` | 中文 / 英文 / 中英双输出 |
| `max_tokens` / `temperature` | 采样参数 |

### 输出

| 输出 | 说明 |
|---|---|
| `positive` | 优化后的正向提示词 / 编辑提示词 / 反推描述 |
| `negative` | 负面提示词（仅生图适配器；无则空） |
| `caption` | 反推描述（仅反推相关模式） |
| `raw` | LLM 原始返回（调试用） |

### 典型工作流

```
原始提示词 → [提示词优化] → positive → [FLUX.1-dev] → 出图
                                    → negative → [SDXL] → 出图

图片 → [提示词优化(mode=caption)] → caption → [文生图] → 复刻图片风格

"一只猫在雨中奔跑" → [提示词优化(model_type=video)] → [Wan2.1] → 生视频

参考图 + "换背景" → [提示词优化(model_type=edit)] → positive → [FLUX.2 Klein 编辑] → 改图
```

## Skill 目录（核心机制）

节点的 `skill` 下拉自动扫描插件根目录的 `skills/` 文件夹，每个子文件夹是一个 skill。选中后，节点把该 skill 的完整规则注入 system prompt，生成符合该规范的提示词。

### 目录规范

```
skills/
    <skill-id>/                # skill 唯一标识（文件夹名）
        SKILL.md               # 必需：frontmatter 声明 name / type / description
        references/            # 可选：额外规则文件（.md/.txt 按文件名拼接）
```

`SKILL.md` 格式：

```markdown
---
name: 我的生图风格
type: image        # image / video / music / caption / edit
description: 用这种风格优化生图提示词
---
（正文规则，会被注入 LLM 的 system prompt……）
```

`type` 决定走哪个适配器：

| type | 适配器 | 用途 | 是否需要图片 |
|---|---|---|---|
| `image` | 生图优化 | 文生图提示词 | 否 |
| `video` | 生视频优化 | 文生视频提示词 | 否 |
| `music` | 音乐优化 | 音乐生成提示词 | 否 |
| `caption` | 图像反推 | 图片 → 描述（VLM） | 是 |
| `edit` | 图像编辑 | 图片 + 指令 → 编辑提示词（VLM） | 是 |

### 内置 skill 一览（34 个）

**🖼️ 生图（image，10 个）**

| skill | 说明 |
|---|---|
| 通用生图黄金公式 | 主体+环境+光影+构图+风格+色调+画质 公式 |
| 三步傻瓜式生图 | 核心人物+氛围+场景 三步生成 |
| 绘画提示词大师（词组式） | SD 词组 tag + 负向词库 |
| 标签库生图 | 280 个中文标签库 |
| Z-image 生图提示词 | 中英混合 tag 堆叠 |
| Krea 2 生图提示词 | 自然语言长细节，文字引号 |
| FLUX.2 Klein 生图提示词 | 自然语言句子，无负面词 |
| Qwen-Image 2512 生图提示词 | 中文友好，复杂构图+文字渲染 |
| 产品广告提示词优化 | 九宫格营销，产品保真 |
| 人物三视图（角色设定图） | 正/侧/背三视图 + 表情集 |

**🎬 生视频（video，18 个）**

| 类别 | skill |
|---|---|
| MiniMax H3 模式（5） | 文生视频 T2VA / 首帧 I2VA / 首尾帧 FL2VA / 尾帧 L2VA / 全参考 Ref2VA |
| MiniMax H3 风格（8） | 3D动画短片 / 品牌宣传片 / 双人游戏开场 / 手绘实拍融合 / 极简产品广告 / 音乐MV字幕 / 纸拼贴讲解动画 / 纸艺定格科普 |
| 通用视频（5） | Wan视频题词 / 电影分镜叙事 / 运镜语言库 / 漫剧九宫格分镜 / 漫剧25宫格分镜 |

**🎵 音乐（music，1 个）**

| skill | 说明 |
|---|---|
| Music3 音乐描述重写 | MiniMax Music3 结构化 caption（含风格路由） |

**👁️ 反推（caption，3 个）**

| skill | 说明 |
|---|---|
| 图片精细反推 | 顶级艺术指导式反推，可复刻风格 |
| 图片JSON结构化反推 | 高密度结构化 JSON（人物/产品/风景模板） |
| 产品广告反推 | 提取产品特征/卖点/光影/营销概念 |

**✏️ 编辑（edit，2 个）**

| skill | 说明 |
|---|---|
| FLUX.2 Klein 图像编辑 | 自然语言编辑提示词 |
| Qwen-Image 2511 图生图编辑 | 基于图片的修改指令 |

### 新增自定义 skill

只需两步：

1. 在 `skills/` 下建一个文件夹，如 `skills/my-style/`
2. 写一个 `SKILL.md`（含 frontmatter 声明 name/type/description）

重启 ComfyUI，节点的 `skill` 下拉就会出现你的 skill，无需改任何代码。

## API 客户端特性

`core/client.py` 实现了一个健壮的 OpenAI 兼容客户端：

- **多 provider**：`providers.json` 可配多个中转站，节点内切换
- **自动重试**：网络错误 / 5xx / 429 时指数退避重试
- **故障转移**：当前 provider 失败自动切换到下一个
- **JSON 模式**：可选 `response_format: json_object` 结构化输出
- **结构化解析**：优先解析 JSON（`{"positive":..., "negative":...}`），回退文本标记

## 图片预处理

`core/image_utils.py` 参照 comfyUI-llama-TE：

- 最大边 1024 等比缩放
- RGBA 透明底合成白底
- 优化 JPEG（quality=90，progressive）编码
- 转 `data:image/jpeg;base64,...` 发给 VLM

## 辅助工具

`scripts/check_api.py` 用于验证 providers.json 里的 API 是否可用：

```bash
python scripts/check_api.py                          # 测试 chat_model
python scripts/check_api.py --test-vision            # 同时测试 vision_model
python scripts/check_api.py --config 路径/providers.json
```

## 扩展

### 新增适配器（新类型）

在 `core/adapters/` 新增文件，继承 `BaseAdapter`：

```python
from .base import BaseAdapter

class MyAdapter(BaseAdapter):
    adapter_id = "my_type"
    display_name = "我的类型"

    def build_messages(self, text, target_model="", data_urls=None):
        system = "..."
        return system, f"请优化：{text}"
```

然后在 `core/adapters/__init__.py` 的 `ADAPTERS` / `ADAPTER_CHOICES` 注册，并在 `core/skill_loader.py` 的 `_VALID_TYPES` 加入新类型即可。

### 新增 skill（无需改代码）

见上文「新增自定义 skill」。

## 文件结构

```text
comfyui-prompt-optimizer/
├── __init__.py              # 节点注册
├── nodes.py                 # 主节点定义
├── providers.example.json   # API 配置模板
├── skills/                  # skill 目录（34 个内置，可扩展）
│   └── <skill-id>/SKILL.md
├── core/
│   ├── client.py            # OpenAI 兼容 API 客户端（重试/故障转移/JSON）
│   ├── image_utils.py       # 图片缩放+JPEG→data URI
│   ├── skill_loader.py      # 目录驱动 skill 扫描
│   └── adapters/
│       ├── base.py          # 适配器基类
│       ├── image.py         # 生图优化
│       ├── video.py         # 生视频优化
│       ├── music.py         # 音乐优化
│       ├── caption.py       # 图像反推
│       └── edit.py          # 图像编辑
├── scripts/
│   └── check_api.py         # API 连通性检测
└── README.md
```

## 常见问题

- **反推/编辑没输出**：确认 `mode` 选了 caption/both（反推）或 `model_type` 选了 edit（编辑）、`image` 已连接、`vision_model` 是 VLM。
- **提示缺少 provider**：检查 `providers.json` 是否创建、`base_url` 是否以 `/v1` 结尾。
- **中文乱码**：确保插件文件保存为 UTF-8（本项目全部 UTF-8）。
- **慢**：反推+优化一次会调用两次 API；拆开用 `mode` 单选可减少等待。
- **skill 不显示**：确认 `skills/<id>/SKILL.md` 的 frontmatter 里 `type` 是 image/video/music/caption/edit 之一，且正文非空。

## 致谢

- 图片预处理与节点风格参考 [comfyUI-llama-TE](https://github.com/tl2012tl/comfyUI-llama-TE)
- MiniMax 视频 skill 来自 [MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3)
- MiniMax 音乐 skill 来自 [MiniMax-Music3](https://github.com/MiniMax-AI/MiniMax-Music3)
