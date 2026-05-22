FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    APP_HOME=/app

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /usr/local/bin/uv

WORKDIR ${APP_HOME}

# 先复制依赖清单，利用 Docker 分层缓存加速构建
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# 再复制业务代码并安装当前项目包
COPY . .
RUN uv sync --frozen --no-dev

# 创建非 root 用户并切换
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser ${APP_HOME}
USER appuser

ENV PATH="${APP_HOME}/.venv/bin:$PATH"

EXPOSE 8000

# 当前默认启动 CLI（后续接入 FastAPI 可改为 uvicorn main:app ...）
CMD ["csa"]
