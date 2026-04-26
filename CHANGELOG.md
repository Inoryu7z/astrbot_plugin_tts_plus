# Changelog

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
