# 更新记录

本文档记录 CustomerServiceAgent 项目的主要变更，按日期归档。

---

## 2026-05-27

### 对话命令与策略

- `app/dialogue_understanding/commands/base.py`、`app/dialogue_understanding/commands/answer_commands.py`、`app/dialogue_understanding/commands/flow_commands.py`、`app/dialogue_understanding/commands/session_commands.py`、`app/dialogue_understanding/commands/slot_commands.py`：补全命令体系实现与注册/执行逻辑，统一命令分发与处理流程。
- `app/dialogue_understanding/commands/error_commands.py`：新增错误类命令实现，补充异常场景下的可执行命令行为。
- `app/policies/policy_ensemble.py`：完善策略编排入口与路由逻辑，统一策略集成执行方式。
- `app/policies/base_policy.py`：补充同步预测循环注释与基础行为细节，提升策略基类可读性。

### 槽位与状态

- `app/core/slots.py`：重构槽位类型解析逻辑，简化 `create_slot/from_dict` 路径并统一槽位类型到类实例映射实现。
- `app/core/tracker.py`：小幅修正状态追踪逻辑，保持与命令处理链路一致。

### 配置与依赖

- `app/shared/config.py`、`app/shared/exceptions.py`：扩展配置与异常定义，支持新增命令/策略链路所需常量与错误类型。
- `pyproject.toml`、`uv.lock`：补充并锁定 `jieba`、`neo4j`、`neo4j-graphrag`、`langchain-anthropic` 等依赖，确保本地环境与项目声明一致。

---

## 2026-05-26

### 策略与流程编排

- `app/policies/base_policy.py`：补全策略基类实现，增加统一的异步/同步预测入口与基础能力（`should_predict`、`does_support_stack_frame`、`train/persist/load` 占位）。
- `app/policies/flow_policy.py`：完善 Flow 执行主流程与槽位作用域重置逻辑，增强 flow 完成态处理和步骤推进控制。
- `app/policies/enterprise_search_policy.py`：补充企业检索策略主干能力，扩展降级链路、Pattern 记录与异常分支处理。
- `app/dialogue_understanding/flow/flow_executor.py`：新增 `advance_step` 与 `set_flows`，支持外部策略推进步骤和动态切换 flow 集合。
- `app/core/tracker.py`：新增 `record_pattern()`，将内置 Pattern 执行记录纳入 `flow_history` 统一观测。

### LLM 与检索

- `app/shared/llm/base_client.py`、`app/shared/llm/langchain_client.py`、`app/shared/llm/__init__.py`：增强 LLM 客户端抽象与实现，补充 `anthropic` 支持并统一导出接口。
- `app/retrieval/base_retriever.py`：补全检索器基类结构，统一检索层对接契约。
- `app/shared/exceptions.py`：扩展 LLM/检索相关异常类型，便于上层策略按错误类型处理。

### 配置与提示词

- `app/shared/config.py`：新增 `PromptConfig` 与降级原因配置，集中管理提示词目录、提示词文件名及默认文案。
- `app/shared/load_prompt.py`：新增简化提示词加载函数 `load_prompt()`，按配置读取 `.prompt` 文件并返回字符串。
- `docs/prompts/rag_prompt.prompt`、`docs/prompts/chitchat_prompt.prompt`：新增检索问答与闲聊提示词模板文件。

### 规则

- `.cursor/rules/changelog-on-commit.mdc`：更新提交流程规则，默认执行 `commit + push`，并保留“用户可显式要求仅 commit”的覆盖行为。

---

## 2026-05-25

### 配置与共享模块

- `app/shared/config.py`：`get_settings/reload_settings/settings` 返回类型统一为 `Settings` 实例，配置访问改为属性风格，提升 IDE 自动补全与类型提示效果。
- `app/core/domain.py`、`app/core/slots.py`、`app/core/tracker.py`、`app/shared/logger.py`：同步从字典下标访问切换为 `settings.xxx` 属性访问，适配强类型配置对象。
- `app/shared/yaml_loader.py`：新增 YAML 工具函数集合（文件/字符串读取、多文档读取、合并与深度合并），并统一使用 `safe_load` 解析。

### 对话流程

- `app/dialogue_understanding/flow/flow.py`：补充 `FlowStep`、`Flow`、`FlowsList` 数据结构与序列化/反序列化能力，完善 Flow 运行时模型定义。
- `app/dialogue_understanding/flow/flow_loader.py`：新增 Flow 加载器，支持单文件、目录与字符串加载，并统一转换为 `FlowsList`。
- `app/dialogue_understanding/flow/flow_executor.py`：新增 Flow 执行器与执行结果模型，补充步骤分派、条件计算、子流程调用与槽位收集流程控制。
- `app/core/tracker.py`：补充 `start_flow/end_flow/cancel_flow`，将 Flow 生命周期与 `dialogue_stack` 状态联动，记录 Flow 历史。
- `app/dialogue_understanding/flow/flow.py`：新增 `get_first_step()` 作为执行器获取入口步骤的统一方法。

### 规则

- `.cursor/rules/changelog-on-commit.mdc`：规则描述更新为“按 commit 次数归档”的表述与示例，便于后续按新约定维护。

---

## 2026-05-24

### 配置与加载

- `config/config.yaml`：新增统一配置源，集中维护 `env_keys/defaults/env_bindings/actions/mysql` 等配置段。
- `app/shared/config.py`：重构为纯 `dataclass` 配置模型（`Settings`、`MysqlConfig` 等），移除旧的动态对象兼容别名。
- `app/shared/yaml_loader.py`：实现 YAML 读取、`env_bindings` 覆盖、`get_settings/reload_settings/settings` 缓存加载入口。
- `app/shared/constants.py`、`app/shared/__init__.py`：统一导出 `Settings` 与新的配置加载入口，清理旧别名。
- `app/shared/utils.py`：沉淀环境变量解析辅助函数（布尔值与运行环境解析）。
- `app/shared/config.py`：进一步合并加载逻辑，直接使用 OmegaConf Structured Config + `${oc.env:...}` 环境变量插值。
- `app/shared/yaml_loader.py`、`config/config.yaml`：移除独立 loader 与外部 YAML 文件，配置默认值统一内聚到 `config.py`。
- `.env.example`：变量命名与新插值方案对齐（`DB_HOST/DB_PORT/DB_USER/...`）。

### 存储模块

- `app/core/stores/tracker_store.py`：补充 TrackerStore 抽象接口与创建/查询辅助流程，明确基类行为。
- `app/core/stores/json_store.py`：实现 JSON 文件存储后端（保存、读取、删除、枚举、关闭）。
- `app/core/stores/mysql_store.py`：实现 MySQL 存储后端初始化与 CRUD，支持 MySQL upsert 和异步上下文关闭连接。

### 核心与共享模块

- `app/core/domain.py`、`app/core/tracker.py`、`app/core/slots.py`：补充/优化注释与配置引用方式，统一从 `yaml_loader.settings` 读取运行配置。
- `app/shared/logger.py`：切换到新配置加载入口，日志环境参数由 `settings` 提供。
- `app/shared/exceptions.py`：补充统一异常定义，完善存储与配置相关异常表达。
- `app/core/domain.py`、`app/core/tracker.py`、`app/core/slots.py`、`app/shared/logger.py`：配置读取入口改为 `app.shared.config`，并统一字典下标访问风格。

### 对话栈与文档

- `app/dialogue_understanding/stack/stack_frame.py`：抽取父类通用 `from_dict`，移除重复子类实现；`from_dict` 改为 Python 3.12 泛型签名。
- `app/dialogue_understanding/stack/dialogue_stack.py`：补充核心实现与字符串表示，完善栈操作可读性。
- `README.md`：重写 4.3 栈帧类型图，合并说明与属性展示并适配 Mermaid 渲染兼容性。

### 规则

- `.cursor/rules/docstring-on-function-and-class.mdc`：新增全局规则，要求新增/修改函数和类时必须补充功能注释。

---

## 2026-05-23

### 日志与配置

- 新增 `app/shared/logger.py`：基于 **loguru** 的全局日志单例
  - 控制台彩色输出 + 文件双写（`LOG_ENABLE_FILE` 控制）
  - 按日目录 `logs/yyyy-MM-dd/yyyy-MM-dd_NNN.log`，配套 `.jsonl`、`debug.log`（7 天）、`error.log`（60 天）
  - 午夜或 10MB 轮转；支持 `session_id`、`trace_id`、`port`、`path`、`method` 等 **contextvars** 上下文
  - 提供 `set_log_context`、`log_context`、`new_trace_id`、`mask_sensitive`、`get_logger` 等 API
- 扩展 `app/shared/constants.py`：集中环境变量键名、默认值与运行时解析（`APP_ENV`、`LOG_LEVEL`、`LOG_ENABLE_FILE`、`SERVICE_NAME`）
- `app/shared/__init__.py`：导出日志与配置相关符号
- 依赖：`pyproject.toml` / `uv.lock` 增加 `loguru>=0.7.3`
- `.gitignore`：忽略 `logs/` 目录
- `docker-compose.prod.yml`：生产环境变量 `APP_ENV=prod` 与 constants 别名对齐

### 核心模块实现

- `app/core/tracker.py`：实现 `UserMessage`、`DialogueStateTracker` 及状态更新逻辑（槽位、对话历史、Flow 上下文等），含中文注释说明
- `app/core/slots.py`：槽位数据类与 `create_slot` 工厂，使用 `@dataclass` 与 `field(default_factory=...)`
- `app/agent/actions.py`：Action 系统完整实现（`Action` 基类、`ActionResult`、内置动作与注册表等）
- `app/core/stores/tracker_store.py`：暂为空文件，存储接口实现待后续补充

### 文档

- `README.md`：补充模块关系 Mermaid 图、Tracker 多轮对话流程图（§2.3.1）、槽位系统说明、Docker 部署步骤
- 新增 `docs/excute.sql`：ECS 演示库建表与示例数据脚本（`ecs` 库：区域、物流、订单等）

### 仓库与演示数据

- 从版本库移除 `ecs_demo/`（已在 `.gitignore` 中忽略，仅本地保留用于联调）
- 已暂存删除：`ecs_demo/actions`、`addons`、`config.yml`、`data`、`endpoints.yml` 等

---

## 2026-05-22

### 项目初始化（提交 `59782d0`）

- 使用 **uv** 初始化 Python 3.12 项目：`pyproject.toml`、`uv.lock`、`.python-version`
- 配置运行时依赖：LangChain / LangGraph、FastAPI、SQLAlchemy、DashScope 等；开发依赖：pytest、ruff、mypy
- CLI 入口：`csa = app.__main__:main`，`[tool.setuptools.packages.find] include = ["app*"]`
- 搭建 `app/` 全量目录骨架（约 80+ 模块文件，含 agent、core、dialogue_understanding、policies、channels、training 等）
- 新增 `main.py` 备用入口

### 部署与运维

- `Dockerfile`：多阶段构建，`uv sync --frozen --no-dev`，非 root 用户运行
- `docker-compose.prod.yml`、`.dockerignore`、`.env.example` 环境变量模板
- `.gitignore`：排除 `.venv`、`.env`、`__pycache__` 等

### 文档与演示

- 首版 `README.md`：项目目录结构说明与架构规划
- 纳入 `ecs_demo/` 占位配置（后续已移出版本库，改本地忽略）
- `docs/__init__.py` 占位

### 远程仓库

- 首次提交并推送至 GitHub：`main` 分支，`chore: initialize customer service agent scaffold`

### 环境与联调（未全部入库）

- 配置 GitHub SSH 远程、`~/.cursor` MCP 与云服务器 MySQL（SSH 隧道 `127.0.0.1:3307`）等开发环境
- `ecs_demo` 测试数据文件名清理；演示库表数据通过隧道验证可读

---

## 说明

- 日常运行产生的 `logs/` 不纳入版本控制。
- `ecs_demo/` 仅作本地 Rasa/Flow 联调，不提交到 Git。
