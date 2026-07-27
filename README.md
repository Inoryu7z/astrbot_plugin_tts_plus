[![TTS Plus Counter](https://count.getloli.com/get/@Inoryu7z.tts_plus?theme=miku)](https://github.com/Inoryu7z/astrbot_plugin_tts_plus)

# 🫧 TTS Plus · 巴巴啵一

让 AI 的回复开口说话——带着情绪、风格和个性。

支持三种 TTS 提供商：

- **硅基流动 CosyVoice2** — 7 种基础情绪标签 + 可扩展风格池
- **MiniMax speech-2.8** — 7 种基础情绪 + 语气词控制（笑声/叹气等）
- **小米 Mimo 音色复刻** — 上传一段音频样本克隆音色，支持叹气/笑/抽泣等非语言元素

每个人格可以独立绑定不同的提供商、音色、风格和语速。

---

## 🎮 可用指令

| 命令 | 说明 |
|------|------|
| `/说话 <内容>` | 用当前人格的语音说指定内容，例如 `/说话 你好呀` |
| `/语音切换 <provider_id>` | 切换当前人格的 TTS 提供商，例如 `/语音切换 mimotts_2`。切换后写入配置文件，重载不丢失 |

## 🎭 风格系统

LLM 会在回复中自动嵌入风格标签，TTS 提供商原生解析后生成带情绪的语音。用户看到的文本会自动清洗掉标签。

```
LLM 回复：(叹气)唉，今天好累啊……
         ↓
TTS 文本：(叹气)唉，今天好累啊……  →  Mimo 解析为叹气 + 文字
显示文本：唉，今天好累啊……        →  标签已清洗
```

不同提供商使用不同的风格机制：

| 提供商 | 风格机制 |
|--------|----------|
| Mimo | 全局音频标签（叹气/笑/小声等），不使用情绪标签——模型能从文字本身理解情感 |
| 硅基流动 | `<\|HAPPY\|>` 等标签 + 可扩展风格池 |
| MiniMax | 7 种情绪字段 + 语气词 `(laughs)` `(sighs)` + 停顿 `<#数字#>` |

## ⚙️ 关键配置

| 配置项 | 说明 |
|--------|------|
| `persona_1` ~ `persona_3` | 人格槽位，绑定 `provider_id` + 设置 `speed` / `prob` / `inject_prompt` / `text_voice_output` |
| `providers` | 硅基流动 / MiniMax 提供商列表（含风格池） |
| `mimotts_1` ~ `mimotts_3` | Mimo 槽位，每个绑定一份音色样本（mp3/wav，≤10MB） |
| `mimo_audio_tags` | Mimo 全局音频标签列表 |
| `siliconflow_prompt_template`<br>`minimax_prompt_template`<br>`mimo_prompt_template` | 三个提供商各自的提示词模板（Markdown 编辑器） |

> v1.3.0 起 Mimo 提供商从 `providers` 列表移到顶层固定槽位，每个槽位可自定义 ID（如将 `mimotts_1` 改为 `voice_alice`），人格配置通过 `provider_id` 引用。

完整配置项请查阅 AstrBot 配置界面。

## 📝 版本记录

详细更新见 `CHANGELOG.md`。

---

## 📜 开源协议

本项目基于 [MIT License](LICENSE) 开源。
