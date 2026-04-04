import { useState } from 'react';
import {
  Card, Button, Space, Modal, Form, Input, Table, Tag, message, Popconfirm, Empty,
  Typography, Checkbox, Tooltip,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined,
  SafetyCertificateOutlined, LockOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { roleService } from '../../services/roleService';
import type { RoleItem, RoleCreateParams } from '../../services/roleService';

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

const RolePage: React.FC = () => {
  const [createOpen, setCreateOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<RoleItem | null>(null);
  const [permissions, setPermissions] = useState<Record<string, string[]>>({});
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['roles'],
    queryFn: () => roleService.list({ limit: 200 }),
  });
  const roles = data?.data ?? [];

  const createMutation = useMutation({
    mutationFn: (params: RoleCreateParams) => roleService.create(params),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['roles'] }); },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: { description?: string; permissions?: Record<string, string[]> } }) =>
      roleService.update(id, d),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['roles'] }); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => roleService.delete(id),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['roles'] }); },
  });

  const handleCreate = () => {
    setEditRecord(null);
    setPermissions({});
    form.resetFields();
    setCreateOpen(true);
  };

  const handleEdit = (record: RoleItem) => {
    setEditRecord(record);
    setPermissions({ ...record.permissions });
    form.setFieldsValue({ name: record.name, description: record.description });
    setCreateOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      message.success('已删除');
    } catch {
      message.error('删除失败');
    }
  };

  const togglePermission = (resource: string, action: string) => {
    setPermissions((prev) => {
      const current = prev[resource] ?? [];
      const has = current.includes(action);
      return {
        ...prev,
        [resource]: has ? current.filter((a) => a !== action) : [...current, action],
      };
    });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editRecord) {
        await updateMutation.mutateAsync({
          id: editRecord.id,
          data: { description: values.description, permissions },
        });
        message.success('更新成功');
      } else {
        await createMutation.mutateAsync({
          name: values.name,
          description: values.description,
          permissions,
        });
        message.success('创建成功');
      }
      setCreateOpen(false);
    } catch {
      message.error('操作失败');
    }
  };

  const permissionCount = (perms: Record<string, string[]>) =>
    Object.values(perms).reduce((sum, actions) => sum + actions.length, 0);

  const columns: ColumnsType<RoleItem> = [
    {
      title: '角色名',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: RoleItem) => (
        <Space>
          <Text strong>{name}</Text>
          {record.is_system && <Tag color="gold"><LockOutlined /> 系统</Tag>}
        </Space>
      ),
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '权限数',
      key: 'perms',
      width: 100,
      render: (_: unknown, record: RoleItem) => (
        <Tag color="blue">{permissionCount(record.permissions)}</Tag>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: RoleItem) => (
        <Space>
          <Tooltip title="编辑">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
              disabled={record.is_system}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除此角色？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            disabled={record.is_system}
          >
            <Tooltip title={record.is_system ? '系统角色不可删除' : '删除'}>
              <Button type="link" danger size="small" icon={<DeleteOutlined />} disabled={record.is_system} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={<Space><SafetyCertificateOutlined />角色管理 (RBAC)</Space>}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => void refetch()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建角色</Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          columns={columns}
          dataSource={roles}
          loading={isLoading}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无角色" /> }}
        />
      </Card>

      <Modal
        title={editRecord ? '编辑角色' : '新建角色'}
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        width={720}
        onOk={() => void handleSubmit()}
        okText={editRecord ? '保存' : '创建'}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="角色名"
            rules={[{ required: true, pattern: /^[a-z][a-z0-9_-]{1,62}[a-z0-9]$/, message: '小写字母开头，字母/数字/连字符/下划线' }]}
          >
            <Input placeholder="dev-team" disabled={!!editRecord} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="角色描述" />
          </Form.Item>
        </Form>

        <Text strong>权限矩阵</Text>
        <Table
          size="small"
          pagination={false}
          rowKey="resource"
          dataSource={RESOURCES.map((r) => ({ resource: r }))}
          style={{ marginTop: 12 }}
          columns={[
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
          ]}
        />
      </Modal>
    </div>
  );
};

export default RolePage;
