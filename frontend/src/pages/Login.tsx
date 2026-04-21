import { useEffect, useState } from 'react';
import { Button, Card, Divider, Form, Input, Space, Typography, App, theme } from 'antd';
import { GithubOutlined, GoogleOutlined, LockOutlined, SafetyOutlined, UserOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import { oauthService } from '../services/oauthService';
import { samlService, type SamlEnabledIdp } from '../services/samlService';

const { Title } = Typography;

/** Provider 元数据：中文名称 + 图标 + 颜色 */
const PROVIDER_META: Record<string, { label: string; icon: React.ReactNode; color?: string }> = {
  github: { label: 'GitHub', icon: <GithubOutlined />, color: '#24292e' },
  wecom: { label: '企业微信', icon: <SafetyOutlined />, color: '#07c160' },
  dingtalk: { label: '钉钉', icon: <SafetyOutlined />, color: '#0089ff' },
  feishu: { label: '飞书', icon: <SafetyOutlined />, color: '#3370ff' },
  google: { label: 'Google', icon: <GoogleOutlined />, color: '#4285f4' },
  oidc: { label: 'SSO', icon: <SafetyOutlined />, color: '#722ed1' },
};

interface LoginFormValues {
  username: string;
  password: string;
}

const LoginPage: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const { login, loading, error, clearError } = useAuthStore();
  const [providers, setProviders] = useState<string[]>([]);
  const [samlIdps, setSamlIdps] = useState<SamlEnabledIdp[]>([]);

  useEffect(() => {
    oauthService.getProviders()
      .then((resp) => setProviders(resp.providers))
      .catch(() => { /* Provider 列表获取失败时静默处理，仅显示密码登录 */ });
    samlService.getEnabledIdps()
      .then((resp) => setSamlIdps(resp.idps))
      .catch(() => { /* SAML IdP 列表获取失败时静默处理 */ });
  }, []);

  const onFinish = async (values: LoginFormValues) => {
    clearError();
    try {
      await login(values.username, values.password);
      message.success('登录成功');
      navigate('/chat');
    } catch {
      // error 已由 store 处理
    }
  };

  /** 发起 OAuth 登录跳转 */
  const handleOAuthLogin = async (provider: string) => {
    const meta = PROVIDER_META[provider];
    const label = meta?.label ?? provider;
    try {
      const { authorize_url } = await oauthService.authorize(provider);
      window.location.href = authorize_url;
    } catch {
      message.error(`${label} 登录暂不可用`);
    }
  };

  /** 发起 SAML SSO 登录 */
  const handleSamlLogin = async (idpId: string) => {
    try {
      const { redirect_url } = await samlService.login(idpId);
      window.location.href = redirect_url;
    } catch {
      message.error('SAML SSO 登录暂不可用');
    }
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: token.colorBgLayout,
    }}>
      <Card style={{ width: 400, maxWidth: '90vw' }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 32 }}>
          Kasaya
        </Title>
        {error && (
          <div role="alert" style={{ color: token.colorError, textAlign: 'center', marginBottom: 16 }}>
            {error}
          </div>
        )}
        <Form onFinish={onFinish} size="large" aria-label="登录表单">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" aria-label="用户名" autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" aria-label="密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
        {providers.length > 0 && (
          <>
            <Divider plain>或</Divider>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {providers.map((provider) => {
                const meta: { label: string; icon: React.ReactNode; color?: string } =
                  PROVIDER_META[provider] ?? { label: provider, icon: <SafetyOutlined /> };
                return (
                  <Button
                    key={provider}
                    icon={meta.icon}
                    block
                    size="large"
                    style={meta.color ? { borderColor: meta.color, color: meta.color } : undefined}
                    onClick={() => handleOAuthLogin(provider)}
                    data-provider={provider}
                  >
                    {meta.label} 登录
                  </Button>
                );
              })}
            </Space>
          </>
        )}
        {samlIdps.length > 0 && (
          <>
            {providers.length === 0 && <Divider plain>或</Divider>}
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {samlIdps.map((idp) => (
                <Button
                  key={idp.id}
                  icon={<SafetyOutlined />}
                  block
                  size="large"
                  style={{ borderColor: '#722ed1', color: '#722ed1' }}
                  onClick={() => handleSamlLogin(idp.id)}
                  data-saml-idp={idp.id}
                >
                  {idp.name} SSO 登录
                </Button>
              ))}
            </Space>
          </>
        )}
      </Card>
    </div>
  );
};

export default LoginPage;
