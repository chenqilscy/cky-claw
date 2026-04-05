#!/usr/bin/env bash
# CkyClaw 数据库备份脚本
# 用法: ./scripts/backup.sh [备份目录]
#
# 功能:
#   - PostgreSQL: pg_dump 全量备份（自定义格式，支持 PITR）
#   - Redis: BGSAVE + 复制 RDB 文件
#   - 自动清理过期备份（PG 30 天，Redis 7 天）
#
# 环境变量:
#   PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE — PostgreSQL 连接信息
#   REDIS_HOST / REDIS_PORT — Redis 连接信息
#   BACKUP_DIR — 备份根目录（默认 /var/backups/ckyclaw）
#   PG_RETAIN_DAYS — PostgreSQL 备份保留天数（默认 30）
#   REDIS_RETAIN_DAYS — Redis 备份保留天数（默认 7）

set -euo pipefail

# ── 配置 ─────────────────────────────────────────────
BACKUP_DIR="${1:-${BACKUP_DIR:-/var/backups/ckyclaw}}"
PG_RETAIN_DAYS="${PG_RETAIN_DAYS:-30}"
REDIS_RETAIN_DAYS="${REDIS_RETAIN_DAYS:-7}"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-ckyclaw}"
PGDATABASE="${PGDATABASE:-ckyclaw}"

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PG_BACKUP_DIR="${BACKUP_DIR}/postgresql"
REDIS_BACKUP_DIR="${BACKUP_DIR}/redis"

# ── 辅助函数 ─────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# ── 创建目录 ─────────────────────────────────────────
mkdir -p "${PG_BACKUP_DIR}" "${REDIS_BACKUP_DIR}"

# ── PostgreSQL 备份 ──────────────────────────────────
log "开始 PostgreSQL 备份..."
PG_BACKUP_FILE="${PG_BACKUP_DIR}/ckyclaw_${TIMESTAMP}.dump"

PGPASSWORD="${PGPASSWORD:-}" pg_dump \
    -h "${PGHOST}" \
    -p "${PGPORT}" \
    -U "${PGUSER}" \
    -d "${PGDATABASE}" \
    -Fc \
    --no-owner \
    --no-privileges \
    -f "${PG_BACKUP_FILE}" \
    || die "PostgreSQL 备份失败"

PG_SIZE=$(du -sh "${PG_BACKUP_FILE}" | cut -f1)
log "PostgreSQL 备份完成: ${PG_BACKUP_FILE} (${PG_SIZE})"

# ── Redis 备份 ───────────────────────────────────────
log "开始 Redis 备份..."
REDIS_BACKUP_FILE="${REDIS_BACKUP_DIR}/dump_${TIMESTAMP}.rdb"

# 触发 BGSAVE 并等待完成
redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" BGSAVE >/dev/null 2>&1 || true
sleep 2

# 从 Redis 容器数据目录复制 RDB（Docker 模式下通过 volume 访问）
REDIS_RDB_SRC="/data/dump.rdb"
if [ -f "${REDIS_RDB_SRC}" ]; then
    cp "${REDIS_RDB_SRC}" "${REDIS_BACKUP_FILE}"
    REDIS_SIZE=$(du -sh "${REDIS_BACKUP_FILE}" | cut -f1)
    log "Redis 备份完成: ${REDIS_BACKUP_FILE} (${REDIS_SIZE})"
else
    # 尝试从 Docker 容器复制
    if docker cp ckyclaw-redis:/data/dump.rdb "${REDIS_BACKUP_FILE}" 2>/dev/null; then
        REDIS_SIZE=$(du -sh "${REDIS_BACKUP_FILE}" | cut -f1)
        log "Redis 备份完成 (Docker): ${REDIS_BACKUP_FILE} (${REDIS_SIZE})"
    else
        log "WARN: Redis RDB 文件不可用，跳过 Redis 备份"
    fi
fi

# ── 清理过期备份 ─────────────────────────────────────
log "清理过期备份（PostgreSQL: ${PG_RETAIN_DAYS} 天, Redis: ${REDIS_RETAIN_DAYS} 天）..."
find "${PG_BACKUP_DIR}" -name "ckyclaw_*.dump" -mtime "+${PG_RETAIN_DAYS}" -delete 2>/dev/null || true
find "${REDIS_BACKUP_DIR}" -name "dump_*.rdb" -mtime "+${REDIS_RETAIN_DAYS}" -delete 2>/dev/null || true

PG_COUNT=$(find "${PG_BACKUP_DIR}" -name "ckyclaw_*.dump" | wc -l)
REDIS_COUNT=$(find "${REDIS_BACKUP_DIR}" -name "dump_*.rdb" | wc -l)
log "当前备份数量 — PostgreSQL: ${PG_COUNT}, Redis: ${REDIS_COUNT}"

log "备份任务完成 ✓"
