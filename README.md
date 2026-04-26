# 🫧 巴巴啵一 | astrbot_plugin_tts_plus

多提供商 TTS 语音合成插件，让 AI 的回复开口说话——带着情绪、风格和个性。

## ✨ 特性

- 🎭 **多提供商支持** — 硅基流动（CosyVoice2）、MiniMax（speech-2.8）、小米 Mimo（音色复刻）
- 🎨 **风格标签系统** — LLM 自动在回复中嵌入风格标签，TTS 提供商原生解析，语音自然生动
- 👤 **多人格路由** — 不同人格绑定不同提供商/音色/风格，UMO 粒度映射
- 🏊 **可视化风格池** — 每个提供商独立风格池，分类展示，支持自定义扩展
- 🔊 **双通道文本** — TTS 文本保留风格标签，显示文本自动清洗，用户无感知
- 🔄 **智能缓存** — SHA256 音频缓存 + 指数退避重试，稳定高效

## 🚀 快速开始

### 安装

在 AstrBot 插件市场搜索「巴巴啵一」或手动安装：

```bash
astrbot.cli plug install astrbot_plugin_tts_plus
```

### 配置

1. **添加提供商** — 在配置界面底部「TTS 提供商」区域，选择提供商类型并填写 API Key
2. **配置人格** — 在「人格 TTS 配置」区域，选择人格并绑定提供商 ID
3. **调整风格池** — 每个提供商自带默认风格列表，可在「风格池」中自定义扩展

### 提供商配置要点

| 提供商 | 必填项 | 风格标签格式 | 特殊说明 |
|--------|--------|-------------|---------|
| 硅基流动 | API Key | `<\|HAPPY\|>` | CosyVoice2 模型，支持情绪标记 |
| MiniMax | API Key | emotion 字段 | 支持 7 种基础情绪 + 语气词标签 |
| 小米 Mimo | API Key + 音频样本 | `(风格)` | 音色复刻模型，需上传音频样本 |

> **Mimo 音色复刻**：在「音色复刻样本」字段上传一段 mp3 或 wav 音频（≤10MB），插件会自动缓存 base64 编码。

## 🎭 风格标签工作原理

插件通过最小化 LLM 提示词注入，让对话模型在回复中自动嵌入风格标签：

```
LLM 回复：(开心)今天天气真好呀！要不要一起出去走走？
         ↓
TTS 文本：(开心)今天天气真好呀！要不要一起出去走走？  → Mimo 直接解析
显示文本：今天天气真好呀！要不要一起出去走走？          → 标签已清洗
```

不同提供商使用不同的标签格式：

- **Mimo**: `(开心)` `(悲伤)` `(东北话)` — 原生风格标签，支持基础情绪、复合情绪、语调、方言等
- **SiliconFlow**: `<|HAPPY|>` `<|SAD|>` — CosyVoice2 情绪标记
- **MiniMax**: `emotion` 字段 — 7 种基础情绪，由插件自动设置

## 🏊 风格池

每个提供商有独立的风格池，在配置界面中以分类方式可视化展示：

**Mimo 风格池**（最丰富）:
- 基础情绪：开心、悲伤、愤怒、恐惧、惊讶、兴奋、委屈、平静、冷漠
- 复合情绪：怅然、欣慰、无奈、愧疚、释然、嫉妒、厌倦、忐忑、动情
- 语调风格：温柔、高冷、活泼、严肃、慵懒、俏皮、深沉、干练、凌厉
- 音色质感：磁性、清亮、甜美、沙哑、空灵、稚嫩、苍老、醇厚
- 方言：东北话、四川话、粤语
- 特殊风格：唱歌、悄悄话、撒娇

**SiliconFlow 风格池**: HAPPY、SAD、ANGRY、FEARFUL、SURPRISED、DISGUSTED、NEUTRAL、EXCITED

**MiniMax 风格池**: neutral、happy、sad、angry、fearful、disgusted、surprised

所有风格池均支持在「自定义风格」中追加扩展。

## 📁 项目结构

```
astrbot_plugin_tts_plus/
├── main.py              # 插件入口：LLM 钩子 + TTS 生成 + 多人格路由
├── config.py            # 配置管理器：提供商池 + 人格 + 风格池
├── emotion.py           # 风格系统：提示词注入 + 标签提取
├── text.py              # 双通道文本：TTS 保留标签 / 显示去除标签
├── utils.py             # 工具：音频验证、缓存、重试
├── _conf_schema.json    # WebUI 配置 Schema
├── metadata.yaml        # 插件元数据
├── providers/
│   ├── base.py          # BaseTTSProvider 抽象基类 + 注册机制
│   ├── siliconflow.py   # 硅基流动 Provider
│   ├── minimax.py       # MiniMax Provider
│   └── mimo.py          # 小米 Mimo Provider（音色复刻）
└── temp/                # 音频临时文件
```

## ⚙️ 配置项说明

### 基础设置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 启用语音合成 | 总开关 | ✅ |
| 文字与语音同时输出 | 同时发送文字和语音 | ✅ |
| 请求超时(秒) | API 请求超时 | 30 |
| 最大重试次数 | 失败后重试次数 | 2 |
| 冷却时间(秒) | 两次合成最小间隔 | 0 |
| 最小文本长度 | 低于此值不生成语音 | 2 |
| 最大文本长度 | 超过此值不生成语音 | 500 |

### 人格 TTS 配置

| 配置项 | 说明 |
|--------|------|
| 人格 | 下拉选择 AstrBot 人格 |
| 提供商 ID | 填写在提供商池中配置的 ID |
| 音色覆盖 | 留空使用提供商默认音色 |
| 默认风格 | 无风格标签时的默认风格 |
| 语速覆盖 | 0 表示使用提供商默认值 |

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
