import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// mock Grid.useBreakpoint
const mockUseBreakpoint = vi.fn();
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return {
    ...actual,
    Grid: {
      ...actual.Grid,
      useBreakpoint: () => mockUseBreakpoint(),
    },
  };
});

import { useResponsive } from '../../hooks/useResponsive';

describe('useResponsive', () => {
  beforeEach(() => {
    mockUseBreakpoint.mockReset();
  });

  it('isMobile=true when md is false', () => {
    mockUseBreakpoint.mockReturnValue({ xs: true, sm: true, md: false, lg: false });
    const { result } = renderHook(() => useResponsive());
    expect(result.current.isMobile).toBe(true);
    expect(result.current.isTablet).toBe(false);
    expect(result.current.isDesktop).toBe(false);
  });

  it('isTablet=true when md is true and lg is false', () => {
    mockUseBreakpoint.mockReturnValue({ xs: true, sm: true, md: true, lg: false });
    const { result } = renderHook(() => useResponsive());
    expect(result.current.isMobile).toBe(false);
    expect(result.current.isTablet).toBe(true);
    expect(result.current.isDesktop).toBe(false);
  });

  it('isDesktop=true when lg is true', () => {
    mockUseBreakpoint.mockReturnValue({ xs: true, sm: true, md: true, lg: true });
    const { result } = renderHook(() => useResponsive());
    expect(result.current.isMobile).toBe(false);
    expect(result.current.isTablet).toBe(false);
    expect(result.current.isDesktop).toBe(true);
  });

  it('exposes raw screens object', () => {
    const screens = { xs: true, sm: true, md: false, lg: false, xl: false, xxl: false };
    mockUseBreakpoint.mockReturnValue(screens);
    const { result } = renderHook(() => useResponsive());
    expect(result.current.screens).toEqual(screens);
  });
});
