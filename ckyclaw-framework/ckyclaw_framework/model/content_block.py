"""ContentBlock — 多模态消息内容块。

支持文本、图像、音频、文件等混合内容，向后兼容纯文本消息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union


class ContentType(str, Enum):
    """内容块类型。"""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"


@dataclass
class TextContent:
    """纯文本内容块。"""

    type: str = field(default="text", init=False)
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextContent:
        return cls(text=data.get("text", ""))


@dataclass
class ImageContent:
    """图像内容块。

    url 和 base64 至少提供一个。LiteLLM 优先使用 url。
    """

    type: str = field(default="image", init=False)
    url: str | None = None
    base64_data: str | None = None
    media_type: str = "image/png"
    alt_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": "image", "media_type": self.media_type}
        if self.url:
            d["url"] = self.url
        if self.base64_data:
            d["base64_data"] = self.base64_data
        if self.alt_text:
            d["alt_text"] = self.alt_text
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageContent:
        return cls(
            url=data.get("url"),
            base64_data=data.get("base64_data"),
            media_type=data.get("media_type", "image/png"),
            alt_text=data.get("alt_text", ""),
        )


@dataclass
class AudioContent:
    """音频内容块。"""

    type: str = field(default="audio", init=False)
    url: str | None = None
    base64_data: str | None = None
    format: str = "mp3"
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": "audio", "format": self.format}
        if self.url:
            d["url"] = self.url
        if self.base64_data:
            d["base64_data"] = self.base64_data
        if self.duration_seconds is not None:
            d["duration_seconds"] = self.duration_seconds
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudioContent:
        return cls(
            url=data.get("url"),
            base64_data=data.get("base64_data"),
            format=data.get("format", "mp3"),
            duration_seconds=data.get("duration_seconds"),
        )


@dataclass
class FileContent:
    """文件附件内容块。"""

    type: str = field(default="file", init=False)
    url: str = ""
    filename: str = ""
    media_type: str = "application/octet-stream"
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": "file",
            "url": self.url,
            "filename": self.filename,
            "media_type": self.media_type,
        }
        if self.size_bytes is not None:
            d["size_bytes"] = self.size_bytes
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileContent:
        return cls(
            url=data.get("url", ""),
            filename=data.get("filename", ""),
            media_type=data.get("media_type", "application/octet-stream"),
            size_bytes=data.get("size_bytes"),
        )


# Union 类型别名
ContentBlock = Union[TextContent, ImageContent, AudioContent, FileContent]

# 类型 tag → 类 的映射
_CONTENT_BLOCK_MAP: dict[str, type] = {
    "text": TextContent,
    "image": ImageContent,
    "audio": AudioContent,
    "file": FileContent,
}


def content_block_from_dict(data: dict[str, Any]) -> ContentBlock:
    """从字典反序列化 ContentBlock。

    Args:
        data: 包含 'type' 键的字典。

    Returns:
        对应类型的 ContentBlock 实例。

    Raises:
        ValueError: 未知的 content type。
    """
    content_type = data.get("type", "text")
    cls = _CONTENT_BLOCK_MAP.get(content_type)
    if cls is None:
        raise ValueError(f"未知的 content type: {content_type}")
    return cls.from_dict(data)


def content_blocks_to_text(blocks: list[ContentBlock]) -> str:
    """将 ContentBlock 列表转为纯文本（用于向后兼容的场景）。

    图像/音频/文件用占位符表示。
    """
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, TextContent):
            parts.append(block.text)
        elif isinstance(block, ImageContent):
            parts.append(f"[图片: {block.alt_text or block.url or '嵌入图片'}]")
        elif isinstance(block, AudioContent):
            parts.append(f"[音频: {block.url or '嵌入音频'}]")
        elif isinstance(block, FileContent):
            parts.append(f"[文件: {block.filename}]")
    return "\n".join(parts)


def content_blocks_to_litellm(blocks: list[ContentBlock]) -> list[dict[str, Any]]:
    """将 ContentBlock 列表转为 LiteLLM 多模态消息格式。

    LiteLLM 格式:
    - text: {"type": "text", "text": "..."}
    - image: {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    """
    parts: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, TextContent):
            parts.append({"type": "text", "text": block.text})
        elif isinstance(block, ImageContent):
            if block.url:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": block.url},
                })
            elif block.base64_data:
                data_uri = f"data:{block.media_type};base64,{block.base64_data}"
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                })
            else:
                # url 和 base64_data 均为空，降级为文本占位
                parts.append({"type": "text", "text": f"[图片: {block.alt_text or '无数据'}]"})
        elif isinstance(block, AudioContent):
            # 部分 LLM 不支持原生音频，降级为文本占位
            parts.append({"type": "text", "text": f"[音频附件: {block.url or '嵌入音频'}]"})
        elif isinstance(block, FileContent):
            parts.append({"type": "text", "text": f"[文件附件: {block.filename}]"})
    return parts
