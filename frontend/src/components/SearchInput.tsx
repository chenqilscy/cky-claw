/**
 * 防抖搜索输入框。
 */
import { Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useState, useEffect, useRef } from 'react';

interface SearchInputProps {
  /** 防抖后的回调 */
  onSearch: (value: string) => void;
  /** placeholder */
  placeholder?: string;
  /** 防抖延迟(ms) */
  delay?: number;
  /** 自定义样式 */
  style?: React.CSSProperties;
}

/**
 * 输入时自动防抖触发 onSearch。
 */
export const SearchInput: React.FC<SearchInputProps> = ({
  onSearch,
  placeholder = '搜索...',
  delay = 300,
  style,
}) => {
  const [value, setValue] = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    const timer = setTimeout(() => { onSearch(value); }, delay);
    timerRef.current = timer;
    return () => { clearTimeout(timer); };
  }, [value, delay, onSearch]);

  return (
    <Input
      prefix={<SearchOutlined />}
      placeholder={placeholder}
      allowClear
      value={value}
      onChange={(e) => setValue(e.target.value)}
      style={{ width: 240, ...style }}
    />
  );
};
