import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, App, Spin } from 'antd';
import { ArrowLeftOutlined, ApiOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { providerService, PROVIDER_TYPES, AUTH_TYPES, PROVIDER_BASE_URLS, PROVIDER_TYPE_LABELS } from '../../services/providerService';
import type { ProviderCreateRequest, ProviderUpdateRequest } from '../../services/providerService';

const ProviderEditPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

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
          form.setFieldsValue({
            name: provider.name,
            provider_type: provider.provider_type,
            base_url: provider.base_url,
            auth_type: provider.auth_type,
            rate_limit_rpm: provider.rate_limit_rpm,
            rate_limit_tpm: provider.rate_limit_tpm,
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
        const payload: ProviderUpdateRequest = {
          name: values.name as string,
          provider_type: values.provider_type as string,
          base_url: values.base_url as string,
          auth_type: values.auth_type as string,
          rate_limit_rpm: values.rate_limit_rpm as number | null ?? null,
          rate_limit_tpm: values.rate_limit_tpm as number | null ?? null,
        };
        if (values.api_key) {
          payload.api_key = values.api_key as string;
        }
        await providerService.update(id, payload);
        message.success('更新成功');
      } else {
        const payload: ProviderCreateRequest = {
          name: values.name as string,
          provider_type: values.provider_type as string,
          base_url: values.base_url as string,
          api_key: values.api_key as string,
          auth_type: (values.auth_type as string) || 'api_key',
          rate_limit_rpm: values.rate_limit_rpm as number | null ?? null,
          rate_limit_tpm: values.rate_limit_tpm as number | null ?? null,
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

  return (
    <PageContainer
      title={isEdit ? '编辑 Provider' : '注册新 Provider'}
      icon={<ApiOutlined />}
      description="配置 Provider 类型、认证方式与模型列表"
      extra={
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/providers')}>
          返回列表
        </Button>
      }
    >
      <Card title={isEdit ? '编辑 Provider' : '注册新 Provider'}>
        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            onFinish={onFinish}
            initialValues={{ auth_type: 'api_key', provider_type: 'openai', base_url: PROVIDER_BASE_URLS.openai }}
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

            <Form.Item
              name="api_key"
              label={isEdit ? 'API Key（留空则不更新）' : 'API Key'}
              rules={isEdit ? [] : [{ required: true, message: '请输入 API Key' }]}
            >
              <Input.Password placeholder="sk-..." visibilityToggle />
            </Form.Item>

            <Form.Item name="auth_type" label="认证方式">
              <Select
                options={AUTH_TYPES.map((t) => ({ label: t, value: t }))}
              />
            </Form.Item>

            <Form.Item name="rate_limit_rpm" label="每分钟请求数上限（RPM）">
              <InputNumber min={0} style={{ width: '100%' }} placeholder="留空表示不限制" />
            </Form.Item>

            <Form.Item name="rate_limit_tpm" label="每分钟 Token 数上限（TPM）">
              <InputNumber min={0} style={{ width: '100%' }} placeholder="留空表示不限制" />
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
    </PageContainer>
  );
};

export default ProviderEditPage;
