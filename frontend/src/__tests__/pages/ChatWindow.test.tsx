import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

/* ---------- mock chatService ---------- */
const mockCreateSession = vi.fn();
const mockRunStream = vi.fn();
vi.mock('../../services/chatService', () => ({
  chatService: {
    createSession: (...args: unknown[]) => mockCreateSession(...args),
    runStream: (...args: unknown[]) => mockRunStream(...args),
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
});
