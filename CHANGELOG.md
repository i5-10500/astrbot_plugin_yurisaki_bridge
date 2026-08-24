# Changelog

本项目使用语义化版本。尚未创建 Git tag 或 GitHub Release 的内容保留在
`Unreleased`。

## Unreleased

### Added

- 受控 AstrBot Tool `yurisaki_song_info(query)`。
- 固定 `/a info` 查询、输入防注入和安全错误模型。
- aiocqhttp/NapCat 私聊 transport、全局 single-flight、限速和超时。
- 严格 sender/self/time 响应匹配、原始响应拦截和热重载清理。
- OneBot 文本与 segment 解析，并保留 `raw_text` 供降级诊断。
- Python 3.12/3.13 离线测试和 GitHub Actions CI。
- 真实 AstrBot/NapCat/Yurisaki 联调清单与 v0.1.0 beta 验收。

### Fixed

- 使用插件包内相对导入，修复 AstrBot 上传安装时找不到 `yurisaki_bridge` 的问题。
- 调试连接日志不再输出机器人 QQ 号。

正式选择许可证、公开仓库并创建 `v0.1.0` Release 后，再将以上内容归档到对应版本。
