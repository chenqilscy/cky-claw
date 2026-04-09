/**
 * 空数据占位组件。
 */
import { Empty } from 'antd';

interface EmptyStateProps {
  /** 描述文本 */
  description?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  description = '暂无数据',
}) => <Empty description={description} />;
