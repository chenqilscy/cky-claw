import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { App } from 'antd';
import ToolEditor from '../../components/ToolEditor';
import type { ToolDefinition } from '../../services/toolGroupService';

/* ---------- mock Monaco Editor ---------- */
vi.mock('@monaco-editor/react', () => ({
  default: (props: { value?: string; onChange?: (v: string) => void; }) => (
    <textarea
      data-testid="monaco-editor"
      value={props.value ?? ''}
      onChange={(e) => props.onChange?.(e.target.value)}
    />
  ),
  __esModule: true,
}));

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <App>{children}</App>
);

describe('ToolEditor', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('空状态显示占位提示', () => {
    render(
      <Wrapper>
        <ToolEditor value={[]} onChange={mockOnChange} />
      </Wrapper>,
    );
    expect(screen.getByText('暂无工具定义')).toBeTruthy();
  });

  it('渲染工具列表', () => {
    const tools: ToolDefinition[] = [
      {
        name: 'web_search',
        description: '搜索互联网',
        parameters_schema: {
          type: 'object',
          properties: { query: { type: 'string', description: '关键词' } },
          required: ['query'],
        },
      },
      {
        name: 'fetch_page',
        description: '获取网页',
        parameters_schema: { type: 'object', properties: {} },
      },
    ];

    render(
      <Wrapper>
        <ToolEditor value={tools} onChange={mockOnChange} />
      </Wrapper>,
    );
    expect(screen.getByText(/web_search/)).toBeTruthy();
    expect(screen.getByText(/fetch_page/)).toBeTruthy();
    expect(screen.getByText(/搜索互联网/)).toBeTruthy();
    /* 参数摘要 */
    expect(screen.getByText(/query \(string, 必填\)/)).toBeTruthy();
  });

  it('添加工具按钮打开弹窗', async () => {
    render(
      <Wrapper>
        <ToolEditor value={[]} onChange={mockOnChange} />
      </Wrapper>,
    );
    const addBtn = screen.getAllByText('添加工具')[0]!;
    await act(async () => { fireEvent.click(addBtn); });
    await waitFor(() => {
      expect(screen.getByText('添加工具', { selector: '.ant-modal-title' })).toBeTruthy();
    });
  });

  it('删除工具触发 onChange', async () => {
    const tools: ToolDefinition[] = [
      { name: 'test_tool', description: '测试', parameters_schema: { type: 'object', properties: {} } },
    ];
    render(
      <Wrapper>
        <ToolEditor value={tools} onChange={mockOnChange} />
      </Wrapper>,
    );
    /* 点击删除图标 → Popconfirm */
    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    await act(async () => { fireEvent.click(deleteBtn); });
    /* Antd 5 Popconfirm 确认按钮 */
    await waitFor(() => {
      const okBtn = document.querySelector('.ant-popconfirm .ant-btn-primary');
      expect(okBtn).toBeTruthy();
    });
    const okBtn = document.querySelector('.ant-popconfirm .ant-btn-primary') as HTMLElement;
    await act(async () => { fireEvent.click(okBtn); });
    expect(mockOnChange).toHaveBeenCalledWith([]);
  });

  it('切换到 JSON 模式', async () => {
    const tools: ToolDefinition[] = [
      { name: 'a', description: 'b', parameters_schema: { type: 'object', properties: {} } },
    ];
    render(
      <Wrapper>
        <ToolEditor value={tools} onChange={mockOnChange} />
      </Wrapper>,
    );
    /* 点击 JSON 标签 */
    const jsonLabel = screen.getByText('JSON');
    await act(async () => { fireEvent.click(jsonLabel); });
    /* 应该看到 Monaco editor（mocked as textarea） */
    expect(screen.getByTestId('monaco-editor')).toBeTruthy();
  });

  it('只读模式不显示添加按钮', () => {
    render(
      <Wrapper>
        <ToolEditor value={[]} onChange={mockOnChange} readOnly />
      </Wrapper>,
    );
    /* 不应有"添加工具"按钮（Empty 里那个和工具栏那个都不渲染） */
    expect(screen.queryByRole('button', { name: /添加工具/ })).toBeNull();
  });

  it('复制工具触发 onChange', async () => {
    const tools: ToolDefinition[] = [
      { name: 'my_tool', description: '工具', parameters_schema: { type: 'object', properties: {} } },
    ];
    render(
      <Wrapper>
        <ToolEditor value={tools} onChange={mockOnChange} />
      </Wrapper>,
    );
    const copyBtn = screen.getByRole('button', { name: /copy/i });
    await act(async () => { fireEvent.click(copyBtn); });
    expect(mockOnChange).toHaveBeenCalledWith([
      tools[0],
      expect.objectContaining({ name: 'my_tool_copy' }),
    ]);
  });

  it('应用模板覆盖当前工具列表', async () => {
    render(
      <Wrapper>
        <ToolEditor value={[]} onChange={mockOnChange} />
      </Wrapper>,
    );
    /* 打开模板下拉 — antd Select 会渲染 dropdown portal */
    const templateSelect = document.querySelector('.ant-select:not(.ant-segmented *)') as HTMLElement;
    expect(templateSelect).toBeTruthy();
    await act(async () => {
      fireEvent.mouseDown(templateSelect!.querySelector('.ant-select-selector')!);
    });
    await waitFor(() => {
      expect(document.querySelector('.ant-select-dropdown')).toBeTruthy();
    });
    /* 选择"网络搜索" */
    const options = document.querySelectorAll('.ant-select-item-option');
    const searchOption = Array.from(options).find((o) => o.textContent?.includes('网络搜索'));
    expect(searchOption).toBeTruthy();
    await act(async () => { fireEvent.click(searchOption!); });
    expect(mockOnChange).toHaveBeenCalled();
    const calledWith = mockOnChange.mock.calls[0]![0] as ToolDefinition[];
    expect(calledWith.length).toBe(2);
    expect(calledWith[0]!.name).toBe('web_search');
  });
});
