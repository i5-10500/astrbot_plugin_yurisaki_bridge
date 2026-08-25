# 真实环境集成测试

本文只描述当前 `AstrBot → NapCat → Yurisaki → Tool Result → Agent` 链路的验收方法。
历史测试结果和发布资产记录由 Git history、CHANGELOG 与 GitHub Releases 保存。

## 支持环境与安全准备

- AstrBot `>=4.17,<5`，Python 3.12 或 3.13。
- aiocqhttp / NapCat / OneBot v11 平台已经连接。
- 测试机器人能够正常私聊 Yurisaki；默认服务账号从插件配置读取。
- AstrBot 已配置可使用 Tool 的 Agent 和模型 Provider。

使用专门的测试 QQ。不要把 QQ 密码、Cookie、二维码、OneBot Token、模型 API Key、群号、
消息 ID、完整日志或未脱敏私聊正文发送给维护者或提交到仓库。

## 安装待验收版本

正式版本优先从 [GitHub Releases](https://github.com/i5-10500/astrbot_plugin_yurisaki_bridge/releases)
下载 ZIP。开发候选版本应从准备验收的明确 commit 构建：

```powershell
git archive --format=zip --output astrbot_plugin_yurisaki_bridge-<version>.zip <commit>
```

在 AstrBot 插件页面上传 ZIP。包根目录必须直接包含 `main.py` 和 `metadata.yaml`。删除或禁用
旧插件副本，并禁用任何监听同一 Yurisaki 私聊的 Probe 插件。插件配置保持
`enabled=true`；只有一个 aiocqhttp 平台时，`platform_id` 留空。

## 基础加载检查

1. 重载插件，确认 AstrBot 没有导入、配置或生命周期错误。
2. 在插件页确认显示版本与 `metadata.yaml` 一致。
3. 确认 NapCat/aiocqhttp 已连接，插件可以找到唯一目标平台。

如果本次只改文档和版本来源，完成这组检查即可作为最小真实 smoke test。修改任何 runtime
Python 行为后，还必须执行下面的 Tool 和可靠性场景。

## Song info

请求一首已知曲目的信息或别名解析，例如让 Agent 查询 `synthesis`：

- Agent 只调用一次 `yurisaki_song_info(query)`。
- 用户会话中不出现内部 `/a info ...` 命令或 Yurisaki 原始私聊回复。
- Tool Result 正常包含曲名、难度等业务字段以及 `raw_text`。
- `image_count` 可以存在，但结果不得包含图片 URL、file 标识或临时媒体值。
- Yurisaki 回复不会触发 Bot-to-Bot 自动回复循环。

## Random song

先请求一次无筛选随机曲目，再请求一个已支持的标级或定数筛选：

```text
yurisaki_random_song(difficulty="")
yurisaki_random_song(difficulty="10.7")
```

确认：

- 无筛选请求发送固定 `/a rand`，筛选请求只附加白名单值。
- 曲绘只发送到发起 Tool 的原会话，并且只发送一次。
- Tool Result 包含正确歌曲字段、`filter`、`image_count` 和 `image_delivered`。
- Tool JSON 和日志不包含临时图片 URL 或 file 标识。
- 合法真实 CDN 没有被图片 URL 安全检查误伤。
- 已知上游无结果时返回稳定错误，不发送图片。

同一 Agent event 中，一个通过校验且插件已启用的随机请求只有一次执行机会；即使上游或
transport 失败，也不会在同轮自动重试，以避免规划循环重复发图。用户可以在下一条消息中
再次请求。

## Transport 与生命周期回归

涉及 transport、事件匹配、超时或生命周期的修改还要验证：

1. 同时发起 info 和 rand，确认两者通过全局 single-flight 串行完成且不串台。
2. 人为缩短 timeout 后发起查询，确认下一请求等待 quarantine；迟到响应不会污染新请求。
3. 暂时断开并恢复 NapCat，确认恢复后新请求正常且没有重复回复。
4. 查询中或 quarantine 等待期间重载插件，确认旧请求安全结束，callback 不重复注册。
5. 群聊和普通私聊中始终看不到内部命令或被消费的 Yurisaki 原始响应。

断开 NapCat 时，AstrBot 可能同时无法收到用户消息；这种情况下无法从用户侧触发 Tool，
`transport_unavailable`、`send_failed` 和 `timeout` 继续由离线测试覆盖。

## 反馈要求

通过时只需提供 AstrBot/NapCat 版本和各场景通过/失败。失败时再附最小复现步骤、脱敏错误
行和 OneBot segment 类型。不要提供完整日志、QQ 号、群号、消息 ID、正文、媒体 URL 或
任何凭据。
