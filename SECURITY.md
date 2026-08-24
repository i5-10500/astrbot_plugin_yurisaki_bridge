# Security Policy

## Supported versions

项目尚处于 v0.1.0 beta 阶段。安全修复只针对 `main` 和最新发布版本；更早的开发快照不
提供单独维护。

## Reporting a vulnerability

如果仓库已启用 GitHub Private Vulnerability Reporting，请优先通过仓库的 **Security**
页面私下报告。若该入口不可用，请先提交一个不包含漏洞细节和凭据的普通 issue，请求维护
者提供私密沟通渠道。

不要在公开 issue、PR、截图或日志中上传：

- QQ Cookie、密码、二维码缓存或真实账号。
- NapCat/OneBot Token、WebSocket 密钥或模型 API Key。
- 未脱敏的私聊正文、群号、用户 ID 或消息 ID。
- 能够定位个人 AstrBot 实例的完整配置和路径。

报告中可以安全提供：受影响版本、攻击前置条件、最小复现步骤、预期影响，以及移除账号、
消息 ID 和正文后的错误堆栈。请给维护者合理时间确认和修复后再公开细节。

## Security boundaries

本插件只允许固定 `/a info` 命令，校验输入，并严格匹配 Yurisaki sender、机器人 self ID
和请求时间窗口。它仍依赖 AstrBot、aiocqhttp/NapCat、QQ 和 Yurisaki 的安全性与可用性；
请保护这些系统的凭据并及时更新它们。
