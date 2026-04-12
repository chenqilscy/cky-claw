import { Grid } from 'antd';

/**
 * 响应式断点 Hook — 封装 Ant Design Grid.useBreakpoint()。
 * 提供 isMobile / isTablet / isDesktop 语义化标志。
 */
export function useResponsive() {
  const screens = Grid.useBreakpoint();
  return {
    /** < 768px */
    isMobile: !screens.md,
    /** >= 768px && < 992px */
    isTablet: !!screens.md && !screens.lg,
    /** >= 992px */
    isDesktop: !!screens.lg,
    /** 原始断点对象 */
    screens,
  };
}
