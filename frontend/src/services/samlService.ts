import { api } from './api';

export interface SamlIdpConfig {
  id: string;
  name: string;
  entity_id: string;
  sso_url: string;
  slo_url: string;
  x509_cert: string;
  metadata_xml: string | null;
  attribute_mapping: Record<string, string>;
  is_enabled: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface SamlIdpConfigCreate {
  name: string;
  entity_id: string;
  sso_url: string;
  slo_url?: string;
  x509_cert: string;
  metadata_xml?: string;
  attribute_mapping?: Record<string, string>;
  is_enabled?: boolean;
  is_default?: boolean;
}

export interface SamlIdpConfigUpdate {
  name?: string;
  entity_id?: string;
  sso_url?: string;
  slo_url?: string;
  x509_cert?: string;
  metadata_xml?: string;
  attribute_mapping?: Record<string, string>;
  is_enabled?: boolean;
  is_default?: boolean;
}

export interface SamlLoginResponse {
  redirect_url: string;
}

export interface SamlSpMetadata {
  entity_id: string;
  acs_url: string;
  sls_url: string;
  metadata_xml: string;
}

export interface SamlEnabledIdp {
  id: string;
  name: string;
}

export const samlService = {
  /** 获取已启用的 SAML IdP 列表（公开，登录页用） */
  getEnabledIdps: () =>
    api.get<{ idps: SamlEnabledIdp[] }>('/auth/saml/enabled-idps'),

  /** 发起 SAML SSO 登录 */
  login: (idpId?: string) =>
    api.post<SamlLoginResponse>('/auth/saml/login', {
      idp_id: idpId ?? null,
    }),

  /** 获取 SP 元数据 */
  getSpMetadata: () =>
    api.get<SamlSpMetadata>('/auth/saml/metadata'),

  /** 获取所有 IdP 配置列表（管理员） */
  listIdpConfigs: () =>
    api.get<SamlIdpConfig[]>('/auth/saml/idp-configs'),

  /** 创建 IdP 配置（管理员） */
  createIdpConfig: (data: SamlIdpConfigCreate) =>
    api.post<SamlIdpConfig>('/auth/saml/idp-configs', data),

  /** 获取指定 IdP 配置（管理员） */
  getIdpConfig: (id: string) =>
    api.get<SamlIdpConfig>(`/auth/saml/idp-configs/${id}`),

  /** 更新 IdP 配置（管理员） */
  updateIdpConfig: (id: string, data: SamlIdpConfigUpdate) =>
    api.patch<SamlIdpConfig>(`/auth/saml/idp-configs/${id}`, data),

  /** 删除 IdP 配置（管理员） */
  deleteIdpConfig: (id: string) =>
    api.delete(`/auth/saml/idp-configs/${id}`),
};
