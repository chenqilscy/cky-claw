import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, fireEvent, screen, waitFor } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';
import type { UseQueryResult, UseMutationResult } from '@tanstack/react-query';

/* ---------- mock ProTable ---------- */
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: Record<string, unknown>) => {
    const {
      dataSource, loading, rowKey, pagination,
    } = props as {
      dataSource?: Array<Record<string, unknown>>;
      loading?: boolean;
      rowKey?: string;
      pagination?: { total?: number; showTotal?: (t: number) => string };
    };
    return (
      <div data-testid="pro-table">
        {loading && <span data-testid="loading">loading</span>}
        <span data-testid="row-key">{rowKey}</span>
        {pagination?.total !== undefined && (
          <span data-testid="total">{pagination.total}</span>
        )}
        <ul data-testid="data">
          {dataSource?.map((d, i) => (
            <li key={i} data-testid={`row-${i}`}>{JSON.stringify(d)}</li>
          ))}
        </ul>
      </div>
    );
  },
}));

import { CrudTable } from '../../components/CrudTable';
import type { CrudTableProps, PagedResult } from '../../components/CrudTable';

/* ---------- helpers ---------- */

interface TestItem {
  id: string;
  name: string;
  description: string;
}

const sampleData: TestItem[] = [
  { id: '1', name: 'item-1', description: '第一项' },
  { id: '2', name: 'item-2', description: '第二项' },
];

/** 创建一个假的 UseQueryResult */
function fakeQueryResult(
  data: PagedResult<TestItem> | undefined,
  overrides?: Partial<UseQueryResult<PagedResult<TestItem>>>,
): UseQueryResult<PagedResult<TestItem>> {
  return {
    data,
    isLoading: false,
    isError: false,
    error: null,
    isFetching: false,
    isSuccess: true,
    isPending: false,
    isLoadingError: false,
    isRefetchError: false,
    isStale: false,
    isFetched: true,
    isFetchedAfterMount: true,
    isPlaceholderData: false,
    isRefetching: false,
    isInitialLoading: false,
    status: 'success',
    fetchStatus: 'idle',
    dataUpdatedAt: Date.now(),
    errorUpdatedAt: 0,
    failureCount: 0,
    failureReason: null,
    errorUpdateCount: 0,
    refetch: vi.fn().mockResolvedValue({ data }),
    promise: Promise.resolve(data!),
    ...overrides,
  } as UseQueryResult<PagedResult<TestItem>>;
}

/** 创建一个假的 UseMutationResult */
function fakeMutation<TArgs = unknown>(
  mutateAsyncFn?: (args: TArgs) => Promise<unknown>,
): UseMutationResult<unknown, Error, TArgs> {
  const mutateAsync = mutateAsyncFn ?? vi.fn().mockResolvedValue({});
  return {
    mutate: vi.fn(),
    mutateAsync: mutateAsync as UseMutationResult<unknown, Error, TArgs>['mutateAsync'],
    isPending: false,
    isIdle: true,
    isSuccess: false,
    isError: false,
    error: null,
    data: undefined,
    variables: undefined,
    status: 'idle',
    failureCount: 0,
    failureReason: null,
    reset: vi.fn(),
    context: undefined,
    submittedAt: 0,
  } as unknown as UseMutationResult<unknown, Error, TArgs>;
}

/** 默认 props */
function defaultProps(
  overrides?: Partial<CrudTableProps<TestItem, Partial<TestItem>, { id: string; data: Partial<TestItem> }>>,
): CrudTableProps<TestItem, Partial<TestItem>, { id: string; data: Partial<TestItem> }> {
  return {
    title: '测试表格',
    columns: [
      { title: '名称', dataIndex: 'name' },
      { title: '描述', dataIndex: 'description' },
    ],
    queryResult: fakeQueryResult({ data: sampleData, total: 2 }),
    renderForm: (_form, editing) => (
      <div data-testid="form-content">
        {editing ? `编辑 ${editing.name}` : '新建'}
      </div>
    ),
    ...overrides,
  };
}

/* ---------- tests ---------- */

describe('CrudTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题和图标', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ title: '工具组管理', icon: <span data-testid="icon">🔧</span> })} />
        </TestQueryWrapper>,
      ));
    });
    expect(container.textContent).toContain('工具组管理');
    expect(screen.getByTestId('icon')).toBeTruthy();
  });

  it('渲染数据行', async () => {
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps()} />
        </TestQueryWrapper>,
      );
    });
    expect(screen.getByTestId('data').children.length).toBe(2);
  });

  it('显示加载状态', async () => {
    const qr = fakeQueryResult(undefined, { isLoading: true });
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ queryResult: qr })} />
        </TestQueryWrapper>,
      );
    });
    expect(screen.getByTestId('loading')).toBeTruthy();
  });

  it('默认显示新建按钮', async () => {
    const cm = fakeMutation<Partial<TestItem>>();
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ createMutation: cm })} />
        </TestQueryWrapper>,
      ));
    });
    expect(container.textContent).toContain('新建');
  });

  it('onCreateClick=false 时隐藏新建按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ onCreateClick: false })} />
        </TestQueryWrapper>,
      ));
    });
    // 不应有"新建"按钮
    const buttons = container.querySelectorAll('button');
    const createBtn = Array.from(buttons).find((b) => b.textContent?.includes('新建'));
    expect(createBtn).toBeUndefined();
  });

  it('自定义 createButtonText', async () => {
    const cm = fakeMutation<Partial<TestItem>>();
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ createMutation: cm, createButtonText: '注册' })} />
        </TestQueryWrapper>,
      ));
    });
    expect(container.textContent).toContain('注册');
  });

  it('点击新建按钮打开 Modal', async () => {
    const cm = fakeMutation<Partial<TestItem>>();
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({
            createMutation: cm,
            createButtonText: '新建测试',
          })} />
        </TestQueryWrapper>,
      ));
    });
    const createBtn = Array.from(container.querySelectorAll('button'))
      .find((b) => b.textContent?.includes('新建测试'));
    expect(createBtn).toBeTruthy();
    await act(async () => {
      fireEvent.click(createBtn!);
    });
    // Modal 应该出现，包含表单内容
    await waitFor(() => {
      expect(screen.getByTestId('form-content').textContent).toBe('新建');
    });
  });

  it('showRefresh 显示刷新按钮', async () => {
    const refetch = vi.fn().mockResolvedValue({});
    const qr = fakeQueryResult({ data: sampleData, total: 2 }, { refetch });
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ queryResult: qr, showRefresh: true })} />
        </TestQueryWrapper>,
      ));
    });
    const refreshBtn = Array.from(container.querySelectorAll('button'))
      .find((b) => b.textContent?.includes('刷新'));
    expect(refreshBtn).toBeTruthy();
    await act(async () => {
      fireEvent.click(refreshBtn!);
    });
    expect(refetch).toHaveBeenCalled();
  });

  it('columns 工厂函数接收 actions', async () => {
    const cm = fakeMutation<Partial<TestItem>>();
    const dm = fakeMutation<string>();
    const columnsFactory = vi.fn().mockReturnValue([
      { title: '名称', dataIndex: 'name' },
    ]);
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({
            columns: columnsFactory,
            createMutation: cm,
            deleteMutation: dm,
          })} />
        </TestQueryWrapper>,
      );
    });
    expect(columnsFactory).toHaveBeenCalledWith(
      expect.objectContaining({
        openEdit: expect.any(Function),
        openCreate: expect.any(Function),
        handleDelete: expect.any(Function),
      }),
    );
  });

  it('modalTitle 自定义', async () => {
    const cm = fakeMutation<Partial<TestItem>>();
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({
            createMutation: cm,
            modalTitle: (editing) => editing ? '修改项目' : '添加项目',
            createButtonText: '添加',
          })} />
        </TestQueryWrapper>,
      ));
    });
    const addBtn = Array.from(container.querySelectorAll('button'))
      .find((b) => b.textContent?.includes('添加'));
    await act(async () => {
      fireEvent.click(addBtn!);
    });
    await waitFor(() => {
      expect(document.body.textContent).toContain('添加项目');
    });
  });

  it('rowKey 默认为 id', async () => {
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps()} />
        </TestQueryWrapper>,
      );
    });
    expect(screen.getByTestId('row-key').textContent).toBe('id');
  });

  it('rowKey 自定义', async () => {
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ rowKey: 'name' })} />
        </TestQueryWrapper>,
      );
    });
    expect(screen.getByTestId('row-key').textContent).toBe('name');
  });

  it('total 从 queryResult 读取', async () => {
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps()} />
        </TestQueryWrapper>,
      );
    });
    expect(screen.getByTestId('total').textContent).toBe('2');
  });

  it('total 可覆盖', async () => {
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ total: 99 })} />
        </TestQueryWrapper>,
      );
    });
    expect(screen.getByTestId('total').textContent).toBe('99');
  });

  it('空数据不崩溃', async () => {
    const qr = fakeQueryResult({ data: [], total: 0 });
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ queryResult: qr })} />
        </TestQueryWrapper>,
      ));
    });
    expect(container).toBeTruthy();
    expect(screen.getByTestId('data').children.length).toBe(0);
  });

  it('queryResult 为 undefined 不崩溃', async () => {
    const qr = fakeQueryResult(undefined);
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({ queryResult: qr })} />
        </TestQueryWrapper>,
      ));
    });
    expect(container).toBeTruthy();
  });

  it('extraToolbar 渲染', async () => {
    await act(async () => {
      render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({
            extraToolbar: <span data-testid="extra">筛选</span>,
          })} />
        </TestQueryWrapper>,
      );
    });
    expect(screen.getByTestId('extra').textContent).toBe('筛选');
  });

  it('onCreateClick 自定义回调', async () => {
    const onClick = vi.fn();
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <TestQueryWrapper>
          <CrudTable {...defaultProps({
            onCreateClick: onClick,
            createButtonText: '自定义新建',
          })} />
        </TestQueryWrapper>,
      ));
    });
    const btn = Array.from(container.querySelectorAll('button'))
      .find((b) => b.textContent?.includes('自定义新建'));
    expect(btn).toBeTruthy();
    await act(async () => {
      fireEvent.click(btn!);
    });
    expect(onClick).toHaveBeenCalledOnce();
  });
});
