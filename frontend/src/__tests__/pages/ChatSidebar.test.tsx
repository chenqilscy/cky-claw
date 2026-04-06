import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';

// Mock 服务
const mockAgentList = vi.fn();
const mockListSessions = vi.fn();
vi.mock('../../services/agentService', () => ({
  agentService: {
    list: (...args: unknown[]) => mockAgentList(...args),
  },
}));
vi.mock('../../services/chatService', () => ({
  chatService: {
    listSessions: (...args: unknown[]) => mockListSessions(...args),
  },
}));

import ChatSidebar from '../../pages/chat/ChatSidebar';

describe('ChatSidebar', () => {
  const defaultProps = {
    currentSessionId: null,
    onSelectSession: vi.fn(),
    onNewSession: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockAgentList.mockResolvedValue({
      data: [{ name: 'test-agent', model: 'gpt-4' }],
      total: 1,
      limit: 100,
      offset: 0,
    });
    mockListSessions.mockResolvedValue({
      data: [
        {
          id: 'session-1',
          agent_name: 'test-agent',
          title: '测试对话',
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    });
  });

  it('渲染选择 Agent 标签', () => {
    const { container } = render(<ChatSidebar {...defaultProps} />);
    expect(container.textContent).toContain('选择 Agent');
  });

  it('渲染新建对话按钮', () => {
    const { container } = render(<ChatSidebar {...defaultProps} />);
    expect(container.textContent).toContain('新建对话');
  });

  it('渲染历史对话标签', () => {
    const { container } = render(<ChatSidebar {...defaultProps} />);
    expect(container.textContent).toContain('历史对话');
  });

  it('加载 Agent 列表', async () => {
    render(<ChatSidebar {...defaultProps} />);
    await waitFor(() => {
      expect(mockAgentList).toHaveBeenCalledWith({ limit: 100 });
    });
  });
});
