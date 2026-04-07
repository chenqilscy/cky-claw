import { useState, useCallback, useEffect } from 'react';
import { ProTable, type ProColumns } from '@ant-design/pro-components';
import { Button, Form, Input, Select, Tag, App, Space, Popconfirm, Drawer } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, StarOutlined } from '@ant-design/icons';
import {
  agentLocaleService,
  type AgentLocaleItem,
  type AgentLocaleCreateParams,
  type AgentLocaleUpdateParams,
} from '../../services/agentLocaleService';
import { agentService, type AgentConfig } from '../../services/agentService';

const { TextArea } = Input;

/** 常见 BCP 47 语言选项 */
const localeOptions = [
  { label: '中文（简体）— zh-CN', value: 'zh-CN' },
  { label: '中文（繁体）— zh-TW', value: 'zh-TW' },
  { label: 'English (US) — en-US', value: 'en-US' },
  { label: 'English (UK) — en-GB', value: 'en-GB' },
  { label: '日本語 — ja-JP', value: 'ja-JP' },
  { label: '한국어 — ko-KR', value: 'ko-KR' },
  { label: 'Français — fr-FR', value: 'fr-FR' },
  { label: 'Deutsch — de-DE', value: 'de-DE' },
  { label: 'Español — es-ES', value: 'es-ES' },
  { label: 'Português (BR) — pt-BR', value: 'pt-BR' },
];

const I18nSettingsPage: React.FC = () => {
  const { message } = App.useApp();
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | undefined>();
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  const [editDrawerOpen, setEditDrawerOpen] = useState(false);
  const [currentLocale, setCurrentLocale] = useState<AgentLocaleItem | null>(null);
  const [tableKey, setTableKey] = useState(0);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const reload = useCallback(() => setTableKey((k) => k + 1), []);

  /* 加载 Agent 列表（仅名称用于下拉选择） */
  useEffect(() => {
    agentService.list({ limit: 500 }).then((res) => setAgents(res.data));
  }, []);

  /* 编辑抽屉回填 */
  useEffect(() => {
    if (editDrawerOpen && currentLocale) {
      editForm.setFieldsValue({
        instructions: currentLocale.instructions,
        is_default: currentLocale.is_default,
      });
    }
  }, [editDrawerOpen, currentLocale, editForm]);

  /* 新增语言版本 */
  const handleCreate = async (values: AgentLocaleCreateParams) => {
    if (!selectedAgent) return;
    await agentLocaleService.create(selectedAgent, values);
    message.success('语言版本创建成功');
    setCreateDrawerOpen(false);
    createForm.resetFields();
    reload();
  };

  /* 更新语言版本 */
  const handleEdit = async (values: AgentLocaleUpdateParams) => {
    if (!selectedAgent || !currentLocale) return;
    await agentLocaleService.update(selectedAgent, currentLocale.locale, values);
    message.success('语言版本更新成功');
    setEditDrawerOpen(false);
    editForm.resetFields();
    setCurrentLocale(null);
    reload();
  };

  /* 删除语言版本 */
  const handleDelete = async (locale: string) => {
    if (!selectedAgent) return;
    await agentLocaleService.delete(selectedAgent, locale);
    message.success('语言版本已删除');
    reload();
  };

  const columns: ProColumns<AgentLocaleItem>[] = [
    {
      title: '语言标识',
      dataIndex: 'locale',
      width: 120,
      copyable: true,
    },
    {
      title: '默认',
      dataIndex: 'is_default',
      width: 80,
      render: (_, record) =>
        record.is_default ? <Tag color="gold"><StarOutlined /> 默认</Tag> : <Tag>—</Tag>,
    },
    {
      title: 'Instructions 预览',
      dataIndex: 'instructions',
      ellipsis: true,
      render: (_, record) => record.instructions.slice(0, 80) + (record.instructions.length > 80 ? '...' : ''),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
      valueType: 'dateTime',
    },
    {
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setCurrentLocale(record);
              setEditDrawerOpen(true);
            }}
          >
            编辑
          </Button>
          {record.is_default ? (
            <Button type="link" size="small" disabled title="默认语言版本不可删除">
              删除
            </Button>
          ) : (
            <Popconfirm
              title="确认删除该语言版本？"
              onConfirm={() => handleDelete(record.locale)}
            >
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* Agent 选择器 */}
      <div style={{ marginBottom: 16 }}>
        <Select
          showSearch
          placeholder="请选择 Agent"
          style={{ width: 320 }}
          value={selectedAgent}
          onChange={(val) => {
            setSelectedAgent(val);
            reload();
          }}
          options={agents.map((a) => ({ label: `${a.name}（${a.description || '无描述'}）`, value: a.name }))}
          filterOption={(input, option) =>
            (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) ?? false
          }
        />
      </div>

      {/* 语言版本表格 */}
      <ProTable<AgentLocaleItem>
        key={tableKey}
        columns={columns}
        rowKey="id"
        search={false}
        pagination={false}
        headerTitle="语言版本列表"
        toolBarRender={() => [
          <Button
            key="add"
            type="primary"
            icon={<PlusOutlined />}
            disabled={!selectedAgent}
            onClick={() => setCreateDrawerOpen(true)}
          >
            新增语言版本
          </Button>,
        ]}
        request={async () => {
          if (!selectedAgent) return { data: [], success: true };
          const res = await agentLocaleService.list(selectedAgent);
          return { data: res.data, success: true };
        }}
      />

      {/* 新增抽屉 */}
      <Drawer
        title="新增语言版本"
        width={640}
        open={createDrawerOpen}
        onClose={() => {
          setCreateDrawerOpen(false);
          createForm.resetFields();
        }}
        extra={
          <Button type="primary" onClick={() => createForm.submit()}>
            保存
          </Button>
        }
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="locale"
            label="语言标识（BCP 47）"
            rules={[{ required: true, message: '请选择语言' }]}
          >
            <Select
              showSearch
              placeholder="选择或输入语言标识"
              options={localeOptions}
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) ?? false
              }
            />
          </Form.Item>
          <Form.Item
            name="instructions"
            label="Instructions"
            rules={[{ required: true, message: '请输入 Instructions' }]}
          >
            <TextArea rows={12} placeholder="输入该语言版本的 Agent Instructions..." />
          </Form.Item>
          <Form.Item name="is_default" label="设为默认" valuePropName="checked" initialValue={false}>
            <Select
              options={[
                { label: '是', value: true },
                { label: '否', value: false },
              ]}
            />
          </Form.Item>
        </Form>
      </Drawer>

      {/* 编辑抽屉 */}
      <Drawer
        title={`编辑 ${currentLocale?.locale ?? ''} Instructions`}
        width={640}
        open={editDrawerOpen}
        onClose={() => {
          setEditDrawerOpen(false);
          editForm.resetFields();
          setCurrentLocale(null);
        }}
        extra={
          <Button type="primary" onClick={() => editForm.submit()}>
            保存
          </Button>
        }
      >
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          <Form.Item
            name="instructions"
            label="Instructions"
            rules={[{ required: true, message: '请输入 Instructions' }]}
          >
            <TextArea rows={16} />
          </Form.Item>
          <Form.Item name="is_default" label="设为默认">
            <Select
              options={[
                { label: '是', value: true },
                { label: '否', value: false },
              ]}
            />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
};

export default I18nSettingsPage;
