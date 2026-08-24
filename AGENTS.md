# Repository Guidelines

## 项目结构与模块组织

本仓库的 v0.1.0 实现和真实环境验收已完成。`main.py` 负责 AstrBot Tool、配置和生命周期；`yurisaki_bridge/` 按 `service.py`、`transport.py`、`parser.py` 和 `models.py` 分层；测试位于 `tests/`，脱敏 OneBot 样本位于 `tests/fixtures/`。真实联调步骤见 `docs/REAL_INTEGRATION.md`。不要复制或依赖 Probe 插件源码。

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

- 真实查询、命令与响应拦截、并发串行、NapCat 重连恢复和查询中热重载均在另一台电脑通过；Probe 插件未参与。详细结果和第五项的测试边界见 `docs/REAL_INTEGRATION.md`。
- 首次实机安装发现入口顶层导入导致 `No module named 'yurisaki_bridge'`；PR #6 已改为包内相对导入并增加 AstrBot 包加载上下文回归测试，修复提交已合并到 `main`。
- `yurisaki_song_info(query)`、固定 `/a info` 命令、输入防注入、全局 single-flight、限速、超时、安全错误模型、严格 sender/self/time 匹配、响应拦截及热重载清理均已实现。
- 本地共 55 项测试通过；GitHub Actions 的 Python 3.12、3.13 检查通过。
- 开源文档、issue 模板、隐私扫描、许可证和安装包精简已完成。维护者选择 `AGPL-3.0-or-later`，版权以公开化名 `i5-10500` 标识；不要写入维护者真实姓名。
- 公开发布前审计已完成，GitHub 仓库已设为 Public。annotated tag `v0.1.0` 和 GitHub Release 已创建，Release 资产 `astrbot_plugin_yurisaki_bridge-0.1.0.zip` 已从未登录公开地址下载复核；大小为 34,189 字节，SHA-256 为 `B78853014A4D7048DA902C573F497A5A32152BB80ADC4C6EC3529962FFBEF6A7`。
- 维护者已在 AstrBot `4.25.1`、NapCat Core `4.18.9` 环境安装公开 Release 资产；插件加载、一次真实查询和热重载三项复验全部通过。
- 官方市场清单中未发现同名、同 `plugin_id` 或同仓库记录；仓库侧 metadata 和发布资产检查通过。不要在当前主机安装或配置 AstrBot/NapCat。

## 接下来要做

1. 当前官方流程要求维护者登录 `https://cloud.astrbot.app/publish`，提交仓库 URL `https://github.com/i5-10500/astrbot_plugin_yurisaki_bridge`；不得索取、记录或共享 AstrBot Cloud 登录凭据。
2. Cloud 提交后记录其创建的审核链接，继续跟进自动检查和审核意见；有缺陷时增加回归测试后修复。
3. 后续代码改动继续执行 `docs/RELEASE_CHECKLIST.md` 中适用的检查，并为新版本重新生成安装 ZIP。

维护者已授权：普通开发修复在本地测试和 CI 通过后自动提交、创建 PR 并合并，无需再次确认。不得自动发布新的 GitHub Release。v0.1.0 市场提交已获授权，但必须由维护者本人在 AstrBot Cloud 登录页面完成最终提交。
