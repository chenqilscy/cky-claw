import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

/* ---------- mock chatService ---------- */
const mockCreateSession = vi.fn();
const mockRunStream = vi.fn();
const mockGetMessages = vi.fn();
vi.mock('../../services/chatService', () => ({
  chatService: {
    createSession: (...args: unknown[]) => mockCreateSession(...args),
    runStream: (...args: unknown[]) => mockRunStream(...args),
    getMessages: (...args: unknown[]) => mockGetMessages(...args),
  },
}));

/* ---------- mock MarkdownRenderer ---------- */
vi.mock('../../components/MarkdownRenderer', () => ({
  default: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}));

import ChatWindow from '../../pages/chat/ChatWindow';

// jsdom 不实现 scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

describe('ChatWindow', () => {
  const defaultProps = {
    sessionId: 'sess-1',
    agentName: 'test-bot',
    onSessionCreated: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateSession.mockResolvedValue({ id: 'new-sess' });
    // runStream 返回一个 AbortController
    mockRunStream.mockReturnValue(new AbortController());
    // getMessages 默认返回空消息列表
    mockGetMessages.mockResolvedValue({ session_id: 'sess-1', messages: [], total: 0 });
  });

  it('渲染 Agent 名称', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ChatWindow {...defaultProps} />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('test-bot');
  });

  it('无 Agent 时显示提示', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ChatWindow {...defaultProps} agentName="" />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('请选择 Agent');
  });

  it('无消息时显示引导文本', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ChatWindow {...defaultProps} />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('发送消息开始对话');
  });

  it('渲染发送按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ChatWindow {...defaultProps} />));
    });
    // 页面渲染了 SendOutlined 图标按钮
    const buttons = container.querySelectorAll('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('切换 session 时加载历史消息', async () => {
    mockGetMessages.mockResolvedValue({
      session_id: 'sess-1',
      messages: [
        { id: 1, role: 'user', content: '你好', agent_name: null, created_at: '2026-01-01T00:00:00Z' },
        { id: 2, role: 'assistant', content: '你好！有什么可以帮助你？', agent_name: 'test-bot', created_at: '2026-01-01T00:00:01Z' },
      ],
      total: 2,
    });
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ChatWindow {...defaultProps} />));
    });
    // 等待异步加载完成
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
    expect(mockGetMessages).toHaveBeenCalledWith('sess-1');
    const text = container.textContent ?? '';
    expect(text).toContain('你好');
    expect(text).toContain('有什么可以帮助你');
  });

  it('sessionId 为 null 时不调用 getMessages', async () => {
    await act(async () => {
      render(<ChatWindow {...defaultProps} sessionId={null} />);
    });
    expect(mockGetMessages).not.toHaveBeenCalled();
  });
});
