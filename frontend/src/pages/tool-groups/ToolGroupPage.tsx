import { Form, Input, Switch, Tag, Button, Space, Popconfirm, App } from 'antd';
import { ToolOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import {
  useToolGroupList,
  useCreateToolGroup,
  useUpdateToolGroup,
  useDeleteToolGroup,
} from '../../hooks/useToolGroupQueries';
import type {
  ToolGroupResponse,
  ToolGroupCreateRequest,
  ToolGroupUpdateRequest,
  ToolDefinition,
} from '../../services/toolGroupService';
import { CrudTable } from '../../components';
import type { CrudTableActions } from '../../components';

const { TextArea } = Input;

const SOURCE_COLORS: Record<string, string> = {
  builtin: 'blue',
  custom: 'green',
};

/* ---- JSON 解析工具 ---- */

const parseToolsJson = (raw: string): ToolDefinition[] => {
  if (!raw.trim()) return [];
  const parsed = JSON.parse(raw) as ToolDefinition[];
  if (!Array.isArray(parsed)) throw new Error('tools must be an array');
  return parsed;
};

const parseConditionsJson = (raw: string): Record<string, unknown> | undefined => {
  if (!raw || !raw.trim()) return undefined;
  return JSON.parse(raw) as Record<string, unknown>;
};

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<ToolGroupResponse>,
  handleToggleEnabled: (record: ToolGroupResponse, enabled: boolean) => void,
): ProColumns<ToolGroupResponse>[] => [
  {
    title: '名称',
    dataIndex: 'name',
    width: 160,
    render: (_, record) => <strong>{record.name}</strong>,
  },
  {
    title: '描述',
    dataIndex: 'description',
    width: 200,
    ellipsis: true,
  },
  {
    title: '来源',
    dataIndex: 'source',
    width: 80,
    render: (_, record) => (
      <Tag color={SOURCE_COLORS[record.source] || 'default'}>
        {record.source === 'builtin' ? '内置' : '自定义'}
      </Tag>
    ),
  },
  {
    title: '工具数量',
    width: 100,
    render: (_, record) => (record.tools || []).length,
  },
  {
    title: '启用',
    dataIndex: 'is_enabled',
    width: 80,
    render: (_, record) => (
      <Switch
        checked={record.is_enabled}
        onChange={(checked) => handleToggleEnabled(record, checked)}
        size="small"
      />
    ),
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 170,
    render: (_, record) => new Date(record.created_at).toLocaleString('zh-CN'),
  },
  {
    title: '操作',
    width: 140,
    render: (_, record) => (
      <Space>
        <Button
          type="link"
          size="small"
          icon={<EditOutlined />}
          onClick={() => actions.openEdit(record)}
        >
          编辑
        </Button>
        <Popconfirm
          title="确认删除此工具组？"
          onConfirm={() => actions.handleDelete(record.name)}
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      </Space>
    ),
  },
];

/* ---- 表单渲染 ---- */

const renderForm = (_form: FormInstance, editing: ToolGroupResponse | null) => (
  <>
    <Form.Item
      name="name"
      label="名称"
      rules={[
        { required: true, message: '请输入工具组名称' },
        { min: 3, max: 64, message: '长度须在 3-64 字符之间' },
      ]}
    >
      <Input placeholder="如: web-search" disabled={!!editing} />
    </Form.Item>

    <Form.Item name="description" label="描述">
      <Input placeholder="工具组用途描述" />
    </Form.Item>

    <Form.Item
      name="tools_json"
      label="工具定义（JSON 数组）"
      tooltip="每个工具需 name、description 和 parameters_schema 字段"
    >
      <TextArea
        rows={8}
        placeholder={`[\n  {\n    "name": "web_search",\n    "description": "搜索网页内容",\n    "parameters_schema": {\n      "type": "object",\n      "properties": {\n        "query": { "type": "string" }\n      },\n      "required": ["query"]\n    }\n  }\n]`}
      />
    </Form.Item>

    {editing && (
      <Form.Item name="is_enabled" label="启用" valuePropName="checked">
        <Switch />
      </Form.Item>
    )}

    <Form.Item
      name="conditions_json"
      label="条件启用配置（JSON）"
      extra='留空表示始终启用。示例：{"env": "production"}'
      rules={[
        {
          validator: (_, value) => {
            if (!value || !value.trim()) return Promise.resolve();
            try {
              JSON.parse(value);
              return Promise.resolve();
            } catch {
              return Promise.reject(new Error('JSON 格式无效'));
            }
          },
        },
      ]}
    >
      <TextArea rows={3} placeholder='{"env": "production"}' />
    </Form.Item>
  </>
);

/* ---- 页面组件 ---- */

const ToolGroupPage: React.FC = () => {
  const { message } = App.useApp();

  const queryResult = useToolGroupList();
  const createMutation = useCreateToolGroup();
  const updateMutation = useUpdateToolGroup();
  const deleteMutation = useDeleteToolGroup();

  /** 启用/禁用开关（不走 CrudTable 的 Modal，直接 mutate） */
  const handleToggleEnabled = async (record: ToolGroupResponse, enabled: boolean) => {
    try {
      await updateMutation.mutateAsync({ name: record.name, data: { is_enabled: enabled } });
      message.success(enabled ? '已启用' : '已禁用');
    } catch {
      message.error('操作失败');
    }
  };

  return (
    <CrudTable<
      ToolGroupResponse,
      ToolGroupCreateRequest,
      { name: string; data: ToolGroupUpdateRequest }
    >
      title="工具组管理"
      icon={<ToolOutlined />}
      queryResult={queryResult}
      createMutation={createMutation}
      updateMutation={updateMutation}
      deleteMutation={deleteMutation}
      createButtonText="新建工具组"
      modalTitle={(editing) => (editing ? '编辑工具组' : '新建工具组')}
      columns={(actions) => buildColumns(actions, handleToggleEnabled)}
      renderForm={renderForm}
      toFormValues={(record) => ({
        name: record.name,
        description: record.description,
        tools_json: JSON.stringify(record.tools, null, 2),
        conditions_json: Object.keys(record.conditions || {}).length > 0
          ? JSON.stringify(record.conditions, null, 2)
          : '',
        is_enabled: record.is_enabled,
      })}
      toCreatePayload={(values) => {
        const tools = parseToolsJson((values.tools_json as string) || '[]');
        const conditions = parseConditionsJson((values.conditions_json as string) || '');
        const payload: ToolGroupCreateRequest = {
          name: values.name as string,
          description: values.description as string,
          tools,
        };
        if (conditions) payload.conditions = conditions;
        return payload;
      }}
      toUpdatePayload={(values, record) => {
        const tools = parseToolsJson((values.tools_json as string) || '[]');
        const conditions = parseConditionsJson((values.conditions_json as string) || '');
        const data: ToolGroupUpdateRequest = {
          description: values.description as string,
          tools,
          is_enabled: values.is_enabled as boolean,
        };
        data.conditions = conditions ?? {};
        return { name: record.name, data };
      }}
    />
  );
};

export default ToolGroupPage;
