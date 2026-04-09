import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

/* ---------- mock evaluationService ---------- */
const mockListEvals = vi.fn();
const mockListFeedbacks = vi.fn();
const mockGetQuality = vi.fn();
vi.mock('../../services/evaluationService', () => ({
  listEvaluations: (...args: unknown[]) => mockListEvals(...args),
  createEvaluation: vi.fn().mockResolvedValue({}),
  listFeedbacks: (...args: unknown[]) => mockListFeedbacks(...args),
  createFeedback: vi.fn().mockResolvedValue({}),
  getAgentQuality: (...args: unknown[]) => mockGetQuality(...args),
}));

import EvaluationPage from '../../pages/evaluations/EvaluationPage';

describe('EvaluationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListEvals.mockResolvedValue({
      data: [
        { id: 'e1', run_id: 'r1', accuracy: 4, relevance: 3, overall_score: 3.5, eval_method: 'manual', created_at: '2024-01-01' },
      ],
      total: 1,
    });
    mockListFeedbacks.mockResolvedValue({
      data: [],
      total: 0,
    });
    mockGetQuality.mockResolvedValue(null);
  });

  it('渲染 Tabs', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><EvaluationPage /></TestQueryWrapper>));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('评估');
  });

  it('渲染评估列表', async () => {
    await act(async () => {
      render(<TestQueryWrapper><EvaluationPage /></TestQueryWrapper>);
    });
    expect(mockListEvals).toHaveBeenCalled();
  });

  it('渲染新建评估按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><EvaluationPage /></TestQueryWrapper>));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('新建评估');
  });

  it('加载失败不崩溃', async () => {
    mockListEvals.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><EvaluationPage /></TestQueryWrapper>));
    });
    expect(container).toBeTruthy();
  });
});
