"""Artifacts — 大型工具输出外部化存储。"""

from __future__ import annotations

from ckyclaw_framework.artifacts.artifact import Artifact
from ckyclaw_framework.artifacts.store import ArtifactStore, InMemoryArtifactStore, LocalArtifactStore

__all__ = [
    "Artifact",
    "ArtifactStore",
    "InMemoryArtifactStore",
    "LocalArtifactStore",
]
