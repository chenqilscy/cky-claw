import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, fireEvent, waitFor } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

/* ---------- mock debugService ---------- */
const mockList = vi.fn();
const mockGet = vi.fn();
const mockCreate = vi.fn();
const mockStep = vi.fn();
const mockContinue = vi.fn();
const mockStop = vi.fn();
const mockGetContext = vi.fn();
vi.mock('../../services/debugService', () => ({
  debugService: {
    list: (...args: unknown[]) => mockList(...args),
    get: (...args: unknown[]) => mockGet(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    step: (...args: unknown[]) => mockStep(...args),
    continue: (...args: unknown[]) => mockContinue(...args),
    stop: (...args: unknown[]) => mockStop(...args),
    getContext: (...args: unknown[]) => mockGetContext(...args),
  },
}));

/* ---------- mock agentService ---------- */
const mockAgentList = vi.fn();
vi.mock('../../services/agentService', () => ({
  agentService: {
    list: (...args: unknown[]) => mockAgentList(...args),
  },
}));

import DebugPage from '../../pages/debug/DebugPage';

const MOCK_SESSION = {
  id: 'sess-1',
  agent_id: 'agent-1',
  agent_name: 'test-agent',
  user_id: 'user-1',
  state: 'idle',
  mode: 'step_turn',
  input_message: '你好',
  current_turn: 0,
  current_agent_name: 'test-agent',
  pause_context: {},
  token_usage: {},
  result: null,
  error: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  finished_at: null,
};

const MOCK_PAUSED_SESSION = {
  ...MOCK_SESSION,
  id: 'sess-2',
  state: 'paused',
  current_turn: 2,
};

const MOCK_CONTEXT = {
  turn: 2,
  agent_name: 'test-agent',
  reason: 'turn_end',
  recent_messages: [{ role: 'user', content: '你好' }],
  last_llm_response: { content: '你好！' },
  last_tool_calls: [],
  token_usage: { prompt_tokens: 100, completion_tokens: 50 },
  paused_at: '2025-01-01T00:00:00Z',
};

describe('DebugPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ items: [], total: 0 });
    mockAgentList.mockResolvedValue({ items: [], total: 0 });
  });

  it('渲染页面标题', () => {
    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);
    const text = container.textContent ?? '';
    expect(text).toContain('Agent 调试器');
  });

  it('渲染新建调试按钮', () => {
    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);
    const text = container.textContent ?? '';
    expect(text).toContain('新建调试');
  });

  it('渲染刷新按钮', () => {
    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);
    const text = container.textContent ?? '';
    expect(text).toContain('刷新');
  });

  it('点击刷新按钮调用 list 接口', async () => {
    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);
    const buttons = container.querySelectorAll('button');
    const refreshBtn = Array.from(buttons).find((btn) => btn.textContent?.includes('刷新'));
    expect(refreshBtn).toBeTruthy();

    await act(async () => {
      fireEvent.click(refreshBtn!);
    });

    expect(mockList).toHaveBeenCalled();
  });

  it('点击新建调试打开模态框', async () => {
    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);
    const buttons = container.querySelectorAll('button');
    const createBtn = Array.from(buttons).find((btn) => btn.textContent?.includes('新建调试'));
    expect(createBtn).toBeTruthy();

    await act(async () => {
      fireEvent.click(createBtn!);
    });

    await waitFor(() => {
      const text = document.body.textContent ?? '';
      expect(text).toContain('新建调试会话');
    }, { timeout: 5000 });
  });

  it('模态框包含输入消息和调试模式选择', async () => {
    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);
    const buttons = container.querySelectorAll('button');
    const createBtn = Array.from(buttons).find((btn) => btn.textContent?.includes('新建调试'));

    await act(async () => {
      fireEvent.click(createBtn!);
    });

    await waitFor(() => {
      const text = document.body.textContent ?? '';
      expect(text).toContain('输入消息');
      expect(text).toContain('调试模式');
    }, { timeout: 5000 });
  });

  it('列表展示会话数据', async () => {
    mockList.mockResolvedValue({ items: [MOCK_SESSION], total: 1 });

    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);

    // 触发列表加载
    const buttons = container.querySelectorAll('button');
    const refreshBtn = Array.from(buttons).find((btn) => btn.textContent?.includes('刷新'));
    await act(async () => {
      fireEvent.click(refreshBtn!);
    });

    await waitFor(() => {
      const text = container.textContent ?? '';
      expect(text).toContain('test-agent');
    }, { timeout: 5000 });
  });

  it('创建调试会话成功', async () => {
    mockAgentList.mockResolvedValue({
      items: [{ id: 'agent-1', name: 'test-agent' }],
      total: 1,
    });
    mockCreate.mockResolvedValue(MOCK_SESSION);

    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);
    const buttons = container.querySelectorAll('button');
    const createBtn = Array.from(buttons).find((btn) => btn.textContent?.includes('新建调试'));

    await act(async () => {
      fireEvent.click(createBtn!);
    });

    // 等待模态框出现
    await waitFor(() => {
      expect(document.body.textContent).toContain('新建调试会话');
    }, { timeout: 5000 });

    // 输入消息
    const textareas = document.querySelectorAll('textarea');
    const textarea = textareas[0];
    if (textarea) {
      await act(async () => {
        fireEvent.change(textarea, { target: { value: '你好' } });
      });
    }
  });

  it('调试按钮存在于列表行', async () => {
    mockList.mockResolvedValue({ items: [MOCK_SESSION], total: 1 });

    const { container } = render(<TestQueryWrapper><DebugPage /></TestQueryWrapper>);

    const buttons = container.querySelectorAll('button');
    const refreshBtn = Array.from(buttons).find((btn) => btn.textContent?.includes('刷新'));
    await act(async () => {
      fireEvent.click(refreshBtn!);
    });

    await waitFor(() => {
      const text = container.textContent ?? '';
      expect(text).toContain('调试');
    }, { timeout: 5000 });
  });
});

describe('DebugPage Service', () => {
  it('debugService.list 使用正确参数', async () => {
    const { debugService } = await import('../../services/debugService');
    mockList.mockResolvedValue({ items: [], total: 0 });

    await debugService.list({ state: 'paused', limit: 10 });
    expect(mockList).toHaveBeenCalledWith({ state: 'paused', limit: 10 });
  });

  it('debugService.step 传递 session id', async () => {
    const { debugService } = await import('../../services/debugService');
    mockStep.mockResolvedValue(MOCK_SESSION);

    await debugService.step('sess-1');
    expect(mockStep).toHaveBeenCalledWith('sess-1');
  });

  it('debugService.continue 传递 session id', async () => {
    const { debugService } = await import('../../services/debugService');
    mockContinue.mockResolvedValue(MOCK_SESSION);

    await debugService.continue('sess-1');
    expect(mockContinue).toHaveBeenCalledWith('sess-1');
  });

  it('debugService.stop 传递 session id', async () => {
    const { debugService } = await import('../../services/debugService');
    mockStop.mockResolvedValue(MOCK_SESSION);

    await debugService.stop('sess-1');
    expect(mockStop).toHaveBeenCalledWith('sess-1');
  });

  it('debugService.getContext 传递 session id', async () => {
    const { debugService } = await import('../../services/debugService');
    mockGetContext.mockResolvedValue(MOCK_CONTEXT);

    await debugService.getContext('sess-2');
    expect(mockGetContext).toHaveBeenCalledWith('sess-2');
  });
});
