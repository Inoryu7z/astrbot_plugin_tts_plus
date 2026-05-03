# Changelog

## [1.3.0] - 2026-05-03

### 🔄 重大重构

- 🏗️ **多人格路由重写** — 参照 aiimg 插件模式：固定命名槽位 (`persona_1`~`persona_3`) 取代 `template_list`；运行时通过 `conversation_manager` / `persona_manager` 获取当前人格 ID，精准匹配 `select_persona`
- 🏗️ **Mimo 音色样本** — `voice_sample` 改为 `type: file` 直接在各人格槽位上传，无需手动填路径

### 🗑️ 删除

- ❌ 删除 `tts_enabled`（全局开关）— 有人格配置即有 TTS，无则无
- ❌ 删除 `text_voice_output`（全局）— 默认文字+语音同出，人格级可覆盖
- ❌ 删除人格级 `voice`（音色覆盖）和 `default_style`（默认风格）字段

### 🔨 改进

- 📝 人格级 `speed` 默认值 0 → 1.0

## [1.2.1] - 2026-05-03

### 🐨 Bug 修复

- 🔧 **Mimo 音色样本上传 "Missing plugin config info" 错误** — 根因：`file` 类型在 `template_list` 内不工作。仿照 aiimg：顶层 `mimo_voice_sample`（`type: file`）直接上传；Mimo 模板中 `voice_sample`（`type: string`）支持多实例独立指定路径。`get_audio_sample_base64` 优先读 provider 级，fallback 到顶层。
- 🔧 **人格级 text_voice_output 被重置** — 类型从 `bool`(default null) 改为 `string`(options "", "true", "false")，避免 validate_config 将 null 强制转为 False。

### 🔨 改进

- 📝 **恢复人格下拉选择器** — `select_persona` 恢复 `_special: "select_persona"`，提供人格下拉框
- 📝 **删除冗余 top-level 字段** — 移除无用的 `default_persona` 和无法渲染的 `umo_persona_map`
- 📝 **Mimo 模板补全** — 恢复 `voice_sample`(string) 支持多实例 + 新增 `pool`(object) 风格池配置

## [1.2.0] - 2026-04-27

### 🐛 Bug 修复

- 🔧 **Mimo 风格标签误提取** — `_extract_mimo_styles` 添加 KNOWN_STYLES 白名单过滤，防止 `(注：此处省略)` 等正常括号内容被误识别为风格标签（emotion.py + text.py）
- 🔧 **_inflight 残留条目** — 在 `on_decorating_result` 入口添加 180 秒过期清理，防止极端情况下防重复键泄漏
- 🔧 **临时文件清理性能** — `clean_temp_dir` 添加 300 秒间隔限制，避免每次合成都扫描整个目录
- 🔧 **未使用代码清理** — 删除 `_bg_tasks` 及相关代码、删除 `struct` 未使用导入

### ✨ 新功能

- 🎯 **人格级概率输出** — 每个人格可独立设置 `prob`（0.0~1.0），控制语音生成概率
- 🎯 **人格级文字+语音输出** — 每个人格可独立设置 `text_voice_output`，覆盖全局设置

## [1.1.0] - 2026-04-27

### 🐛 Bug 修复

- 🔧 **MiniMax URL 下载死锁** — 将 `_handle_json_response` 改为 async，避免在已有事件循环中嵌套 `run_until_complete`
- 🔧 **_inflight 防重复泄漏** — 处理 `CancelledError` 确保 finally 块始终执行
- 🔧 **临时文件无限积累** — 在语音合成入口调用 `clean_temp_dir` 自动清理
- 🔧 **提供商类型检测不可靠** — 在 schema 中添加 `provider_type` 只读字段
- 🔧 **无 system_prompt 时跳过注入** — 初始化为空字符串而非跳过整个注入
- 🔧 **validate_audio_file 误判** — 未知格式返回 False 而非 True

### ✨ 新功能

- 🎯 **系统提示词注入暴露** — 参考 dayflow 的 XML 标签 + 幂等清理模式
  - 三个提供商独立提示词模板（Markdown 格式，暗色编辑器，全屏模式）
  - 每次注入前自动清除旧注入内容，确保幂等
- 🎯 **Mimo 专属提示词设计** — 禁止情绪标签，只允许音频标签（叹气/笑/抽泣等）
- 🎯 **Mimo 音频标签可配置** — 新增 `mimo_audio_tags` 配置字段
- 🎯 **Mimo 合并格式支持** — 多风格写在同一对括号内 `(温柔 甜美)`

### 🔨 改进

- 📝 **PAREN_STYLE_RE 减少误匹配** — 加入 KNOWN_STYLES 白名单过滤
- 📝 **Mimo _build_messages 简化** — 去掉冗余的 user_content 判断逻辑
- 📝 **_cooldowns 自动清理** — 在 cooldown 检查时清理过期条目
- 📝 **providers/__init__.py 添加导入** — 触发 provider 自动注册

## [1.0.0] - 2026-04-26

### 🎉 初始发布

- 🎭 **多提供商 TTS** — 支持硅基流动（CosyVoice2）、MiniMax（speech-2.8）、小米 Mimo（音色复刻）
- 🎨 **风格标签系统** — LLM 自动嵌入风格标签，TTS 提供商原生解析
- 👤 **多人格路由** — 不同人格绑定不同提供商/音色/风格，UMO 粒度映射
- 🏊 **可视化风格池** — 每个提供商独立风格池，分类展示，支持自定义扩展
- 🔊 **双通道文本** — TTS 文本保留风格标签，显示文本自动清洗
- 🔄 **智能缓存** — SHA256 音频缓存 + 指数退避重试
- 📁 **统一 Provider 接口** — BaseTTSProvider 抽象基类 + 注册机制，易于扩展
- 🎯 **最小提示词注入** — 仅注入风格标签格式和可用列表，减少对话污染
