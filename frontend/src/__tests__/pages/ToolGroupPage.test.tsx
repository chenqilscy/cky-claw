import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

/* ---------- mock toolGroupService ---------- */
const mockList = vi.fn();
vi.mock('../../services/toolGroupService', () => ({
  toolGroupService: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
}));

/* ---------- mock ProTable ---------- */
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: Record<string, unknown>) => {
    const { headerTitle, toolBarRender, dataSource } = props as {
      headerTitle?: React.ReactNode;
      toolBarRender?: () => React.ReactNode[];
      dataSource?: Array<{ name: string }>;
    };
    return (
      <div data-testid="pro-table">
        <div data-testid="header-title">{headerTitle}</div>
        <div data-testid="toolbar">{typeof toolBarRender === 'function' ? toolBarRender() : null}</div>
        <div data-testid="data">
          {dataSource?.map((d, i) => <span key={i}>{d.name}</span>)}
        </div>
      </div>
    );
  },
}));

import ToolGroupPage from '../../pages/tool-groups/ToolGroupPage';

describe('ToolGroupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      data: [
        { id: '1', name: 'search-tools', description: '搜索工具', source: 'builtin', is_enabled: true, tools: [] },
      ],
      total: 1,
    });
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ToolGroupPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('工具组管理');
  });

  it('渲染新建按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ToolGroupPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('新建工具组');
  });

  it('调用列表接口', async () => {
    await act(async () => {
      render(<ToolGroupPage />);
    });
    expect(mockList).toHaveBeenCalled();
  });

  it('加载失败不崩溃', async () => {
    mockList.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ToolGroupPage />));
    });
    expect(container).toBeTruthy();
  });
});
