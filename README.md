# Yurisaki Bridge for AstrBot

Yurisaki Bridge 是一个非官方第三方 AstrBot 插件，通过 QQ 私聊调用 Yurisaki，并将 Arcaea 曲目信息作为结构化 Tool Result 返回给 Agent。本项目不代表 Yurisaki、AstrBot、Arcaea 或 lowiro 的官方立场。

## 开发声明

本项目的代码、测试、文档与工程配置完全由 OpenAI Codex 开发。仓库维护者负责提出需求、确认产品方向，以及批准许可证、公开发布和外部服务操作。

## 当前状态

Milestone 3 已完成：插件已注册受控工具 `yurisaki_song_info(query)`，并实现配置注入、输入校验、全局 single-flight、请求限速、超时处理、严格响应匹配和热重载清理。离线测试不会连接真实 QQ 或 Yurisaki；真实响应格式仍需在 Milestone 4 联调中校准。

插件不会提供任意 Yurisaki 命令执行能力。每次 Tool 调用只会生成：

```text
/a info <经校验的 query>
```

## 架构

```text
AstrBot Tool -> Service -> Transport -> Yurisaki
                         \-> Parser -> Structured Result
```

- `main.py`：AstrBot Tool、事件拦截、配置与生命周期入口。
- `yurisaki_bridge/service.py`：输入校验、业务编排和安全错误模型。
- `yurisaki_bridge/transport.py`：aiocqhttp 私聊、回调和 single-flight。
- `yurisaki_bridge/parser.py`：OneBot segments 与 `/a info` 结果解析。
- `tests/`：不连接真实外部服务的离线测试。

## 配置

安装到 AstrBot 后，在插件配置页确认：

- `yurisaki_user_id`：默认 `3889054356`。
- `platform_id`：仅有一个 aiocqhttp 平台时留空；多个平台时填写目标平台 ID。
- `timeout_seconds`：默认等待 15 秒。
- `min_request_interval`：默认全局间隔 2 秒。

插件启动时会尝试连接；若 NapCat 尚未就绪，会在首次 Tool 调用时自动重试。

真实环境验收请按 [`docs/REAL_INTEGRATION.md`](docs/REAL_INTEGRATION.md) 执行。仓库为私有状态时优先上传本地 ZIP，不要向第三方页面提供 GitHub Token。

## 本地开发

要求 Python 3.12 或 3.13。

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -m pytest
```

## 发布前待确认

项目许可证尚未确定。首次公开发布前必须完成真实环境联调与隐私检查，并由维护者选择许可证。严禁提交 QQ Cookie、Token、WebSocket 密钥、二维码缓存、真实私聊日志或其他账号凭据。
