import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, fireEvent } from '@testing-library/react';

/* ---------- mock checkpointService ---------- */
const mockList = vi.fn();
const mockGetLatest = vi.fn();
const mockDelete = vi.fn();
vi.mock('../../services/checkpointService', () => ({
  checkpointService: {
    list: (...args: unknown[]) => mockList(...args),
    getLatest: (...args: unknown[]) => mockGetLatest(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}));

import CheckpointPage from '../../pages/checkpoints/CheckpointPage';

const MOCK_CHECKPOINT = {
  checkpoint_id: 'cp-1',
  run_id: 'run-1',
  turn_count: 3,
  current_agent_name: 'test-agent',
  messages: [{ role: 'user', content: 'hello' }, { role: 'assistant', content: 'hi' }],
  token_usage: { prompt_tokens: 100, completion_tokens: 50 },
  context: {},
  created_at: '2024-06-01T12:00:00Z',
};

describe('CheckpointPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ data: [MOCK_CHECKPOINT], total: 1 });
    mockDelete.mockResolvedValue(undefined);
  });

  it('渲染页面标题', () => {
    const { container } = render(<CheckpointPage />);
    const text = container.textContent ?? '';
    expect(text).toContain('检查点管理');
  });

  it('渲染搜索框和查询按钮', () => {
    const { container } = render(<CheckpointPage />);
    const text = container.textContent ?? '';
    expect(text).toContain('查询');
    const input = container.querySelector('input');
    expect(input).toBeTruthy();
  });

  it('空 Run ID 时查询按钮禁用', () => {
    const { container } = render(<CheckpointPage />);
    const btn = container.querySelector('button');
    expect(btn).toBeTruthy();
    expect(btn!.disabled).toBe(true);
  });

  it('输入 Run ID 后点击查询调用 list 接口', async () => {
    const { container } = render(<CheckpointPage />);
    const input = container.querySelector('input')!;

    await act(async () => {
      fireEvent.change(input, { target: { value: 'run-1' } });
    });

    const btn = container.querySelector('button')!;
    expect(btn.disabled).toBe(false);

    await act(async () => {
      fireEvent.click(btn);
    });

    expect(mockList).toHaveBeenCalledWith('run-1');
  });

  it('显示检查点列表数据', async () => {
    const { container } = render(<CheckpointPage />);
    const input = container.querySelector('input')!;

    await act(async () => {
      fireEvent.change(input, { target: { value: 'run-1' } });
    });
    await act(async () => {
      fireEvent.click(container.querySelector('button')!);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const text = container.textContent ?? '';
    expect(text).toContain('test-agent');
    expect(text).toContain('3'); // turn_count
    expect(text).toContain('cp-1'); // checkpoint_id
  });

  it('显示消息数和 Token 使用', async () => {
    const { container } = render(<CheckpointPage />);
    const input = container.querySelector('input')!;

    await act(async () => {
      fireEvent.change(input, { target: { value: 'run-1' } });
    });
    await act(async () => {
      fireEvent.click(container.querySelector('button')!);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const text = container.textContent ?? '';
    expect(text).toContain('2'); // messages.length
    expect(text).toContain('150'); // 100+50
  });
});
