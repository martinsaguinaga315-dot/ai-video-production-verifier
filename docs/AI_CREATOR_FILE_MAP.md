# AI Creator v0.3.0：仓库文件职责地图

审计日期：2026-08-01。审计对象为 `git ls-files` 的全部 80 个文件；结论基于实际内容、导入关系、工作流和打包配置，而不是文件名推断。

标记：**内核** = 已稳定的核验边界；**复用** = AI Creator 可调用但不应改写其职责；**可改**仅指 Phase 0 约束下是否允许修改。

| 路径（或明确文件组） | 当前职责、入口 / 调用方 | 主要依赖 | 内核 / 复用 / 可改 / 风险 | 对应测试 | 进入 Windows 产品 |
|---|---|---|---|---|---|
| `.env.example` | DeepSeek 环境变量示例；CLI `verify.py` 以 `load_dotenv()` 读取 | dotenv | 否 / 配置参照 / 否 / 高（密钥与兼容性） | `test_cli.py` 间接 | 否 |
| `.gitattributes`, `.gitignore` | 行尾与忽略规则 | Git | 否 / 否 / 否 / 中 | 无专测 | 否 |
| `.github/workflows/tests.yml` | Ubuntu 3.11：安装依赖、编译、pytest、两例 CLI 回归 | Actions、Python | 否 / CI 参照 / 否 / 高 | 工作流自身 | 否 |
| `.github/workflows/windows-build.yml`, `release-windows.yml` | Windows 构建 / 发布；目前分别固定 v0.2.0 分支和制品名 | Actions、Inno Setup | 否 / 未来需适配 / 否 / 高 | 构建脚本 | 否 |
| `LICENSE` | 分发许可证 | 无 | 否 / 继承 / 否 / 高 | 无 | 是 |
| `README.md`, `SKILL.md`, `CHANGELOG.md` | 产品说明、使用技能、版本记录 | 无 | 否 / 参照 / 否 / 中 | 无 | 否 |
| `app_version.py` | 应用名、英文名、`0.2.0` 版本的单一来源 | 无 | 否 / 未来读取 / 否 / 高（发布一致性） | 打包测试间接 | 是 |
| `desktop_app.py` | PyInstaller 与源码桌面入口，调用 `creator_desktop.app.run()` | `creator_desktop.app` | 否 / 未来入口扩展 / 否 / 高 | `test_desktop_distribution_paths.py` | 是 |
| `assets/app.ico`, `assets/app.png` | Windows 图标和图片资源（二进制，已作资源存在性审计） | PyInstaller | 否 / 继承 / 否 / 低 | 打包 smoke 间接 | 是 |
| `build_support/__init__.py` | 打包辅助包标记 | 无 | 否 / 否 / 否 / 低 | 无 | 构建时 |
| `build_support/generate_release_metadata.py`, `release_utils.py` | 产物 hash、manifest、敏感信息扫描 | `app_version`、pathlib | 否 / 继承 / 否 / 高（发布安全） | `test_packaging_utils.py` | 构建时 |
| `packaging/windows.spec` | PyInstaller 入口、数据文件、隐藏依赖；仅打包 assets/examples/LICENSE | PyInstaller | 否 / 未来加入新资源目录 / 否 / 高 | `test_desktop_distribution_paths.py` | 构建规则 |
| `packaging/build_windows.ps1` | 建 venv、pytest、CLI 回归、PyInstaller、便携包、安装包、扫描、manifest | Python 3.11、PS、Inno | 否 / 未来接入点 / 否 / 高 | `test_packaging_utils.py` | 是 |
| `packaging/package_portable.ps1`, `verify_build.ps1`, `installer.iss` | 便携包、冻结 EXE smoke、Inno 安装器 | PowerShell、Inno | 否 / 未来接入点 / 否 / 高 | `test_desktop_distribution_paths.py` | 是 |
| `requirements.txt` | 核心 Python 依赖：Pydantic、dotenv、OpenAI SDK | pip | 否 / 未来客户端受约束 / 否 / 高 | CI 安装 | 是 |
| `requirements-desktop.txt`, `requirements-dev.txt` | 桌面（CustomTkinter/keyring/docx）和开发（pytest/PyInstaller）依赖 | pip | 否 / 未来受约束 / 否 / 高 | CI/打包安装 | 是（desktop） |
| `models.py` | `ProjectFacts`、`DirectorOutput`、`VerificationReport` 及嵌套 Pydantic 合约 | Pydantic | **是** / 仅作为转换目标 / 否 / 极高 | 多数 `test_*` | 是 |
| `rules.py` | 确定性本地硬规则 `verify()` | `models` | **是** / 仅调用 / 否 / 极高 | `test_director_event_anchoring.py` 等 | 是 |
| `llm_audit.py` | 深度语义审计：预检、DeepSeek 请求、响应归一化、问题过滤 | OpenAI、models | **是** / 仅可选调用 / 否 / 极高 | `test_verification_service.py` 间接 | 是 |
| `verification_service.py` | 文件读取、模型校验、硬规则与可选语义审计编排、报告写出 | 核验内核 | **是** / AI Creator 最终调用 / 否 / 极高 | `test_verification_service.py` | 是 |
| `verify.py` | CLI 入口；加载 `.env`、调用服务、退出码/JSON 输出 | `verification_service` | 否 / 保持兼容 / 否 / 高 | `test_cli.py` | 是 |
| `creator_desktop/__init__.py` | 桌面包标记 | 无 | 否 / 是 / 否 / 低 | 无 | 是 |
| `creator_desktop/app.py`, `app_paths.py` | CustomTkinter 初始化、主窗体、资源 / 数据 / 日志目录、smoke 分支 | CTk、路径 | 否 / 未来 UI 容器 / 否 / 高 | `test_desktop_distribution_paths.py` | 是 |
| `creator_desktop/main_window.py` | 当前主窗体：模式切换、事件轮询、导入流程、核验、导出、日志 | CTk、controllers、views | 否 / Phase 9 再改 / 否 / 高 | `test_desktop_services.py`, `test_creator_workflow.py` | 是 |
| `creator_desktop/natural_language_view.py`, `facts_review.py`, `director_review.py`, `creator_result.py` | 当前“普通创作者”输入、事实确认、导演草案确认、结果/JSON 导出 UI | CTk、models | 否 / 交互经验可复用，组件不可直接承担生成器 / 否 / 高 | `test_natural_language_layout.py`, `test_facts_review.py` | 是 |
| `creator_desktop/analysis_controller.py` | 后台提取事实、解析导演文本、调用核验；队列事件，单任务互斥 | threading、现有 importer、service | 否 / 并发模式可参考 / 否 / 高 | `test_analysis_controller.py`, `test_creator_workflow.py` | 是 |
| `creator_desktop/verification_controller.py` | 专业 JSON 核验后台线程、队列事件、单任务互斥 | threading、service | 否 / 仅核验模式复用 / 否 / 中 | `test_desktop_services.py` | 是 |
| `creator_desktop/credentials.py`, `api_key_state.py`, `api_key_dialog.py` | Windows Credential Manager 密钥存储、无密钥 UI 状态、编辑/清除对话框 | keyring、CTk | 否 / 凭据访问可抽象复用 / 否 / 高（泄露风险） | `test_desktop_services.py` | 是 |
| `creator_desktop/ui_errors.py` | 对网络/服务/凭据异常的安全用户提示 | urllib、异常类别 | 否 / 错误文案映射可参考 / 否 / 中 | `test_desktop_services.py` | 是 |
| `creator_import/__init__.py` | 导入 / 结构化包标记 | 无 | 否 / 否 / 否 / 低 | 无 | 是 |
| `creator_import/file_reader.py`, `extraction_errors.py` | TXT/MD/DOCX/JSON 受限读取、公共导入异常 | docx、pathlib | 否 / 文件导入能力可复用（经新适配层） / 否 / 中 | `test_file_reader.py` | 是 |
| `creator_import/llm_client.py` | 当前 `DeepSeekClient.request_json()`：keyring/env、OpenAI SDK、45s、最多 2 次网络类重试 | OpenAI、credentials | 否 / 可作为 Phase 2 差距样本，不可直接扩写为生成客户端 / 否 / 高 | `test_creator_workflow.py` 间接 | 是 |
| `creator_import/prompt_templates.py` | 当前事实提取与导演“解析”提示词及 JSON 修复提示词 | models、compact models | 否 / 仅反向参照；不得放入新生成提示词 / 否 / 高 | importer 测试 | 是 |
| `creator_import/facts_extractor.py`, `director_parser.py` | 从用户已有文本提取 `ProjectFacts`、解析已有导演稿为 `DirectorOutput`，含有界修复 | models、rules、LLM client | **禁止耦合** / 只作为现有导入能力 / 否 / 极高 | `test_facts_extractor.py`, `test_director_parser.py`, `test_creator_input_adaptation.py`, `test_compact_director_parsing.py`, `test_sparse_director_normalization.py` | 是 |
| `creator_import/compact_director_models.py`, `json_cleanup.py`, `json_repair.py` | 精简导演草案合约、清洗 JSON、有界修复 | Pydantic、prompts | 否 / JSON 清洗思路可参考；模型不可污染 / 否 / 高 | `test_compact_director_parsing.py`, `test_json_cleanup.py`, `test_json_repair.py` | 是 |
| `examples/clean/{facts,director_output,verification_report}.json` | 通过的核验 fixtures / 示例 | models、CLI | 否 / 最终转换验收样本 / 否 / 中 | `test_cli.py`、workflow | 是 |
| `examples/unknown_character_error/{facts,director_output,verification_report}.json` | 失败的未知人物 fixtures / 示例 | models、CLI | 否 / 回归参照 / 否 / 中 | `test_cli.py`、workflow | 是 |
| `docs/MANUAL_ACCEPTANCE.md`, `RELEASE_CHECKLIST.md` | v0.2.0 手工验收和发布阻断说明 | 构建产物 | 否 / 未来验收格式可参考 / 否 / 中 | 人工 | 否 |
| `tests/test_analysis_controller.py` | 分析线程、事件与错误边界 | controller | 否 / 回归保护 / 否 / 中 | 自身 | 否 |
| `tests/test_cli.py` | CLI 参数、退出码、UTF-8 | verify/service | 否 / 回归保护 / 否 / 高 | 自身 | 否 |
| `tests/test_creator_input_adaptation.py`, `test_creator_workflow.py` | 当前文本导入、确认、解析、核验流程 | importer、desktop | 否 / 回归保护 / 否 / 高 | 自身 | 否 |
| `tests/test_compact_director_parsing.py`, `test_sparse_director_normalization.py`, `test_director_parser.py` | 精简导演草案、批次和补全/证据解析 | director parser | 否 / 回归保护 / 否 / 高 | 自身 | 否 |
| `tests/test_director_event_anchoring.py` | 导演文本的事实事件锚定与顺序 | parser、rules | 否 / 回归保护 / 否 / 高 | 自身 | 否 |
| `tests/test_facts_extractor.py`, `test_facts_review.py` | 事实提取和人工确认 UI | facts extractor/view | 否 / 回归保护 / 否 / 中 | 自身 | 否 |
| `tests/test_file_reader.py`, `test_json_cleanup.py`, `test_json_repair.py` | 文件安全读取、JSON 清洗/有界修复 | creator_import | 否 / 回归保护 / 否 / 中 | 自身 | 否 |
| `tests/test_desktop_distribution_paths.py`, `test_desktop_services.py`, `test_natural_language_layout.py` | 桌面路径、凭据、线程、UI 文案/隐私布局 | desktop | 否 / 回归保护 / 否 / 高 | 自身 | 否 |
| `tests/test_packaging_utils.py` | manifest、hash、敏感信息扫描 | build_support | 否 / 回归保护 / 否 / 高 | 自身 | 否 |
| `tests/test_verification_service.py` | 服务编排、临时 API key、错误脱敏、无语义模式不联网 | service | **是（保护）** / 必须保持通过 / 否 / 极高 | 自身 | 否 |

## 已确认的边界

可以复用的是：现有的密钥安全存储、受限文件读取、后台线程/队列交互模式、JSON 清洗经验，以及 **已确认后** 调用 `run_verification_models()` 的最终核验入口。

必须抽象、新建的内容：创作领域模型、阶段式管线、版本化提示词、具备取消/用量/统一错误分类的通用 AI 客户端、转换器、项目存储、AI Creator 控制器和视图。

不得耦合的内容：`rules.py`、`llm_audit.py`、`verification_service.py`、现有事实提取器和现有导演方案解析器。它们只能检查或解析既有材料，不能生成剧情、人物、场景、分镜或“修复后事实”。
