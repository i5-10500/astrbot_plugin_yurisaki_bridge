# Contributing

感谢你改进 Yurisaki Bridge。提交修改前，请先确认它保持受控 Tool、安全日志和离线可测试
这三个边界。

## 开发环境

要求 Python 3.12 或 3.13：

```bash
git clone https://github.com/i5-10500/astrbot_plugin_yurisaki_bridge.git
cd astrbot_plugin_yurisaki_bridge
python -m venv .venv
python -m pip install -r requirements-dev.txt
```

Windows PowerShell 可以使用 `.venv\Scripts\Activate.ps1` 激活环境。

## 提交前检查

```bash
ruff check .
ruff format --check .
python -m pytest
```

测试必须保持离线，不得登录 QQ、连接真实 NapCat 或请求 Yurisaki。新增缺陷修复必须附带
回归测试；未知 OneBot 字段应能降级处理，并保留用于诊断的 `raw_text`。

## 设计约束

- 公开接口保持为受控的 `yurisaki_song_info(query)` 与
  `yurisaki_random_song(difficulty="")`，不要增加任意命令执行入口。
- 不要复制、导入或依赖 Probe 插件源码。
- OneBot 解析放在 `yurisaki_bridge/`，不要堆积到 `main.py`。
- 网络 I/O 必须异步，并正确处理超时、取消和插件热重载。
- 新 transport 必须在隔离的真实环境中验证。
- 当前没有增加其他 Yurisaki 命令的计划；曲目 preview 音频也已明确列为 non-goal。
- 真实 QQ/Yurisaki 联调不得进入 CI。

## Commit 与 Pull Request

使用清晰的 Conventional Commit，例如：

```text
fix: reject stale private responses
feat: parse additional song fields
docs: clarify NapCat setup
```

PR 应说明目的、主要改动、测试结果和兼容性影响；涉及配置或界面时提供脱敏示例。请保持
改动范围集中，不要顺带格式化或重写无关文件。

## 隐私要求

绝不提交或粘贴以下内容：

- QQ Cookie、账号密码或登录二维码缓存。
- NapCat/OneBot Token、WebSocket 密钥或模型 API Key。
- 真实 QQ 号、群号、消息 ID 或未脱敏私聊日志。
- 本地 AstrBot `data/`、配置、数据库或日志目录。

Bug 报告应包含 AstrBot/NapCat 版本、最小复现步骤、脱敏错误行和 OneBot segment 类型。
安全问题请按 [`SECURITY.md`](SECURITY.md) 报告。
