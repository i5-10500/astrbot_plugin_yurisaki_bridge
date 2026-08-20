# Yurisaki Bridge for AstrBot

Yurisaki Bridge 是一个非官方第三方 AstrBot 插件，计划通过 QQ 私聊调用
Yurisaki，并把 Arcaea 曲目信息作为结构化 Tool Result 返回给 Agent。本项目不代表
Yurisaki、AstrBot、Arcaea 或 lowiro 的官方立场。

## 开发声明

本项目的代码、测试、文档与工程配置完全由 OpenAI Codex 开发。仓库维护者负责提出
需求、确认产品方向，以及批准许可证、公开发布和外部服务操作。

## 当前状态

项目处于 Milestone 2：仓库脚手架、`/a info` 离线 Parser 和 aiocqhttp
single-flight Transport 已建立，尚未注册 AstrBot Tool。Parser 当前基于明确标注的
合成 OneBot fixture 开发，Transport 当前通过 mock 验证，真实响应兼容性将在联调阶段
校准。首个目标版本仅提供受控接口 `yurisaki_song_info(query)`，不会提供任意
Yurisaki 命令执行能力。

## 计划架构

```text
AstrBot Plugin Entry -> Service -> Transport -> Yurisaki
                              \-> Parser -> Structured Result
```

- `main.py`：AstrBot 注册与生命周期入口。
- `yurisaki_bridge/service.py`：输入校验、业务编排和错误模型。
- `yurisaki_bridge/transport.py`：aiocqhttp 私聊、回调及全局 single-flight。
- `yurisaki_bridge/parser.py`：OneBot segments 与 `/a info` 结果解析。
- `tests/`：不连接真实 QQ 或 Yurisaki 的离线测试。

## 开发

要求 Python 3.12 或 3.13。

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -m pytest
```

AstrBot 仅从 `requirements.txt` 安装运行时依赖；开发工具放在
`requirements-dev.txt`。真实联调必须在独立 AstrBot/NapCat 测试环境中完成，并禁用
Probe 插件。

## 发布前待确认

项目许可证尚未确定。首次公开发布前必须完成隐私检查，并由维护者选择许可证。
