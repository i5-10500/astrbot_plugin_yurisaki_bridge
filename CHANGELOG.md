# Changelog

本项目使用语义化版本。尚未创建 Git tag 或 GitHub Release 的内容保留在
`Unreleased`。

## Unreleased

### Added

- 新增 Agent Tool `yurisaki_song_preview(query)`；只生成固定 `/a preview` 命令，并复用
  info/rand 的输入校验、全局 single-flight、限速、响应拦截和超时隔离。
- 根据三次真实脱敏探测增加有限多事件 collector：曲名文本与 `record` 都到齐才完成，支持
  text/audio 任意顺序和单事件组合，部分响应超时返回 `incomplete_response`。
- 通过 AstrBot `Record` 消息链把 HTTPS 短预览发送到原 Tool 会话；临时 URL、file 和
  path 不进入 Tool JSON 或日志，也不下载、缓存或预先调用 ffmpeg。
- 新增 `enable_preview_tool` 配置和同一 Agent 事件防重复调用保护。

### Fixed

- transport 同时兼容 Python 3.10 的 `asyncio.TimeoutError` 和新版 Python 的内置
  `TimeoutError`，避免正常超时被误报为未知错误。

## 0.2.0 - 2026-08-25

### Added

- 新增 Agent Tool `yurisaki_random_song(difficulty="")`，支持无条件随机以及严格白名单化的
  标级或谱面定数筛选。
- 根据三次真实脱敏响应增加单事件 `image → text` parser 和 fixture。
- 随机曲目封面通过当前 `AstrMessageEvent` 即时发送到原会话；Tool JSON 不暴露临时图片
  URL 或 file 值。
- 同一 Agent 事件最多执行一次随机曲目 Tool，避免规划循环重复发图。
- 精确识别 Yurisaki 的“定数范围错误”和“无符合曲目”纯文本响应，返回稳定错误类型且不
  发送图片。

### Changed

- 歌曲字段解析新增 `曲侧` 和 `艺术家` 别名。
- 随机 Tool JSON 新增 `filter` 元数据，明确区分标级与定数；过滤响应的单值字段与曲名
  `[...]` 后缀保持兼容。

## 0.1.1 - 2026-08-25

### Fixed

- 查询超时后进入全局响应隔离期，下一次查询会等待安静窗口；隔离期内的迟到回复会被
  丢弃并重新计时，避免旧回复被错误归入新请求。
- 插件关闭会立即中断正在等待隔离期结束的查询，不会在热重载后继续发送旧请求。
- 非空但不符合歌曲信息结构的文本不再被标记为成功；有效响应现在必须包含曲名或曲目 ID，
  以及至少一个其他已知信息字段，同时继续容忍未知字段并保留 `raw_text`。

### Added

- 新增 `timeout_quarantine_seconds` 配置，默认 5 秒。

## 0.1.0 - 2026-08-25

### Added

- 受控 AstrBot Tool `yurisaki_song_info(query)`。
- 固定 `/a info` 查询、输入防注入和安全错误模型。
- aiocqhttp/NapCat 私聊 transport、全局 single-flight、限速和超时。
- 严格 sender/self/time 响应匹配、原始响应拦截和热重载清理。
- OneBot 文本与 segment 解析，并保留 `raw_text` 供降级诊断。
- Python 3.12/3.13 离线测试和 GitHub Actions CI。
- 真实 AstrBot/NapCat/Yurisaki 联调清单与 v0.1.0 首次发布验收。
- 以公开化名 `i5-10500` 持有版权，并采用 `AGPL-3.0-or-later` 许可证。

### Fixed

- 使用插件包内相对导入，修复 AstrBot 上传安装时找不到 `yurisaki_bridge` 的问题。
- 调试连接日志不再输出机器人 QQ 号。
