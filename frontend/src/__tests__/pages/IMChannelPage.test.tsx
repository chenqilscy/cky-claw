import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

/* ---------- mock imChannelService ---------- */
const mockListIMChannels = vi.fn();
vi.mock('../../services/imChannelService', () => ({
  CHANNEL_TYPES: ['wecom', 'dingtalk', 'feishu', 'slack', 'webhook'],
  listIMChannels: (...args: unknown[]) => mockListIMChannels(...args),
  createIMChannel: vi.fn().mockResolvedValue({}),
  updateIMChannel: vi.fn().mockResolvedValue({}),
  deleteIMChannel: vi.fn().mockResolvedValue({}),
}));

import IMChannelPage from '../../pages/im-channels/IMChannelPage';

describe('IMChannelPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListIMChannels.mockResolvedValue({
      data: [
        {
          id: '1', name: 'test-wecom', channel_type: 'wecom',
          webhook_url: 'https://hook', is_enabled: true, agent_name: 'bot',
        },
      ],
      total: 1,
    });
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><IMChannelPage /></TestQueryWrapper>));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('IM 渠道管理');
  });

  it('渲染新建按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><IMChannelPage /></TestQueryWrapper>));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('创建渠道');
  });

  it('调用列表接口', async () => {
    await act(async () => {
      render(<TestQueryWrapper><IMChannelPage /></TestQueryWrapper>);
    });
    expect(mockListIMChannels).toHaveBeenCalled();
  });

  it('加载失败不崩溃', async () => {
    mockListIMChannels.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><IMChannelPage /></TestQueryWrapper>));
    });
    expect(container).toBeTruthy();
  });
});
