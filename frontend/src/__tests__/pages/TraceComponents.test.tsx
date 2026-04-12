import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import SpanDetailsPanel from '../../pages/traces/SpanDetailsPanel';
import TraceStatsPanel from '../../pages/traces/TraceStatsPanel';

/* ---------- SpanDetailsPanel ---------- */

const baseSpan = {
  id: 'span-001',
  trace_id: 'trace-001',
  name: 'llm-call',
  type: 'llm' as const,
  status: 'completed' as const,
  model: 'gpt-4o',
  duration_ms: 123.4,
  start_time: '2026-01-01T12:00:00Z',
  token_usage: { prompt_tokens: 100, completion_tokens: 50 },
  input: { role: 'user', content: 'hello' },
  output: { role: 'assistant', content: 'hi' },
};

describe('SpanDetailsPanel', () => {
  it('渲染 Span 名称', () => {
    const { container } = render(<SpanDetailsPanel span={baseSpan} />);
    expect(container.textContent).toContain('llm-call');
  });

  it('渲染基本字段', () => {
    const { container } = render(<SpanDetailsPanel span={baseSpan} />);
    const text = container.textContent ?? '';
    expect(text).toContain('span-001');
    expect(text).toContain('gpt-4o');
    expect(text).toContain('123');
  });

  it('渲染 token 使用量', () => {
    const { container } = render(<SpanDetailsPanel span={baseSpan} />);
    const text = container.textContent ?? '';
    expect(text).toContain('100');
    expect(text).toContain('50');
  });

  it('guardrail 拦截时显示告警', () => {
    const guardrailSpan = {
      ...baseSpan,
      type: 'guardrail' as const,
      status: 'failed' as const,
      name: 'injection-guard',
      guardrail_type: 'llm',
      triggered: true,
      guardrail_message: 'Prompt injection detected',
      tool_name: 'search_web',
    };
    const { container } = render(<SpanDetailsPanel span={guardrailSpan} />);
    expect(container.textContent).toContain('拦截');
  });

  it('无 input/output 时不崩溃', () => {
    const minimalSpan = {
      id: 's2',
      trace_id: 't2',
      name: 'test',
      type: 'tool' as const,
      status: 'completed' as const,
      duration_ms: 10,
      start_time: '2026-01-01T12:00:00Z',
    };
    const { container } = render(<SpanDetailsPanel span={minimalSpan} />);
    expect(container).toBeTruthy();
  });
});

/* ---------- TraceStatsPanel ---------- */

const baseStats = {
  total_traces: 100,
  total_spans: 500,
  avg_duration_ms: 234.5,
  total_tokens: { total_tokens: 12000, prompt_tokens: 8000, completion_tokens: 4000 },
  guardrail_stats: { total: 20, triggered: 3 },
  error_rate: 0.05,
};

describe('TraceStatsPanel', () => {
  it('渲染总 Trace 数', () => {
    render(<TraceStatsPanel stats={baseStats} />);
    expect(document.body.textContent).toContain('100');
  });

  it('渲染总 Span 数', () => {
    render(<TraceStatsPanel stats={baseStats} />);
    expect(document.body.textContent).toContain('500');
  });

  it('渲染平均耗时', () => {
    render(<TraceStatsPanel stats={baseStats} />);
    // toFixed(0) → "235" or "234"
    const text = document.body.textContent ?? '';
    expect(text).toMatch(/23[45]/);
  });

  it('渲染 Guardrail 拦截统计', () => {
    render(<TraceStatsPanel stats={baseStats} />);
    const text = document.body.textContent ?? '';
    expect(text).toContain('3');
    expect(text).toContain('20');
  });

  it('渲染错误率', () => {
    render(<TraceStatsPanel stats={baseStats} />);
    // (0.05 * 100).toFixed(1) → "5.0"
    expect(document.body.textContent).toContain('5.0');
  });

  it('零值不崩溃', () => {
    const zeroStats = {
      total_traces: 0,
      total_spans: 0,
      avg_duration_ms: 0,
      total_tokens: { total_tokens: 0, prompt_tokens: 0, completion_tokens: 0 },
      guardrail_stats: { total: 0, triggered: 0 },
      error_rate: 0,
    };
    const { container } = render(<TraceStatsPanel stats={zeroStats} />);
    expect(container).toBeTruthy();
  });
});
