# Windows 发布后验收

在本地构建产物目录执行（不访问网络，也不会启动 GUI）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_windows_release.ps1 -ReleaseDirectory .\dist\release -ExpectedCommit <commit>
```

`ExpectedVersion` 可省略，脚本会从 `app_version.py` 的版本单一来源读取。验证 GitHub 下载的 Release 时，先将全部发布附件下载到一个本地目录，再对该目录运行相同命令；不要把下载目录与历史构建目录混用。

脚本检查安装包、便携 ZIP、`SHA256SUMS.txt` 和 manifest，随后核对 manifest 的版本/提交、重新计算两份资产的 SHA256，并检查 ZIP 内的 `AI视频制作核验器.exe` 与 `_internal` 内容。GitHub Actions 的重建文件可能和本地构建哈希不同，因此应以**随发布附件提供的 `SHA256SUMS.txt`**为准。

默认还检查 `%LOCALAPPDATA%\AIVideoProductionVerifier\creator_history`。测试或不需历史检查时传入 `-SkipHistoryCheck`；指定其他目录使用 `-HistoryDirectory`。安装版检查可用 `-InstalledExecutable`，并可用 `-SkipInstalledAppCheck` 跳过。默认不会启动程序；只有明确传 `-LaunchInstalledApp` 才会启动。

PowerShell 5.1 对无 BOM UTF-8 的默认文本解码不是 UTF-8，因此脚本对 JSON 和文本读取始终显式使用 `-Encoding UTF8`，以保证中文路径与中文历史内容可靠。

退出码 `0` 且最后输出 `RELEASE_ACCEPTANCE_RESULT = OK` 表示全部检查完成。任何失败均输出错误、返回非零退出码，且绝不会输出该成功标记。

Windows PowerShell 5.1 的控制台 stdout/stderr 可能采用当前 Windows 代码页，因此自动测试先捕获原始 bytes，再安全解码；测试不假定控制台输出本身为 UTF-8。JSON 和文本文件读取仍明确指定 `-Encoding UTF8`。

`-InstalledExecutable` 会强制验证文件存在。FileVersion/ProductVersion 是可选增强检查：若缺失，脚本会给出非致命说明并继续；若可读取且规范化后与期望版本明确不一致，才会失败。
