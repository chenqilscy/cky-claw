import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Switch, Table, Tabs, Tag, App, Spin } from 'antd';
import { ArrowLeftOutlined, ApiOutlined, PlusOutlined, SyncOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { providerService, PROVIDER_TYPES, AUTH_TYPES, PROVIDER_BASE_URLS, PROVIDER_TYPE_LABELS, MODEL_TIER_OPTIONS, CAPABILITY_OPTIONS } from '../../services/providerService';
import type { ProviderCreateRequest, ProviderUpdateRequest, ProviderModelResponse, ProviderModelCreateRequest, ProviderModelUpdateRequest } from '../../services/providerService';
import type { ColumnsType } from 'antd/es/table';

/** 认证方式中文标签 */
const AUTH_TYPE_LABELS: Record<string, string> = {
  api_key: 'API Key',
  azure_ad: 'Azure AD',
  custom_header: '自定义 Header',
};

/** 根据 auth_type 从表单值构建 auth_config */
function buildAuthConfig(authType: string, values: Record<string, unknown>): Record<string, unknown> {
  switch (authType) {
    case 'azure_ad':
      return {
        tenant_id: (values.azure_tenant_id as string) || '',
        client_id: (values.azure_client_id as string) || '',
      };
    case 'custom_header':
      return {
        header_name: (values.auth_header_name as string) || '',
        header_value: (values.auth_header_value as string) || '',
      };
    default:
      return {};
  }
}

const ProviderEditPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [providerName, setProviderName] = useState<string>('');
  const [authType, setAuthType] = useState<string>('api_key');

  /* ---- 模型管理状态 ---- */
  const [models, setModels] = useState<ProviderModelResponse[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelModalOpen, setModelModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ProviderModelResponse | null>(null);
  const [modelForm] = Form.useForm();
  const [modelSaving, setModelSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  /** 切换厂商类型时自动填写 Base URL（仅当 base_url 为空或匹配已知厂商 URL 时覆盖） */
  const handleProviderTypeChange = (type: string) => {
    const currentUrl = (form.getFieldValue('base_url') as string) ?? '';
    const knownUrls = new Set(Object.values(PROVIDER_BASE_URLS).filter(Boolean));
    if (!currentUrl || knownUrls.has(currentUrl)) {
      form.setFieldValue('base_url', PROVIDER_BASE_URLS[type] ?? '');
    }
  };

  useEffect(() => {
    if (isEdit && id) {
      setLoading(true);
      providerService.get(id)
        .then((provider) => {
          setProviderName(provider.name);
          setAuthType(provider.auth_type || 'api_key');
          form.setFieldsValue({
            name: provider.name,
            provider_type: provider.provider_type,
            base_url: provider.base_url,
            auth_type: provider.auth_type,
            auth_header_name: provider.auth_config?.header_name ?? '',
            auth_header_value: provider.auth_config?.header_value ?? '',
            azure_tenant_id: provider.auth_config?.tenant_id ?? '',
            azure_client_id: provider.auth_config?.client_id ?? '',
            rate_limit_rpm: provider.rate_limit_rpm,
            rate_limit_tpm: provider.rate_limit_tpm,
            model_tier: provider.model_tier || 'moderate',
            capabilities: provider.capabilities || [],
          });
        })
        .catch(() => message.error('加载 Provider 失败'))
        .finally(() => setLoading(false));
    }
  }, [isEdit, id, form, message]);

  const onFinish = async (values: Record<string, unknown>) => {
    setSaving(true);
    try {
      if (isEdit && id) {
        const currentAuthType = (values.auth_type as string) || 'api_key';
        const payload: ProviderUpdateRequest = {
          name: values.name as string,
          provider_type: values.provider_type as string,
          base_url: values.base_url as string,
          auth_type: currentAuthType,
          auth_config: buildAuthConfig(currentAuthType, values),
          rate_limit_rpm: values.rate_limit_rpm as number | null ?? null,
          rate_limit_tpm: values.rate_limit_tpm as number | null ?? null,
          model_tier: values.model_tier as ProviderUpdateRequest['model_tier'],
          capabilities: values.capabilities as ProviderUpdateRequest['capabilities'],
        };
        if (values.api_key) {
          payload.api_key = values.api_key as string;
        }
        await providerService.update(id, payload);
        message.success('更新成功');
      } else {
        const createAuthType = (values.auth_type as string) || 'api_key';
        const payload: ProviderCreateRequest = {
          name: values.name as string,
          provider_type: values.provider_type as string,
          base_url: values.base_url as string,
          api_key: values.api_key as string,
          auth_type: createAuthType,
          auth_config: buildAuthConfig(createAuthType, values),
          rate_limit_rpm: values.rate_limit_rpm as number | null ?? null,
          rate_limit_tpm: values.rate_limit_tpm as number | null ?? null,
          model_tier: values.model_tier as ProviderCreateRequest['model_tier'],
          capabilities: values.capabilities as ProviderCreateRequest['capabilities'],
        };
        await providerService.create(payload);
        message.success('注册成功');
      }
      navigate('/providers');
    } catch {
      message.error(isEdit ? '更新失败' : '注册失败');
    } finally {
      setSaving(false);
    }
  };

  /** 测试连接（仅编辑模式可用） */
  const handleTestConnection = async () => {
    if (!id) return;
    setTesting(true);
    try {
      const result = await providerService.testConnection(id);
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
      setTesting(false);
    }
  };

  /* ---- 模型管理 ---- */

  const loadModels = useCallback(async () => {
    if (!id) return;
    setModelsLoading(true);
    try {
      const res = await providerService.listModels(id);
      setModels(res.data);
    } catch {
      message.error('加载模型列表失败');
    } finally {
      setModelsLoading(false);
    }
  }, [id, message]);

  useEffect(() => {
    if (isEdit && id) loadModels();
  }, [isEdit, id, loadModels]);

  const openModelCreate = () => {
    setEditingModel(null);
    modelForm.resetFields();
    modelForm.setFieldsValue({ context_window: 4096, prompt_price_per_1k: 0, completion_price_per_1k: 0, is_enabled: true });
    setModelModalOpen(true);
  };

  const openModelEdit = (record: ProviderModelResponse) => {
    setEditingModel(record);
    modelForm.setFieldsValue({
      model_name: record.model_name,
      display_name: record.display_name,
      context_window: record.context_window,
      max_output_tokens: record.max_output_tokens,
      prompt_price_per_1k: record.prompt_price_per_1k,
      completion_price_per_1k: record.completion_price_per_1k,
      is_enabled: record.is_enabled,
    });
    setModelModalOpen(true);
  };

  const handleModelSave = async () => {
    if (!id) return;
    try {
      const values = await modelForm.validateFields();
      setModelSaving(true);
      if (editingModel) {
        const payload: ProviderModelUpdateRequest = {
          model_name: values.model_name,
          display_name: values.display_name,
          context_window: values.context_window,
          max_output_tokens: values.max_output_tokens ?? null,
          prompt_price_per_1k: values.prompt_price_per_1k,
          completion_price_per_1k: values.completion_price_per_1k,
          is_enabled: values.is_enabled,
        };
        await providerService.updateModel(id, editingModel.id, payload);
        message.success('模型已更新');
      } else {
        const payload: ProviderModelCreateRequest = {
          model_name: values.model_name,
          display_name: values.display_name || '',
          context_window: values.context_window ?? 4096,
          max_output_tokens: values.max_output_tokens ?? null,
          prompt_price_per_1k: values.prompt_price_per_1k ?? 0,
          completion_price_per_1k: values.completion_price_per_1k ?? 0,
          is_enabled: values.is_enabled ?? true,
        };
        await providerService.createModel(id, payload);
        message.success('模型已添加');
      }
      setModelModalOpen(false);
      loadModels();
    } catch {
      // validation error or API error
    } finally {
      setModelSaving(false);
    }
  };

  const handleModelDelete = async (modelId: string) => {
    if (!id) return;
    try {
      await providerService.deleteModel(id, modelId);
      message.success('模型已删除');
      loadModels();
    } catch {
      message.error('删除失败');
    }
  };

  /** 从厂商自动同步模型列表 */
  const handleSyncModels = async () => {
    if (!id) return;
    setSyncing(true);
    try {
      const result = await providerService.syncModels(id);
      if (result.errors.length > 0) {
        message.warning(`同步完成，但有 ${result.errors.length} 个错误：${result.errors[0]}`);
      } else {
        message.success(`同步完成：新增 ${result.created} 个，更新 ${result.updated} 个`);
      }
      loadModels();
    } catch {
      message.error('模型同步失败，请确认厂商已配置正确的 Base URL 和 API Key');
    } finally {
      setSyncing(false);
    }
  };

  const modelColumns: ColumnsType<ProviderModelResponse> = [
    { title: '模型标识', dataIndex: 'model_name', key: 'model_name', width: 200 },
    { title: '显示名称', dataIndex: 'display_name', key: 'display_name', width: 160, render: (v: string) => v || '-' },
    { title: '上下文窗口', dataIndex: 'context_window', key: 'context_window', width: 120, render: (v: number) => v.toLocaleString() },
    { title: '最大输出', dataIndex: 'max_output_tokens', key: 'max_output_tokens', width: 100, render: (v: number | null) => v?.toLocaleString() ?? '-' },
    { title: '输入价格/1k', dataIndex: 'prompt_price_per_1k', key: 'prompt_price_per_1k', width: 120, render: (v: number) => `$${v}` },
    { title: '输出价格/1k', dataIndex: 'completion_price_per_1k', key: 'completion_price_per_1k', width: 120, render: (v: number) => `$${v}` },
    {
      title: '状态', dataIndex: 'is_enabled', key: 'is_enabled', width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作', key: 'actions', width: 140,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => openModelEdit(record)}>编辑</Button>
          <Popconfirm title="确认删除该模型？" onConfirm={() => handleModelDelete(record.id)} okText="删除" cancelText="取消">
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer
      title={isEdit ? (providerName ? `编辑模型厂商：${providerName}` : '编辑模型厂商') : '注册新模型厂商'}
      icon={<ApiOutlined />}
      description="配置模型厂商类型、认证方式与模型管理"
      extra={
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/providers')}>
          返回列表
        </Button>
      }
    >
      <Tabs
        defaultActiveKey="basic"
        items={[
          {
            key: 'basic',
            label: '基本配置',
            children: (
              <Card>
                <Spin spinning={loading}>
                  <Form
                    form={form}
                    layout="vertical"
                    onFinish={onFinish}
                    initialValues={{ auth_type: 'api_key', provider_type: 'openai', base_url: PROVIDER_BASE_URLS.openai, model_tier: 'moderate', capabilities: ['text'] }}
                  >
                    <Form.Item
                      name="name"
                      label="名称"
                      rules={[{ required: true, message: '请输入厂商名称' }]}
                    >
                      <Input placeholder="如：OpenAI 官方、Azure China" />
                    </Form.Item>

                    <Form.Item
                      name="provider_type"
                      label="厂商类型"
                      rules={[{ required: true, message: '请选择厂商类型' }]}
                    >
                      <Select
                        options={PROVIDER_TYPES.map((t) => ({ label: PROVIDER_TYPE_LABELS[t] ?? t, value: t }))}
                        placeholder="选择厂商类型"
                        onChange={handleProviderTypeChange}
                      />
                    </Form.Item>

                    <Form.Item
                      name="base_url"
                      label="Base URL"
                      rules={[{ required: true, message: '请输入 API 端点 URL' }]}
                    >
                      <Input placeholder="https://api.openai.com/v1" />
                    </Form.Item>

                    <Form.Item name="auth_type" label="认证方式">
                      <Select
                        options={AUTH_TYPES.map((t) => ({ label: AUTH_TYPE_LABELS[t] ?? t, value: t }))}
                        onChange={(v: string) => setAuthType(v)}
                      />
                    </Form.Item>

                    <Form.Item
                      name="api_key"
                      label={isEdit ? 'API Key（留空则不更新）' : 'API Key'}
                      rules={isEdit ? [] : [{ required: true, message: '请输入 API Key' }]}
                      style={{ display: authType === 'custom_header' ? 'none' : undefined }}
                    >
                      <Input.Password placeholder="sk-..." visibilityToggle />
                    </Form.Item>

                    {authType === 'azure_ad' && (
                      <>
                        <Form.Item name="azure_tenant_id" label="Tenant ID" rules={[{ required: true, message: '请输入 Azure Tenant ID' }]}>
                          <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
                        </Form.Item>
                        <Form.Item name="azure_client_id" label="Client ID" rules={[{ required: true, message: '请输入 Azure Client ID' }]}>
                          <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
                        </Form.Item>
                      </>
                    )}

                    {authType === 'custom_header' && (
                      <>
                        <Form.Item name="auth_header_name" label="Header 名称" rules={[{ required: true, message: '请输入 Header 名称' }]}>
                          <Input placeholder="如：X-Api-Key、Authorization" />
                        </Form.Item>
                        <Form.Item name="auth_header_value" label="Header 值" rules={[{ required: true, message: '请输入 Header 值' }]}>
                          <Input.Password placeholder="Header 值（加密存储）" visibilityToggle />
                        </Form.Item>
                      </>
                    )}

                    <Form.Item name="rate_limit_rpm" label="每分钟请求数上限（RPM）">
                      <InputNumber min={0} style={{ width: '100%' }} placeholder="留空表示不限制" />
                    </Form.Item>

                    <Form.Item name="rate_limit_tpm" label="每分钟 Token 数上限（TPM）">
                      <InputNumber min={0} style={{ width: '100%' }} placeholder="留空表示不限制" />
                    </Form.Item>

                    <Form.Item name="model_tier" label="模型层级" tooltip="用于 CostRouter 智能路由，根据输入复杂度匹配合适层级的 Provider">
                      <Select
                        options={MODEL_TIER_OPTIONS}
                        placeholder="选择模型层级"
                      />
                    </Form.Item>

                    <Form.Item name="capabilities" label="模型能力" tooltip="声明该 Provider 支持的能力，CostRouter 会根据任务需求过滤">
                      <Select
                        mode="multiple"
                        options={CAPABILITY_OPTIONS}
                        placeholder="选择模型能力标签（可多选）"
                      />
                    </Form.Item>

                    <Form.Item>
                      <Space>
                        <Button type="primary" htmlType="submit" loading={saving}>
                          {isEdit ? '保存' : '注册'}
                        </Button>
                        {isEdit && (
                          <Button
                            icon={<ApiOutlined />}
                            loading={testing}
                            onClick={handleTestConnection}
                          >
                            测试连接
                          </Button>
                        )}
                        <Button onClick={() => navigate('/providers')}>取消</Button>
                      </Space>
                    </Form.Item>
                  </Form>
                </Spin>
              </Card>
            ),
          },
          ...(isEdit ? [{
            key: 'models',
            label: '关联模型',
            children: (
              <Card>
                <div style={{ marginBottom: 16 }}>
                  <Space>
                    <Button type="primary" icon={<PlusOutlined />} onClick={openModelCreate}>
                      添加模型
                    </Button>
                    <Button icon={<SyncOutlined spin={syncing} />} onClick={handleSyncModels} loading={syncing}>
                      从厂商同步
                    </Button>
                  </Space>
                </div>
                <Table<ProviderModelResponse>
                  rowKey="id"
                  columns={modelColumns}
                  dataSource={models}
                  loading={modelsLoading}
                  pagination={{ pageSize: 10 }}
                  scroll={{ x: 900 }}
                  size="small"
                />
              </Card>
            ),
          }] : []),
        ]}
      />

      {/* 模型编辑弹窗 */}
      <Modal
        title={editingModel ? '编辑模型' : '添加模型'}
        open={modelModalOpen}
        onCancel={() => setModelModalOpen(false)}
        onOk={handleModelSave}
        confirmLoading={modelSaving}
        destroyOnHidden
      >
        <Form form={modelForm} layout="vertical">
          <Form.Item
            name="model_name"
            label="模型标识"
            rules={[{ required: true, message: '请输入模型标识' }]}
          >
            <Input placeholder="如 gpt-4o、deepseek-chat" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="可选，用于前端展示" />
          </Form.Item>
          <Form.Item name="context_window" label="上下文窗口">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_output_tokens" label="最大输出 Token">
            <InputNumber min={1} style={{ width: '100%' }} placeholder="留空表示不限" />
          </Form.Item>
          <Form.Item name="prompt_price_per_1k" label="输入价格 / 千 Token（$）">
            <InputNumber min={0} step={0.001} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="completion_price_per_1k" label="输出价格 / 千 Token（$）">
            <InputNumber min={0} step={0.001} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default ProviderEditPage;
