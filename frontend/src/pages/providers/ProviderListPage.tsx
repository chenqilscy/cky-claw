import { useState } from 'react';
import { Button, DatePicker, Form, Input, App, Modal, Popconfirm, Switch, Tag, Space, theme } from 'antd';
import { KeyOutlined, PlusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { useNavigate } from 'react-router-dom';
import {
  useProviderList,
  useDeleteProvider,
  useToggleProvider,
  useTestProviderConnection,
  useRotateProviderKey,
} from '../../hooks/useProviderQueries';
import type { ProviderResponse } from '../../services/providerService';
import { PROVIDER_TYPE_LABELS } from '../../services/providerService';

const HEALTH_STATUS_MAP: Record<string, { color: string; text: string }> = {
  healthy: { color: 'green', text: '健康' },
  unhealthy: { color: 'red', text: '异常' },
  unknown: { color: 'default', text: '未知' },
};

const ProviderListPage: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const { data: listData, isLoading: loading, refetch } = useProviderList({
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const data = listData?.data ?? [];
  const total = listData?.total ?? 0;

  const deleteMutation = useDeleteProvider();
  const toggleMutation = useToggleProvider();
  const testMutation = useTestProviderConnection();
  const rotateMutation = useRotateProviderKey();

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      message.success('删除成功');
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    try {
      await toggleMutation.mutateAsync({ id, isEnabled: enabled });
      message.success(enabled ? '已启用' : '已禁用');
    } catch {
      message.error('操作失败');
    }
  };

  const [testing, setTesting] = useState<string | null>(null);
  const [rotateModalOpen, setRotateModalOpen] = useState(false);
  const [rotateTarget, setRotateTarget] = useState<ProviderResponse | null>(null);
  const [rotateForm] = Form.useForm();

  const handleTest = async (record: ProviderResponse) => {
    setTesting(record.id);
    try {
      const result = await testMutation.mutateAsync(record.id);
      if (result.success) {
        Modal.success({
          title: '连接成功',
          content: `模型: ${result.model_used ?? '-'}，延迟: ${result.latency_ms}ms`,
        });
      } else {
        Modal.error({
          title: '连接失败',
          content: result.error ?? '未知错误',
        });
      }
    } catch {
      message.error('测试请求失败');
    } finally {
      setTesting(null);
    }
  };

  const openRotateModal = (record: ProviderResponse) => {
    setRotateTarget(record);
    rotateForm.resetFields();
    setRotateModalOpen(true);
  };

  const handleRotateKey = async () => {
    if (!rotateTarget) return;
    try {
      const values = await rotateForm.validateFields();
      const expiresAt = values.key_expires_at ? values.key_expires_at.toISOString() : null;
      await rotateMutation.mutateAsync({
        id: rotateTarget.id,
        data: { new_api_key: values.new_api_key, key_expires_at: expiresAt },
      });
      message.success('密钥轮换成功');
      setRotateModalOpen(false);
    } catch {
      message.error('密钥轮换失败');
    }
  };

  const columns: ProColumns<ProviderResponse>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 160,
      render: (_, record) => (
        <a onClick={() => navigate(`/providers/${record.id}/edit`)}>{record.name}</a>
      ),
    },
    {
      title: '厂商类型',
      dataIndex: 'provider_type',
      width: 120,
      render: (_, record) => <Tag color="blue">{PROVIDER_TYPE_LABELS[record.provider_type] ?? record.provider_type}</Tag>,
    },
    {
      title: 'Base URL',
      dataIndex: 'base_url',
      width: 260,
      ellipsis: true,
    },
    {
      title: 'API Key',
      dataIndex: 'api_key_set',
      width: 100,
      render: (_, record) => record.api_key_set
        ? <Tag color="green">已设置</Tag>
        : <Tag color="red">未设置</Tag>,
    },
    {
      title: '密钥状态',
      dataIndex: 'key_expired',
      width: 100,
      render: (_, record) => {
        if (!record.api_key_set) return <Tag color="default">无密钥</Tag>;
        if (record.key_expired) return <Tag color="red">已过期</Tag>;
        if (record.key_expires_at) return <Tag color="green">有效</Tag>;
        return <Tag color="default">永久</Tag>;
      },
    },
    {
      title: '认证方式',
      dataIndex: 'auth_type',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      width: 80,
      render: (_, record) => (
        <Switch
          checked={record.is_enabled}
          size="small"
          onChange={(checked) => handleToggle(record.id, checked)}
        />
      ),
    },
    {
      title: '健康状态',
      dataIndex: 'health_status',
      width: 100,
      render: (_, record) => {
        const s = HEALTH_STATUS_MAP[record.health_status] ?? { color: 'default', text: record.health_status };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
      render: (_, record) => new Date(record.updated_at).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 260,
      render: (_, record) => (
        <Space>
          <a onClick={() => navigate(`/providers/${record.id}/edit`)}>编辑</a>
          <a onClick={() => openRotateModal(record)}>
            <KeyOutlined /> 轮换
          </a>
          <a
            onClick={() => handleTest(record)}
            style={{ color: testing === record.id ? token.colorTextQuaternary : undefined }}
          >
            {testing === record.id ? '测试中...' : <><ThunderboltOutlined /> 测试</>}
          </a>
          <Popconfirm
            title="确定删除此模型厂商？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <a style={{ color: token.colorError }}>删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer
      title="模型厂商管理"
      icon={<KeyOutlined />}
      description="管理 LLM 厂商连接、密钥轮换与健康检测"
    >
    <ProTable<ProviderResponse>
      headerTitle="模型厂商管理"
      rowKey="id"
      columns={columns}
      dataSource={data}
      loading={loading}
      search={false}
      pagination={{
        current: pagination.current,
        pageSize: pagination.pageSize,
        total,
        showSizeChanger: true,
        onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
      }}
      toolBarRender={() => [
        <Button
          key="create"
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/providers/new')}
        >
          注册厂商
        </Button>,
        <ReloadOutlined
          key="reload"
          style={{ cursor: 'pointer', fontSize: 16 }}
          onClick={() => void refetch()}
        />,
      ]}
    />

    <Modal
      title={`轮换密钥 — ${rotateTarget?.name ?? ''}`}
      open={rotateModalOpen}
      onOk={handleRotateKey}
      onCancel={() => setRotateModalOpen(false)}
      okText="确认轮换"
      cancelText="取消"
      destroyOnHidden
    >
      <Form form={rotateForm} layout="vertical">
        <Form.Item
          name="new_api_key"
          label="新 API Key"
          rules={[{ required: true, message: '请输入新 API Key' }]}
        >
          <Input.Password placeholder="请输入新的 API Key" />
        </Form.Item>
        <Form.Item name="key_expires_at" label="过期时间（可选）">
          <DatePicker showTime style={{ width: '100%' }} placeholder="留空表示永不过期" />
        </Form.Item>
      </Form>
    </Modal>
  </PageContainer>
  );
};

export default ProviderListPage;
