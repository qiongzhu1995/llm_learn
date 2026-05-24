# 更新记录

本文档记录 CustomerServiceAgent 项目的主要变更，按日期归档。

---

## 2026-05-24

### 配置与加载

- `config/config.yaml`：新增统一配置源，集中维护 `env_keys/defaults/env_bindings/actions/mysql` 等配置段。
- `app/shared/config.py`：重构为纯 `dataclass` 配置模型（`Settings`、`MysqlConfig` 等），移除旧的动态对象兼容别名。
- `app/shared/yaml_loader.py`：实现 YAML 读取、`env_bindings` 覆盖、`get_settings/reload_settings/settings` 缓存加载入口。
- `app/shared/constants.py`、`app/shared/__init__.py`：统一导出 `Settings` 与新的配置加载入口，清理旧别名。
- `app/shared/utils.py`：沉淀环境变量解析辅助函数（布尔值与运行环境解析）。

### 存储模块

- `app/core/stores/tracker_store.py`：补充 TrackerStore 抽象接口与创建/查询辅助流程，明确基类行为。
- `app/core/stores/json_store.py`：实现 JSON 文件存储后端（保存、读取、删除、枚举、关闭）。
- `app/core/stores/mysql_store.py`：实现 MySQL 存储后端初始化与 CRUD，支持 MySQL upsert 和异步上下文关闭连接。

### 核心与共享模块

- `app/core/domain.py`、`app/core/tracker.py`、`app/core/slots.py`：补充/优化注释与配置引用方式，统一从 `yaml_loader.settings` 读取运行配置。
- `app/shared/logger.py`：切换到新配置加载入口，日志环境参数由 `settings` 提供。
- `app/shared/exceptions.py`：补充统一异常定义，完善存储与配置相关异常表达。

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
