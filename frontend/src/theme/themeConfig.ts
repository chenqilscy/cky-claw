/**
 * 企业级设计令牌配置。
 *
 * 双色系 × 双模式：aurora（极光蓝紫）/ dawn（拂晓蓝） × light / dark。
 * 参考：Ant Design Pro 官方配色 + Linear / Vercel 的克制感。
 */
import type { ThemeConfig } from 'antd';
import { theme } from 'antd';

/* ------------------------------------------------------------------ */
/*  色系定义                                                           */
/* ------------------------------------------------------------------ */

/** 色系类型 */
export type PaletteType = 'aurora' | 'dawn';

/** 色系色板 */
const PALETTES: Record<PaletteType, { primary: string; info: string }> = {
  /** 极光蓝紫 — Indigo-600，企业级科技感 */
  aurora: {
    primary: '#4F46E5',
    info: '#6366F1',
  },
  /** 拂晓蓝 — Ant Design Pro 经典蓝 */
  dawn: {
    primary: '#1677FF',
    info: '#1677FF',
  },
};

/** 共用功能色 */
const COLOR_SUCCESS = '#52C41A';
const COLOR_WARNING = '#FAAD14';
const COLOR_ERROR = '#FF4D4F';

/* ------------------------------------------------------------------ */
/*  共享令牌                                                           */
/* ------------------------------------------------------------------ */

const sharedMeta = {
  /* 圆角体系 — 现代感 */
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

  /* 线宽 & 控件高度 */
  lineWidth: 1,
  controlHeight: 36,
  controlHeightLG: 40,
  controlHeightSM: 28,
};

/* ------------------------------------------------------------------ */
/*  组件级令牌                                                         */
/* ------------------------------------------------------------------ */

const buildSharedComponents = (primary: string): NonNullable<ThemeConfig['components']> => ({
  Layout: {
    headerBg: 'transparent',
    siderBg: 'transparent',
  },
  Card: {
    borderRadiusLG: 12,
    paddingLG: 20,
    boxShadowTertiary:
      '0 1px 2px 0 rgba(0,0,0,0.03), 0 1px 6px -1px rgba(0,0,0,0.02), 0 2px 4px 0 rgba(0,0,0,0.02)',
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
    defaultShadow: '0 2px 0 rgba(0,0,0,0.02)',
    primaryShadow: '0 2px 0 rgba(0,0,0,0.04)',
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
    itemActiveColor: primary,
    itemSelectedColor: primary,
    inkBarColor: primary,
  },
  Menu: {
    itemBorderRadius: 8,
    subMenuItemBorderRadius: 8,
    itemMarginInline: 4,
  },
  Dropdown: {
    borderRadiusLG: 10,
  },
  Statistic: {
    titleFontSize: 14,
    contentFontSize: 24,
  },
});

/* ------------------------------------------------------------------ */
/*  亮色主题                                                           */
/* ------------------------------------------------------------------ */

const PRO_BOX_SHADOW =
  '0 1px 2px 0 rgba(0,0,0,0.03), 0 1px 6px -1px rgba(0,0,0,0.02), 0 2px 4px 0 rgba(0,0,0,0.02)';
const PRO_BOX_SHADOW_SECONDARY =
  '0 6px 16px 0 rgba(0,0,0,0.08), 0 3px 6px -4px rgba(0,0,0,0.12), 0 9px 28px 8px rgba(0,0,0,0.05)';

const buildLightTheme = (palette: PaletteType): ThemeConfig => {
  const { primary, info } = PALETTES[palette];
  const comps = buildSharedComponents(primary);
  return {
    algorithm: theme.defaultAlgorithm,
    token: {
      ...sharedMeta,
      colorPrimary: primary,
      colorSuccess: COLOR_SUCCESS,
      colorWarning: COLOR_WARNING,
      colorError: COLOR_ERROR,
      colorInfo: info,
      /* 亮色背景 */
      colorBgContainer: '#FFFFFF',
      colorBgLayout: '#F0F2F5',
      colorBgElevated: '#FFFFFF',
      /* 亮色边框 */
      colorBorder: '#F0F0F0',
      colorBorderSecondary: '#F5F5F5',
      /* 亮色文字 */
      colorText: 'rgba(0, 0, 0, 0.88)',
      colorTextSecondary: 'rgba(0, 0, 0, 0.45)',
      colorTextTertiary: 'rgba(0, 0, 0, 0.25)',
      /* 阴影 */
      boxShadow: PRO_BOX_SHADOW,
      boxShadowSecondary: PRO_BOX_SHADOW_SECONDARY,
    },
    components: {
      ...comps,
      Layout: {
        headerBg: 'transparent',
        siderBg: 'transparent',
        bodyBg: '#F0F2F5',
      },
      Card: {
        ...comps.Card,
        colorBgContainer: '#FFFFFF',
      },
      Table: {
        ...comps.Table,
        headerBg: '#FAFAFA',
      },
    },
  };
};

/* ------------------------------------------------------------------ */
/*  暗色主题                                                           */
/* ------------------------------------------------------------------ */

const DARK_BOX_SHADOW =
  '0 1px 2px 0 rgba(0,0,0,0.4), 0 1px 6px -1px rgba(0,0,0,0.3), 0 2px 4px 0 rgba(0,0,0,0.3)';
const DARK_BOX_SHADOW_SECONDARY =
  '0 6px 16px 0 rgba(0,0,0,0.32), 0 3px 6px -4px rgba(0,0,0,0.48), 0 9px 28px 8px rgba(0,0,0,0.2)';

const buildDarkTheme = (palette: PaletteType): ThemeConfig => {
  const { primary, info } = PALETTES[palette];
  const comps = buildSharedComponents(primary);
  return {
    algorithm: theme.darkAlgorithm,
    token: {
      ...sharedMeta,
      colorPrimary: primary,
      colorSuccess: COLOR_SUCCESS,
      colorWarning: COLOR_WARNING,
      colorError: COLOR_ERROR,
      colorInfo: info,
      /* 暗色背景 — antd 标准暗色 */
      colorBgContainer: '#1F1F1F',
      colorBgLayout: '#141414',
      colorBgElevated: '#262626',
      /* 暗色边框 */
      colorBorder: '#424242',
      colorBorderSecondary: '#303030',
      /* 暗色文字 */
      colorText: 'rgba(255, 255, 255, 0.85)',
      colorTextSecondary: 'rgba(255, 255, 255, 0.45)',
      colorTextTertiary: 'rgba(255, 255, 255, 0.25)',
      /* 阴影 */
      boxShadow: DARK_BOX_SHADOW,
      boxShadowSecondary: DARK_BOX_SHADOW_SECONDARY,
    },
    components: {
      ...comps,
      Layout: {
        headerBg: 'transparent',
        siderBg: 'transparent',
        bodyBg: '#141414',
      },
      Card: {
        ...comps.Card,
        colorBgContainer: '#1F1F1F',
      },
      Table: {
        ...comps.Table,
        headerBg: '#1F1F1F',
      },
    },
  };
};

/* ------------------------------------------------------------------ */
/*  导出                                                               */
/* ------------------------------------------------------------------ */

/** 根据 palette + mode 组合获取完整主题配置 */
export function getTheme(palette: PaletteType, mode: 'light' | 'dark'): ThemeConfig {
  return mode === 'dark' ? buildDarkTheme(palette) : buildLightTheme(palette);
}

/** 保留旧导出名（兼容） */
export const lightTheme: ThemeConfig = buildLightTheme('dawn');
export const darkTheme: ThemeConfig = buildDarkTheme('dawn');

/** 获取色系主色值 */
export function getPrimaryColor(palette: PaletteType): string {
  return PALETTES[palette].primary;
}

/** 暗色模式布局背景色（用于闪烁预防） */
export const DARK_LAYOUT_BG = '#141414';
export const LIGHT_LAYOUT_BG = '#F0F2F5';
