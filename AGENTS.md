# Repository Guidelines

## 项目结构与模块组织

本仓库的 v0.1.0 已公开发布；v0.1.1 离线实现已完成，等待针对性真实环境回归。`main.py` 负责 AstrBot Tool、配置和生命周期；`yurisaki_bridge/` 按 `service.py`、`transport.py`、`parser.py` 和 `models.py` 分层；测试位于 `tests/`，脱敏 OneBot 样本位于 `tests/fixtures/`。真实联调步骤见 `docs/REAL_INTEGRATION.md`。不要复制或依赖 Probe 插件源码。

## 构建、测试与开发命令

项目为 Python 插件，无独立编译步骤。脚手架完成后使用：

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
python -m pytest
ruff check .
ruff format --check .
```

`pytest` 运行离线测试；两个 `ruff` 命令分别检查代码质量和格式。真实 QQ/Yurisaki 联调不得纳入 CI，也不得依赖 Probe 已安装。

## 编码风格与命名规范

使用 4 空格缩进、类型注解和异步 I/O；避免阻塞式网络请求。模块、函数和变量使用 `snake_case`，类使用 `PascalCase`，常量使用 `UPPER_SNAKE_CASE`。入口层不得堆积 OneBot 解析逻辑。公开 Tool 使用受控接口 `yurisaki_song_info(query)`，禁止暴露任意命令执行入口。

## 测试规范

测试文件命名为 `test_*.py`，测试函数命名为 `test_<行为>`。使用 mock/fixture 覆盖解析、输入校验、超时、取消、错误发送者、热重载和全局 single-flight；并验证未知字段可降级处理且保留 `raw_text`。新增缺陷修复必须附回归测试。

## 提交与拉取请求

现有提交采用 Conventional Commit 风格，例如 `feat: add AstrBot song info tool`、`docs: add real integration checklist`。PR 应说明目的、主要改动、测试结果和兼容性影响，并关联 issue；涉及配置或用户界面时附示例或截图。

## 安全与配置

绝不提交 QQ Cookie、Token、WebSocket 密钥、二维码缓存、真实账号或未脱敏私聊日志。Yurisaki ID、超时和请求间隔应从配置读取。日志仅记录必要元数据；发布前检查 `.env`、日志和本地 AstrBot 数据未被跟踪。

## 当前交接状态（2026-08-25）

- v0.1.0 的真实查询、响应拦截、并发串行、NapCat 重连恢复和热重载均已在 AstrBot `4.25.1`、NapCat Core `4.18.9` 通过；公开 tag、Release 和安装资产已经复核。
- v0.1.1 新增全局超时响应隔离期：超时后下一请求等待安静窗口，迟到响应会被丢弃并重新计时；等待期间热重载可安全中断。
- v0.1.1 收紧解析成功条件：响应必须包含曲名或曲目 ID，以及至少一个其他已知字段；未知字段仍可容忍，失败结果仍保留 `raw_text`。
- 新配置 `timeout_quarantine_seconds` 默认 5 秒；`metadata.yaml` 和包版本均为 `0.1.1`。
- 本地共 64 项测试通过，`ruff check .` 和 `ruff format --check .` 通过；下一步等待 GitHub Actions 的 Python 3.12、3.13 检查及合并。
- 许可证为 `AGPL-3.0-or-later`，版权仅使用公开化名 `i5-10500`；不要写入维护者真实姓名。
- 维护者已删除 AstrBot Cloud 市场页面，当前开发周期不重新提交市场。不要在当前主机安装或配置 AstrBot/NapCat。

## 接下来要做

1. CI 与 PR 合并后，从合并后的 `main` 生成 `astrbot_plugin_yurisaki_bridge-0.1.1.zip`，检查包根目录和敏感残留。
2. 维护者在另一台电脑覆盖安装该 ZIP，按 `docs/REAL_INTEGRATION.md` 的“v0.1.1 针对性回归”测试正常查询、超时后连续查询和隔离期热重载。
3. 下次只反馈三项通过/失败，以及必要的脱敏错误行；不要提供账号、消息 ID、Token 或完整日志。
4. 实机回归通过前不要创建 v0.1.1 tag/Release，也不要开始 v0.2.0。

维护者已授权：普通开发修复在本地测试和 CI 通过后自动提交、创建 PR 并合并，无需再次确认。不得自动发布新的 GitHub Release。
