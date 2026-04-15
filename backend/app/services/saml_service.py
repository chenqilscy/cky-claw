"""SAML 2.0 Service Provider 业务逻辑。

轻量级实现，不依赖 python3-saml，仅使用标准库 XML 解析 + lxml（可选）。
支持 SP-Initiated SSO (HTTP-Redirect Binding) + IdP-Initiated SSO。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import uuid
import zlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.core.config import settings
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.redis import get_redis
from app.models.saml_config import SamlIdpConfig
from app.models.user import User

logger = logging.getLogger(__name__)

# SAML 命名空间
_NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}

# Redis key 前缀
_SAML_STATE_PREFIX = "saml:request_id:"
_SAML_STATE_TTL = 600  # 10 分钟


# ---- IdP 配置 CRUD ----


async def list_idp_configs(db: AsyncSession) -> list[SamlIdpConfig]:
    """获取所有 SAML IdP 配置列表。"""
    stmt = select(SamlIdpConfig).order_by(SamlIdpConfig.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_idp_config(db: AsyncSession, idp_id: uuid.UUID) -> SamlIdpConfig:
    """根据 ID 获取 IdP 配置。

    Raises:
        NotFoundError: 未找到指定 IdP 配置。
    """
    stmt = select(SamlIdpConfig).where(SamlIdpConfig.id == idp_id)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if config is None:
        raise NotFoundError(f"SAML IdP 配置不存在: {idp_id}")
    return config


async def get_default_idp(db: AsyncSession) -> SamlIdpConfig | None:
    """获取默认（或唯一启用的）IdP 配置。"""
    # 优先取 is_default=True
    stmt = select(SamlIdpConfig).where(
        SamlIdpConfig.is_enabled.is_(True),
        SamlIdpConfig.is_default.is_(True),
    ).limit(1)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if config is not None:
        return config

    # 退而求其次：取唯一启用的
    stmt2 = select(SamlIdpConfig).where(SamlIdpConfig.is_enabled.is_(True)).limit(2)
    enabled = list((await db.execute(stmt2)).scalars().all())
    if len(enabled) == 1:
        return enabled[0]
    return None


async def create_idp_config(
    db: AsyncSession,
    *,
    name: str,
    entity_id: str,
    sso_url: str,
    slo_url: str = "",
    x509_cert: str,
    metadata_xml: str | None = None,
    attribute_mapping: dict[str, str] | None = None,
    is_enabled: bool = True,
    is_default: bool = False,
) -> SamlIdpConfig:
    """创建 SAML IdP 配置。"""
    # 若设为默认，先取消原默认
    if is_default:
        await _clear_default_idp(db)

    config = SamlIdpConfig(
        name=name,
        entity_id=entity_id,
        sso_url=sso_url,
        slo_url=slo_url,
        x509_cert=x509_cert,
        metadata_xml=metadata_xml,
        attribute_mapping=attribute_mapping or {},
        is_enabled=is_enabled,
        is_default=is_default,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def update_idp_config(
    db: AsyncSession,
    idp_id: uuid.UUID,
    **updates: Any,
) -> SamlIdpConfig:
    """更新 SAML IdP 配置。"""
    config = await get_idp_config(db, idp_id)

    # 若要设为默认，先取消原默认
    if updates.get("is_default") is True and not config.is_default:
        await _clear_default_idp(db)

    for key, value in updates.items():
        if value is not None and hasattr(config, key):
            setattr(config, key, value)

    await db.commit()
    await db.refresh(config)
    return config


async def delete_idp_config(db: AsyncSession, idp_id: uuid.UUID) -> None:
    """删除 SAML IdP 配置。"""
    config = await get_idp_config(db, idp_id)
    await db.delete(config)
    await db.commit()


async def _clear_default_idp(db: AsyncSession) -> None:
    """取消所有 IdP 的默认状态。"""
    stmt = select(SamlIdpConfig).where(SamlIdpConfig.is_default.is_(True))
    result = await db.execute(stmt)
    for config in result.scalars().all():
        config.is_default = False


# ---- SP 元数据生成 ----


def generate_sp_metadata() -> str:
    """生成 SAML SP 元数据 XML。"""
    sp_entity_id = settings.saml_sp_entity_id
    acs_url = settings.saml_sp_acs_url

    if not sp_entity_id or not acs_url:
        raise ValidationError("SAML SP 未配置：需要设置 SAML_SP_ENTITY_ID 和 SAML_SP_ACS_URL")

    sls_url = settings.saml_sp_sls_url or ""

    md = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"'
        f' entityID="{_xml_escape(sp_entity_id)}">'
        '<md:SPSSODescriptor'
        ' AuthnRequestsSigned="false"'
        ' WantAssertionsSigned="true"'
        ' protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
        '<md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>'
        '<md:AssertionConsumerService'
        ' Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
        f' Location="{_xml_escape(acs_url)}"'
        ' index="0" isDefault="true"/>'
    )

    if sls_url:
        md += (
            '<md:SingleLogoutService'
            ' Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"'
            f' Location="{_xml_escape(sls_url)}"/>'
        )

    if settings.saml_sp_x509_cert:
        md += (
            '<md:KeyDescriptor use="signing">'
            '<ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'
            '<ds:X509Data><ds:X509Certificate>'
            f'{settings.saml_sp_x509_cert}'
            '</ds:X509Certificate></ds:X509Data>'
            '</ds:KeyInfo></md:KeyDescriptor>'
        )

    md += '</md:SPSSODescriptor></md:EntityDescriptor>'
    return md


# ---- SP-Initiated SSO ----


async def create_authn_request(
    db: AsyncSession,
    idp_id: uuid.UUID | None = None,
) -> tuple[str, str]:
    """创建 SAML AuthnRequest，返回 (redirect_url, request_id)。

    使用 HTTP-Redirect Binding：将 AuthnRequest 进行 Deflate + Base64 后附加到 IdP SSO URL 查询参数。

    Raises:
        ValidationError: SP 未配置。
        NotFoundError: 指定 IdP 不存在或无可用 IdP。
    """
    if not settings.saml_sp_entity_id or not settings.saml_sp_acs_url:
        raise ValidationError("SAML SP 未配置")

    # 获取 IdP 配置
    if idp_id is not None:
        idp = await get_idp_config(db, idp_id)
        if not idp.is_enabled:
            raise ValidationError(f"IdP '{idp.name}' 已禁用")
    else:
        idp = await get_default_idp(db)
        if idp is None:
            raise NotFoundError("无可用的 SAML IdP 配置")

    # 生成 AuthnRequest
    request_id = f"_ckyclaw_{secrets.token_hex(16)}"
    issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    authn_request = (
        '<samlp:AuthnRequest'
        ' xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
        ' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
        f' ID="{request_id}"'
        ' Version="2.0"'
        f' IssueInstant="{issue_instant}"'
        f' Destination="{_xml_escape(idp.sso_url)}"'
        f' AssertionConsumerServiceURL="{_xml_escape(settings.saml_sp_acs_url)}"'
        ' ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
        f'<saml:Issuer>{_xml_escape(settings.saml_sp_entity_id)}</saml:Issuer>'
        '<samlp:NameIDPolicy'
        ' Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"'
        ' AllowCreate="true"/>'
        '</samlp:AuthnRequest>'
    )

    # Deflate + Base64
    deflated = zlib.compress(authn_request.encode("utf-8"))[2:-4]  # raw deflate
    encoded = base64.b64encode(deflated).decode("ascii")

    # 存储 request_id 到 Redis 用于 Response 校验
    redis = await get_redis()
    await redis.set(
        f"{_SAML_STATE_PREFIX}{request_id}",
        str(idp.id),
        ex=_SAML_STATE_TTL,
    )

    # 拼接重定向 URL
    params = urlencode({"SAMLRequest": encoded})
    separator = "&" if "?" in idp.sso_url else "?"
    redirect_url = f"{idp.sso_url}{separator}{params}"

    return redirect_url, request_id


# ---- ACS (Assertion Consumer Service) ----


async def process_saml_response(
    db: AsyncSession,
    saml_response_b64: str,
    relay_state: str | None = None,
) -> str:
    """处理 IdP 返回的 SAML Response，返回 JWT access_token。

    流程：
    1. Base64 解码 Response XML
    2. 解析并验证 Response（Status、Issuer、Audience、时间窗口）
    3. 提取用户属性（NameID、email、username）
    4. 通过 InResponseTo 验证 Request（SP-Initiated）或跳过验证（IdP-Initiated）
    5. 查找或创建本地用户
    6. 返回 JWT

    Raises:
        AuthenticationError: SAML Response 验证失败。
    """
    # 1. Base64 解码
    try:
        response_xml = base64.b64decode(saml_response_b64).decode("utf-8")
    except Exception as exc:
        raise AuthenticationError("SAML Response 解码失败") from exc

    # 2. 解析 XML
    try:
        root = ET.fromstring(response_xml)
    except ET.ParseError as exc:
        raise AuthenticationError("SAML Response XML 解析失败") from exc

    # 3. 检查 Status
    status_el = root.find("samlp:Status/samlp:StatusCode", _NS)
    if status_el is None:
        raise AuthenticationError("SAML Response 缺少 Status")
    status_value = status_el.get("Value", "")
    if not status_value.endswith(":Success"):
        raise AuthenticationError(f"SAML 认证失败: {status_value}")

    # 4. 查找 Assertion
    assertion = root.find("saml:Assertion", _NS)
    if assertion is None:
        raise AuthenticationError("SAML Response 缺少 Assertion")

    # 5. 检查 Issuer
    issuer_el = assertion.find("saml:Issuer", _NS)
    if issuer_el is None or not issuer_el.text:
        raise AuthenticationError("SAML Assertion 缺少 Issuer")
    issuer = issuer_el.text.strip()

    # 查找对应的 IdP 配置
    idp = await _find_idp_by_entity_id(db, issuer)

    # 6. 验证 InResponseTo（SP-Initiated 流程）
    in_response_to = root.get("InResponseTo")
    if in_response_to:
        redis = await get_redis()
        redis_key = f"{_SAML_STATE_PREFIX}{in_response_to}"
        stored_idp_id = await redis.getdel(redis_key)
        if stored_idp_id is None:
            logger.warning("SAML InResponseTo 验证失败: %s", in_response_to)
            raise AuthenticationError("SAML Response 已过期或请求 ID 无效")
        if stored_idp_id != str(idp.id):
            raise AuthenticationError("SAML Response 的 IdP 不匹配")

    # 7. 检查 Audience（可选但推荐）
    audiences = assertion.findall(
        "saml:Conditions/saml:AudienceRestriction/saml:Audience", _NS
    )
    if audiences and settings.saml_sp_entity_id:
        audience_values = [a.text.strip() for a in audiences if a.text]
        if settings.saml_sp_entity_id not in audience_values:
            raise AuthenticationError(
                f"SAML Audience 不匹配: 期望 {settings.saml_sp_entity_id}，"
                f"收到 {audience_values}"
            )

    # 8. 检查 NotBefore / NotOnOrAfter（防重放）
    conditions = assertion.find("saml:Conditions", _NS)
    if conditions is not None:
        now = datetime.now(timezone.utc)
        not_before = conditions.get("NotBefore")
        not_on_or_after = conditions.get("NotOnOrAfter")
        if not_before:
            nb = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
            if now < nb:
                raise AuthenticationError("SAML Assertion 尚未生效")
        if not_on_or_after:
            noa = datetime.fromisoformat(not_on_or_after.replace("Z", "+00:00"))
            if now >= noa:
                raise AuthenticationError("SAML Assertion 已过期")

    # 9. 提取 NameID
    subject = assertion.find("saml:Subject/saml:NameID", _NS)
    name_id = subject.text.strip() if subject is not None and subject.text else None
    if not name_id:
        raise AuthenticationError("SAML Assertion 缺少 NameID")

    # 10. 提取属性
    attributes = _extract_attributes(assertion, idp.attribute_mapping)

    # 11. 查找或创建用户
    email = attributes.get("email") or name_id
    username = attributes.get("username") or email.split("@")[0]
    display_name = attributes.get("display_name") or username

    user = await _find_or_create_saml_user(db, email, username, display_name, idp)

    # 12. 返回 JWT
    return create_access_token(
        data={"sub": str(user.id), "role": user.role},
    )


# ---- 内部辅助函数 ----


async def _find_idp_by_entity_id(db: AsyncSession, entity_id: str) -> SamlIdpConfig:
    """根据 entity_id 查找 IdP 配置。"""
    stmt = select(SamlIdpConfig).where(
        SamlIdpConfig.entity_id == entity_id,
        SamlIdpConfig.is_enabled.is_(True),
    )
    config = (await db.execute(stmt)).scalar_one_or_none()
    if config is None:
        raise AuthenticationError(f"未找到匹配的 SAML IdP: {entity_id}")
    return config


def _extract_attributes(
    assertion: ET.Element,
    mapping: dict[str, str],
) -> dict[str, str]:
    """从 SAML Assertion 的 AttributeStatement 中提取属性。

    mapping 格式: {"email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"}
    """
    attrs: dict[str, str] = {}
    attr_statement = assertion.find("saml:AttributeStatement", _NS)
    if attr_statement is None:
        return attrs

    # 构建反向映射: saml_attr_name → local_key
    reverse_map: dict[str, str] = {v: k for k, v in mapping.items()} if mapping else {}

    for attr_el in attr_statement.findall("saml:Attribute", _NS):
        attr_name = attr_el.get("Name", "")
        value_el = attr_el.find("saml:AttributeValue", _NS)
        if value_el is not None and value_el.text:
            value = value_el.text.strip()
            # 通过映射名或属性名查找
            local_key = reverse_map.get(attr_name)
            if local_key:
                attrs[local_key] = value
            else:
                # 尝试常见默认映射
                lower_name = attr_name.lower()
                if "email" in lower_name and "email" not in attrs:
                    attrs["email"] = value
                elif "name" in lower_name and "username" not in attrs:
                    attrs["username"] = value
                elif "displayname" in lower_name and "display_name" not in attrs:
                    attrs["display_name"] = value

    return attrs


async def _find_or_create_saml_user(
    db: AsyncSession,
    email: str,
    username: str,
    display_name: str,
    idp: SamlIdpConfig,
) -> User:
    """根据 email 查找已有用户，不存在则自动创建。

    SAML 用户使用不可登录的随机密码创建。
    """
    # 按 email 查找
    stmt = select(User).where(User.email == email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user

    # 按 username 查找（兼容非 email NameID）
    stmt2 = select(User).where(User.username == username)
    user = (await db.execute(stmt2)).scalar_one_or_none()
    if user is not None:
        return user

    # 自动创建 — 使用随机密码（SAML 用户无法通过密码登录）
    from app.core.auth import hash_password

    random_password = secrets.token_urlsafe(32)
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(random_password),
        role="user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("SAML 自动创建用户: username=%s, email=%s, idp=%s", username, email, idp.name)
    return user


def _xml_escape(s: str) -> str:
    """简单 XML 属性转义。"""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
