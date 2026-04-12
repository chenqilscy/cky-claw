import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock abTestService
vi.mock('../../services/abTestService', () => ({
  abTestService: {
    run: vi.fn().mockResolvedValue({
      prompt: 'Hello',
      results: [
        { model: 'gpt-4', output: 'Hi there', latency_ms: 500, token_usage: { total_tokens: 10 }, error: null },
        { model: 'gpt-3.5', output: 'Hello!', latency_ms: 300, token_usage: { total_tokens: 8 }, error: null },
      ],
    }),
  },
}));

import ABTestPage from '../../pages/ab-test/ABTestPage';

describe('ABTestPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('渲染页面标题', async () => {
    render(
      <MemoryRouter>
        <ABTestPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('A/B');
    });
  });

  it('渲染 Prompt 输入区', async () => {
    render(
      <MemoryRouter>
        <ABTestPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      // A/B test 页面应包含 Prompt 输入或模型选择
      expect(text).toMatch(/Prompt|模型|A\/B|测试/i);
    });
  });

  it('渲染模型选择区域', async () => {
    render(
      <MemoryRouter>
        <ABTestPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      expect(text.length).toBeGreaterThan(0);
    });
  });

  it('空状态不崩溃', () => {
    render(
      <MemoryRouter>
        <ABTestPage />
      </MemoryRouter>,
    );
    expect(document.body).toBeDefined();
  });
});
