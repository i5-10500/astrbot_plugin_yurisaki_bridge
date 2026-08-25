# Changelog

本项目使用语义化版本。尚未创建 Git tag 或 GitHub Release 的内容保留在
`Unreleased`。

## Unreleased

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
