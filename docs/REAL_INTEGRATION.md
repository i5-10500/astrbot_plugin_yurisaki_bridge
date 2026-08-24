# Milestone 4 真实联调清单

本阶段验证 `AstrBot → NapCat → Yurisaki → Tool Result → Agent` 的真实链路。请使用专门的测试 QQ；不要把 QQ 密码、Cookie、二维码、OneBot Token、模型 API Key 或 GitHub Token 发到聊天、日志或仓库。

## 验收记录（2026-08-24）

维护者在另一台已有 AstrBot/NapCat 的电脑完成了真实联调：真实查询、命令拦截、原始响应
拦截、两次并发查询、重连恢复和查询中热重载均通过，Probe 插件未参与测试。首次上传曾因
入口使用顶层导入而出现 `No module named 'yurisaki_bridge'`，该问题已由 PR #6 的包内相对
导入修复，重新打包安装成功。

断开 NapCat 时，AstrBot 同时无法收到用户的查询消息，因此实机没有进入 Tool 并观察到
`transport_unavailable`、`send_failed` 或 `timeout`；重连后新查询正常，且没有迟到错误或
重复回复。断线错误模型继续由离线回归测试覆盖。AstrBot/NapCat 的具体版本未在本次反馈中
记录。

## 1. 准备隔离环境

Windows 推荐使用本机已有的 `uv` 安装 AstrBot，不需要 Docker：

```powershell
uv tool install astrbot --python 3.12
mkdir astrbot-integration
cd astrbot-integration
astrbot init
astrbot run --reload
```

浏览器访问 `http://localhost:6185`。首次用户名通常为 `astrbot`，随机密码只从启动日志读取，并应在登录后立即修改。按照 [AstrBot 官方 uv 部署文档](https://docs.astrbot.app/deploy/astrbot/package.html) 配置一个测试用模型 Provider；API Key 只在 WebUI 中填写。

## 2. 接入 NapCat

按照 [NapCat 官方 Windows Shell 文档](https://doc.napneko.icu/guide/boot/Shell) 安装并登录测试 QQ。在 NapCat WebUI 的“网络配置”中新建并启用 `WebSocket 客户端`：

```text
ws://127.0.0.1:6199/ws
```

在 AstrBot 的“机器人”页面创建 `OneBot v11 (QQ 个人号等)` 平台。若设置 Token，两端必须一致。确认 NapCat 显示已连接，并确认测试 QQ 能正常私聊 Yurisaki（默认账号 `3889054356`）。

## 3. 安装本地插件

仓库当前是私有仓库，不要把 GitHub Token 填入第三方安装页面。合并最新 `main` 后，在仓库根目录创建本地测试包：

```powershell
git archive --format=zip --output astrbot_plugin_yurisaki_bridge-test.zip main
```

在 AstrBot“插件”页面通过本地文件上传该 ZIP。若已安装 Probe 插件，必须先禁用；插件配置保持 `enabled=true`，只有一个 aiocqhttp 平台时将 `platform_id` 留空。

## 4. 验收场景

依次执行并记录结果：

1. 从另一个 QQ 向机器人询问一首 Arcaea 曲目的信息，确认 Agent 调用 `yurisaki_song_info` 并返回曲名、难度等结果。
2. 确认群聊或用户私聊中没有出现 `/a info ...` 命令。
3. 确认 Yurisaki 的原始私聊回复没有触发 AstrBot 再次自动回复。
4. 同时发起两次查询，确认请求串行完成且没有串台。
5. 暂时断开 NapCat，确认 Tool 返回 `transport_unavailable`、`send_failed` 或 `timeout`，恢复连接后可再次查询。
6. 查询进行中重载插件，确认旧请求安全结束，后续查询仍可用且没有重复回复。

## 5. 反馈给 Codex

请只提供：AstrBot/NapCat 版本、六项场景的通过或失败、脱敏后的相关错误行，以及一条去除 QQ 号和消息 ID 的真实 `/a info` 文本及其 OneBot segment 类型。不要提供完整日志；截图前遮盖账号、群号、Token 和模型密钥。
