# Security Policy

## Supported versions

安全修复针对 `main` 和最新发布版本；更早的开发快照不提供单独维护。

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

本插件不会向 Agent 暴露任意 Yurisaki 命令执行能力。当前只允许插件内部生成：

```text
/a info <validated query>
/a rand [validated difficulty]
```

Agent 不能控制目标 QQ、OneBot API 名称、任意 `/a` 子命令或 raw payload。查询输入经过
单行、长度和控制字符校验；随机筛选只接受已确认的标级与定数白名单。响应还会严格匹配
Yurisaki sender、机器人 self ID 和请求时间窗口。

`/a info` 的 Agent-facing 结果不会包含图片 URL 或 file 标识；随机曲目图片引用只用于向
原会话即时发送，并拒绝明显的 localhost、私有、回环和 link-local IP 目标。插件不会
自行解析 DNS 或下载图片，因此该检查是针对可信上游媒体引用的轻量防御，不是通用网络
代理安全边界。

插件仍依赖 AstrBot、aiocqhttp/NapCat、QQ 和 Yurisaki 的安全性与可用性；请保护这些
系统的凭据并及时更新它们。
