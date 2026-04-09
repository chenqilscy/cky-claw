/**
 * 统一日期时间展示。
 */
import dayjs from 'dayjs';

interface DateTimeDisplayProps {
  /** ISO 日期字符串或 Date 对象 */
  value?: string | Date | null;
  /** dayjs 格式化模板 */
  format?: string;
  /** value 为空时的占位文本 */
  placeholder?: string;
}

/**
 * 格式化日期到 'YYYY-MM-DD HH:mm:ss'，可自定义。
 */
export const DateTimeDisplay: React.FC<DateTimeDisplayProps> = ({
  value,
  format = 'YYYY-MM-DD HH:mm:ss',
  placeholder = '-',
}) => {
  if (!value) return <span>{placeholder}</span>;
  return <span>{dayjs(value).format(format)}</span>;
};
