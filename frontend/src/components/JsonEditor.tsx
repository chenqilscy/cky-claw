/**
 * JsonEditor — 基于 Monaco Editor 的 JSON 编辑器组件。
 *
 * 功能：
 * - JSON 语法高亮 + 自动格式化
 * - 红色波浪线标注语法错误
 * - 自动跟随暗色/亮色主题
 * - 支持只读模式
 * - 通过 Form.Item 受控：value / onChange
 */
import { useCallback, useRef } from 'react';
import Editor, { type OnMount, type OnChange } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';
import { Spin } from 'antd';
import useThemeStore from '../stores/themeStore';

export interface JsonEditorProps {
  /** 受控值（JSON 字符串） */
  value?: string;
  /** 值变化回调 */
  onChange?: (value: string) => void;
  /** 编辑器高度，默认 200 */
  height?: number | string;
  /** 只读模式 */
  readOnly?: boolean;
  /** 占位提示（通过覆盖层显示） */
  placeholder?: string;
  /** 编辑器挂载完成回调 */
  onMount?: OnMount;
}

/** JSON 格式化快捷操作 */
function formatJson(val: string): string {
  try {
    return JSON.stringify(JSON.parse(val), null, 2);
  } catch {
    return val;
  }
}

export default function JsonEditor({
  value = '',
  onChange,
  height = 200,
  readOnly = false,
  placeholder,
  onMount: onMountProp,
}: JsonEditorProps) {
  const mode = useThemeStore((s) => s.mode);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleMount: OnMount = useCallback(
    (ed, monaco) => {
      editorRef.current = ed;

      /* JSON 诊断选项 */
      monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
        validate: true,
        allowComments: false,
        trailingCommas: 'error',
      });

      /* Shift+Alt+F 格式化 */
      ed.addAction({
        id: 'json-format',
        label: '格式化 JSON',
        keybindings: [monaco.KeyMod.Shift | monaco.KeyMod.Alt | monaco.KeyCode.KeyF],
        run: (editor) => {
          const val = editor.getValue();
          const formatted = formatJson(val);
          if (formatted !== val) {
            editor.setValue(formatted);
            onChange?.(formatted);
          }
        },
      });

      onMountProp?.(ed, monaco);
    },
    [onChange, onMountProp],
  );

  const handleChange: OnChange = useCallback(
    (val) => {
      onChange?.(val ?? '');
    },
    [onChange],
  );

  return (
    <Editor
      height={height}
      language="json"
      theme={mode === 'dark' ? 'vs-dark' : 'vs'}
      value={value}
      onChange={handleChange}
      onMount={handleMount}
      loading={<Spin size="small" />}
      options={{
        readOnly,
        minimap: { enabled: false },
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
        tabSize: 2,
        fontSize: 13,
        wordWrap: 'on',
        automaticLayout: true,
        scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
        padding: { top: 8, bottom: 8 },
        placeholder,
      }}
    />
  );
}
