"""Multi-Modal ContentBlock + Message 扩展测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.model.content_block import (
    AudioContent,
    ContentBlock,
    FileContent,
    ImageContent,
    TextContent,
    content_block_from_dict,
    content_blocks_to_litellm,
    content_blocks_to_text,
)
from ckyclaw_framework.model.message import Message, MessageRole

# ── ContentBlock 序列化 ──────────────────────────────────


class TestTextContent:
    def test_create(self) -> None:
        tc = TextContent(text="hello")
        assert tc.type == "text"
        assert tc.text == "hello"

    def test_to_dict(self) -> None:
        tc = TextContent(text="world")
        d = tc.to_dict()
        assert d == {"type": "text", "text": "world"}

    def test_from_dict(self) -> None:
        tc = TextContent.from_dict({"text": "hi"})
        assert tc.text == "hi"


class TestImageContent:
    def test_with_url(self) -> None:
        ic = ImageContent(url="https://example.com/img.png")
        assert ic.type == "image"
        d = ic.to_dict()
        assert d["url"] == "https://example.com/img.png"
        assert d["media_type"] == "image/png"

    def test_with_base64(self) -> None:
        ic = ImageContent(base64_data="abc123", media_type="image/jpeg")
        d = ic.to_dict()
        assert d["base64_data"] == "abc123"
        assert "url" not in d

    def test_from_dict(self) -> None:
        ic = ImageContent.from_dict({"url": "http://x.com/a.jpg", "media_type": "image/jpeg", "alt_text": "图"})
        assert ic.url == "http://x.com/a.jpg"
        assert ic.alt_text == "图"


class TestAudioContent:
    def test_basic(self) -> None:
        ac = AudioContent(url="https://example.com/a.mp3", duration_seconds=10.5)
        assert ac.type == "audio"
        d = ac.to_dict()
        assert d["duration_seconds"] == 10.5

    def test_from_dict(self) -> None:
        ac = AudioContent.from_dict({"url": "x.wav", "format": "wav"})
        assert ac.format == "wav"


class TestFileContent:
    def test_basic(self) -> None:
        fc = FileContent(url="/files/doc.pdf", filename="doc.pdf", media_type="application/pdf", size_bytes=1024)
        assert fc.type == "file"
        d = fc.to_dict()
        assert d["size_bytes"] == 1024

    def test_from_dict(self) -> None:
        fc = FileContent.from_dict({"url": "/a.txt", "filename": "a.txt"})
        assert fc.filename == "a.txt"


# ── content_block_from_dict ──────────────────────────────


class TestContentBlockFromDict:
    def test_text(self) -> None:
        b = content_block_from_dict({"type": "text", "text": "hi"})
        assert isinstance(b, TextContent)

    def test_image(self) -> None:
        b = content_block_from_dict({"type": "image", "url": "http://x.png"})
        assert isinstance(b, ImageContent)

    def test_audio(self) -> None:
        b = content_block_from_dict({"type": "audio", "url": "http://x.mp3"})
        assert isinstance(b, AudioContent)

    def test_file(self) -> None:
        b = content_block_from_dict({"type": "file", "url": "/x.pdf", "filename": "x.pdf"})
        assert isinstance(b, FileContent)

    def test_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="未知"):
            content_block_from_dict({"type": "video"})


# ── content_blocks_to_text ───────────────────────────────


class TestContentBlocksToText:
    def test_text_only(self) -> None:
        blocks: list[ContentBlock] = [TextContent(text="hello"), TextContent(text="world")]
        assert content_blocks_to_text(blocks) == "hello\nworld"

    def test_mixed(self) -> None:
        blocks: list[ContentBlock] = [
            TextContent(text="看这张图"),
            ImageContent(url="http://img.png", alt_text="猫"),
            FileContent(url="/doc.pdf", filename="doc.pdf"),
        ]
        text = content_blocks_to_text(blocks)
        assert "看这张图" in text
        assert "[图片: 猫]" in text
        assert "[文件: doc.pdf]" in text


# ── content_blocks_to_litellm ────────────────────────────


class TestContentBlocksToLiteLLM:
    def test_text(self) -> None:
        blocks: list[ContentBlock] = [TextContent(text="hi")]
        parts = content_blocks_to_litellm(blocks)
        assert parts == [{"type": "text", "text": "hi"}]

    def test_image_url(self) -> None:
        blocks: list[ContentBlock] = [ImageContent(url="http://img.png")]
        parts = content_blocks_to_litellm(blocks)
        assert parts[0]["type"] == "image_url"
        assert parts[0]["image_url"]["url"] == "http://img.png"

    def test_image_base64(self) -> None:
        blocks: list[ContentBlock] = [ImageContent(base64_data="abc", media_type="image/jpeg")]
        parts = content_blocks_to_litellm(blocks)
        assert "data:image/jpeg;base64,abc" in parts[0]["image_url"]["url"]

    def test_audio_fallback(self) -> None:
        blocks: list[ContentBlock] = [AudioContent(url="http://a.mp3")]
        parts = content_blocks_to_litellm(blocks)
        assert parts[0]["type"] == "text"
        assert "音频" in parts[0]["text"]


# ── Message multi-modal 扩展 ─────────────────────────────


class TestMessageMultiModal:
    def test_text_content_property_plain(self) -> None:
        msg = Message(role=MessageRole.USER, content="plain text")
        assert msg.text_content == "plain text"
        assert msg.content_blocks is None

    def test_text_content_property_blocks(self) -> None:
        msg = Message(
            role=MessageRole.USER,
            content="",
            content_blocks=[TextContent(text="from blocks")],
        )
        assert msg.text_content == "from blocks"

    def test_to_dict_with_blocks(self) -> None:
        msg = Message(
            role=MessageRole.USER,
            content="fallback",
            content_blocks=[
                TextContent(text="hello"),
                ImageContent(url="http://img.png"),
            ],
        )
        d = msg.to_dict()
        assert "content_blocks" in d
        assert len(d["content_blocks"]) == 2
        assert d["content_blocks"][0]["type"] == "text"
        assert d["content_blocks"][1]["type"] == "image"

    def test_to_dict_without_blocks(self) -> None:
        msg = Message(role=MessageRole.USER, content="plain")
        d = msg.to_dict()
        assert "content_blocks" not in d

    def test_from_dict_with_blocks(self) -> None:
        data = {
            "role": "user",
            "content": "fallback",
            "content_blocks": [
                {"type": "text", "text": "hi"},
                {"type": "image", "url": "http://x.png"},
            ],
        }
        msg = Message.from_dict(data)
        assert msg.content_blocks is not None
        assert len(msg.content_blocks) == 2
        assert isinstance(msg.content_blocks[0], TextContent)
        assert isinstance(msg.content_blocks[1], ImageContent)

    def test_from_dict_without_blocks(self) -> None:
        data = {"role": "user", "content": "plain"}
        msg = Message.from_dict(data)
        assert msg.content_blocks is None

    def test_roundtrip(self) -> None:
        original = Message(
            role=MessageRole.USER,
            content="fallback text",
            content_blocks=[
                TextContent(text="看图"),
                ImageContent(url="http://example.com/cat.jpg", alt_text="猫"),
                AudioContent(url="http://example.com/voice.mp3"),
                FileContent(url="/files/doc.pdf", filename="doc.pdf"),
            ],
        )
        d = original.to_dict()
        restored = Message.from_dict(d)
        assert restored.content == "fallback text"
        assert restored.content_blocks is not None
        assert len(restored.content_blocks) == 4
        assert isinstance(restored.content_blocks[0], TextContent)
        assert isinstance(restored.content_blocks[1], ImageContent)
        assert isinstance(restored.content_blocks[2], AudioContent)
        assert isinstance(restored.content_blocks[3], FileContent)
