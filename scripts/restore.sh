#!/usr/bin/env bash
# CkyClaw 数据恢复脚本
# 用法: ./scripts/restore.sh <pg_backup_file> [redis_backup_file]
#
# 功能:
#   - PostgreSQL: pg_restore 从 dump 文件恢复（覆盖式）
#   - Redis: 停止 Redis → 替换 RDB → 重启 Redis
#
# 安全措施:
#   - 恢复前确认提示（除非设置 RESTORE_CONFIRM=yes）
#   - 自动在恢复前创建当前状态的安全备份
#
# 环境变量:
#   PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE — PostgreSQL 连接信息
#   REDIS_HOST / REDIS_PORT — Redis 连接信息
#   RESTORE_CONFIRM — 设为 "yes" 跳过确认提示

set -euo pipefail

# ── 配置 ─────────────────────────────────────────────
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-ckyclaw}"
PGDATABASE="${PGDATABASE:-ckyclaw}"

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

RESTORE_CONFIRM="${RESTORE_CONFIRM:-}"

# ── 辅助函数 ─────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# ── 参数校验 ─────────────────────────────────────────
PG_BACKUP="${1:-}"
REDIS_BACKUP="${2:-}"

if [ -z "${PG_BACKUP}" ]; then
    echo "用法: $0 <pg_backup_file> [redis_backup_file]"
    echo ""
    echo "示例:"
    echo "  $0 /var/backups/ckyclaw/postgresql/ckyclaw_20260405_020000.dump"
    echo "  $0 /var/backups/ckyclaw/postgresql/ckyclaw_20260405_020000.dump /var/backups/ckyclaw/redis/dump_20260405_020000.rdb"
    exit 1
fi

[ -f "${PG_BACKUP}" ] || die "PostgreSQL 备份文件不存在: ${PG_BACKUP}"
if [ -n "${REDIS_BACKUP}" ] && [ ! -f "${REDIS_BACKUP}" ]; then
    die "Redis 备份文件不存在: ${REDIS_BACKUP}"
fi

# ── 确认提示 ─────────────────────────────────────────
if [ "${RESTORE_CONFIRM}" != "yes" ]; then
    echo "⚠️  警告: 此操作将覆盖当前数据库内容！"
    echo ""
    echo "  PostgreSQL 备份: ${PG_BACKUP}"
    [ -n "${REDIS_BACKUP}" ] && echo "  Redis 备份:      ${REDIS_BACKUP}"
    echo ""
    read -rp "确认恢复？输入 'yes' 继续: " confirm
    [ "${confirm}" = "yes" ] || die "用户取消恢复"
fi

# ── 恢复前安全备份 ────────────────────────────────────
SAFETY_DIR="/tmp/ckyclaw_pre_restore_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${SAFETY_DIR}"
log "创建恢复前安全备份到 ${SAFETY_DIR}..."

PGPASSWORD="${PGPASSWORD:-}" pg_dump \
    -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
    -Fc --no-owner --no-privileges \
    -f "${SAFETY_DIR}/pre_restore.dump" 2>/dev/null \
    || log "WARN: 恢复前安全备份失败（数据库可能已损坏），继续恢复..."

log "安全备份完成: ${SAFETY_DIR}/pre_restore.dump"

# ── PostgreSQL 恢复 ──────────────────────────────────
log "开始 PostgreSQL 恢复..."

# 先断开现有连接
PGPASSWORD="${PGPASSWORD:-}" psql \
    -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PGDATABASE}' AND pid <> pg_backend_pid();" \
    >/dev/null 2>&1 || true

# 删除并重建数据库
PGPASSWORD="${PGPASSWORD:-}" psql \
    -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres \
    -c "DROP DATABASE IF EXISTS ${PGDATABASE};" \
    -c "CREATE DATABASE ${PGDATABASE} OWNER ${PGUSER};" \
    || die "数据库重建失败"

# 从备份恢复
PGPASSWORD="${PGPASSWORD:-}" pg_restore \
    -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
    --no-owner --no-privileges \
    "${PG_BACKUP}" \
    || die "PostgreSQL 恢复失败"

log "PostgreSQL 恢复完成 ✓"

# ── Redis 恢复 ───────────────────────────────────────
if [ -n "${REDIS_BACKUP}" ]; then
    log "开始 Redis 恢复..."

    # 尝试 Docker 模式恢复
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q ckyclaw-redis; then
        docker cp "${REDIS_BACKUP}" ckyclaw-redis:/data/dump.rdb
        docker restart ckyclaw-redis
        log "Redis 恢复完成 (Docker) ✓"
    else
        # 非 Docker 模式：直接替换 RDB
        redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" SHUTDOWN NOSAVE 2>/dev/null || true
        sleep 1
        REDIS_DATA_DIR=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG GET dir 2>/dev/null | tail -1 || echo "/var/lib/redis")
        cp "${REDIS_BACKUP}" "${REDIS_DATA_DIR}/dump.rdb"
        log "Redis RDB 已替换，请手动启动 Redis 服务"
    fi
else
    log "未指定 Redis 备份文件，跳过 Redis 恢复"
fi

log "恢复任务完成 ✓"
log "安全备份保存在: ${SAFETY_DIR} (可在确认恢复正常后删除)"
