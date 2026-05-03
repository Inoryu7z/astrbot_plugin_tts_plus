# Changelog

## [1.2.1] - 2026-05-03

### 🐛 Bug 修复

- 🔧 **Mimo 音色样本上传 "Missing plugin config info" 错误** — 根因：`file` 类型放在 `template_list` 内部时，TemplateListEditor 不传 `pluginName`/`configKey` 给 FileConfigItem。仿照 aiimg 方案，将 `voice_sample` 从模板中移出，改为顶层 `mimo_voice_sample`（`type: file`），`get_audio_sample_base64` 自动从顶层配置读取。
- 🔧 **人格级 text_voice_output 被重置** — 将 schema 类型从 `bool`（默认 null）改为 `string`（选项 "", "true", "false"），避免 `validate_config` 在校验时将 null 转为 False，导致"使用全局设置"行为失效。

### 🔨 改进

- 📝 **配置面板优化** — 新增 `default_persona` 字段（含人格选择器下拉框），替代模板列表内无法渲染的 `_special` 字段
- 📝 **模板列表字段提示增强** — `select_persona` 和 `provider_id` 添加明显提示（obvious_hint），引导用户正确填写

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
