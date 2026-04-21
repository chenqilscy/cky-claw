import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { App } from 'antd';
import { buildActionColumn } from '../../components/CrudTable';
import type { CrudTableActions } from '../../components/CrudTable';

interface TestRecord {
  id: string;
  name: string;
  is_system?: boolean;
}

function makeActions(overrides?: Partial<CrudTableActions<TestRecord>>): CrudTableActions<TestRecord> {
  return {
    openEdit: vi.fn(),
    openCreate: vi.fn(),
    handleDelete: vi.fn(),
    ...overrides,
  };
}

/** 渲染操作列单元格 */
function renderCell(
  actions: CrudTableActions<TestRecord>,
  record: TestRecord,
  opts?: Parameters<typeof buildActionColumn<TestRecord>>[1],
) {
  const col = buildActionColumn<TestRecord>(actions, opts);
  const renderFn = col.render as (val: unknown, record: TestRecord, index: number) => React.ReactNode;
  return render(<App>{renderFn(undefined, record, 0)}</App>);
}

describe('buildActionColumn', () => {
  it('渲染编辑按钮和更多下拉', () => {
    const actions = makeActions();
    renderCell(actions, { id: '1', name: 'Agent-A' });
    expect(screen.getByText('编辑')).toBeTruthy();
  });

  it('点击编辑按钮调用 openEdit', async () => {
    const actions = makeActions();
    const record = { id: '1', name: 'Agent-A' };
    renderCell(actions, record);
    await act(async () => {
      fireEvent.click(screen.getByText('编辑'));
    });
    expect(actions.openEdit).toHaveBeenCalledWith(record);
  });

  it('hideEdit 隐藏编辑按钮', () => {
    const actions = makeActions();
    renderCell(actions, { id: '1', name: 'X' }, { hideEdit: true });
    expect(screen.queryByText('编辑')).toBeNull();
  });

  it('isDisabled 禁用编辑按钮', () => {
    const actions = makeActions();
    renderCell(actions, { id: '1', name: 'admin', is_system: true }, {
      isDisabled: (r) => !!r.is_system,
      disabledTooltip: '系统角色不可操作',
    });
    const editBtn = screen.getByText('编辑').closest('button');
    expect(editBtn?.disabled).toBe(true);
  });

  it('isDisabled=false 时编辑按钮可用', () => {
    const actions = makeActions();
    renderCell(actions, { id: '1', name: 'dev', is_system: false }, {
      isDisabled: (r) => !!r.is_system,
    });
    const editBtn = screen.getByText('编辑').closest('button');
    expect(editBtn?.disabled).toBe(false);
  });

  it('extraItems 传入后返回列定义正常', () => {
    const onPreview = vi.fn();
    const actions = makeActions();
    const col = buildActionColumn<TestRecord>(actions, {
      extraItems: () => [
        { key: 'preview', label: '预览', onClick: onPreview },
      ],
    });
    expect(col.title).toBe('操作');
    // 渲染单元格不报错
    const renderFn = col.render as (val: unknown, record: TestRecord, index: number) => React.ReactNode;
    const { container } = render(<App>{renderFn(undefined, { id: '1', name: 'Wf' }, 0)}</App>);
    // 编辑按钮 + more 按钮都渲染
    expect(container.querySelectorAll('button').length).toBeGreaterThanOrEqual(2);
  });

  it('返回的列定义包含 title 和 fixed', () => {
    const col = buildActionColumn<TestRecord>(makeActions());
    expect(col.title).toBe('操作');
    expect(col.fixed).toBe('right');
  });

  it('自定义 width', () => {
    const col = buildActionColumn<TestRecord>(makeActions(), { width: 200 });
    expect(col.width).toBe(200);
  });
});
