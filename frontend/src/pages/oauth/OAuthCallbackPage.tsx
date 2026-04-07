import { useEffect, useState } from 'react';
import { useSearchParams, useParams, useNavigate } from 'react-router-dom';
import { Spin, Result, Typography } from 'antd';
import useAuthStore from '../../stores/authStore';
import { oauthService } from '../../services/oauthService';

const { Text } = Typography;

/** OAuth 回调页面 — 处理 Provider 回调后的 code + state 交换 */
const OAuthCallbackPage: React.FC = () => {
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setToken = useAuthStore((s) => s.setToken);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!provider || !code || !state) {
      setError('缺少必要的 OAuth 回调参数');
      return;
    }

    oauthService
      .callback(provider, code, state)
      .then((resp) => {
        setToken(resp.access_token);
        navigate('/chat', { replace: true });
      })
      .catch((err: Error) => {
        setError(err.message || 'OAuth 登录失败，请重试');
      });
  }, [provider, searchParams, navigate, setToken]);

  if (error) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <Result
          status="error"
          title="OAuth 登录失败"
          subTitle={<Text type="danger">{error}</Text>}
          extra={
            <a href="/login" style={{ fontSize: 16 }}>
              返回登录页
            </a>
          }
        />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <Spin size="large" />
    </div>
  );
};

export default OAuthCallbackPage;
