# CkyClaw Backend Dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 先复制依赖文件，利用 Docker 缓存层
COPY backend/pyproject.toml backend/README.md backend/
COPY ckyclaw-framework/pyproject.toml ckyclaw-framework/
COPY ckyclaw-framework/ckyclaw_framework/ ckyclaw-framework/ckyclaw_framework/
COPY ckyclaw-framework/py.typed ckyclaw-framework/
COPY ckyclaw-framework/README.md ckyclaw-framework/

# 安装依赖
WORKDIR /app/backend
ARG UV_INDEX_URL=https://pypi.org/simple
ENV UV_INDEX_URL=${UV_INDEX_URL}
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# 复制应用代码
COPY backend/ /app/backend/

EXPOSE 8000

COPY backend/entrypoint.sh /app/backend/entrypoint.sh
RUN chmod +x /app/backend/entrypoint.sh

CMD ["/app/backend/entrypoint.sh"]
