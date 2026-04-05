# CkyClaw 灾备运维指南

## 概述

CkyClaw 灾备方案围绕 **RTO < 4 小时、RPO < 1 小时** 目标设计，覆盖 PostgreSQL 和 Redis 两大数据组件。

## 备份策略

| 组件 | 备份方式 | 频率 | 保留策略 |
|------|---------|------|---------|
| **PostgreSQL** | pg_dump 自定义格式（.dump） | 每日 02:00 | 30 天 |
| **Redis** | BGSAVE + RDB 复制 | 随 PG 同步（每日 02:00） | 7 天 |
| **Agent 配置** | AgentVersion 自动快照（内置） | 每次变更 | 最近 50 个版本 |

## 恢复目标

| 指标 | 目标 | 说明 |
|------|------|------|
| **RTO** | < 4 小时 | 从灾难发生到服务恢复的最大允许时间 |
| **RPO** | < 1 小时 | 最大可接受的数据丢失时间窗口 |

## 脚本使用

### 手动备份

```bash
# 设置连接信息
export PGHOST=localhost PGPORT=5432 PGUSER=ckyclaw PGPASSWORD=your_password PGDATABASE=ckyclaw
export REDIS_HOST=localhost REDIS_PORT=6379

# 执行备份
./scripts/backup.sh /var/backups/ckyclaw
```

### 自动备份（Docker Compose）

```bash
# 启用 backup profile（每日 02:00 自动执行）
docker-compose --profile backup up -d backup

# 查看备份日志
docker logs ckyclaw-backup

# 手动触发一次备份
docker exec ckyclaw-backup bash /scripts/backup.sh
```

### 验证备份

```bash
./scripts/backup-verify.sh /var/backups/ckyclaw
```

输出示例：
```
======================================
 CkyClaw 备份完整性验证
======================================

▸ PostgreSQL 备份
  ✓ 最新备份: ckyclaw_20260405_020000.dump (45M)
  ✓ 文件完整性验证通过（35 个对象）
  ✓ 备份文件数量: 28

▸ Redis 备份
  ✓ 最新备份: dump_20260405_020000.rdb (1.2M)
  ✓ RDB 文件头验证通过
  ✓ 备份文件数量: 7

======================================
 验证结果: 全部通过 ✓
======================================
```

### 数据恢复

```bash
# 恢复 PostgreSQL + Redis
./scripts/restore.sh /var/backups/ckyclaw/postgresql/ckyclaw_20260405_020000.dump \
                     /var/backups/ckyclaw/redis/dump_20260405_020000.rdb

# 仅恢复 PostgreSQL
./scripts/restore.sh /var/backups/ckyclaw/postgresql/ckyclaw_20260405_020000.dump

# 跳过确认提示（自动化场景）
RESTORE_CONFIRM=yes ./scripts/restore.sh /var/backups/ckyclaw/postgresql/ckyclaw_20260405_020000.dump
```

## 恢复流程

### 场景 1：单节点故障

1. Docker Compose 自动重启（`restart: unless-stopped`）
2. PostgreSQL healthcheck 自动检测并重启

### 场景 2：数据损坏

1. 停止 backend 服务：`docker-compose stop backend`
2. 执行恢复：`./scripts/restore.sh <备份文件>`
3. 运行迁移：`docker-compose exec backend alembic upgrade head`
4. 启动 backend：`docker-compose start backend`
5. 验证服务：`curl http://localhost:8000/health`

### 场景 3：整体灾难

1. 重建基础设施：`docker-compose up -d db redis`
2. 等待 healthcheck 通过
3. 恢复 PostgreSQL：`./scripts/restore.sh <pg_backup>`
4. 恢复 Redis：`./scripts/restore.sh <pg_backup> <redis_backup>`
5. 启动应用：`docker-compose up -d backend frontend`
6. 验证全部服务

## 运维建议

1. **定期验证备份**：至少每周运行一次 `backup-verify.sh`
2. **异地存储**：将备份同步到外部存储（S3/OSS/NAS），避免单点故障
3. **恢复演练**：每月在测试环境执行一次完整恢复演练
4. **监控告警**：监控备份脚本执行结果，失败时及时告警
5. **备份加密**：生产环境建议使用 `gpg` 加密备份文件
