# Yurisaki Bridge for AstrBot

Yurisaki Bridge 是一个非官方第三方 AstrBot 插件，将 Yurisaki 的 Arcaea
曲目信息查询能力桥接为 AstrBot Agent Tool。本项目不代表 Yurisaki、AstrBot、
Arcaea 或 lowiro 的官方立场；使用外部服务时请遵守对应服务的规则。

## 当前状态

v0.1.1 已经完成离线检查、针对性实机回归和公开发布。当前 `main` 为 v0.2.0
开发版本，新增随机曲目 Tool 和原会话封面交付；正式发布前仍需完成一次媒体链路实机
回归。详细边界见
[`docs/REAL_INTEGRATION.md`](docs/REAL_INTEGRATION.md)。

当前支持：

- aiocqhttp / NapCat / OneBot v11。
- Yurisaki 私聊 `/a info` 查询。
- AstrBot Agent Tool `yurisaki_song_info(query)`。
- Yurisaki 私聊 `/a rand [标级或定数]` 与 Agent Tool
  `yurisaki_random_song(difficulty="")`。
- 曲名、别名或曲目 ID 查询，以及结构化结果和安全错误模型。

随机 Tool 支持无条件随机，也支持 Yurisaki 已定义的标级或谱面定数筛选；不支持曲包、
成绩或任意文本过滤。暂不支持 `/a chart`、其他 Yurisaki 命令或其他平台适配器。

## 前置条件

- AstrBot `>=4.17,<5`，使用 Python 3.12 或 3.13。
- 已连接的 aiocqhttp / NapCat 平台。
- 机器人 QQ 能够正常私聊 Yurisaki；默认账号为 `3889054356`。
- 已配置可使用 Tool 的 AstrBot Agent 和模型 Provider。

## 安装

在 AstrBot WebUI 的插件页面选择通过 URL 安装，并填写本仓库地址：

```text
https://github.com/i5-10500/astrbot_plugin_yurisaki_bridge
```

也可以克隆仓库后，从最新 `main` 生成本地安装包：

```powershell
git archive --format=zip --output astrbot_plugin_yurisaki_bridge-0.2.0.zip main
```

在 AstrBot WebUI 的插件页面选择本地文件上传该 ZIP。若旧版本安装失败，请先删除失败的
插件副本再重新上传。不要把 GitHub Token 填入 AstrBot 或第三方安装页面。

安装包的根目录必须直接包含 `main.py` 和 `metadata.yaml`，不能在 ZIP 内额外套一层目录。
如果曾安装 Probe 插件，必须先禁用，以免两个插件同时消费同一条私聊响应。

## 配置

- `enabled`：是否启用插件，默认启用。
- `yurisaki_user_id`：目标 Yurisaki QQ 号，默认 `3889054356`。
- `platform_id`：只有一个 aiocqhttp 平台时留空；多个平台时填写目标平台 ID。
- `timeout_seconds`：等待私聊响应的最长时间，默认 15 秒。
- `min_request_interval`：所有会话共享的最小请求间隔，默认 2 秒。
- `timeout_quarantine_seconds`：查询超时后的安静窗口，默认 5 秒；窗口内收到
  Yurisaki 消息会丢弃该消息并重新计时。
- `debug_logging`：仅排查连接问题时启用；日志不会记录私聊正文或机器人 QQ 号。

插件启动时会尝试连接；若 NapCat 尚未就绪，会在首次 Tool 调用时自动重试。

## Agent Tool

插件只公开以下受控 Tool：

```text
yurisaki_song_info(query)
yurisaki_random_song(difficulty="")
```

Agent 可以在回答 Arcaea 曲目信息问题时调用它。输入经过长度、换行和命令注入校验后，
插件只会生成：

```text
/a info <经校验的 query>
```

插件不提供任意 QQ 消息或 Yurisaki 命令执行入口。

`yurisaki_random_song(difficulty="")` 每轮用户请求最多执行一次。`difficulty` 留空时发送
`/a rand`；标级只接受 `1`–`12` 与 `8+`、`9+`、`10+`、`11+`，定数只接受
`1.0`–`7.5`（步长 `0.5`）与 `8.0`–`12.0`（步长 `0.1`）。例如 `8+` 是标级，
`8.0` 是定数。插件只会把白名单值附加到 `/a rand`，其他值返回 `invalid_filter` 且不会
发送 QQ 命令。

成功时，插件会即时把 Yurisaki 封面 URL 作为图片发送到发起 Tool 的原会话，再向 Agent
返回不含临时 URL/file 值的结构化歌曲信息。过滤响应中的曲名 `[...]` 后缀与单个难度、
物量、谱师字段按上游原文保留。Yurisaki 的已知纯文本错误会分别返回 `invalid_filter` 或
`no_matching_song`，不会被当成成功结果或触发图片发送。

## 工作原理

```text
Agent -> Tool -> QQ private -> Yurisaki -> Parser -> Tool Result -> Agent
```

入口层负责 AstrBot Tool、配置、响应拦截和生命周期；Service 负责输入校验与业务编排；
Transport 负责 OneBot 私聊、超时、限速和回调；Parser 将文本与 OneBot segments 转换为
结构化结果。`/a info` 和 `/a rand` 共享同一个 single-flight 与超时隔离状态。

Yurisaki 响应不包含原请求 request ID，因此所有会话共享全局 single-flight，同一时间只
允许一个在途查询。这会牺牲并发吞吐量，但可以避免不同用户的响应串台。查询超时后还会
进入可配置的全局隔离期；迟到响应会被丢弃并延长隔离期，安静窗口结束后才会发送下一条
命令。

## 常见问题

- **安装时报 `No module named 'yurisaki_bridge'`**：删除旧插件副本，重新安装 v0.1.1
  或更新版本。
- **找不到 aiocqhttp 平台**：确认 NapCat 已连接；多平台环境还要填写正确的
  `platform_id`。
- **无法发送私聊**：确认机器人 QQ 能主动私聊目标账号，并检查 NapCat 的连接状态。
- **查询超时**：确认 Yurisaki 在线且能回复 `/a info`，必要时适当增加
  `timeout_seconds`；超时后的新查询还会等待 `timeout_quarantine_seconds` 指定的
  安静窗口。
- **出现重复响应**：禁用 Probe 或其他监听同一 Yurisaki 私聊的插件，然后重载本插件。
- **随机曲目有文字但没有封面**：确认 NapCat 能访问 Yurisaki 图片 URL；插件仍会保留
  结构化文字结果，并把 `image_delivered` 标记为 `false`。
- **重连后仍不可用**：确认 AstrBot 已重新收到 aiocqhttp 平台连接，再发起一个新查询。

报告问题时请提供 AstrBot/NapCat 版本、脱敏错误行和 OneBot segment 类型，不要上传完整
日志、QQ Cookie、Token、二维码缓存、账号或未脱敏私聊内容。

## 隐私与安全

插件不会主动收集普通群友聊天正文。原始事件监听器只接受目标 Yurisaki 账号、当前机器人
账号和当前请求时间窗口同时匹配的私聊响应；超时隔离期内来自目标账号的迟到响应只会被
丢弃和拦截。响应正文只用于完成本次 Tool 调用。随机曲目图片 URL 只用于即时发送，不写入
日志或 Tool JSON，也不由插件下载或持久化。默认日志只记录必要元数据，不记录私聊正文。

更多报告要求见 [`SECURITY.md`](SECURITY.md)。

## 本地开发

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -m pytest
```

离线测试不会连接真实 QQ 或 Yurisaki。贡献流程见
[`CONTRIBUTING.md`](CONTRIBUTING.md)，版本记录见 [`CHANGELOG.md`](CHANGELOG.md)，
维护者发布流程见 [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)。

## 开发声明

本项目的代码、测试、文档与工程配置由 OpenAI Codex 在维护者监督下开发。仓库维护者负责
提出需求、确认产品方向，以及批准许可证、公开发布和外部服务操作。

## 许可证

Copyright (C) 2026 `i5-10500`。

本项目采用 GNU Affero General Public License v3.0 or later（SPDX：
`AGPL-3.0-or-later`）。你可以在该许可证条款下使用、修改和再发布；通过网络向用户提供
修改版服务时，还需要按许可证要求向这些用户提供对应源码。完整条款见 [`LICENSE`](LICENSE)。
