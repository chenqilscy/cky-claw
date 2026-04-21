#!/usr/bin/env bash
# Kasaya 备份完整性验证脚本
# 用法: ./scripts/backup-verify.sh [备份目录]
#
# 功能:
#   - PostgreSQL: pg_restore --list 验证 dump 文件完整性
#   - Redis: 检查 RDB 文件头魔数
#   - 输出最近备份的详细信息

set -euo pipefail

BACKUP_DIR="${1:-${BACKUP_DIR:-/var/backups/kasaya}}"
PG_BACKUP_DIR="${BACKUP_DIR}/postgresql"
REDIS_BACKUP_DIR="${BACKUP_DIR}/redis"

# ── 辅助函数 ─────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
ok()  { echo "  ✓ $*"; }
fail() { echo "  ✗ $*"; ERRORS=$((ERRORS + 1)); }

ERRORS=0

echo "======================================"
echo " Kasaya 备份完整性验证"
echo "======================================"
echo ""

# ── PostgreSQL 备份验证 ──────────────────────────────
echo "▸ PostgreSQL 备份 (${PG_BACKUP_DIR})"

if [ ! -d "${PG_BACKUP_DIR}" ]; then
    fail "备份目录不存在: ${PG_BACKUP_DIR}"
else
    PG_LATEST=$(find "${PG_BACKUP_DIR}" -name "kasaya_*.dump" -type f | sort -r | head -1)
    if [ -z "${PG_LATEST}" ]; then
        fail "未找到 PostgreSQL 备份文件"
    else
        PG_SIZE=$(du -sh "${PG_LATEST}" | cut -f1)
        PG_DATE=$(stat -c '%y' "${PG_LATEST}" 2>/dev/null || stat -f '%Sm' "${PG_LATEST}" 2>/dev/null || echo "unknown")
        ok "最新备份: $(basename "${PG_LATEST}") (${PG_SIZE}, ${PG_DATE})"

        # pg_restore --list 验证
        if pg_restore --list "${PG_LATEST}" >/dev/null 2>&1; then
            TABLE_COUNT=$(pg_restore --list "${PG_LATEST}" 2>/dev/null | grep -c "TABLE " || echo "0")
            ok "文件完整性验证通过（${TABLE_COUNT} 个对象）"
        else
            fail "pg_restore --list 验证失败: ${PG_LATEST}"
        fi

        # 备份数量统计
        PG_COUNT=$(find "${PG_BACKUP_DIR}" -name "kasaya_*.dump" | wc -l)
        ok "备份文件数量: ${PG_COUNT}"
    fi
fi

echo ""

# ── Redis 备份验证 ───────────────────────────────────
echo "▸ Redis 备份 (${REDIS_BACKUP_DIR})"

if [ ! -d "${REDIS_BACKUP_DIR}" ]; then
    fail "备份目录不存在: ${REDIS_BACKUP_DIR}"
else
    REDIS_LATEST=$(find "${REDIS_BACKUP_DIR}" -name "dump_*.rdb" -type f | sort -r | head -1)
    if [ -z "${REDIS_LATEST}" ]; then
        fail "未找到 Redis 备份文件"
    else
        REDIS_SIZE=$(du -sh "${REDIS_LATEST}" | cut -f1)
        REDIS_DATE=$(stat -c '%y' "${REDIS_LATEST}" 2>/dev/null || stat -f '%Sm' "${REDIS_LATEST}" 2>/dev/null || echo "unknown")
        ok "最新备份: $(basename "${REDIS_LATEST}") (${REDIS_SIZE}, ${REDIS_DATE})"

        # 检查 RDB 魔数（REDIS 开头）
        MAGIC=$(head -c 5 "${REDIS_LATEST}" 2>/dev/null || echo "")
        if [ "${MAGIC}" = "REDIS" ]; then
            ok "RDB 文件头验证通过"
        else
            fail "RDB 文件头异常（期望 REDIS，实际: ${MAGIC}）"
        fi

        REDIS_COUNT=$(find "${REDIS_BACKUP_DIR}" -name "dump_*.rdb" | wc -l)
        ok "备份文件数量: ${REDIS_COUNT}"
    fi
fi

echo ""

# ── 总结 ─────────────────────────────────────────────
echo "======================================"
if [ "${ERRORS}" -eq 0 ]; then
    echo " 验证结果: 全部通过 ✓"
else
    echo " 验证结果: ${ERRORS} 项异常 ✗"
fi
echo "======================================"

exit "${ERRORS}"
