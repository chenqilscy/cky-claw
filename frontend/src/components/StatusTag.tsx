/**
 * 通用状态标签组件，统一颜色映射。
 */
import { Tag } from 'antd';

export interface StatusMap {
  [key: string]: { color: string; text: string };
}

interface StatusTagProps {
  /** 状态值 */
  value: string;
  /** 状态→颜色/文本映射 */
  map: StatusMap;
  /** 兜底显示文本（当 map 中无该 value 时使用），默认为 value 本身 */
  fallback?: string;
  /** 兜底颜色，默认 'default' */
  fallbackColor?: string;
}

/**
 * 根据 map 渲染对应颜色的 Tag。
 */
export const StatusTag: React.FC<StatusTagProps> = ({
  value,
  map,
  fallback,
  fallbackColor = 'default',
}) => {
  const entry = map[value];
  return (
    <Tag color={entry?.color ?? fallbackColor}>
      {entry?.text ?? fallback ?? value}
    </Tag>
  );
};
