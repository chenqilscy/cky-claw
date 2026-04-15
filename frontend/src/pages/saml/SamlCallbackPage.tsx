import { useEffect, useRef, useState } from 'react';
import { Card, Result, Spin, Typography } from 'antd';
import useAuthStore from '../../stores/authStore';

const { Text } = Typography;

/**
 * SAML ACS 回调页面。
 *
 * IdP 通过 POST 将 SAMLResponse 发送到后端 ACS 端点，
 * 后端验证后返回 JWT，前端通过此页面中转处理。
 *
 * 流程：前端 SAML 登录 → 重定向到 IdP → IdP POST 到后端 ACS →
 * 后端返回 JWT → 前端通过 window.opener 或 URL 参数接收 token。
 *
 * 实际上 SAML ACS POST 是由 IdP 直接发送到后端的，
 * 后端处理完后可以通过以下方式将 token 传递给前端：
 * 1. 重定向到前端页面，token 附在 URL fragment 中
 * 2. 设置 HTTP-only cookie
 *
 * 此页面处理方式 1：从 URL hash 中提取 token。
 */
const SamlCallbackPage: React.FC = () => {
  const [error, setError] = useState<string | null>(null);
  const setToken = useAuthStore((s) => s.setToken);
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = window.location.hash;
    const params = new URLSearchParams(hash.replace(/^#/, ''));
    const token = params.get('token');

    if (token) {
      setToken(token);
      window.location.href = '/chat';
    } else {
      setError('SAML 认证失败：未收到认证令牌');
    }
  }, [setToken]);

  if (error) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <Card style={{ width: 400 }}>
          <Result
            status="error"
            title="SAML SSO 登录失败"
            subTitle={<Text type="secondary">{error}</Text>}
            extra={<a href="/login">返回登录页</a>}
          />
        </Card>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <Spin size="large" tip="正在完成 SSO 登录..." />
    </div>
  );
};

export default SamlCallbackPage;
