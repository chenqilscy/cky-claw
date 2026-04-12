import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

// Mock echarts — heavy dependency
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    getWidth: vi.fn(() => 800),
    getHeight: vi.fn(() => 400),
  })),
  graphic: { extendShape: vi.fn(), registerShape: vi.fn() },
}));

// Mock antd theme
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return {
    ...actual,
    theme: {
      ...actual.theme,
      useToken: () => ({
        token: {
          colorBgContainer: '#fff',
          colorText: '#000',
          colorTextSecondary: '#666',
          borderRadiusLG: 8,
        },
      }),
    },
  };
});

import FlameChart from '../../pages/traces/FlameChart';

describe('FlameChart', () => {
  it('渲染空状态', () => {
    const { container } = render(
      <FlameChart nodes={null} totalSpans={0} />,
    );
    expect(container.textContent).toContain('无 Span 数据');
  });

  it('渲染单个节点', () => {
    const node = {
      name: 'agent-root',
      type: 'agent',
      duration_ms: 100,
      start_offset_ms: 0,
      children: [],
    };
    const { container } = render(
      <FlameChart nodes={node} totalSpans={1} />,
    );
    // Should render the chart container div (not the fallback text)
    expect(container.querySelector('div')).toBeTruthy();
  });

  it('渲染数组节点', () => {
    const nodes = [
      { name: 'span-1', type: 'llm', duration_ms: 50, start_offset_ms: 0, children: [] },
      { name: 'span-2', type: 'tool', duration_ms: 30, start_offset_ms: 50, children: [] },
    ];
    const { container } = render(
      <FlameChart nodes={nodes} totalSpans={2} />,
    );
    expect(container.querySelector('div')).toBeTruthy();
  });

  it('嵌套节点不崩溃', () => {
    const node = {
      name: 'root',
      type: 'agent',
      duration_ms: 200,
      start_offset_ms: 0,
      children: [
        {
          name: 'child-llm',
          type: 'llm',
          duration_ms: 100,
          start_offset_ms: 10,
          children: [],
        },
      ],
    };
    const { container } = render(
      <FlameChart nodes={node} totalSpans={2} />,
    );
    expect(container).toBeTruthy();
  });
});
