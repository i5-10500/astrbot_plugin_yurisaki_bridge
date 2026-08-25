# Repository Guidelines

## 项目定位

Yurisaki Bridge 是 AstrBot 与 Yurisaki 之间的受控 QQ/OneBot Bridge。公开 Agent Tool 仅有
`yurisaki_song_info(query)` 和 `yurisaki_random_song(difficulty="")`；不提供任意
Yurisaki 命令、目标 QQ、OneBot API 或 raw payload 代理。

## 仓库结构

- `main.py`：AstrBot Tool、配置、响应拦截和生命周期。
- `yurisaki_bridge/`：service、transport、parser 和结果模型。
- `tests/`：离线回归测试与脱敏/合成 fixture。
- `docs/INTEGRATION_TESTING.md`：当前真实环境验收方法。
- `docs/PROTOCOL_NOTES.md`：长期有效的 Yurisaki/OneBot 协议事实。

正式插件不得复制、导入或依赖 Probe 插件源码或运行状态。

## 开发与质量检查

使用 Python 3.12 或 3.13、4 空格缩进、类型注解和异步 I/O。模块、函数和变量使用
`snake_case`，类使用 `PascalCase`，常量使用 `UPPER_SNAKE_CASE`。

```bash
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -m pytest
```

测试必须离线；新增缺陷修复必须附回归测试。真实 QQ/Yurisaki 联调不得进入 CI。

## 核心设计约束

- 插件内部只生成经过校验的 `/a info` 和白名单化 `/a rand` 命令。
- 所有 Tool 共享 global single-flight transport；Yurisaki 没有 request ID，禁止按 Tool
  或会话拆锁。
- timeout 后必须进入全局 quarantine，丢弃并隔离迟到响应。
- raw callback、pending request 和 consumed marker 必须在热重载与 shutdown 时安全清理。
- parser 保持宽容但不得把任意非空文本误报为成功；未知字段仍保留在 `raw_text`。
- 不在入口层堆积 OneBot 解析逻辑，不修改 AstrBot 或 NapCat Core。
- 不重新实现 `/a preview`；当前也没有新增其他 Yurisaki 命令的计划。

## 隐私与安全

绝不提交 QQ Cookie、Token、WebSocket 密钥、二维码缓存、真实账号、群号、消息 ID、未脱敏
私聊日志或本地 AstrBot/NapCat 数据。fixture 必须合成或严格脱敏。日志只记录必要元数据，
不得记录私聊正文、媒体引用或机器人 QQ 号。许可证为 `AGPL-3.0-or-later`，版权仅使用
公开化名 `i5-10500`。

## Git 与维护状态

使用 Conventional Commit，PR 说明目的、改动、测试和兼容性影响。不要 force push、改写
公开历史或移动已发布 Tag。The planned feature set is complete. Future work focuses on
maintenance, compatibility, reliability, security, documentation, and bug fixes.
