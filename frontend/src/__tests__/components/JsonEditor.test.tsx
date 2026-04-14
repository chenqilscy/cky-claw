import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

/* ---------- mock themeStore ---------- */
let mockThemeMode = 'light';
vi.mock('../../stores/themeStore', () => ({
  default: (selector: (s: { mode: string }) => string) => selector({ mode: mockThemeMode }),
}));

/* ---------- mock @monaco-editor/react ---------- */
let capturedProps: Record<string, unknown> = {};
vi.mock('@monaco-editor/react', () => ({
  default: (props: Record<string, unknown>) => {
    capturedProps = props;
    return <div data-testid="monaco-editor" data-theme={props.theme as string} />;
  },
}));

import JsonEditor from '../../components/JsonEditor';

describe('JsonEditor', () => {
  beforeEach(() => {
    mockThemeMode = 'light';
    capturedProps = {};
  });

  it('渲染 Monaco Editor', () => {
    render(<JsonEditor />);
    expect(screen.getByTestId('monaco-editor')).toBeTruthy();
  });

  it('亮色主题传递 vs', () => {
    mockThemeMode = 'light';
    render(<JsonEditor />);
    expect(capturedProps.theme).toBe('vs');
  });

  it('暗色主题传递 vs-dark', () => {
    mockThemeMode = 'dark';
    render(<JsonEditor />);
    expect(capturedProps.theme).toBe('vs-dark');
  });

  it('传递 value 和 height', () => {
    render(<JsonEditor value='{"a":1}' height={300} />);
    expect(capturedProps.value).toBe('{"a":1}');
    expect(capturedProps.height).toBe(300);
  });

  it('默认 height 为 200', () => {
    render(<JsonEditor />);
    expect(capturedProps.height).toBe(200);
  });

  it('readOnly 传递到 options', () => {
    render(<JsonEditor readOnly />);
    const opts = capturedProps.options as Record<string, unknown>;
    expect(opts.readOnly).toBe(true);
  });

  it('非 readOnly 默认为 false', () => {
    render(<JsonEditor />);
    const opts = capturedProps.options as Record<string, unknown>;
    expect(opts.readOnly).toBe(false);
  });

  it('language 始终为 json', () => {
    render(<JsonEditor />);
    expect(capturedProps.language).toBe('json');
  });

  it('onChange 回调转发', () => {
    const onChange = vi.fn();
    render(<JsonEditor onChange={onChange} />);
    const onChangeProp = capturedProps.onChange as (val?: string) => void;
    onChangeProp('{"b":2}');
    expect(onChange).toHaveBeenCalledWith('{"b":2}');
  });

  it('onChange 空值转为空字符串', () => {
    const onChange = vi.fn();
    render(<JsonEditor onChange={onChange} />);
    const onChangeProp = capturedProps.onChange as (val?: string) => void;
    onChangeProp(undefined);
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('minimap 默认关闭', () => {
    render(<JsonEditor />);
    const opts = capturedProps.options as Record<string, Record<string, unknown>>;
    expect(opts.minimap?.enabled).toBe(false);
  });

  it('placeholder 传递到 options', () => {
    render(<JsonEditor placeholder="{}" />);
    const opts = capturedProps.options as Record<string, unknown>;
    expect(opts.placeholder).toBe('{}');
  });
});
