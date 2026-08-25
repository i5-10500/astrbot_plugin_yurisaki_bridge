# 真实环境验收与回归测试

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

## Release 资产复验（2026-08-25）

维护者从公开 GitHub Release 安装 v0.1.0 资产，并在 AstrBot `4.25.1`、NapCat Core
`4.18.9` 环境完成发布后复验。插件加载、一次真实查询和热重载后三项检查全部通过，未再出现
`No module named 'yurisaki_bridge'`。

## v0.1.1 针对性回归（2026-08-25）

维护者使用本地 `astrbot_plugin_yurisaki_bridge-0.1.1.zip` 完成以下三项回归，全部通过：

1. 默认超时和 5 秒隔离期下，`synthesis` 正常返回，原始私聊回复仍被拦截。
2. 人为缩短超时后连续查询，旧回复没有污染新请求，新请求在安静窗口结束后正常完成。
3. 在新请求等待隔离期时重载插件，请求安全结束；恢复默认超时后查询正常且没有重复回复。

其中一次测试中，Agent 最终回答加入了所有 Tool 查询结果和 `raw_text` 中均不存在的信息；
同期 transport、解析和查询归属均正常，因此记录为模型最终回答幻觉，而非插件串台。诊断
类似问题时应先核对 Tool JSON，不应把模型自行补充的内容反向写入 parser 规则。

## `/a rand` 协议记录（2026-08-25）

维护者使用固定指令的受限探测包连续执行三次 `/a rand`。三次响应结构一致：

- 每次只有一个 OneBot private message event，3 秒观察窗口内没有延迟拆包。
- 每个 event 固定包含两个 segment，顺序为 `image → text`，没有 reply。
- image data 均包含 `file`、`file_size`、`sub_type`、`summary`、`url`；
  `file` 与 `url` 均有值。
- text 使用“为您推荐的曲目是：”前导行，随后为曲目、难度、物量、谱面设计、曲侧、
  艺术家、BPM、版本、上线日期和曲包字段。

脱敏 fixture 位于 `tests/fixtures/yurisaki_rand_response.json`；账号、消息 ID、时间戳和
媒体值均未保留。

维护者随后确认 `/a rand` 可选附加一个严格参数：整数及带 `+` 的值表示游戏内标级，
带一位小数的值表示谱面定数。过滤成功响应仍是相同的单 event `image → text` 结构，仅将
难度、物量等多难度字段收窄为单个值，并在曲名后以 `[...]` 标记难度。因此不需要再次
捕获媒体协议；离线 parser 使用合成响应覆盖该字段收窄行为，正式插件实测负责确认参数
传递及实际内容对应关系。

已知纯文本失败响应为“谱面定数应该在 [1.0, 12.0] 区间内。”和“没有找到符合条件的
曲目。”。parser 仅精确匹配这两个已确认文案，分别映射为 `invalid_filter` 与
`no_matching_song`，不使用容易误判的关键词规则。

## v0.2.0 针对性回归（2026-08-25）

维护者安装从合并后 `main` 生成的本地验收包，保持 Probe 插件禁用，并完成以下六项检查，
结果全部通过：

1. 用自然语言要求“随机一首 Arcaea”，确认 Agent 只调用一次
   `yurisaki_random_song(difficulty="")`，原会话先收到一张封面，随后收到与 Tool 数据
   一致的文字，Tool JSON 中 `filter` 为 `null`。
2. 确认群聊或私聊中不出现 `/a rand` 和 Yurisaki 原始回复，且封面不重复发送。
3. 要求“随机一首标级 8+ 的歌”，确认 Tool 传入 `difficulty="8+"`，结果
   `filter.type` 为 `level`，曲目和单难度字段确实满足 8+。
4. 要求“随机一首定数 10.7 的歌”，确认 Tool 传入 `difficulty="10.7"`，结果
   `filter.type` 为 `constant`，曲名含上游 `[...]` 难度标记，难度、物量和谱师均为单值。
5. 让 Tool 尝试 `difficulty="10.70"`，确认返回 `invalid_filter`、不发送 QQ 命令，随后
   同一轮改用 `10.7` 仍可正常调用。如果合法筛选恰好返回无曲目，确认错误类型为
   `no_matching_song` 且不发送图片。
6. 同时发起一次 `/a info` 和一次随机曲目请求，确认两者串行完成、结果不串台且随机封面
   只发到对应的原会话。

验收包大小为 41,095 字节，SHA-256 为
`46AA678B3E3DB84D231C00A297402A887B069875586F0F08690BD2554D1D3AA9`。本次没有报告
新的错误行、响应串台、重复图片、原始私聊泄漏或 Tool 参数兼容问题。两个已知上游错误的
精确分类继续由离线回归测试覆盖；实机过程中若自然遇到 `no_matching_song`，仍应保留
对应 Tool JSON 供复核。

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

## 3. 安装待验收版本

正式版本优先从对应 GitHub Release 下载 ZIP。开发中版本才从准备验收的提交或分支生成
本地安装包；不要把 GitHub Token 填入第三方安装页面：

```powershell
git archive --format=zip --output astrbot_plugin_yurisaki_bridge-<version>.zip <tag-or-commit>
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
