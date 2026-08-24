# 发布前检查路线

本路线用于公开仓库、创建 Git tag/GitHub Release 和提交 AstrBot 插件市场之前的每个版本。
各阶段按顺序执行；任一阻断项失败时停止发布，修复并重新运行相关检查。

## 1. 确认发布范围

- 确认 `main` 与 `origin/main` 同步且工作区干净。
- 确认 `metadata.yaml`、`yurisaki_bridge.__version__`、CHANGELOG 和目标 tag 的版本一致。
- 确认公开、创建 tag/Release、提交插件市场分别获得维护者授权。
- 确认真实环境支持范围和已知限制已经写入 README。

## 2. 清理开发与测试遗留

- 搜索并移除面向用户文档中的候选版、私有仓库、测试 ZIP、旧提交号和里程碑措辞。
- 确认没有 `TODO`、`FIXME`、临时调试入口、占位 URL 或任意命令执行接口。
- 确认 `.env`、日志、数据库、缓存、虚拟环境、本地 AstrBot/NapCat 数据和 ZIP 未被跟踪。
- 安装包名称使用版本号，不使用 `test`、`debug`、`temp` 或 `dev` 后缀。

## 3. 安全、隐私与来源审计

- 扫描当前文件和完整 Git patch 历史中的 Token、API Key、私钥、Cookie 与本机绝对路径。
- 扫描历史文件名，确认没有删除后仍留在 Git 对象中的配置、日志、数据库或密钥文件。
- 检查 commit author/committer，仅使用批准的公开化名和 GitHub noreply 邮箱。
- 扫描即将公开的 Actions 日志、PR/Issue 正文及评论。
- 核对 webhook、deploy key、Actions secret、environment 和 artifact；不保留不明外部连接。
- 确认 fixture 为合成或脱敏数据，且项目不复制或依赖 Probe 插件源码。

## 4. 许可证与社区文件

- 确认完整 `LICENSE` 存在，README 的 SPDX 标识和版权化名正确。
- 确认所有分发源码保留 SPDX 版权与许可证标识。
- 确认 README 包含免责声明、安装、配置、Tool、限制、排错、隐私和许可证。
- 确认 CONTRIBUTING、SECURITY、CHANGELOG 和脱敏 Bug Report 模板存在。

## 5. 代码质量与离线验证

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
```

- Python 3.12、3.13 的 GitHub Actions 必须通过。
- 外部 GitHub Actions 固定到来自官方仓库 release tag 的完整 commit SHA，并由
  Dependabot 定期检查更新。
- 测试只能使用 mock/fixture，不得连接真实 QQ、NapCat 或 Yurisaki。
- 新缺陷修复必须有回归测试；真实协议变化还要完成隔离实机复测。

## 6. 安装包验证

```powershell
git archive --format=zip --output astrbot_plugin_yurisaki_bridge-<version>.zip <tag-or-commit>
```

- ZIP 根目录直接包含 `LICENSE`、`main.py`、`metadata.yaml`、`_conf_schema.json`、
  `requirements.txt` 和 `yurisaki_bridge/`。
- ZIP 不包含 `.git`、`.github`、tests、AGENTS、开发依赖、缓存、本地数据或其他 ZIP。
- ZIP 小于 AstrBot 插件市场的 16 MB 上限，并记录 SHA-256。

## 7. 公开仓库门禁

- 默认分支为 `main`，无开放 PR，无未合并远程开发分支，无意外 tag/Release。
- GitHub 仓库描述、topics、Issues、许可证识别和安全报告入口正确。
- 复核公开仓库会暴露完整代码、提交历史、PR 和 Actions 日志。
- 切换为 Public 后，从未登录视角验证仓库与 README 可访问，并查看 GitHub secret scanning 结果。

## 8. Tag、Release 与插件市场门禁

- 公开仓库验证完成后，单独确认创建签名或 annotated `v<version>` tag。
- 从该 tag 重建 ZIP，核对 SHA-256，并在 GitHub Release 记录变更、兼容范围和安装说明。
- 用干净 AstrBot 环境安装 Release 资产；通过后再单独授权提交 AstrBot 插件市场。
- 市场记录的 author、name、version、repo 和安装包内 `metadata.yaml` 必须一致。
