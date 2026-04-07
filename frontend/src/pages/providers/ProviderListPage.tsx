import { useCallback, useEffect, useState } from 'react';
import { Button, DatePicker, Form, Input, App, Modal, Popconfirm, Switch, Tag, Space } from 'antd';
import { KeyOutlined, PlusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { useNavigate } from 'react-router-dom';
import { providerService } from '../../services/providerService';
import type { ProviderResponse, ProviderTestResult } from '../../services/providerService';

const HEALTH_STATUS_MAP: Record<string, { color: string; text: string }> = {
  healthy: { color: 'green', text: '健康' },
  unhealthy: { color: 'red', text: '异常' },
  unknown: { color: 'default', text: '未知' },
};

const ProviderListPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [data, setData] = useState<ProviderResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const fetchProviders = useCallback(async () => {
    setLoading(true);
    try {
      const offset = (pagination.current - 1) * pagination.pageSize;
      const res = await providerService.list({ limit: pagination.pageSize, offset });
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取 Provider 列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination, message]);

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

  const handleDelete = async (id: string) => {
    try {
      await providerService.delete(id);
      message.success('删除成功');
      fetchProviders();
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    try {
      await providerService.toggle(id, enabled);
      message.success(enabled ? '已启用' : '已禁用');
      fetchProviders();
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
      const result: ProviderTestResult = await providerService.testConnection(record.id);
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
      fetchProviders();
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
      await providerService.rotateKey(rotateTarget.id, {
        new_api_key: values.new_api_key,
        key_expires_at: expiresAt,
      });
      message.success('密钥轮换成功');
      setRotateModalOpen(false);
      fetchProviders();
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
      render: (_, record) => <Tag color="blue">{record.provider_type}</Tag>,
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
            style={{ color: testing === record.id ? '#999' : undefined }}
          >
            {testing === record.id ? '测试中...' : <><ThunderboltOutlined /> 测试</>}
          </a>
          <Popconfirm
            title="确定删除此 Provider？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <a style={{ color: '#ff4d4f' }}>删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
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
          onClick={fetchProviders}
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
  </>
  );
};

export default ProviderListPage;
