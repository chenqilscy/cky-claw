import { api } from './api';

export interface OAuthAuthorizeResponse {
  authorize_url: string;
  state: string;
}

export interface OAuthConnection {
  id: string;
  provider: string;
  provider_user_id: string;
  provider_username: string;
  provider_email: string | null;
  provider_avatar_url: string | null;
  created_at: string;
}

export const oauthService = {
  /** 获取已配置的 OAuth Provider 列表 */
  getProviders: () =>
    api.get<{ providers: string[] }>('/auth/oauth/providers'),

  /** 获取 OAuth 授权跳转 URL */
  authorize: (provider: string) =>
    api.get<OAuthAuthorizeResponse>(`/auth/oauth/${provider}/authorize`),

  /** 处理 OAuth 回调（登录） */
  callback: (provider: string, code: string, state: string) =>
    api.get<{ access_token: string; token_type: string; expires_in: number }>(
      `/auth/oauth/${provider}/callback`,
      { code, state },
    ),

  /** 绑定 OAuth 到当前用户 */
  bind: (provider: string, code: string, state: string) =>
    api.post<OAuthConnection>(`/auth/oauth/${provider}/bind`, { code, state }),

  /** 获取当前用户的 OAuth 绑定列表 */
  getConnections: () =>
    api.get<OAuthConnection[]>('/auth/oauth/connections'),

  /** 解绑 OAuth */
  unbind: (provider: string) =>
    api.delete(`/auth/oauth/${provider}/unbind`),
};
