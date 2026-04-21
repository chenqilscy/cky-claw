# Kasaya Backend

FastAPI 后端服务。

## 开发

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## 数据库迁移

```bash
# 创建迁移
uv run alembic revision --autogenerate -m "描述"

# 执行迁移
uv run alembic upgrade head
```
