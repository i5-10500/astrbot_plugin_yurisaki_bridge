# Repository Guidelines

## 项目结构与模块组织

本仓库的 v0.1.1 和 v0.2.0 已公开发布。`main.py` 负责 AstrBot Tool、配置和生命周期；`yurisaki_bridge/` 按 `service.py`、`transport.py`、`parser.py` 和 `models.py` 分层；测试位于 `tests/`，脱敏 OneBot 样本位于 `tests/fixtures/`。真实联调步骤见 `docs/REAL_INTEGRATION.md`。不要复制或依赖 Probe 插件源码。

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

使用 4 空格缩进、类型注解和异步 I/O；避免阻塞式网络请求。模块、函数和变量使用 `snake_case`，类使用 `PascalCase`，常量使用 `UPPER_SNAKE_CASE`。入口层不得堆积 OneBot 解析逻辑。公开 Tool 仅使用受控接口 `yurisaki_song_info(query)` 和 `yurisaki_random_song(difficulty="")`，禁止暴露任意命令执行入口。

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
- 新配置 `timeout_quarantine_seconds` 默认 5 秒。
- v0.2.0 基础离线实现已完成：`yurisaki_random_song(difficulty="")`、受控 `/a rand`、随机响应 parser、
  原 caller 图片即时交付、同事件防重复调用及 URL/file 不进入 Tool JSON。
- `metadata.yaml` 和包版本已准备为 `0.2.1`；v0.2.1 只做文档一致性、数据最小化和轻量
  URL 安全加固，不增加业务命令。
- 维护者完成 v0.1.1 三项实机回归并全部通过。一次 Agent 最终回答出现 Tool JSON 与 `raw_text` 中均不存在的信息，归类为模型幻觉，不是插件响应串台；不要据此增加猜测性 parser 规则。
- 维护者已明确授权创建 annotated `v0.1.1` tag 和 GitHub Release；发布资产必须从 tag 重建并公开复核。
- annotated `v0.1.1` tag 和 GitHub Release 已创建；公开资产大小 36,243 字节，SHA-256 为 `8A942DF5476E1D4E873AD8F3DD8F2A1609944DC1D106620263A284D0DCA2D544`。
- 三次 `/a rand` 受限探测均确认单 event、`image → text`、无 reply、无延迟拆包；脱敏 fixture 已保存。
- v0.2.0 随机 Tool 仅允许空值或已确认的标级/定数白名单，内部只生成 `/a rand` 及一个
  白名单参数；图片只即时发送到原 Tool caller，Tool JSON 不得暴露临时 URL/file 值。
- 维护者已使用合并后测试包完成 v0.2.0 六项实机验收：无筛选、标级 `8+`、定数 `10.7`、
  非法值恢复、图片/响应拦截及 info/rand 串行均通过。验收包 SHA-256 为
  `46AA678B3E3DB84D231C00A297402A887B069875586F0F08690BD2554D1D3AA9`。
- 许可证为 `AGPL-3.0-or-later`，版权仅使用公开化名 `i5-10500`；不要写入维护者真实姓名。
- 维护者已删除 AstrBot Cloud 市场页面，当前开发周期不重新提交市场。不要在当前主机安装或配置 AstrBot/NapCat。
- annotated `v0.2.0` tag 和 GitHub Release 已创建；Tag 指向 `6a68467`，公开资产大小
  41,307 字节，SHA-256 为
  `D6A8CB46A345039F66D4BF77981A1E5599DD1511153C4D2C25F2AC38380C16EB`，未认证公开下载
  复核一致。
- `/a preview` 已明确放弃：真实链路仍会产生二次转码，OneBot 转发又只显示语音摘要。
  主线已通过 PR #31 恢复到 v0.2.0 功能范围；不得恢复 preview 探针、Tool、配置或规划。
- v0.2.1 将 `/a info` 的 Agent-facing 图片字段缩减为 `image_count`，内部 parser 仍保留
  ImageReference；`/a rand` 发送前拒绝 localhost 和明显的本地/私有 IP literal。
- v0.2.1 共 128 项本地测试、Ruff、Python 3.12/3.13 GitHub Actions 和三项真实 smoke
  test 全部通过；本次实机反馈未重复提供 AstrBot/NapCat 版本，也没有错误行。
- annotated `v0.2.1` tag 和 GitHub Release 已创建；Tag 指向 `2a834c0`，公开资产大小
  43,802 字节，SHA-256 为
  `529133C18177F66BB81EBF457DD065372AC6DBB67A868A12006A58B7BB34D4AF`，GitHub digest、
  本地 tag 构建和未认证公开下载三者一致。
- 项目在 v0.2.1 后进入 feature-complete、actively maintained 状态，只处理兼容性、
  可靠性、parser 韧性和已复现缺陷。

## 接下来要做

1. 项目当前进入 maintenance mode；没有新的 Yurisaki 命令开发计划。
2. 后续只在 Yurisaki 协议、AstrBot/NapCat API 变化或可靠复现缺陷时启动维护周期。
3. 不重新提交 AstrBot Cloud 市场；任何后续 Tag/Release 仍需维护者单独授权。

维护者已授权：普通开发修复在本地测试和 CI 通过后自动提交、创建 PR 并合并，无需再次确认。不得自动发布新的 GitHub Release。
