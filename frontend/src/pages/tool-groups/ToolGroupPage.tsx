import { Form, Input, Switch, Tag, App, Space, Typography } from 'antd';
import { ToolOutlined } from '@ant-design/icons';
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
import { CrudTable, PageContainer, buildActionColumn, ToolEditor, ConditionRuleEditor } from '../../components';
import type { CrudTableActions } from '../../components';

const { Text } = Typography;

const SOURCE_COLORS: Record<string, string> = {
  builtin: 'blue',
  custom: 'green',
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
    width: 100,
    render: (_, record) => (
      <Tag color={SOURCE_COLORS[record.source] || 'default'}>
        {record.source === 'builtin' ? '🏠 内置' : '✏️ 自定义'}
      </Tag>
    ),
  },
  {
    title: '工具',
    width: 200,
    render: (_, record) => {
      const tools = record.tools || [];
      if (tools.length === 0) return <Text type="secondary">无工具</Text>;
      return (
        <Space size={4} wrap>
          <Tag>{tools.length} 个</Tag>
          {tools.slice(0, 3).map((t) => (
            <Tag key={t.name} color="cyan">{t.name}</Tag>
          ))}
          {tools.length > 3 && <Text type="secondary">+{tools.length - 3}</Text>}
        </Space>
      );
    },
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
  buildActionColumn<ToolGroupResponse>(actions, {
    deleteConfirmTitle: '确认删除工具组',
    getRecordId: (r) => r.name,
  }),
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
        { pattern: /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/, message: '仅允许小写字母、数字和连字符，以字母或数字开头结尾' },
      ]}
    >
      <Input placeholder="如: web-search" disabled={!!editing} />
    </Form.Item>

    <Form.Item name="description" label="描述">
      <Input placeholder="工具组用途描述" />
    </Form.Item>

    <Form.Item
      name="tools"
      label="工具定义"
      tooltip="定义工具组包含的工具，每个工具需要名称、描述和参数定义"
    >
      <ToolEditor />
    </Form.Item>

    {editing && (
      <Form.Item name="is_enabled" label="启用" valuePropName="checked">
        <Switch />
      </Form.Item>
    )}

    <Form.Item
      name="conditions"
      label="条件启用"
      tooltip="配置工具组的条件启用规则，留空表示始终启用"
    >
      <ConditionRuleEditor />
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
    <PageContainer
      title="工具组管理"
      icon={<ToolOutlined />}
      description="管理工具组定义与条件配置"
    >
    <CrudTable<
      ToolGroupResponse,
      ToolGroupCreateRequest,
      { name: string; data: ToolGroupUpdateRequest }
    >
      hideTitle
      mobileHiddenColumns={['description', 'created_at']}
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
        tools: (record.tools || []) as ToolDefinition[],
        conditions: record.conditions || {},
        is_enabled: record.is_enabled,
      })}
      toCreatePayload={(values) => {
        const tools = (values.tools as ToolDefinition[]) || [];
        const conditions = (values.conditions as Record<string, unknown>) || {};
        const payload: ToolGroupCreateRequest = {
          name: values.name as string,
          description: values.description as string,
          tools,
        };
        if (Object.keys(conditions).length > 0) payload.conditions = conditions;
        return payload;
      }}
      toUpdatePayload={(values, record) => {
        const tools = (values.tools as ToolDefinition[]) || [];
        const conditions = (values.conditions as Record<string, unknown>) || {};
        const data: ToolGroupUpdateRequest = {
          description: values.description as string,
          tools,
          is_enabled: values.is_enabled as boolean,
        };
        data.conditions = Object.keys(conditions).length > 0 ? conditions : {};
        return { name: record.name, data };
      }}
    />
    </PageContainer>
  );
};

export default ToolGroupPage;
