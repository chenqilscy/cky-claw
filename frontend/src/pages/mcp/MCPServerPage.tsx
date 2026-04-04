import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  message,
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
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { mcpServerService, TRANSPORT_TYPES } from '../../services/mcpServerService';
import type {
  MCPServerResponse,
  MCPServerCreateRequest,
  MCPServerUpdateRequest,
  MCPTestResult,
  MCPToolInfo,
  TransportType,
} from '../../services/mcpServerService';

const { TextArea } = Input;

const TRANSPORT_COLORS: Record<string, string> = {
  stdio: 'blue',
  sse: 'green',
  http: 'orange',
};

const TRANSPORT_OPTIONS = TRANSPORT_TYPES.map((t) => ({ label: t.toUpperCase(), value: t }));

const MCPServerPage: React.FC = () => {
  const [data, setData] = useState<MCPServerResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // 创建/编辑 Modal
  const [modalVisible, setModalVisible] = useState(false);
  const [editingServer, setEditingServer] = useState<MCPServerResponse | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [selectedTransport, setSelectedTransport] = useState<TransportType>('stdio');

  // 连接测试 Modal
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<MCPTestResult | null>(null);
  const [testServerName, setTestServerName] = useState('');

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mcpServerService.list({
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      });
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取 MCP Server 列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // ── 创建/编辑 ─────────────────────────────────────────────

  const openCreate = () => {
    setEditingServer(null);
    setSelectedTransport('stdio');
    form.resetFields();
    form.setFieldsValue({ transport_type: 'stdio', is_enabled: true, auth_entries: [] });
    setModalVisible(true);
  };

  const openEdit = (record: MCPServerResponse) => {
    setEditingServer(record);
    setSelectedTransport(record.transport_type);

    // 将 auth_config 转为 Key-Value 数组（已脱敏值显示为空，不回填 ***）
    const authEntries: { key: string; value: string }[] = [];
    if (record.auth_config) {
      Object.entries(record.auth_config).forEach(([k, v]) => {
        authEntries.push({
          key: k,
          value: v === '***' ? '' : String(v ?? ''),
        });
      });
    }

    form.setFieldsValue({
      name: record.name,
      description: record.description,
      transport_type: record.transport_type,
      command: record.command || '',
      url: record.url || '',
      env: record.env ? Object.entries(record.env).map(([k, v]) => `${k}=${v}`).join('\n') : '',
      is_enabled: record.is_enabled,
      auth_entries: authEntries,
    });
    setModalVisible(true);
  };

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

  const buildAuthConfig = (entries: { key: string; value: string }[] | undefined): Record<string, unknown> | undefined => {
    if (!entries || entries.length === 0) return undefined;
    const config: Record<string, string> = {};
    for (const entry of entries) {
      const key = (entry.key || '').trim();
      const value = (entry.value || '').trim();
      if (!key) continue;
      // 编辑模式下，如果值为空且原始是 ***，说明用户没修改，跳过（不覆盖）
      if (!value && editingServer?.auth_config?.[key] === '***') continue;
      if (value) config[key] = value;
    }
    return Object.keys(config).length > 0 ? config : undefined;
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const env = parseEnv(values.env || '');
      const authConfig = buildAuthConfig(values.auth_entries);

      if (editingServer) {
        const updateData: MCPServerUpdateRequest = {
          description: values.description,
          transport_type: values.transport_type,
          command: values.transport_type === 'stdio' ? values.command : null,
          url: values.transport_type !== 'stdio' ? values.url : null,
          env,
          auth_config: authConfig ?? {},
          is_enabled: values.is_enabled,
        };
        await mcpServerService.update(editingServer.id, updateData);
        message.success('更新成功');
      } else {
        const createData: MCPServerCreateRequest = {
          name: values.name,
          transport_type: values.transport_type,
          description: values.description,
          command: values.transport_type === 'stdio' ? values.command : undefined,
          url: values.transport_type !== 'stdio' ? values.url : undefined,
          env,
          auth_config: authConfig,
          is_enabled: values.is_enabled ?? true,
        };
        await mcpServerService.create(createData);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchList();
    } catch {
      message.error('操作失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await mcpServerService.delete(id);
      message.success('删除成功');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggleEnabled = async (record: MCPServerResponse, enabled: boolean) => {
    try {
      await mcpServerService.update(record.id, { is_enabled: enabled });
      message.success(enabled ? '已启用' : '已禁用');
      fetchList();
    } catch {
      message.error('操作失败');
    }
  };

  // ── 连接测试 ─────────────────────────────────────────────

  const handleTestConnection = async (record: MCPServerResponse) => {
    setTestServerName(record.name);
    setTestResult(null);
    setTestModalVisible(true);
    setTesting(true);
    try {
      const result = await mcpServerService.testConnection(record.id);
      setTestResult(result);
    } catch {
      setTestResult({
        success: false,
        tools: [],
        error: '请求失败，请检查网络连接和后端服务状态',
        duration_ms: 0,
      });
    } finally {
      setTesting(false);
    }
  };

  // ── 工具预览表格列 ────────────────────────────────────────

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

  // ── ProTable Columns ──────────────────────────────────────

  const columns: ProColumns<MCPServerResponse>[] = [
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
      width: 200,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => handleTestConnection(record)}
          >
            测试
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除此 MCP Server？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title={
          <Space>
            <ApiOutlined />
            MCP Server 管理
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建 MCP Server
          </Button>
        }
      >
        <ProTable<MCPServerResponse>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          search={false}
          toolBarRender={false}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>

      {/* ── 创建/编辑 Modal ─────────────────────────────── */}
      <Modal
        title={editingServer ? '编辑 MCP Server' : '新建 MCP Server'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请输入 MCP Server 名称' },
              { min: 2, max: 64, message: '长度须在 2-64 字符之间' },
            ]}
          >
            <Input placeholder="如: github-mcp-server" disabled={!!editingServer} />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input placeholder="MCP Server 用途描述" />
          </Form.Item>

          <Form.Item
            name="transport_type"
            label="传输类型"
            rules={[{ required: true, message: '请选择传输类型' }]}
          >
            <Select
              options={TRANSPORT_OPTIONS}
              onChange={(v: TransportType) => setSelectedTransport(v)}
            />
          </Form.Item>

          {selectedTransport === 'stdio' && (
            <Form.Item
              name="command"
              label="启动命令"
              rules={[{ required: true, message: 'stdio 模式必须提供启动命令' }]}
            >
              <Input placeholder="如: npx -y @modelcontextprotocol/server-github" />
            </Form.Item>
          )}

          {selectedTransport !== 'stdio' && (
            <Form.Item
              name="url"
              label="服务 URL"
              rules={[
                { required: true, message: `${selectedTransport.toUpperCase()} 模式必须提供 URL` },
                { type: 'url', message: '请输入有效的 URL' },
              ]}
            >
              <Input placeholder="如: http://localhost:8080/sse" />
            </Form.Item>
          )}

          <Form.Item
            name="env"
            label="环境变量（每行 KEY=VALUE）"
          >
            <TextArea rows={3} placeholder={'GITHUB_TOKEN=ghp_xxx\nNODE_OPTIONS=--max-old-space-size=4096'} />
          </Form.Item>

          {/* ── 认证配置 Key-Value 编辑器 ─────────────────── */}
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
        </Form>
      </Modal>

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
        {testing ? (
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
