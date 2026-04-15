/**
 * JsonEditor — 基于 Monaco Editor 的 JSON 编辑器组件。
 *
 * 功能：
 * - JSON 语法高亮 + 自动格式化
 * - 红色波浪线标注语法错误
 * - 自动跟随暗色/亮色主题
 * - 支持只读模式
 * - 通过 Form.Item 受控：value / onChange
 * - 可选 JSON Schema 验证（注入 schema 后提供属性提示 + 类型检查 + 错误诊断）
 */
import { useCallback, useRef } from 'react';
import Editor, { type OnMount, type OnChange } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';
import type { Rule } from 'antd/es/form';
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
  /**
   * JSON Schema 对象，用于对编辑器内容进行 schema 验证。
   * 注入后 Monaco 会提供：属性自动补全、类型检查、必填字段诊断。
   */
  schema?: Record<string, unknown>;
  /**
   * Schema 绑定的唯一 URI。同一页面多个 JsonEditor 时需唯一，避免冲突。
   * 默认 'http://ckyclaw/schema.json'。
   */
  schemaUri?: string;
}

/** JSON 格式化快捷操作 */
function formatJson(val: string): string {
  try {
    return JSON.stringify(JSON.parse(val), null, 2);
  } catch {
    return val;
  }
}

export function createJsonValidatorRule(message = 'JSON 格式无效', required = false): Rule {
  return {
    validator: async (_, value: unknown) => {
      const text = typeof value === 'string' ? value.trim() : '';
      if (!text) {
        if (required) {
          throw new Error(message);
        }
        return;
      }
      try {
        JSON.parse(text);
      } catch {
        throw new Error(message);
      }
    },
  };
}

/**
 * 工具参数 JSON Schema 的元 schema。
 * 传入 JsonEditor 的 schema prop，可为工具 parameters_schema 编辑提供：
 * - 属性名自动补全（type/properties/required/description/enum/default/items）
 * - 类型值约束提示
 * - 必填字段缺失诊断
 */
export const TOOL_PARAMETERS_META_SCHEMA: Record<string, unknown> = {
  type: 'object',
  properties: {
    type: { type: 'string', enum: ['object'] },
    properties: {
      type: 'object',
      additionalProperties: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['string', 'integer', 'number', 'boolean', 'array', 'object'] },
          description: { type: 'string' },
          default: {},
          enum: { type: 'array' },
          items: { type: 'object' },
          properties: { type: 'object' },
          required: { type: 'array', items: { type: 'string' } },
        },
        required: ['type'],
      },
    },
    required: { type: 'array', items: { type: 'string' } },
  },
  required: ['type', 'properties'],
};

/**
 * Agent output_type 的元 schema（与工具参数相同的 JSON Schema Draft 7 子集）。
 */
export const OUTPUT_TYPE_META_SCHEMA: Record<string, unknown> = TOOL_PARAMETERS_META_SCHEMA;

export default function JsonEditor({
  value = '',
  onChange,
  height = 200,
  readOnly = false,
  placeholder,
  onMount: onMountProp,
  schema,
  schemaUri = 'http://ckyclaw/schema.json',
}: JsonEditorProps) {
  const mode = useThemeStore((s) => s.mode);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleMount: OnMount = useCallback(
    (ed, monaco) => {
      editorRef.current = ed;

      /* JSON 诊断选项 + 可选 schema 验证 */
      const diagOptions: Record<string, unknown> = {
        validate: true,
        allowComments: false,
        trailingCommas: 'error',
      };
      if (schema) {
        const modelUri = monaco.Uri.parse(schemaUri);
        diagOptions.schemas = [
          {
            uri: schemaUri,
            fileMatch: [modelUri.toString()],
            schema,
          },
        ];
        /* 确保编辑器模型使用匹配的 URI */
        const model = ed.getModel();
        if (model && model.uri.toString() !== modelUri.toString()) {
          const newModel = monaco.editor.createModel(value, 'json', modelUri);
          ed.setModel(newModel);
          model.dispose();
        }
      }
      monaco.languages.json.jsonDefaults.setDiagnosticsOptions(
        diagOptions as Parameters<typeof monaco.languages.json.jsonDefaults.setDiagnosticsOptions>[0],
      );

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
    [onChange, onMountProp, schema, schemaUri, value],
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
