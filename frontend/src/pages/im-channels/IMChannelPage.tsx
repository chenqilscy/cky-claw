import { useState, useCallback } from 'react';
import {
  App, Form, Input, Select, Tag, Typography, Switch,
} from 'antd';
import type { FormInstance } from 'antd';
import {
  LinkOutlined, CopyOutlined,
} from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { IMChannel, IMChannelCreate, IMChannelUpdate, ChannelType } from '../../services/imChannelService';
import { CHANNEL_TYPES } from '../../services/imChannelService';
import {
  useIMChannelList,
  useCreateIMChannel,
  useUpdateIMChannel,
  useDeleteIMChannel,
} from '../../hooks/useIMChannelQueries';
import { CrudTable, PageContainer, buildActionColumn, createJsonValidatorRule, JsonEditor } from '../../components';
import type { CrudTableActions } from '../../components';

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

/* ---- 列工厂 ---- */
function buildColumns(
  actions: CrudTableActions<IMChannel>,
  copyWebhookUrl: (r: IMChannel) => void,
): ProColumns<IMChannel>[] {
  return [
    {
      title: '名称',
      dataIndex: 'name',
      render: (_: unknown, r: IMChannel) => <Text strong>{r.name}</Text>,
    },
    {
      title: '渠道类型',
      dataIndex: 'channel_type',
      render: (_: unknown, r: IMChannel) => (
        <Tag color={channelColor[r.channel_type] || 'default'}>
          {channelLabel[r.channel_type] || r.channel_type}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      render: (_: unknown, r: IMChannel) => (
        <Tag color={r.is_enabled ? 'success' : 'default'}>
          {r.is_enabled ? '启用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '绑定 Agent',
      dataIndex: 'agent_id',
      render: (_: unknown, r: IMChannel) =>
        r.agent_id
          ? <Text code>{r.agent_id.slice(0, 8)}...</Text>
          : <Text type="secondary">未绑定</Text>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      render: (_: unknown, r: IMChannel) => new Date(r.created_at).toLocaleString(),
    },
    buildActionColumn<IMChannel>(actions, {
      extraItems: (record) => [
        {
          key: 'copy',
          label: '复制 Webhook URL',
          icon: <CopyOutlined />,
          onClick: () => copyWebhookUrl(record),
        },
      ],
    }),
  ];
}

/* ---- 表单渲染 ---- */
function renderForm(_form: FormInstance, editing: IMChannel | null) {
  return (
    <>
      <Form.Item
        name="name"
        label="渠道名称"
        rules={[{ required: true, message: '请输入名称' }]}
      >
        <Input maxLength={64} placeholder="如: wecom-sales" disabled={!!editing} />
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
          placeholder={editing ? '留空表示不修改' : '用于验证消息签名'}
        />
      </Form.Item>
      <Form.Item name="agent_id" label="绑定 Agent ID">
        <Input placeholder="接收消息后路由到此 Agent" />
      </Form.Item>
      <Form.Item name="is_enabled" label="启用" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item name="app_config_json" label="应用配置 (JSON)" rules={[createJsonValidatorRule()]}>
        <JsonEditor height={120} placeholder='{"app_id": "xxx", "token": "xxx"}' />
      </Form.Item>
    </>
  );
}

/* ---- Payload 构建 ---- */
function parseAppConfig(values: Record<string, unknown>): Record<string, unknown> {
  const raw = values.app_config_json as string;
  try {
    return raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
  } catch {
    throw new Error('应用配置必须是合法 JSON');
  }
}

function toCreatePayload(values: Record<string, unknown>): IMChannelCreate {
  return {
    name: values.name as string,
    description: (values.description as string) || '',
    channel_type: values.channel_type as string,
    webhook_url: (values.webhook_url as string) || null,
    webhook_secret: (values.webhook_secret as string) || null,
    app_config: parseAppConfig(values),
    agent_id: (values.agent_id as string) || null,
    is_enabled: (values.is_enabled as boolean) ?? true,
  };
}

function toUpdatePayload(
  values: Record<string, unknown>,
  editing: IMChannel,
): { id: string; data: IMChannelUpdate } {
  const { name: _, ...update } = toCreatePayload(values);
  void _;
  return { id: editing.id, data: update };
}

function toFormValues(record: IMChannel): Record<string, unknown> {
  return {
    name: record.name,
    description: record.description,
    channel_type: record.channel_type,
    webhook_url: record.webhook_url ?? '',
    webhook_secret: '',
    agent_id: record.agent_id ?? '',
    is_enabled: record.is_enabled,
    app_config_json: JSON.stringify(record.app_config, null, 2),
  };
}

/* ---- 页面组件 ---- */

const IMChannelPage: React.FC = () => {
  const { message } = App.useApp();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filterType, setFilterType] = useState<string | undefined>(undefined);

  const queryResult = useIMChannelList({
    channel_type: filterType,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });
  const createMut = useCreateIMChannel();
  const updateMut = useUpdateIMChannel();
  const deleteMut = useDeleteIMChannel();

  const copyWebhookUrl = useCallback(
    (record: IMChannel) => {
      const url = `${window.location.origin}/api/v1/im-channels/${record.id}/webhook`;
      navigator.clipboard?.writeText(url).then(
        () => message.success('Webhook URL 已复制'),
        () => message.info(url),
      );
    },
    [message],
  );

  const filterSelect = (
    <Select
      placeholder="渠道类型"
      allowClear
      style={{ width: 140 }}
      onChange={(v: string | undefined) => { setFilterType(v); setPage(1); }}
      options={CHANNEL_TYPES.map((t) => ({ value: t, label: channelLabel[t] || t }))}
    />
  );

  return (
    <PageContainer
      title="IM 渠道管理"
      icon={<LinkOutlined />}
      description="管理 IM 消息渠道（企微 / 钉钉 / Slack / Telegram / 飞书）"
    >
    <CrudTable<IMChannel, IMChannelCreate, { id: string; data: IMChannelUpdate }>
      hideTitle
      mobileHiddenColumns={['description', 'created_at']}
      title="IM 渠道管理"
      icon={<LinkOutlined />}
      columns={(actions) => buildColumns(actions, copyWebhookUrl)}
      queryResult={queryResult}
      createMutation={createMut}
      updateMutation={updateMut}
      deleteMutation={deleteMut}
      renderForm={renderForm}
      toFormValues={toFormValues}
      toCreatePayload={toCreatePayload}
      toUpdatePayload={toUpdatePayload}
      createDefaults={{ channel_type: 'webhook', is_enabled: true, app_config_json: '{}' }}
      createButtonText="创建渠道"
      modalTitle={(editing) => (editing ? '编辑渠道' : '创建渠道')}
      showRefresh
      extraToolbar={filterSelect}
      pagination={{ current: page, pageSize }}
      onPaginationChange={(p, ps) => { setPage(p); setPageSize(ps); }}
      total={queryResult.data?.total ?? 0}
    />
    </PageContainer>
  );
};

export default IMChannelPage;
