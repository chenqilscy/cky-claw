import { useState, useCallback } from 'react';
import {
  Button,
  Form,
  Input,
  App,
  Modal,
  Result,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  ThunderboltOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import { TRANSPORT_TYPES } from '../../services/mcpServerService';
import type {
  MCPServerResponse,
  MCPServerCreateRequest,
  MCPServerUpdateRequest,
  MCPTestResult,
  MCPToolInfo,
  TransportType,
} from '../../services/mcpServerService';
import {
  useMCPServerList,
  useCreateMCPServer,
  useUpdateMCPServer,
  useDeleteMCPServer,
  useTestMCPConnection,
} from '../../hooks/useMCPServerQueries';
import { CrudTable } from '../../components';
import type { CrudTableActions } from '../../components';

const { TextArea } = Input;

const TRANSPORT_COLORS: Record<string, string> = {
  stdio: 'blue',
  sse: 'green',
  http: 'orange',
};

const TRANSPORT_OPTIONS = TRANSPORT_TYPES.map((t) => ({ label: t.toUpperCase(), value: t }));

/* ---- 工具预览表格列 ---- */

const toolColumns = [
  {
    title: '工具名称',
    dataIndex: 'name',
    key: 'name',
    width: 240,
    render: (name: string) => <code>{name}</code>,
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
  },
];

/* ---- 辅助函数 ---- */

const parseEnv = (envStr: string): Record<string, string> => {
  const result: Record<string, string> = {};
  if (!envStr) return result;
  envStr.split('\n').forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const idx = trimmed.indexOf('=');
    if (idx > 0) {
      result[trimmed.slice(0, idx)] = trimmed.slice(idx + 1);
    }
  });
  return result;
};

const buildAuthConfig = (
  entries: { key: string; value: string }[] | undefined,
  editingRecord: MCPServerResponse | null,
): Record<string, unknown> | undefined => {
  if (!entries || entries.length === 0) return undefined;
  const config: Record<string, string> = {};
  for (const entry of entries) {
    const key = (entry.key || '').trim();
    const value = (entry.value || '').trim();
    if (!key) continue;
    if (!value && editingRecord?.auth_config?.[key] === '***') continue;
    if (value) config[key] = value;
  }
  return Object.keys(config).length > 0 ? config : undefined;
};

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<MCPServerResponse>,
  onToggleEnabled: (record: MCPServerResponse, enabled: boolean) => void,
  onTestConnection: (record: MCPServerResponse) => void,
): ProColumns<MCPServerResponse>[] => [
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
    title: '传输类型',
    dataIndex: 'transport_type',
    width: 100,
    render: (_, record) => (
      <Tag color={TRANSPORT_COLORS[record.transport_type] || 'default'}>
        {record.transport_type.toUpperCase()}
      </Tag>
    ),
  },
  {
    title: '命令 / URL',
    width: 260,
    ellipsis: true,
    render: (_, record) =>
      record.transport_type === 'stdio'
        ? record.command || '-'
        : record.url || '-',
  },
  {
    title: '认证',
    width: 80,
    render: (_, record) =>
      record.auth_config && Object.keys(record.auth_config).length > 0
        ? <Tag color="green">已配置</Tag>
        : <Tag color="default">无</Tag>,
  },
  {
    title: '启用',
    dataIndex: 'is_enabled',
    width: 80,
    render: (_, record) => (
      <Switch
        checked={record.is_enabled}
        onChange={(checked) => onToggleEnabled(record, checked)}
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
    width: 200,
    render: (_, record) => (
      <Space>
        <Button
          type="link"
          size="small"
          icon={<ThunderboltOutlined />}
          onClick={() => onTestConnection(record)}
        >
          测试
        </Button>
        <Button
          type="link"
          size="small"
          icon={<EditOutlined />}
          onClick={() => actions.openEdit(record)}
        >
          编辑
        </Button>
        <Popconfirm
          title="确认删除此 MCP Server？"
          onConfirm={() => actions.handleDelete(record.id)}
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      </Space>
    ),
  },
];

/* ---- 页面组件 ---- */

const MCPServerPage: React.FC = () => {
  const { message } = App.useApp();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // 连接测试 Modal
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [testResult, setTestResult] = useState<MCPTestResult | null>(null);
  const [testServerName, setTestServerName] = useState('');

  const queryResult = useMCPServerList({
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const createMutation = useCreateMCPServer();
  const updateMutation = useUpdateMCPServer();
  const deleteMutation = useDeleteMCPServer();
  const testMutation = useTestMCPConnection();

  const handleToggleEnabled = useCallback(async (record: MCPServerResponse, enabled: boolean) => {
    try {
      await updateMutation.mutateAsync({ id: record.id, data: { is_enabled: enabled } });
      message.success(enabled ? '已启用' : '已禁用');
    } catch {
      message.error('操作失败');
    }
  }, [updateMutation, message]);

  const handleTestConnection = useCallback(async (record: MCPServerResponse) => {
    setTestServerName(record.name);
    setTestResult(null);
    setTestModalVisible(true);
    try {
      const result = await testMutation.mutateAsync(record.id);
      setTestResult(result);
    } catch {
      setTestResult({
        success: false,
        tools: [],
        error: '请求失败，请检查网络连接和后端服务状态',
        duration_ms: 0,
      });
    }
  }, [testMutation]);

  const renderForm = useCallback((_form: FormInstance, editing: MCPServerResponse | null) => (
    <>
      <Form.Item
        name="name"
        label="名称"
        rules={[
          { required: true, message: '请输入 MCP Server 名称' },
          { min: 2, max: 64, message: '长度须在 2-64 字符之间' },
        ]}
      >
        <Input placeholder="如: github-mcp-server" disabled={!!editing} />
      </Form.Item>

      <Form.Item name="description" label="描述">
        <Input placeholder="MCP Server 用途描述" />
      </Form.Item>

      <Form.Item
        name="transport_type"
        label="传输类型"
        rules={[{ required: true, message: '请选择传输类型' }]}
      >
        <Select options={TRANSPORT_OPTIONS} />
      </Form.Item>

      {/* 动态字段：根据 transport_type 显示 command 或 url */}
      <Form.Item noStyle shouldUpdate={(prev, next) => prev.transport_type !== next.transport_type}>
        {({ getFieldValue }) => {
          const transport = getFieldValue('transport_type') as string;
          if (transport === 'stdio') {
            return (
              <Form.Item
                name="command"
                label="启动命令"
                rules={[{ required: true, message: 'stdio 模式必须提供启动命令' }]}
              >
                <Input placeholder="如: npx -y @modelcontextprotocol/server-github" />
              </Form.Item>
            );
          }
          return (
            <Form.Item
              name="url"
              label="服务 URL"
              rules={[
                { required: true, message: `${(transport ?? 'HTTP').toUpperCase()} 模式必须提供 URL` },
                { type: 'url', message: '请输入有效的 URL' },
              ]}
            >
              <Input placeholder="如: http://localhost:8080/sse" />
            </Form.Item>
          );
        }}
      </Form.Item>

      <Form.Item name="env" label="环境变量（每行 KEY=VALUE）">
        <TextArea rows={3} placeholder={'GITHUB_TOKEN=ghp_xxx\nNODE_OPTIONS=--max-old-space-size=4096'} />
      </Form.Item>

      <Form.List name="auth_entries">
        {(fields, { add, remove }) => (
          <>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>认证配置</div>
            {fields.map((field) => (
              <Space key={field.key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                <Form.Item
                  {...field}
                  name={[field.name, 'key']}
                  rules={[{ required: true, message: '请输入字段名' }]}
                  style={{ marginBottom: 0 }}
                >
                  <Input placeholder="字段名 (如 api_key)" style={{ width: 180 }} />
                </Form.Item>
                <Form.Item
                  {...field}
                  name={[field.name, 'value']}
                  style={{ marginBottom: 0 }}
                >
                  <Input.Password
                    placeholder="值（敏感字段自动加密）"
                    style={{ width: 300 }}
                    visibilityToggle
                  />
                </Form.Item>
                <MinusCircleOutlined onClick={() => remove(field.name)} style={{ color: '#ff4d4f' }} />
              </Space>
            ))}
            <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />} style={{ width: '100%' }}>
              添加认证字段
            </Button>
          </>
        )}
      </Form.List>

      <Form.Item name="is_enabled" label="启用" valuePropName="checked" style={{ marginTop: 16 }}>
        <Switch />
      </Form.Item>
    </>
  ), []);

  return (
    <>
      <CrudTable<
        MCPServerResponse,
        MCPServerCreateRequest,
        { id: string; data: MCPServerUpdateRequest }
      >
        title={<Space><ApiOutlined />MCP Server 管理</Space>}
        queryResult={queryResult}
        createMutation={createMutation}
        updateMutation={updateMutation}
        deleteMutation={deleteMutation}
        createButtonText="新建 MCP Server"
        modalTitle={(editing) => (editing ? '编辑 MCP Server' : '新建 MCP Server')}
        modalWidth={640}
        columns={(actions) => buildColumns(actions, handleToggleEnabled, handleTestConnection)}
        renderForm={renderForm}
        createDefaults={{ transport_type: 'stdio', is_enabled: true, auth_entries: [] }}
        toFormValues={(record) => {
          const authEntries: { key: string; value: string }[] = [];
          if (record.auth_config) {
            Object.entries(record.auth_config).forEach(([k, v]) => {
              authEntries.push({ key: k, value: v === '***' ? '' : String(v ?? '') });
            });
          }
          return {
            name: record.name,
            description: record.description,
            transport_type: record.transport_type,
            command: record.command || '',
            url: record.url || '',
            env: record.env ? Object.entries(record.env).map(([k, v]) => `${k}=${v}`).join('\n') : '',
            is_enabled: record.is_enabled,
            auth_entries: authEntries,
          };
        }}
        toCreatePayload={(values) => ({
          name: values.name as string,
          transport_type: values.transport_type as TransportType,
          description: values.description as string,
          command: values.transport_type === 'stdio' ? (values.command as string) : undefined,
          url: values.transport_type !== 'stdio' ? (values.url as string) : undefined,
          env: parseEnv((values.env as string) || ''),
          auth_config: buildAuthConfig(values.auth_entries as { key: string; value: string }[] | undefined, null),
          is_enabled: (values.is_enabled as boolean) ?? true,
        })}
        toUpdatePayload={(values, record) => ({
          id: record.id,
          data: {
            description: values.description as string,
            transport_type: values.transport_type as TransportType,
            command: values.transport_type === 'stdio' ? (values.command as string) : null,
            url: values.transport_type !== 'stdio' ? (values.url as string) : null,
            env: parseEnv((values.env as string) || ''),
            auth_config: buildAuthConfig(values.auth_entries as { key: string; value: string }[] | undefined, record) ?? {},
            is_enabled: values.is_enabled as boolean,
          },
        })}
        pagination={pagination}
        onPaginationChange={(current, pageSize) => setPagination({ current, pageSize })}
        showRefresh
      />

      {/* ── 连接测试结果 Modal ─────────────────────────── */}
      <Modal
        title={`连接测试 — ${testServerName}`}
        open={testModalVisible}
        onCancel={() => setTestModalVisible(false)}
        footer={
          <Button onClick={() => setTestModalVisible(false)}>关闭</Button>
        }
        width={700}
      >
        {testMutation.isPending ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#666' }}>正在连接 MCP Server 并发现工具...</div>
          </div>
        ) : testResult ? (
          testResult.success ? (
            <>
              <Result
                status="success"
                title="连接成功"
                subTitle={`耗时 ${testResult.duration_ms}ms，发现 ${testResult.tools.length} 个工具`}
                style={{ padding: '16px 0' }}
              />
              {testResult.tools.length > 0 && (
                <Table<MCPToolInfo>
                  rowKey="name"
                  columns={toolColumns}
                  dataSource={testResult.tools}
                  size="small"
                  pagination={false}
                  scroll={{ y: 300 }}
                />
              )}
            </>
          ) : (
            <Result
              status="error"
              title="连接失败"
              subTitle={testResult.error || '未知错误'}
              style={{ padding: '16px 0' }}
            />
          )
        ) : null}
      </Modal>
    </>
  );
};

export default MCPServerPage;
