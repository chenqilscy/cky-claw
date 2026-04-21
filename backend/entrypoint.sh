#!/bin/sh
set -e

echo "=== Kasaya Backend Entrypoint ==="

# 运行数据库迁移（--no-sync 避免容器内重复下载依赖）
echo "[1/2] Running database migrations..."
uv run --no-sync alembic upgrade head
echo "[1/2] Migrations complete."

# 启动应用
echo "[2/2] Starting uvicorn..."
exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000
