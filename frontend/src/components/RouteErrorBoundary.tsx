import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { Result, Button, Space, Typography } from 'antd';
import { ReloadOutlined, HomeOutlined } from '@ant-design/icons';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * 路由级错误边界：捕获单个页面的渲染异常，保留侧边栏布局。
 * 提供「重试」和「返回首页」两个恢复操作。
 */
class RouteErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[RouteErrorBoundary]', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/dashboard';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert">
        <Result
          status="error"
          title="页面加载出错"
          subTitle={this.state.error?.message || '发生了未知错误，请重试'}
          extra={
            <Space>
              <Button type="primary" icon={<ReloadOutlined />} onClick={this.handleRetry}>
                重试
              </Button>
              <Button icon={<HomeOutlined />} onClick={this.handleGoHome}>
                返回首页
              </Button>
            </Space>
          }
        >
          {import.meta.env.DEV && this.state.error?.stack && (
            <Typography.Paragraph
              type="secondary"
              ellipsis={{ rows: 5, expandable: true }}
              style={{ maxWidth: 600, margin: '0 auto', fontSize: 12, fontFamily: 'monospace' }}
            >
              {this.state.error.stack}
            </Typography.Paragraph>
          )}
        </Result>
        </div>
      );
    }

    return this.props.children;
  }
}

export default RouteErrorBoundary;
