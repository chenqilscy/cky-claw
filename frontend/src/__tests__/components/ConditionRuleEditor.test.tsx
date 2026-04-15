import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { App } from 'antd';
import ConditionRuleEditor from '../../components/ConditionRuleEditor';

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

describe('ConditionRuleEditor', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('空条件显示占位提示', () => {
    render(
      <Wrapper>
        <ConditionRuleEditor value={{}} onChange={mockOnChange} />
      </Wrapper>,
    );
    expect(screen.getByText('无条件规则（始终启用）')).toBeTruthy();
  });

  it('已有规则时渲染规则列表', () => {
    const conditions = {
      match: 'all',
      rules: [
        { field: 'env', operator: 'equals', value: 'production' },
      ],
    };
    render(
      <Wrapper>
        <ConditionRuleEditor value={conditions} onChange={mockOnChange} />
      </Wrapper>,
    );
    /* 应存在匹配模式选择 */
    expect(screen.getByText('匹配模式：')).toBeTruthy();
  });

  it('添加规则触发 onChange', async () => {
    render(
      <Wrapper>
        <ConditionRuleEditor value={{}} onChange={mockOnChange} />
      </Wrapper>,
    );
    const addBtn = screen.getByText('添加规则');
    await act(async () => { fireEvent.click(addBtn); });
    expect(mockOnChange).toHaveBeenCalled();
    const called = mockOnChange.mock.calls[0][0] as Record<string, unknown>;
    expect(called).toHaveProperty('match', 'all');
    expect(called).toHaveProperty('rules');
    const rules = called.rules as Array<Record<string, unknown>>;
    expect(rules.length).toBe(1);
    expect(rules[0].field).toBe('env');
  });

  it('删除规则触发 onChange', async () => {
    const conditions = {
      match: 'all',
      rules: [
        { field: 'env', operator: 'equals', value: 'production' },
      ],
    };
    render(
      <Wrapper>
        <ConditionRuleEditor value={conditions} onChange={mockOnChange} />
      </Wrapper>,
    );
    /* 删除按钮 */
    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    await act(async () => { fireEvent.click(deleteBtn); });
    expect(mockOnChange).toHaveBeenCalledWith({});
  });

  it('切换到 JSON 模式', async () => {
    render(
      <Wrapper>
        <ConditionRuleEditor value={{}} onChange={mockOnChange} />
      </Wrapper>,
    );
    const jsonLabel = screen.getByText('JSON');
    await act(async () => { fireEvent.click(jsonLabel); });
    expect(screen.getByTestId('monaco-editor')).toBeTruthy();
  });

  it('只读模式不显示添加按钮', () => {
    render(
      <Wrapper>
        <ConditionRuleEditor value={{}} onChange={mockOnChange} readOnly />
      </Wrapper>,
    );
    expect(screen.queryByText('添加规则')).toBeNull();
  });
});
