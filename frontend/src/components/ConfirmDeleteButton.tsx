/**
 * 删除确认按钮组件，封装 Popconfirm + 删除图标按钮。
 */
import { Button, Popconfirm, Tooltip } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';

interface ConfirmDeleteButtonProps {
  /** 确认提示语 */
  title?: string;
  /** 确认后回调 */
  onConfirm: () => void;
  /** 是否禁用 */
  disabled?: boolean;
  /** 禁用时的 tooltip */
  disabledTip?: string;
}

export const ConfirmDeleteButton: React.FC<ConfirmDeleteButtonProps> = ({
  title = '确认删除？',
  onConfirm,
  disabled = false,
  disabledTip,
}) => (
  <Popconfirm
    title={title}
    onConfirm={onConfirm}
    okText="删除"
    cancelText="取消"
    disabled={disabled}
  >
    <Tooltip title={disabled ? disabledTip : '删除'}>
      <Button type="link" danger size="small" icon={<DeleteOutlined />} disabled={disabled} />
    </Tooltip>
  </Popconfirm>
);
