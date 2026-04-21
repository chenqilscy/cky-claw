/**
 * ToolEditor — 结构化工具定义编辑器。
 *
 * 功能：
 * - 可视化工具列表（名称、描述、参数一览）
 * - 工具添加/编辑/删除
 * - 参数表格化编辑
 * - JSON 模式切换（保留高级用户手写 JSON 能力）
 * - 工具组模板一键填充
 */
import { useState, useCallback } from 'react';
import {
  Button, Card, Space, Typography, Tag, Modal, Form, Input, Select,
  Switch, Table, Popconfirm, Empty, Tooltip, Segmented, App,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  CodeOutlined, FormOutlined, CopyOutlined,
} from '@ant-design/icons';
import type { ToolDefinition } from '../services/toolGroupService';
import { JsonEditor, TOOL_PARAMETERS_META_SCHEMA } from './index';

const { Text } = Typography;

/* ---- 参数类型选项 ---- */
const PARAM_TYPES = [
  { label: 'string', value: 'string' },
  { label: 'integer', value: 'integer' },
  { label: 'number', value: 'number' },
  { label: 'boolean', value: 'boolean' },
  { label: 'array', value: 'array' },
  { label: 'object', value: 'object' },
];

/* ---- 工具组模板 ---- */
const TOOL_TEMPLATES: Record<string, ToolDefinition[]> = {
  '网络搜索': [
    {
      name: 'web_search',
      description: '搜索互联网并返回相关结果摘要',
      parameters_schema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '搜索关键词' },
          max_results: { type: 'integer', description: '最大返回结果数', default: 5 },
        },
        required: ['query'],
      },
    },
    {
      name: 'fetch_webpage',
      description: '获取指定 URL 的网页内容',
      parameters_schema: {
        type: 'object',
        properties: {
          url: { type: 'string', description: '目标网页 URL' },
          format: { type: 'string', description: '返回格式', enum: ['text', 'html', 'markdown'] },
        },
        required: ['url'],
      },
    },
  ],
  '代码执行': [
    {
      name: 'execute_python',
      description: '在沙箱中执行 Python 代码并返回结果',
      parameters_schema: {
        type: 'object',
        properties: {
          code: { type: 'string', description: 'Python 代码' },
          timeout: { type: 'integer', description: '超时时间（秒）', default: 30 },
        },
        required: ['code'],
      },
    },
    {
      name: 'execute_shell',
      description: '在沙箱中执行 Shell 命令',
      parameters_schema: {
        type: 'object',
        properties: {
          command: { type: 'string', description: 'Shell 命令' },
        },
        required: ['command'],
      },
    },
  ],
  '文件操作': [
    {
      name: 'file_read',
      description: '读取指定路径的文件内容',
      parameters_schema: {
        type: 'object',
        properties: {
          path: { type: 'string', description: '文件路径' },
        },
        required: ['path'],
      },
    },
    {
      name: 'file_write',
      description: '将内容写入指定路径的文件',
      parameters_schema: {
        type: 'object',
        properties: {
          path: { type: 'string', description: '文件路径' },
          content: { type: 'string', description: '文件内容' },
        },
        required: ['path', 'content'],
      },
    },
    {
      name: 'file_list',
      description: '列出目录下的文件',
      parameters_schema: {
        type: 'object',
        properties: {
          directory: { type: 'string', description: '目录路径' },
        },
        required: ['directory'],
      },
    },
  ],
  'HTTP 客户端': [
    {
      name: 'http_request',
      description: '发送 HTTP 请求并返回响应',
      parameters_schema: {
        type: 'object',
        properties: {
          url: { type: 'string', description: '请求 URL' },
          method: { type: 'string', description: 'HTTP 方法', enum: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] },
          headers: { type: 'object', description: '请求头' },
          body: { type: 'string', description: '请求体' },
        },
        required: ['url'],
      },
    },
  ],
  '邮件通知': [
    {
      name: 'send_email',
      description: '发送电子邮件',
      parameters_schema: {
        type: 'object',
        properties: {
          to: { type: 'array', items: { type: 'string' }, description: '收件人邮箱列表' },
          subject: { type: 'string', description: '邮件主题' },
          body: { type: 'string', description: '邮件正文' },
          priority: { type: 'string', enum: ['low', 'normal', 'high'], default: 'normal', description: '优先级' },
        },
        required: ['to', 'subject', 'body'],
      },
    },
  ],
};

/* ---- 参数行类型 ---- */
interface ParamRow {
  key: string;
  name: string;
  type: string;
  required: boolean;
  description: string;
  defaultValue?: string;
  enumValues?: string;
}

/* ---- 从 schema 提取参数行 ---- */
function schemaToParamRows(schema: Record<string, unknown>): ParamRow[] {
  const props = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = (schema.required ?? []) as string[];
  return Object.entries(props).map(([name, def]) => ({
    key: name,
    name,
    type: (def.type as string) ?? 'string',
    required: required.includes(name),
    description: (def.description as string) ?? '',
    defaultValue: def.default !== undefined ? String(def.default) : undefined,
    enumValues: Array.isArray(def.enum) ? (def.enum as string[]).join(', ') : undefined,
  }));
}

/* ---- 从参数行构建 schema ---- */
function paramRowsToSchema(rows: ParamRow[]): Record<string, unknown> {
  const properties: Record<string, Record<string, unknown>> = {};
  const required: string[] = [];
  for (const row of rows) {
    const propDef: Record<string, unknown> = { type: row.type };
    if (row.description) propDef.description = row.description;
    if (row.defaultValue !== undefined && row.defaultValue !== '') {
      if (row.type === 'integer' || row.type === 'number') {
        propDef.default = Number(row.defaultValue);
      } else if (row.type === 'boolean') {
        propDef.default = row.defaultValue === 'true';
      } else {
        propDef.default = row.defaultValue;
      }
    }
    if (row.enumValues) {
      propDef.enum = row.enumValues.split(',').map((s) => s.trim()).filter(Boolean);
    }
    properties[row.name] = propDef;
    if (row.required) required.push(row.name);
  }
  return { type: 'object', properties, required };
}

/* ---- 参数摘要文本 ---- */
function paramSummary(schema: Record<string, unknown> | undefined): string {
  if (!schema) return '无参数';
  const props = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = new Set((schema.required ?? []) as string[]);
  const parts = Object.entries(props).map(([name, def]) => {
    const type = (def.type as string) ?? '?';
    const req = required.has(name) ? ', 必填' : '';
    return `${name} (${type}${req})`;
  });
  return parts.length > 0 ? parts.join(' · ') : '无参数';
}

/* ========================== ToolEditModal ========================== */

interface ToolEditModalProps {
  open: boolean;
  tool: ToolDefinition | null;
  existingNames: string[];
  onOk: (tool: ToolDefinition) => void;
  onCancel: () => void;
}

/** 单个工具的编辑弹窗：名称+描述+参数表格 */
const ToolEditModal: React.FC<ToolEditModalProps> = ({ open, tool, existingNames, onOk, onCancel }) => {
  const [form] = Form.useForm();
  const [params, setParams] = useState<ParamRow[]>([]);

  const handleOpen = useCallback(() => {
    if (tool) {
      form.setFieldsValue({ name: tool.name, description: tool.description });
      setParams(schemaToParamRows(tool.parameters_schema));
    } else {
      form.resetFields();
      setParams([]);
    }
  }, [tool, form]);

  const handleAddParam = () => {
    const key = `param_${Date.now()}`;
    setParams((prev) => [...prev, { key, name: '', type: 'string', required: false, description: '' }]);
  };

  const handleRemoveParam = (key: string) => {
    setParams((prev) => prev.filter((p) => p.key !== key));
  };

  const handleParamChange = (key: string, field: keyof ParamRow, value: string | boolean) => {
    setParams((prev) => prev.map((p) => (p.key === key ? { ...p, [field]: value } : p)));
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const schema = paramRowsToSchema(params);
    onOk({
      name: values.name as string,
      description: (values.description as string) ?? '',
      parameters_schema: schema,
    });
  };

  const paramColumns = [
    {
      title: '参数名',
      dataIndex: 'name',
      width: 120,
      render: (_: unknown, record: ParamRow) => (
        <Input
          size="small"
          value={record.name}
          placeholder="param_name"
          onChange={(e) => handleParamChange(record.key, 'name', e.target.value)}
        />
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      width: 100,
      render: (_: unknown, record: ParamRow) => (
        <Select
          size="small"
          value={record.type}
          options={PARAM_TYPES}
          style={{ width: '100%' }}
          onChange={(v) => handleParamChange(record.key, 'type', v)}
        />
      ),
    },
    {
      title: '必填',
      dataIndex: 'required',
      width: 60,
      render: (_: unknown, record: ParamRow) => (
        <Switch
          size="small"
          checked={record.required}
          onChange={(v) => handleParamChange(record.key, 'required', v)}
        />
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      render: (_: unknown, record: ParamRow) => (
        <Input
          size="small"
          value={record.description}
          placeholder="参数说明"
          onChange={(e) => handleParamChange(record.key, 'description', e.target.value)}
        />
      ),
    },
    {
      title: '',
      width: 40,
      render: (_: unknown, record: ParamRow) => (
        <Button
          type="text"
          danger
          size="small"
          icon={<DeleteOutlined />}
          onClick={() => handleRemoveParam(record.key)}
        />
      ),
    },
  ];

  return (
    <Modal
      title={tool ? '编辑工具' : '添加工具'}
      open={open}
      width={680}
      onOk={handleSubmit}
      onCancel={onCancel}
      afterOpenChange={(visible) => { if (visible) handleOpen(); }}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" size="middle">
        <Form.Item
          name="name"
          label="工具名称"
          rules={[
            { required: true, message: '请输入工具名称' },
            { pattern: /^[a-z][a-z0-9_]{0,127}$/, message: '小写字母开头，仅含小写字母/数字/下划线' },
            {
              validator: (_, value: string) => {
                if (value && !tool && existingNames.includes(value)) {
                  return Promise.reject('工具名称已存在');
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input placeholder="如: web_search" disabled={!!tool} />
        </Form.Item>
        <Form.Item
          name="description"
          label="工具描述"
          tooltip="LLM 据此决定是否调用该工具，建议详细描述功能"
          rules={[{ required: true, message: '请输入工具描述' }]}
        >
          <Input.TextArea rows={2} placeholder="搜索互联网并返回相关结果摘要" />
        </Form.Item>
      </Form>

      <div style={{ marginTop: 16 }}>
        <Space style={{ marginBottom: 8 }} align="center">
          <Text strong>参数定义</Text>
          <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={handleAddParam}>
            添加参数
          </Button>
        </Space>
        <Table
          dataSource={params}
          columns={paramColumns}
          rowKey="key"
          pagination={false}
          size="small"
            locale={{ emptyText: <Empty description={'无参数（点击"添加参数"）'} image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        />
      </div>
    </Modal>
  );
};

/* ========================== ToolEditor 主组件 ========================== */

export interface ToolEditorProps {
  /** 受控值：工具定义数组 */
  value?: ToolDefinition[];
  /** 值变化回调 */
  onChange?: (tools: ToolDefinition[]) => void;
  /** 是否只读 */
  readOnly?: boolean;
}

/** 工具定义数组的元 schema — 用于 JSON 模式下 Monaco 验证 */
const TOOL_ARRAY_META_SCHEMA: Record<string, unknown> = {
  type: 'array',
  items: {
    type: 'object',
    properties: {
      name: { type: 'string', description: '工具名称（小写字母/数字/下划线）' },
      description: { type: 'string', description: '工具功能描述' },
      parameters_schema: TOOL_PARAMETERS_META_SCHEMA,
    },
    required: ['name', 'description', 'parameters_schema'],
  },
};

/** 结构化工具定义编辑器——可视化列表 + JSON 模式切换 */
export default function ToolEditor({ value = [], onChange, readOnly }: ToolEditorProps) {
  const { message } = App.useApp();
  const [mode, setMode] = useState<'visual' | 'json'>('visual');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<ToolDefinition | null>(null);
  /* JSON 模式下的文本值 */
  const [jsonText, setJsonText] = useState('');

  const tools = value;

  const handleModeChange = (newMode: string | number) => {
    if (newMode === 'json') {
      setJsonText(JSON.stringify(tools, null, 2));
    } else if (newMode === 'visual') {
      /* 切回可视化时尝试解析 JSON */
      try {
        const parsed = JSON.parse(jsonText || '[]') as ToolDefinition[];
        if (!Array.isArray(parsed)) throw new Error('not array');
        onChange?.(parsed);
      } catch {
        message.warning('JSON 格式无效，已恢复上次有效数据');
      }
    }
    setMode(newMode as 'visual' | 'json');
  };

  /* ---- 工具 CRUD ---- */
  const handleAddTool = () => {
    setEditingTool(null);
    setModalOpen(true);
  };

  const handleEditTool = (tool: ToolDefinition) => {
    setEditingTool(tool);
    setModalOpen(true);
  };

  const handleDeleteTool = (name: string) => {
    onChange?.(tools.filter((t) => t.name !== name));
  };

  const handleToolOk = (tool: ToolDefinition) => {
    if (editingTool) {
      /* 编辑模式：替换同名工具 */
      onChange?.(tools.map((t) => (t.name === editingTool.name ? tool : t)));
    } else {
      /* 新增模式 */
      onChange?.([...tools, tool]);
    }
    setModalOpen(false);
    setEditingTool(null);
  };

  const handleApplyTemplate = (templateName: string) => {
    const templateTools = TOOL_TEMPLATES[templateName];
    if (templateTools) {
      onChange?.(templateTools);
      message.success(`已应用"${templateName}"模板`);
    }
  };

  /* JSON 模式失焦时同步 */
  const handleJsonBlur = () => {
    try {
      const parsed = JSON.parse(jsonText || '[]') as ToolDefinition[];
      if (Array.isArray(parsed)) onChange?.(parsed);
    } catch {
      /* 用户还在编辑，暂不报错 */
    }
  };

  const existingNames = tools.map((t) => t.name);

  return (
    <div>
      {/* ---- 工具栏 ---- */}
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }} align="center">
        <Space>
          {!readOnly && mode === 'visual' && (
            <>
              <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleAddTool}>
                添加工具
              </Button>
              <Select
                size="small"
                placeholder="从模板创建"
                style={{ width: 140 }}
                options={Object.keys(TOOL_TEMPLATES).map((k) => ({ label: k, value: k }))}
                onChange={handleApplyTemplate}
                value={undefined}
                allowClear
              />
            </>
          )}
        </Space>
        <Segmented
          size="small"
          options={[
            { label: <><FormOutlined /> 可视化</>, value: 'visual' },
            { label: <><CodeOutlined /> JSON</>, value: 'json' },
          ]}
          value={mode}
          onChange={handleModeChange}
        />
      </Space>

      {/* ---- JSON 模式 ---- */}
      {mode === 'json' && (
        <div onBlur={handleJsonBlur}>
          <JsonEditor
            height={240}
            value={jsonText}
            onChange={setJsonText}
            readOnly={readOnly}
            schema={TOOL_ARRAY_META_SCHEMA}
            schemaUri="http://kasaya/tool-definitions-schema.json"
            placeholder='[\n  {\n    "name": "tool_name",\n    "description": "工具描述",\n    "parameters_schema": { "type": "object", "properties": {} }\n  }\n]'
          />
        </div>
      )}

      {/* ---- 可视化模式 ---- */}
      {mode === 'visual' && (
        <div>
          {tools.length === 0 ? (
            <Empty
              description="暂无工具定义"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ padding: '24px 0' }}
            >
              {!readOnly && (
                <Button type="dashed" icon={<PlusOutlined />} onClick={handleAddTool}>
                  添加工具
                </Button>
              )}
            </Empty>
          ) : (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {tools.map((tool) => (
                <Card
                  key={tool.name}
                  size="small"
                  style={{ borderLeft: '3px solid var(--ant-color-primary)' }}
                  styles={{ body: { padding: '8px 12px' } }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Space size={8} align="center">
                        <Text strong style={{ fontSize: 13 }}>🔧 {tool.name}</Text>
                        <Tag color="processing" style={{ fontSize: 11 }}>
                          {Object.keys((tool.parameters_schema?.properties ?? {}) as object).length} 参数
                        </Tag>
                      </Space>
                      <div style={{ color: 'var(--ant-color-text-secondary)', fontSize: 12, margin: '4px 0' }}>
                        {tool.description || '无描述'}
                      </div>
                      <div style={{ color: 'var(--ant-color-text-tertiary)', fontSize: 11 }}>
                        {paramSummary(tool.parameters_schema)}
                      </div>
                    </div>
                    {!readOnly && (
                      <Space size={4}>
                        <Tooltip title="编辑">
                          <Button
                            type="text"
                            size="small"
                            icon={<EditOutlined />}
                            onClick={() => handleEditTool(tool)}
                          />
                        </Tooltip>
                        <Tooltip title="复制">
                          <Button
                            type="text"
                            size="small"
                            icon={<CopyOutlined />}
                            onClick={() => {
                              const copy = { ...tool, name: `${tool.name}_copy` };
                              onChange?.([...tools, copy]);
                            }}
                          />
                        </Tooltip>
                        <Popconfirm
                          title="确认删除该工具？"
                          onConfirm={() => handleDeleteTool(tool.name)}
                        >
                          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </Space>
                    )}
                  </div>
                </Card>
              ))}
            </Space>
          )}
        </div>
      )}

      {/* ---- 工具编辑弹窗 ---- */}
      <ToolEditModal
        open={modalOpen}
        tool={editingTool}
        existingNames={existingNames}
        onOk={handleToolOk}
        onCancel={() => { setModalOpen(false); setEditingTool(null); }}
      />
    </div>
  );
}
