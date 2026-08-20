# Repository Guidelines

## 项目结构与模块组织

本仓库已完成 Milestone 3 的离线实现。`main.py` 负责 AstrBot Tool、配置和生命周期；`yurisaki_bridge/` 按 `service.py`、`transport.py`、`parser.py` 和 `models.py` 分层；测试位于 `tests/`，脱敏 OneBot 样本位于 `tests/fixtures/`。真实联调步骤见 `docs/REAL_INTEGRATION.md`。不要复制或依赖 Probe 插件源码。

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

## 当前交接状态（2026-08-21）

- `main` 已同步 GitHub，当前提交为 `efac729`；PR #3（Tool/Service）和 PR #4（联调清单）已合并。
- `yurisaki_song_info(query)`、固定 `/a info` 命令、输入防注入、全局 single-flight、限速、超时、安全错误模型、严格 sender/self/time 匹配、响应拦截及热重载清理均已实现。
- 本地共 51 项测试通过；GitHub Actions 的 Python 3.12、3.13 检查通过。
- 当前停在 Milestone 4 真实联调。维护者明确使用另一台电脑已有的 AstrBot 环境；不要在当前主机重新安装或配置 AstrBot/NapCat。

## 维护者接下来要做

1. 在另一台电脑获取最新 `main`，可运行 `git archive --format=zip --output astrbot_plugin_yurisaki_bridge-test.zip main`，再从 AstrBot 插件页上传 ZIP。私有仓库不要向第三方页面提供 GitHub Token。
2. 禁用 Probe 插件；确认 aiocqhttp/NapCat 已连接，插件配置 `enabled=true`，Yurisaki ID 默认为 `3889054356`，单平台时 `platform_id` 留空。
3. 按 `docs/REAL_INTEGRATION.md` 的六项场景测试真实查询、响应拦截、并发、断线恢复和热重载。
4. 下次只反馈 AstrBot/NapCat 版本、各场景通过/失败、脱敏错误行，以及去除 QQ 号和消息 ID 的一条真实 `/a info` 文本与 OneBot segment 类型；不要提供完整日志或任何凭据。

后续代理应先根据真实测试结果诊断；有缺陷时增加回归测试后修复。联调全部通过后进入 Milestone 5（开源完善），但许可证必须等待维护者选择。维护者已授权：测试和 CI 通过后自动提交、创建 PR 并合并，无需再次确认。
