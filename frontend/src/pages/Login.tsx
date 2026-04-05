import { Button, Card, Divider, Form, Input, Typography, message } from 'antd';
import { GithubOutlined, LockOutlined, UserOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import { oauthService } from '../services/oauthService';

const { Title } = Typography;

interface LoginFormValues {
  username: string;
  password: string;
}

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, loading, error, clearError } = useAuthStore();

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

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#f0f2f5',
    }}>
      <Card style={{ width: 400 }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 32 }}>
          CkyClaw
        </Title>
        {error && (
          <div style={{ color: '#ff4d4f', textAlign: 'center', marginBottom: 16 }}>
            {error}
          </div>
        )}
        <Form onFinish={onFinish} size="large">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
        <Divider plain>或</Divider>
        <Button
          icon={<GithubOutlined />}
          block
          size="large"
          onClick={async () => {
            try {
              const { authorize_url } = await oauthService.authorize('github');
              window.location.href = authorize_url;
            } catch {
              message.error('GitHub 登录暂不可用');
            }
          }}
        >
          GitHub 登录
        </Button>
      </Card>
    </div>
  );
};

export default LoginPage;
