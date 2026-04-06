import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import type { SpanItem } from '../../services/traceService';

import SpanWaterfall from '../../pages/traces/SpanWaterfall';

const mockSpans: SpanItem[] = [
  {
    id: 's1',
    trace_id: 't1',
    name: 'agent-run',
    type: 'agent',
    status: 'success',
    start_time: '2024-01-01T00:00:00.000Z',
    end_time: '2024-01-01T00:00:00.500Z',
    duration_ms: 500,
    parent_span_id: null,
    model: null,
    metadata: {},
    token_usage: null,
    input: null,
    output: null,
    created_at: '2024-01-01T00:00:00.000Z',
  },
  {
    id: 's2',
    trace_id: 't1',
    name: 'llm-call',
    type: 'llm',
    status: 'success',
    start_time: '2024-01-01T00:00:00.100Z',
    end_time: '2024-01-01T00:00:00.400Z',
    duration_ms: 300,
    parent_span_id: 's1',
    model: 'gpt-4',
    metadata: {},
    token_usage: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
    input: null,
    output: null,
    created_at: '2024-01-01T00:00:00.100Z',
  },
];

describe('SpanWaterfall', () => {
  it('渲染 Span 行', () => {
    const { container } = render(<SpanWaterfall spans={mockSpans} />);
    const text = container.textContent ?? '';
    expect(text).toContain('agent-run');
    expect(text).toContain('llm-call');
  });

  it('空 spans 不崩溃', () => {
    const { container } = render(<SpanWaterfall spans={[]} />);
    expect(container).toBeTruthy();
  });

  it('渲染 Span 类型标签', () => {
    const { container } = render(<SpanWaterfall spans={mockSpans} />);
    const text = container.textContent ?? '';
    expect(text).toContain('agent');
    expect(text).toContain('llm');
  });

  it('渲染耗时信息', () => {
    const { container } = render(<SpanWaterfall spans={mockSpans} />);
    const text = container.textContent ?? '';
    expect(text).toContain('500');
    expect(text).toContain('300');
  });
});
