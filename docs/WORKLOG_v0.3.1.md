# v0.3.1 工作记录

- 基线提交：`93ccc7877e64407950fbb85301ff68b33ee37ee1`（分支 `feature/v0.3.1`）。
- 背景：v0.3.0 发布后需要人工分别核对 GitHub Release、哈希、manifest、便携 ZIP、安装版与创作历史安全性，步骤易遗漏且编码行为不一致。
- v0.3.0 人工验收发现的问题：哈希核对、发布 metadata、ZIP 结构和历史 JSON/API Key 检查分散，且 PowerShell 5.1 读取 UTF-8 无 BOM 文件有误解码风险。
- 修改文件：新增 `scripts/verify_windows_release.ps1`、`tests/test_release_acceptance_script.py`、`docs/RELEASE_ACCEPTANCE_WINDOWS.md` 与本文档。
- 测试结果（人工审核修复后）：新增验收测试 `8 passed`；关联测试 `25 passed`；完整 pytest `245 passed`；`git diff --check` 通过。
- 尚未完成事项：人工审核；不提交、不推送、不创建标签或发布分支。

## 人工审核修复

- Windows PowerShell 5.1 控制台输出不能假定为 UTF-8；测试改为捕获原始 bytes，并依次尝试 UTF-8、系统首选编码和 `mbcs`，最后以替换字符兜底。
- JSON 文件读取仍明确指定 `-Encoding UTF8`，不依赖控制台代码页。
- 安装程序 FileVersion/ProductVersion 改为可选增强检查：没有版本资源不会阻止验收；可读取且明确不兼容时才失败。
- 补充仅缺失 release manifest 的失败测试，并保留中文路径、UTF-8 无 BOM 中文历史 JSON 与疑似 API Key 的隔离测试。

## v0.3.1-02 CI 验收门禁

- 修改 `.github/workflows/release-windows.yml`：在构建并生成安装包、Portable ZIP、SHA256SUMS 和 manifest 后，正式 Release 上传前运行 Windows 验收脚本。
- CI 使用工作流既有的 `VERSION` 环境变量和当前 `${{ github.sha }}`；跳过历史与安装版检查，只验证可重复构建的发布资产。
- 新增 `tests/test_release_workflow_acceptance.py`，覆盖 PowerShell 调用、必需参数、版本/提交来源、无绕过配置以及验收步骤先于正式上传。
- 测试结果：现有本地验收测试 `8 passed`；新增工作流测试 `2 passed`；关联发布测试 `29 passed`；完整 pytest `247 passed`。
