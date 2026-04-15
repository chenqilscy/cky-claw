"""ArtifactStore — 大型工具输出外部化存储。"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from ckyclaw_framework.artifacts.artifact import Artifact

logger = logging.getLogger(__name__)

# 摘要最大字符数
_MAX_SUMMARY_CHARS = 200


def _make_summary(content: str, max_chars: int = _MAX_SUMMARY_CHARS) -> str:
    """截取内容前 max_chars 字符作为摘要。"""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "... [truncated]"


def _estimate_token_count(content: str) -> int:
    """估算 token 数（中英混合保守策略：字符数 / 3）。"""
    return max(len(content) // 3, 1)


class ArtifactStore(ABC):
    """Artifact 存储后端抽象。

    Runner 在工具结果超过 token 阈值时，自动将结果存入 ArtifactStore，
    上下文中只保留摘要 + artifact_id 引用。
    """

    @abstractmethod
    async def save(self, run_id: str, content: str, metadata: dict[str, Any] | None = None) -> Artifact:
        """保存工具输出，返回 Artifact。"""

    @abstractmethod
    async def load(self, artifact_id: str) -> Artifact | None:
        """根据 artifact_id 加载 Artifact。不存在返回 None。"""

    @abstractmethod
    async def list_by_run(self, run_id: str) -> list[Artifact]:
        """按 run_id 查询所有 Artifact。"""

    @abstractmethod
    async def cleanup(self, older_than: datetime) -> int:
        """清理过期 Artifact，返回删除数量。"""


class InMemoryArtifactStore(ArtifactStore):
    """内存实现，用于测试。"""

    def __init__(self) -> None:
        self._store: dict[str, Artifact] = {}

    async def save(self, run_id: str, content: str, metadata: dict[str, Any] | None = None) -> Artifact:
        """保存到内存。"""
        artifact = Artifact(
            run_id=run_id,
            content=content,
            summary=_make_summary(content),
            token_count=_estimate_token_count(content),
            metadata=metadata or {},
        )
        self._store[artifact.artifact_id] = artifact
        return artifact

    async def load(self, artifact_id: str) -> Artifact | None:
        """从内存加载。"""
        return self._store.get(artifact_id)

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        """按 run_id 过滤。"""
        return [a for a in self._store.values() if a.run_id == run_id]

    async def cleanup(self, older_than: datetime) -> int:
        """清理过期 artifact。"""
        to_delete = [
            aid for aid, a in self._store.items()
            if a.created_at < older_than
        ]
        for aid in to_delete:
            del self._store[aid]
        return len(to_delete)


class LocalArtifactStore(ArtifactStore):
    """本地文件系统实现。

    存储路径：{base_dir}/{run_id}/{artifact_id}.json
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _artifact_path(self, run_id: str, artifact_id: str) -> Path:
        """构建 artifact 文件路径。"""
        # 防止路径穿越：净化 run_id 和 artifact_id
        safe_run_id = run_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        safe_artifact_id = artifact_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self._base_dir / safe_run_id / f"{safe_artifact_id}.json"

    async def save(self, run_id: str, content: str, metadata: dict[str, Any] | None = None) -> Artifact:
        """保存到本地文件系统。"""
        artifact = Artifact(
            run_id=run_id,
            content=content,
            summary=_make_summary(content),
            token_count=_estimate_token_count(content),
            metadata=metadata or {},
        )
        path = self._artifact_path(run_id, artifact.artifact_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 同步写入（小 JSON 文件，< 几 MB，可接受）
        data = json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2)
        path.write_text(data, encoding="utf-8")

        logger.debug("Artifact saved: %s (%d tokens)", artifact.artifact_id, artifact.token_count)
        return artifact

    async def load(self, artifact_id: str) -> Artifact | None:
        """从文件系统加载 artifact。遍历所有 run 目录查找。"""
        for run_dir in self._base_dir.iterdir():
            if not run_dir.is_dir():
                continue
            safe_id = artifact_id.replace("/", "_").replace("\\", "_").replace("..", "_")
            path = run_dir / f"{safe_id}.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return Artifact.from_dict(data)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to load artifact %s: %s", artifact_id, e)
                    return None
        return None

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        """按 run_id 列出所有 artifact。"""
        safe_run_id = run_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        run_dir = self._base_dir / safe_run_id
        if not run_dir.exists():
            return []
        artifacts: list[Artifact] = []
        for path in run_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                artifacts.append(Artifact.from_dict(data))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load artifact %s: %s", path, e)
        return artifacts

    async def cleanup(self, older_than: datetime) -> int:
        """清理过期 artifact 文件。"""
        deleted = 0
        for run_dir in self._base_dir.iterdir():
            if not run_dir.is_dir():
                continue
            for path in list(run_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    created_at_raw = data.get("created_at", "")
                    if isinstance(created_at_raw, str) and created_at_raw:
                        created_at = datetime.fromisoformat(created_at_raw)
                        if created_at < older_than:
                            os.remove(path)
                            deleted += 1
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Failed to process artifact %s during cleanup: %s", path, e)

            # 清理空目录
            if run_dir.exists() and not any(run_dir.iterdir()):
                with contextlib.suppress(OSError):
                    run_dir.rmdir()

        logger.info("Artifact cleanup: deleted %d artifacts older than %s", deleted, older_than)
        return deleted
