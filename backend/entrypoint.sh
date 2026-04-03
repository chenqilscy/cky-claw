#!/bin/sh
set -e

echo "=== CkyClaw Backend Entrypoint ==="

# 运行数据库迁移
echo "[1/2] Running database migrations..."
uv run alembic upgrade head
echo "[1/2] Migrations complete."

# 启动应用
echo "[2/2] Starting uvicorn..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
