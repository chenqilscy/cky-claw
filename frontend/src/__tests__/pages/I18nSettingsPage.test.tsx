import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

/* ---------- mock services ---------- */
const mockAgentList = vi.fn();
const mockLocaleList = vi.fn();
vi.mock('../../services/agentLocaleService', () => ({
  agentLocaleService: {
    list: (...args: unknown[]) => mockLocaleList(...args),
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
}));
vi.mock('../../services/agentService', () => ({
  agentService: {
    list: (...args: unknown[]) => mockAgentList(...args),
  },
}));

/* ---------- mock ProTable ---------- */
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: Record<string, unknown>) => {
    const { headerTitle, toolBarRender, dataSource } = props as {
      headerTitle?: React.ReactNode;
      toolBarRender?: () => React.ReactNode[];
      dataSource?: Array<{ locale: string }>;
    };
    return (
      <div data-testid="pro-table">
        <div data-testid="header-title">{headerTitle}</div>
        <div data-testid="toolbar">{toolBarRender?.()}</div>
        <div data-testid="data">
          {dataSource?.map((d, i) => <span key={i}>{d.locale}</span>)}
        </div>
      </div>
    );
  },
}));

import I18nSettingsPage from '../../pages/agents/I18nSettingsPage';

describe('I18nSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAgentList.mockResolvedValue({
      data: [{ name: 'test-bot', description: 'test' }],
    });
    mockLocaleList.mockResolvedValue({
      data: [
        { id: '1', locale: 'zh-CN', instructions: '你好', is_default: true },
      ],
      total: 1,
    });
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<I18nSettingsPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('语言版本');
  });

  it('加载 Agent 列表', async () => {
    await act(async () => {
      render(<I18nSettingsPage />);
    });
    expect(mockAgentList).toHaveBeenCalled();
  });

  it('渲染 Agent 下拉选择器', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<I18nSettingsPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('选择 Agent');
  });

  it('加载失败不崩溃', async () => {
    mockAgentList.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<I18nSettingsPage />));
    });
    expect(container).toBeTruthy();
  });
});
