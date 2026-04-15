"""SAML 2.0 认证与 IdP 配置管理路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.saml import (
    SamlIdpConfigCreate,
    SamlIdpConfigResponse,
    SamlIdpConfigUpdate,
    SamlLoginRequest,
    SamlLoginResponse,
    SamlSpMetadataResponse,
)
from app.services import saml_service

router = APIRouter(prefix="/api/v1/auth/saml", tags=["saml"])


# ---- SP 元数据 ----


@router.get("/metadata", response_model=SamlSpMetadataResponse)
async def get_sp_metadata() -> SamlSpMetadataResponse:
    """获取 SAML SP 元数据。"""
    metadata_xml = saml_service.generate_sp_metadata()
    return SamlSpMetadataResponse(
        entity_id=settings.saml_sp_entity_id,
        acs_url=settings.saml_sp_acs_url,
        sls_url=settings.saml_sp_sls_url,
        metadata_xml=metadata_xml,
    )


@router.get("/metadata.xml")
async def get_sp_metadata_xml() -> Response:
    """获取 SAML SP 元数据 XML 文件（供 IdP 自动配置）。"""
    metadata_xml = saml_service.generate_sp_metadata()
    return Response(content=metadata_xml, media_type="application/xml")


# ---- SSO 登录流程 ----


@router.post("/login", response_model=SamlLoginResponse)
async def saml_login(
    request: SamlLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> SamlLoginResponse:
    """发起 SAML SSO 登录 — 生成 AuthnRequest 并返回重定向 URL。"""
    redirect_url, _ = await saml_service.create_authn_request(db, request.idp_id)
    return SamlLoginResponse(redirect_url=redirect_url)


@router.post("/acs", response_model=TokenResponse)
async def assertion_consumer_service(
    SAMLResponse: str = Form(..., description="Base64 编码的 SAML Response"),
    RelayState: str | None = Form(None, description="RelayState 回传参数"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """SAML ACS (Assertion Consumer Service) — 处理 IdP POST 回来的 SAML Response。"""
    access_token = await saml_service.process_saml_response(db, SAMLResponse, RelayState)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ---- IdP 配置管理（Admin Only）----


@router.get("/idp-configs", response_model=list[SamlIdpConfigResponse])
async def list_idp_configs(
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[SamlIdpConfigResponse]:
    """获取所有 SAML IdP 配置列表（管理员）。"""
    configs = await saml_service.list_idp_configs(db)
    return [SamlIdpConfigResponse.model_validate(c) for c in configs]


@router.post("/idp-configs", response_model=SamlIdpConfigResponse, status_code=201)
async def create_idp_config(
    data: SamlIdpConfigCreate,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SamlIdpConfigResponse:
    """创建 SAML IdP 配置（管理员）。"""
    config = await saml_service.create_idp_config(db, **data.model_dump())
    return SamlIdpConfigResponse.model_validate(config)


@router.get("/idp-configs/{idp_id}", response_model=SamlIdpConfigResponse)
async def get_idp_config(
    idp_id: uuid.UUID,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SamlIdpConfigResponse:
    """获取指定 SAML IdP 配置（管理员）。"""
    config = await saml_service.get_idp_config(db, idp_id)
    return SamlIdpConfigResponse.model_validate(config)


@router.patch("/idp-configs/{idp_id}", response_model=SamlIdpConfigResponse)
async def update_idp_config(
    idp_id: uuid.UUID,
    data: SamlIdpConfigUpdate,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SamlIdpConfigResponse:
    """更新 SAML IdP 配置（管理员）。"""
    updates = data.model_dump(exclude_unset=True)
    config = await saml_service.update_idp_config(db, idp_id, **updates)
    return SamlIdpConfigResponse.model_validate(config)


@router.delete("/idp-configs/{idp_id}", status_code=204)
async def delete_idp_config(
    idp_id: uuid.UUID,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除 SAML IdP 配置（管理员）。"""
    await saml_service.delete_idp_config(db, idp_id)


# ---- 公开查询 ----


@router.get("/enabled-idps")
async def get_enabled_idps(
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[dict[str, str]]]:
    """获取已启用的 SAML IdP 列表（公开，供登录页展示）。"""
    configs = await saml_service.list_idp_configs(db)
    enabled = [
        {"id": str(c.id), "name": c.name}
        for c in configs
        if c.is_enabled
    ]
    return {"idps": enabled}
