"""Artifacts — 大型工具输出外部化存储。"""

from __future__ import annotations

from kasaya.artifacts.artifact import Artifact
from kasaya.artifacts.store import ArtifactStore, InMemoryArtifactStore, LocalArtifactStore

__all__ = [
    "Artifact",
    "ArtifactStore",
    "InMemoryArtifactStore",
    "LocalArtifactStore",
]
