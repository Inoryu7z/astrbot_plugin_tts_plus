# 🫧 巴巴啵一 | astrbot_plugin_tts_plus

多提供商 TTS 语音合成插件，让 AI 的回复开口说话——带着情绪、风格和个性。

## ✨ 特性

- 🎭 **多提供商支持** — 硅基流动（CosyVoice2）、MiniMax（speech-2.8）、小米 Mimo（音色复刻）
- 🎨 **风格标签系统** — LLM 自动在回复中嵌入风格标签，TTS 提供商原生解析，语音自然生动
- 👤 **多人格路由** — 固定命名槽位 `persona_1`~`persona_3`，运行时通过 `conversation_manager` 精准匹配当前人格
- 🏊 **风格池与音频标签** — 硅基流动/MiniMax 提供商独立风格池（分类扩展）；Mimo 使用全局音频标签（叹气/笑/抽泣等）
- 🔊 **双通道文本** — TTS 文本保留风格标签，显示文本自动清洗，用户无感知
- 🔄 **智能缓存** — SHA256 音频缓存 + 指数退避重试，稳定高效
- 🎛️ **运行时切换** — `/语音切换` 命令在不重载配置的情况下切换当前人格的 TTS 提供商

## 🚀 快速开始

### 安装

在 AstrBot 插件市场搜索「巴巴啵一」或手动安装：

```bash
astrbot.cli plug install astrbot_plugin_tts_plus
```

### 配置流程

1. **添加提供商**
   - 硅基流动 / MiniMax：在配置界面的「TTS 提供商」区域添加（template_list）
   - 小米 Mimo：在下方独立的 `mimotts_1`~`mimotts_3` 槽位中配置（需上传音色样本）
2. **配置人格** — 在 `persona_1`~`persona_3` 槽位中选择人格并绑定提供商 ID
3. **调整风格** — 硅基流动/MiniMax 可在提供商配置的「风格池」中扩展；Mimo 通过全局 `mimo_audio_tags` 配置

> v1.3.0 起，**有人格配置即有 TTS，无则无**——不再有全局 `tts_enabled` 开关。

### 提供商配置要点

| 提供商 | 配置位置 | 必填项 | 风格机制 |
|--------|----------|--------|----------|
| 硅基流动 | `providers` 列表 | API Key | `<\|HAPPY\|>` 风格标签 + 风格池 |
| MiniMax | `providers` 列表 | API Key | `emotion` 字段 + 语气词标签 + 风格池 |
| 小米 Mimo | `mimotts_1`~`mimotts_3` 槽位 | API Key + 音频样本 | 全局音频标签（叹气/笑等），禁用情绪标签 |

> **Mimo 音色复刻**：在 `mimotts_N` 槽位的「音色样本」字段上传一段 mp3 或 wav 音频（≤10MB），插件会自动缓存 base64 编码。每个 Mimo 槽位独立绑定一份音色样本。

## 🎛️ 命令

| 命令 | 说明 |
|------|------|
| `/说话 <内容>` | 用当前人格的语音说指定内容，例如 `/说话 你好呀` |
| `/语音切换 <provider_id>` | 切换当前人格的 TTS 提供商，例如 `/语音切换 mimotts_2` |

**`/语音切换` 详细行为**：
- 切换后直接写入 `cmd_config.json`，**重载不丢失**
- 仅对已在 `persona_1`~`persona_3` 中显式配置当前人格的窗口生效
- 切换后自动清除音频样本缓存，确保新提供商的样本被正确加载

## 🎭 风格标签工作原理

插件通过最小化 LLM 提示词注入，让对话模型在回复中自动嵌入风格标签：

```
LLM 回复：(叹气)唉，今天好累啊……
         ↓
TTS 文本：(叹气)唉，今天好累啊……  → Mimo 直接解析音频标签
显示文本：唉，今天好累啊……        → 标签已清洗
```

不同提供商使用不同的标签机制：

| 提供商 | 标签格式 | 说明 |
|--------|---------|------|
| Mimo | `(叹气)` `(笑)` `(小声)` | 全局音频标签，由 `mimo_audio_tags` 配置控制；**禁用情绪标签**（如开心/悲伤），模型从文字本身推断情感 |
| SiliconFlow | `<\|HAPPY\|>` `<\|SAD\|>` | CosyVoice2 情绪标记，来自风格池 |
| MiniMax | `emotion` 字段 | 7 种基础情绪，由插件自动设置；支持语气词 `(laughs)` `(sighs)` 和停顿 `<#数字#>` |

## 🏊 风格池与音频标签

### 硅基流动 / MiniMax 风格池

每个提供商有独立的风格池，在配置界面中以分类方式可视化展示：

**SiliconFlow 风格池**: HAPPY、SAD、ANGRY、FEARFUL、SURPRISED、DISGUSTED、NEUTRAL、EXCITED

**MiniMax 风格池**: neutral、happy、sad、angry、fearful、disgusted、surprised

所有风格池均支持在「自定义风格」中追加扩展。

### Mimo 音频标签

Mimo **不使用风格池**，而是通过全局音频标签控制语音中的非语言元素：

**默认音频标签**（可通过 `mimo_audio_tags` 配置项增减）：
吸气、深呼吸、叹气、长叹一口气、喘息、屏息、笑、轻笑、大笑、冷笑、抽泣、呜咽、哽咽、嚎啕大哭、悄悄话

> Mimo 的提示词模板明确禁止情绪标签（如开心/悲伤），因为语音模型能从文字本身理解情感。仅在文字无法传达时才使用音频标签，例如 `(叹气)唉`、`(小声)应该没问题`、`(紧张，深呼吸)冷静`。多标签可合并写在同一对括号内：`(温柔 甜美)`。

## 💡 提示词模板

v1.3.0 起提示词注入改为**人格级配置**（`inject_prompt` 字段，默认关闭）。开启后会在系统提示词中注入对应提供商的风格控制说明。

每个提供商有独立的提示词模板（Markdown 编辑器，支持全屏模式）：

| 配置项 | 适用提供商 | 可用变量 |
|--------|-----------|----------|
| `siliconflow_prompt_template` | 硅基流动 | `{tag_example}`（标签示例）、`{style_list}`（风格列表） |
| `minimax_prompt_template` | MiniMax | `{tag_example}`、`{style_list}` |
| `mimo_prompt_template` | 小米 Mimo | `{audio_tags}`（音频标签列表） |

每次注入前自动清除旧注入内容，确保幂等（参考 dayflow 的 XML 标签清理模式）。

## 📁 项目结构

```
astrbot_plugin_tts_plus/
├── main.py              # 插件入口：LLM 钩子 + TTS 生成 + 多人格路由 + 命令
├── config.py            # 配置管理器：提供商池 + 人格槽位 + 风格池 + 音频样本
├── emotion.py           # 风格系统：提示词注入 + 标签提取
├── text.py              # 双通道文本：TTS 保留标签 / 显示去除标签
├── utils.py             # 工具：音频验证、缓存、重试、base64 编码
├── _conf_schema.json    # WebUI 配置 Schema
├── metadata.yaml        # 插件元数据
├── providers/
│   ├── base.py          # BaseTTSProvider 抽象基类 + 注册机制
│   ├── siliconflow.py   # 硅基流动 Provider（CosyVoice2）
│   ├── minimax.py       # MiniMax Provider（speech-2.8）
│   └── mimo.py          # 小米 Mimo Provider（音色复刻）
└── temp/                # 音频临时文件（自动清理）
```

## ⚙️ 配置项说明

### 全局设置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `timeout` | API 请求超时（秒） | 30 |
| `max_retries` | 失败后重试次数 | 2 |
| `cooldown` | 两次合成最小间隔（秒），0 表示不限制 | 0 |
| `text_min_limit` | 文本长度低于此值不生成语音 | 2 |
| `text_limit` | 文本长度超过此值不生成语音，0 表示不限制 | 500 |

### 全局提示词模板与音频标签

| 配置项 | 适用 | 说明 |
|--------|------|------|
| `siliconflow_prompt_template` | 硅基流动 | 风格标签格式说明 + 可用风格列表 |
| `minimax_prompt_template` | MiniMax | 风格标签 + 语气词 + 停顿语法 |
| `mimo_prompt_template` | Mimo | 禁用情绪标签 + 音频标签用法 |
| `mimo_audio_tags` | Mimo | 全局音频标签列表（吸气/叹气/笑等） |

### TTS 提供商（`providers` template_list）

仅硅基流动和 MiniMax 在此添加。每个提供商包含：

| 字段 | 硅基流动 | MiniMax | 说明 |
|------|:---:|:---:|------|
| `id` | ✓ | ✓ | 提供商 ID（唯一，人格配置的 `provider_id` 填此值） |
| `api_url` | ✓ | ✓ | API 端点 |
| `api_key` | ✓ | ✓ | API 密钥 |
| `model` | ✓ | ✓ | 模型名称 |
| `voice` / `voice_id` | `voice` | `voice_id` | 默认音色 |
| `format` | ✓ | ✓ | 音频格式（mp3/wav/...） |
| `speed` | ✓ | ✓ | 语速（0.5-2.0） |
| `sample_rate` | ✓ | ✓ | 采样率 |
| `pool` | ✓ | ✓ | 风格池（基础情绪 + 自定义风格） |
| `gain` | ✓ | — | 增益（仅硅基流动） |
| `vol` / `pitch` | — | ✓ | 音量/音调（仅 MiniMax） |
| `proxy` | — | ✓ | 代理地址（仅 MiniMax） |

### Mimo 提供商（`mimotts_1` ~ `mimotts_3` 顶层槽位）

每个槽位独立配置一份 Mimo 提供商，**自带音色样本上传字段**：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `id` | 提供商 ID（唯一） | `mimotts_1` / `mimotts_2` / `mimotts_3` |
| `api_url` | API 端点 | `https://api.xiaomimimo.com/v1` |
| `api_key` | API 密钥 | — |
| `model` | 模型名称 | `mimo-v2.5-tts-voiceclone` |
| `voice_sample` | 音色样本（mp3/wav，≤10MB，`type: file`） | — |
| `format` | 输出格式（wav/mp3） | `wav` |

> v1.3.0 起 Mimo 提供商从 `providers` template_list 移到顶层固定槽位，因为 `file` 类型在 template_list 内不工作。每个槽位可自定义 ID（如将 `mimotts_1` 改为 `voice_alice`），人格配置通过 `provider_id` 引用。

### 人格 TTS 配置（`persona_1` ~ `persona_3` 顶层槽位）

固定命名槽位取代 v1.2.x 的 `template_list`，运行时通过 `conversation_manager` / `persona_manager` 获取当前人格 ID 后精准匹配 `select_persona`：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `select_persona` | 人格（下拉选择，由框架 `PersonaManager` 提供） | `default` |
| `provider_id` | 提供商 ID（如 `siliconflow`、`minimax`、`mimotts_1`） | — |
| `inject_prompt` | 是否注入风格控制提示词 | `false` |
| `speed` | 语速覆盖（1.0 表示使用提供商默认） | `1.0` |
| `prob` | 语音输出概率（0.0~1.0，1.0 表示始终生成） | `1.0` |
| `text_voice_output` | 文字与语音同时输出（留空使用默认 / `true` / `false`） | 留空 |

> v1.3.0 删除的字段：全局 `tts_enabled`、全局 `text_voice_output`、人格级 `voice`（音色覆盖）、人格级 `default_style`（默认风格）、Mimo 提供商的 `pool` 字段。这些功能由提供商级配置或人格级 `speed`/`prob`/`inject_prompt` 替代。

## 🔧 扩展开发

添加新的 TTS 提供商只需：

1. 在 `providers/` 下创建新文件
2. 继承 `BaseTTSProvider` 并实现 `synth()` 方法
3. 使用 `@register_provider("name")` 注册
4. 在 `_conf_schema.json` 的 providers templates 中添加对应模板

```python
from .base import BaseTTSProvider, register_provider

@register_provider("my_provider")
class MyProvider(BaseTTSProvider):
    provider_name = "my_provider"
    supports_style_tags = True
    style_tag_format = "parentheses"

    async def synth(self, text, voice, out_dir, *, speed=None, emotion=None, style_tags=None):
        # 实现合成逻辑
        ...
```

## 📄 许可证

MIT License
