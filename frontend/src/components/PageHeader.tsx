/**
 * 页面标题栏组件。
 */
import { Card, Space, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';

interface PageHeaderProps {
  /** 页面图标 */
  icon?: React.ReactNode;
  /** 页面标题 */
  title: string;
  /** 刷新回调（传入时显示刷新按钮） */
  onRefresh?: () => void;
  /** 标题栏右侧自定义操作 */
  extra?: React.ReactNode;
  /** 内容 */
  children: React.ReactNode;
}

/**
 * Card 容器 + 标题（含图标）+ 可选刷新和自定义按钮。
 */
export const PageHeader: React.FC<PageHeaderProps> = ({
  icon,
  title,
  onRefresh,
  extra,
  children,
}) => (
  <Card
    title={<Space>{icon}{title}</Space>}
    extra={
      <Space>
        {onRefresh && (
          <Button icon={<ReloadOutlined />} onClick={onRefresh}>刷新</Button>
        )}
        {extra}
      </Space>
    }
  >
    {children}
  </Card>
);
