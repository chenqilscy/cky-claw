import { Checkbox, Empty, Input, Tag, theme } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useState, useMemo } from 'react';

export interface MultiSelectOption {
  /** 表单值 */
  value: string;
  /** 显示标签 */
  label: string;
  /** 副标题/描述 */
  description?: string;
  /** 右侧标签列表 */
  tags?: string[];
}

interface MultiSelectListProps {
  /** 当前选中值数组（Form 注入） */
  value?: string[];
  /** 值变化回调（Form 注入） */
  onChange?: (value: string[]) => void;
  /** 可选项列表 */
  options?: MultiSelectOption[];
  /** 最大高度，默认 260px */
  maxHeight?: number;
  /** 是否显示搜索框，默认 true */
  showSearch?: boolean;
  /** 空状态提示 */
  emptyText?: string;
  /** 是否禁用 */
  disabled?: boolean;
}

/**
 * 替代 Select mode="multiple" 的可见列表选择组件。
 *
 * 每个选项以行形式展示，含复选框、名称、描述和标签，
 * 用户无需展开下拉菜单即可浏览并勾选。
 */
const MultiSelectList: React.FC<MultiSelectListProps> = ({
  value = [],
  onChange,
  options = [],
  maxHeight = 260,
  showSearch = true,
  emptyText = '暂无可选项',
  disabled = false,
}) => {
  const { token } = theme.useToken();
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        (o.description && o.description.toLowerCase().includes(q))
    );
  }, [options, search]);

  const toggle = (val: string) => {
    if (disabled) return;
    const next = value.includes(val)
      ? value.filter((v) => v !== val)
      : [...value, val];
    onChange?.(next);
  };

  return (
    <div style={{ border: `1px solid ${token.colorBorder}`, borderRadius: token.borderRadius }}>
      {showSearch && (
        <div style={{ padding: '6px 8px', borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
          <Input
            size="small"
            prefix={<SearchOutlined />}
            placeholder="搜索…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
        </div>
      )}

      <div style={{ maxHeight, overflowY: 'auto', padding: '4px 0' }}>
        {filtered.length === 0 ? (
          <Empty description={emptyText} style={{ margin: '24px 0' }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          filtered.map((opt) => {
            const checked = value.includes(opt.value);
            return (
              <div
                key={opt.value}
                onClick={() => toggle(opt.value)}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  padding: '6px 10px',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  background: checked ? token.colorPrimaryBg : 'transparent',
                  borderLeft: checked ? `3px solid ${token.colorPrimary}` : '3px solid transparent',
                  transition: 'background 0.15s',
                  userSelect: 'none',
                }}
              >
                <Checkbox
                  checked={checked}
                  disabled={disabled}
                  style={{ marginTop: 2 }}
                  onClick={(e) => e.stopPropagation()}
                  onChange={() => toggle(opt.value)}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: checked ? 600 : 400, color: token.colorText }}>
                      {opt.label}
                    </span>
                    {opt.tags?.map((tag) => (
                      <Tag key={tag} style={{ margin: 0, fontSize: 11 }}>
                        {tag}
                      </Tag>
                    ))}
                  </div>
                  {opt.description && (
                    <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {opt.description}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {value.length > 0 && (
        <div style={{ padding: '4px 10px', borderTop: `1px solid ${token.colorBorderSecondary}`, fontSize: 12, color: token.colorTextSecondary }}>
          已选 {value.length} 项
        </div>
      )}
    </div>
  );
};

export default MultiSelectList;
