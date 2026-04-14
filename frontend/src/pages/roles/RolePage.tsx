import { useState, useCallback } from 'react';
import {
  Form, Input, Tag, Checkbox, Table,
  Typography,
} from 'antd';
import {
  SafetyCertificateOutlined, LockOutlined,
} from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { RoleItem, RoleCreateParams, RoleUpdateParams } from '../../services/roleService';
import {
  useRoleList,
  useCreateRole,
  useUpdateRole,
  useDeleteRole,
} from '../../hooks/useRoleQueries';
import { CrudTable, PageContainer, buildActionColumn } from '../../components';
import type { CrudTableActions } from '../../components';

const { Text } = Typography;

const RESOURCES = [
  'agents', 'providers', 'workflows', 'teams', 'guardrails',
  'mcp_servers', 'tool_groups', 'skills', 'templates', 'memories',
  'runs', 'traces', 'approvals', 'sessions', 'token_usage',
  'audit_logs', 'roles', 'users',
];

const ACTIONS = ['read', 'write', 'delete', 'execute'];

const RESOURCE_LABELS: Record<string, string> = {
  agents: 'Agent',
  providers: '模型厂商',
  workflows: '工作流',
  teams: '团队',
  guardrails: '护栏',
  mcp_servers: 'MCP Server',
  tool_groups: '工具组',
  skills: '技能',
  templates: '模板',
  memories: '记忆',
  runs: '执行记录',
  traces: 'Trace',
  approvals: '审批',
  sessions: '会话',
  token_usage: 'Token 用量',
  audit_logs: '审计日志',
  roles: '角色',
  users: '用户',
};

const permissionCount = (perms: Record<string, string[]>) =>
  Object.values(perms).reduce((sum, actions) => sum + actions.length, 0);

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<RoleItem>,
): ProColumns<RoleItem>[] => [
  {
    title: '角色名',
    dataIndex: 'name',
    render: (_, record) => (
      <Space>
        <Text strong>{record.name}</Text>
        {record.is_system && <Tag color="gold"><LockOutlined /> 系统</Tag>}
      </Space>
    ),
  },
  { title: '描述', dataIndex: 'description', ellipsis: true },
  {
    title: '权限数',
    width: 100,
    render: (_, record) => (
      <Tag color="blue">{permissionCount(record.permissions)}</Tag>
    ),
  },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    width: 180,
    render: (_, record) => new Date(record.updated_at).toLocaleString(),
  },
  buildActionColumn<RoleItem>(actions, {
    deleteConfirmTitle: '确认删除此角色',
    isDisabled: (r) => r.is_system,
    disabledTooltip: '系统角色不可操作',
  }),
];

/* ---- 页面组件 ---- */

const RolePage: React.FC = () => {
  const [permissions, setPermissions] = useState<Record<string, string[]>>({});

  const queryResult = useRoleList({ limit: 200 });
  const createMutation = useCreateRole();
  const updateMutation = useUpdateRole();
  const deleteMutation = useDeleteRole();

  const togglePermission = useCallback((resource: string, action: string) => {
    setPermissions((prev) => {
      const current = prev[resource] ?? [];
      const has = current.includes(action);
      return {
        ...prev,
        [resource]: has ? current.filter((a) => a !== action) : [...current, action],
      };
    });
  }, []);

  const permMatrixColumns: ColumnsType<{ resource: string }> = [
    {
      title: '资源',
      dataIndex: 'resource',
      width: 140,
      render: (r: string) => RESOURCE_LABELS[r] ?? r,
    },
    ...ACTIONS.map((action) => ({
      title: action,
      key: action,
      width: 80,
      render: (_: unknown, row: { resource: string }) => (
        <Checkbox
          checked={(permissions[row.resource] ?? []).includes(action)}
          onChange={() => togglePermission(row.resource, action)}
        />
      ),
    })),
  ];

  /** renderForm 需要访问 permissions state，所以在组件内定义 */
  const renderForm = (_form: FormInstance, editing: RoleItem | null) => (
    <>
      <Form.Item
        name="name"
        label="角色名"
        rules={[{ required: true, pattern: /^[a-z][a-z0-9_-]{1,62}[a-z0-9]$/, message: '小写字母开头，字母/数字/连字符/下划线' }]}
      >
        <Input placeholder="dev-team" disabled={!!editing} />
      </Form.Item>
      <Form.Item name="description" label="描述">
        <Input placeholder="角色描述" />
      </Form.Item>

      <Text strong>权限矩阵</Text>
      <Table
        size="small"
        pagination={false}
        rowKey="resource"
        dataSource={RESOURCES.map((r) => ({ resource: r }))}
        style={{ marginTop: 12 }}
        columns={permMatrixColumns}
      />
    </>
  );

  return (
    <PageContainer
      title="角色管理"
      icon={<SafetyCertificateOutlined />}
      description="管理 RBAC 角色与权限矩阵"
    >
      <CrudTable<
        RoleItem,
        RoleCreateParams,
        { id: string; data: RoleUpdateParams }
      >
        hideTitle
        title="角色管理"
        queryResult={queryResult}
        createMutation={createMutation}
        updateMutation={updateMutation}
        deleteMutation={deleteMutation}
        createButtonText="新建角色"
        modalTitle={(editing) => (editing ? '编辑角色' : '新建角色')}
        modalWidth={720}
        columns={(actions) => buildColumns(actions)}
        renderForm={renderForm}
        toFormValues={(record) => {
          setPermissions({ ...record.permissions });
          return {
            name: record.name,
            description: record.description,
          };
        }}
        toCreatePayload={(values) => ({
          name: values.name as string,
          description: (values.description as string) || '',
          permissions,
        })}
        toUpdatePayload={(values, record) => ({
          id: record.id,
          data: {
            description: (values.description as string) || '',
            permissions,
          },
        })}
        createDefaults={{}}
        showRefresh
      />
    </PageContainer>
  );
};

export default RolePage;
