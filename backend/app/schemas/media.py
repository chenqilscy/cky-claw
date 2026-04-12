"""媒体上传响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    """媒体上传结果。"""

    url: str = Field(..., description="可访问地址")
    filename: str = Field(..., description="原始文件名")
    media_type: str = Field(..., description="MIME 类型")
    size_bytes: int = Field(..., description="文件大小")
