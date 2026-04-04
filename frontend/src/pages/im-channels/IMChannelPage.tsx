import { useEffect, useState } from 'react';
import {
  Card, Button, Space, Modal, Form, Input, Select, Tag, message,
  Popconfirm, Empty, Table, Typography, Tooltip, Switch,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined,
  LinkOutlined, CopyOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { IMChannel, IMChannelCreate, ChannelType } from '../../services/imChannelService';
import {
  CHANNEL_TYPES, listIMChannels, createIMChannel, updateIMChannel, deleteIMChannel,
} from '../../services/imChannelService';

const { TextArea } = Input;
const { Text } = Typography;

const channelLabel: Record<ChannelType, string> = {
  wecom: '企业微信',
  dingtalk: '钉钉',
  slack: 'Slack',
  telegram: 'Telegram',
  feishu: '飞书',
  webhook: '通用 Webhook',
};

const channelColor: Record<ChannelType, string> = {
  wecom: 'green',
  dingtalk: 'blue',
  slack: 'purple',
  telegram: 'cyan',
  feishu: 'orange',
  webhook: 'default',
};

const IMChannelPage: React.FC = () => {
  const [channels, setChannels] = useState<IMChannel[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<IMChannel | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filterType, setFilterType] = useState<string | undefined>(undefined);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await listIMChannels({
        channel_type: filterType,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setChannels(res.data);
      setTotal(res.total);
    } catch {
      message.error('加载 IM 渠道列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [page, pageSize, filterType]);

  const handleCreate = () => {
    setEditRecord(null);
    form.resetFields();
    form.setFieldsValue({ channel_type: 'webhook', is_enabled: true, app_config_json: '{}' });
    setModalOpen(true);
  };

  const handleEdit = (record: IMChannel) => {
    setEditRecord(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      channel_type: record.channel_type,
      webhook_url: record.webhook_url ?? '',
      webhook_secret: '',
      agent_id: record.agent_id ?? '',
      is_enabled: record.is_enabled,
      app_config_json: JSON.stringify(record.app_config, null, 2),
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteIMChannel(id);
      message.success('已删除');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      let appConfig = {};
      try {
        appConfig = values.app_config_json ? JSON.parse(values.app_config_json) : {};
      } catch {
        message.error('应用配置必须是合法 JSON');
        return;
      }
      const payload: IMChannelCreate = {
        name: values.name,
        description: values.description || '',
        channel_type: values.channel_type,
        webhook_url: values.webhook_url || null,
        webhook_secret: values.webhook_secret || null,
        app_config: appConfig,
        agent_id: values.agent_id || null,
        is_enabled: values.is_enabled ?? true,
      };
      if (editRecord) {
        const { name: _, ...updatePayload } = payload;
        await updateIMChannel(editRecord.id, updatePayload);
        message.success('更新成功');
      } else {
        await createIMChannel(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch {
      // form validation error
    }
  };

  const copyWebhookUrl = (record: IMChannel) => {
    const url = `${window.location.origin}/api/v1/im-channels/${record.id}/webhook`;
    navigator.clipboard?.writeText(url).then(
      () => message.success('Webhook URL 已复制'),
      () => message.info(url),
    );
  };

  const columns: ColumnsType<IMChannel> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: '渠道类型',
      dataIndex: 'channel_type',
      key: 'channel_type',
      render: (val: ChannelType) => (
        <Tag color={channelColor[val] || 'default'}>
          {channelLabel[val] || val}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      render: (val: boolean) => (
        <Tag color={val ? 'success' : 'default'}>
          {val ? '启用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '绑定 Agent',
      dataIndex: 'agent_id',
      key: 'agent_id',
      render: (val: string | null) => val ? <Text code>{val.slice(0, 8)}...</Text> : <Text type="secondary">未绑定</Text>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: IMChannel) => (
        <Space size="small">
          <Tooltip title="复制 Webhook URL">
            <Button type="text" icon={<CopyOutlined />} onClick={() => copyWebhookUrl(record)} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <LinkOutlined />
          <span>IM 渠道管理</span>
        </Space>
      }
      extra={
        <Space>
          <Select
            placeholder="渠道类型"
            allowClear
            style={{ width: 140 }}
            onChange={(v) => { setFilterType(v); setPage(1); }}
            options={CHANNEL_TYPES.map((t) => ({ value: t, label: channelLabel[t] || t }))}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            创建渠道
          </Button>
        </Space>
      }
    >
      {channels.length === 0 && !loading ? (
        <Empty description="暂无 IM 渠道配置" />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={channels}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
            showTotal: (t) => `共 ${t} 个渠道`,
          }}
        />
      )}

      <Modal
        title={editRecord ? '编辑渠道' : '创建渠道'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="渠道名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input maxLength={64} placeholder="如: wecom-sales" disabled={!!editRecord} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} maxLength={2000} placeholder="渠道用途描述" />
          </Form.Item>
          <Form.Item
            name="channel_type"
            label="渠道类型"
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select
              options={CHANNEL_TYPES.map((t) => ({ value: t, label: channelLabel[t] || t }))}
            />
          </Form.Item>
          <Form.Item name="webhook_url" label="Webhook URL">
            <Input placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" />
          </Form.Item>
          <Form.Item name="webhook_secret" label="Webhook 签名密钥">
            <Input.Password
              placeholder={editRecord ? '留空表示不修改' : '用于验证消息签名'}
            />
          </Form.Item>
          <Form.Item name="agent_id" label="绑定 Agent ID">
            <Input placeholder="接收消息后路由到此 Agent" />
          </Form.Item>
          <Form.Item name="is_enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="app_config_json" label="应用配置 (JSON)">
            <TextArea rows={4} placeholder='{"app_id": "xxx", "token": "xxx"}' />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default IMChannelPage;
