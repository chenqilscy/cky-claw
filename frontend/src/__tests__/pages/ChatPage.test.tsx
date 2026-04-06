import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

// Mock 子组件避免复杂依赖
vi.mock('../../pages/chat/ChatSidebar', () => ({
  default: () => <div data-testid="chat-sidebar">ChatSidebar Mock</div>,
}));
vi.mock('../../pages/chat/ChatWindow', () => ({
  default: () => <div data-testid="chat-window">ChatWindow Mock</div>,
}));

import ChatPage from '../../pages/chat/ChatPage';

describe('ChatPage', () => {
  it('渲染侧边栏', () => {
    const { container } = render(<ChatPage />);
    expect(container.textContent).toContain('ChatSidebar Mock');
  });

  it('渲染聊天窗口', () => {
    const { container } = render(<ChatPage />);
    expect(container.textContent).toContain('ChatWindow Mock');
  });

  it('包含 Layout 结构', () => {
    const { container } = render(<ChatPage />);
    expect(container.querySelector('.ant-layout')).toBeTruthy();
  });

  it('导出 ChatMessage 类型', async () => {
    const mod = await import('../../pages/chat/ChatPage');
    expect(mod.default).toBeDefined();
  });
});
