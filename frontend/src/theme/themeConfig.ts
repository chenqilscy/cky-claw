/**
 * 企业级设计令牌配置。
 *
 * 参考方案：Ant Design Pro / Linear / Vercel Dashboard / Raycast。
 * 两套主题：亮色（专业克制）+ 暗色（低对比舒适），共享品牌色和圆角体系。
 */
import type { ThemeConfig } from 'antd';
import { theme } from 'antd';

/* ---------- 品牌色系 ---------- */

/** 主色 — 琥珀橙黄（蓝黑底配橙黄点缀，突出品牌轨达感） */
const BRAND_PRIMARY = '#F59E0B';

/** 成功 / 警告 / 错误 — 柔和企业风 */
const COLOR_SUCCESS = '#16A34A';
const COLOR_WARNING = '#EAB308';
const COLOR_ERROR = '#DC2626';
const COLOR_INFO = '#0EA5E9';

/* ---------- 共享令牌 ---------- */

const sharedToken = {
  /* 品牌色 */
  colorPrimary: BRAND_PRIMARY,
  colorSuccess: COLOR_SUCCESS,
  colorWarning: COLOR_WARNING,
  colorError: COLOR_ERROR,
  colorInfo: COLOR_INFO,

  /* 圆角体系 — 偏大圆角，现代感 */
  borderRadius: 8,
  borderRadiusLG: 12,
  borderRadiusSM: 6,

  /* 字体 */
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif',
  fontSize: 14,
  fontSizeHeading1: 30,
  fontSizeHeading2: 24,
  fontSizeHeading3: 20,
  fontSizeHeading4: 16,

  /* 动效 — 偏快节奏 */
  motionDurationFast: '0.1s',
  motionDurationMid: '0.2s',
  motionDurationSlow: '0.3s',

  /* 间距 */
  marginXS: 4,
  marginSM: 8,
  marginMD: 16,
  marginLG: 24,
  marginXL: 32,
  paddingXS: 4,
  paddingSM: 8,
  paddingMD: 16,
  paddingLG: 24,
  paddingXL: 32,

  /* 线宽 */
  lineWidth: 1,
  controlHeight: 36,
  controlHeightLG: 40,
  controlHeightSM: 28,
};

/* ---------- 组件级令牌 ---------- */

const sharedComponents: ThemeConfig['components'] = {
  Layout: {
    headerBg: 'transparent',
    siderBg: 'transparent',
  },
  Card: {
    borderRadiusLG: 12,
    paddingLG: 20,
  },
  Table: {
    borderRadiusLG: 8,
    headerBorderRadius: 8,
  },
  Button: {
    borderRadius: 8,
    controlHeight: 36,
    controlHeightLG: 40,
    controlHeightSM: 28,
    paddingInline: 16,
  },
  Input: {
    borderRadius: 8,
    controlHeight: 36,
  },
  Select: {
    borderRadius: 8,
    controlHeight: 36,
  },
  Modal: {
    borderRadiusLG: 16,
  },
  Tag: {
    borderRadiusSM: 6,
  },
  Tabs: {
    itemActiveColor: BRAND_PRIMARY,
    itemSelectedColor: BRAND_PRIMARY,
    inkBarColor: BRAND_PRIMARY,
  },
  Menu: {
    itemBorderRadius: 8,
    subMenuItemBorderRadius: 8,
  },
  Dropdown: {
    borderRadiusLG: 10,
  },
};

/* ---------- 亮色主题 ---------- */

export const lightTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    ...sharedToken,
    /* 亮色微调 */
    colorBgContainer: '#FFFFFF',
    colorBgLayout: '#F5F5F7',
    colorBgElevated: '#FFFFFF',
    colorBorder: '#E5E7EB',
    colorBorderSecondary: '#F0F0F0',
    colorText: '#1F2937',
    colorTextSecondary: '#6B7280',
    colorTextTertiary: '#9CA3AF',
    boxShadow: '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.06)',
    boxShadowSecondary: '0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05)',
  },
  components: {
    ...sharedComponents,
    Layout: {
      ...sharedComponents.Layout,
      bodyBg: '#F5F5F7',
    },
    Card: {
      ...sharedComponents.Card,
      colorBgContainer: '#FFFFFF',
    },
  },
};

/* ---------- 暗色主题 ---------- */

export const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    ...sharedToken,
    /* 暗色微调 — 低对比度，护眼 */
    colorBgContainer: '#111827',
    colorBgLayout: '#0A1628',
    colorBgElevated: '#1F2937',
    colorBorder: '#374151',
    colorBorderSecondary: '#1F2937',
    colorText: '#F4F4F5',
    colorTextSecondary: '#A1A1AA',
    colorTextTertiary: '#71717A',
    boxShadow: '0 1px 3px 0 rgba(0,0,0,0.3), 0 1px 2px -1px rgba(0,0,0,0.3)',
    boxShadowSecondary: '0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3)',
  },
  components: {
    ...sharedComponents,
    Layout: {
      ...sharedComponents.Layout,
      bodyBg: '#0A1628',
    },
    Card: {
      ...sharedComponents.Card,
      colorBgContainer: '#111827',
    },
  },
};
