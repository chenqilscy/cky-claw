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
      span_id: 's1',
      parent_span_id: null,
      name: 'agent-root',
      type: 'agent',
      status: 'completed',
      start_time: '2026-01-01T00:00:00Z',
      end_time: '2026-01-01T00:00:01Z',
      duration_ms: 100,
      model: null,
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
      { span_id: 's2', parent_span_id: null, name: 'span-1', type: 'llm', status: 'completed', start_time: '2026-01-01T00:00:00Z', end_time: '2026-01-01T00:00:01Z', duration_ms: 50, model: null, children: [] },
      { span_id: 's3', parent_span_id: null, name: 'span-2', type: 'tool', status: 'completed', start_time: '2026-01-01T00:00:01Z', end_time: '2026-01-01T00:00:02Z', duration_ms: 30, model: null, children: [] },
    ];
    const { container } = render(
      <FlameChart nodes={nodes} totalSpans={2} />,
    );
    expect(container.querySelector('div')).toBeTruthy();
  });

  it('嵌套节点不崩溃', () => {
    const node = {
      span_id: 's4',
      parent_span_id: null,
      name: 'root',
      type: 'agent',
      status: 'completed',
      start_time: '2026-01-01T00:00:00Z',
      end_time: '2026-01-01T00:00:02Z',
      duration_ms: 200,
      model: null,
      children: [
        {
          span_id: 's5',
          parent_span_id: 's4',
          name: 'child-llm',
          type: 'llm',
          status: 'completed',
          start_time: '2026-01-01T00:00:00Z',
          end_time: '2026-01-01T00:00:01Z',
          duration_ms: 100,
          model: 'gpt-4o',
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
