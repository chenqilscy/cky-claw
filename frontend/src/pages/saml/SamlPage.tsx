import { useCallback, useEffect, useState } from 'react';
import { App, Button, Form, Input, Modal, Popconfirm, Space, Switch, Table, Tag, Typography } from 'antd';
import { CopyOutlined, DeleteOutlined, EditOutlined, PlusOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { PageContainer } from '../../components/PageContainer';
import { samlService, type SamlIdpConfig, type SamlIdpConfigCreate, type SamlSpMetadata } from '../../services/samlService';

const { TextArea } = Input;
const { Paragraph, Text } = Typography;

const SamlPage: React.FC = () => {
  const { message, modal } = App.useApp();
  const [configs, setConfigs] = useState<SamlIdpConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [spMetadata, setSpMetadata] = useState<SamlSpMetadata | null>(null);
  const [form] = Form.useForm();

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    try {
      const list = await samlService.listIdpConfigs();
      setConfigs(list);
    } catch {
      message.error('加载 SAML IdP 配置失败');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchConfigs();
    samlService.getSpMetadata()
      .then(setSpMetadata)
      .catch(() => { /* SP 未配置时静默 */ });
  }, [fetchConfigs]);

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      attribute_mapping_email: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
      attribute_mapping_username: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name',
      is_enabled: true,
      is_default: false,
    });
    setModalOpen(true);
  };

  const handleEdit = (record: SamlIdpConfig) => {
    setEditingId(record.id);
    form.setFieldsValue({
      ...record,
      attribute_mapping_email: record.attribute_mapping?.email ?? '',
      attribute_mapping_username: record.attribute_mapping?.username ?? '',
      attribute_mapping_display_name: record.attribute_mapping?.display_name ?? '',
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await samlService.deleteIdpConfig(id);
      message.success('删除成功');
      fetchConfigs();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: SamlIdpConfigCreate = {
        name: values.name,
        entity_id: values.entity_id,
        sso_url: values.sso_url,
        slo_url: values.slo_url || '',
        x509_cert: values.x509_cert,
        metadata_xml: values.metadata_xml || undefined,
        attribute_mapping: {
          ...(values.attribute_mapping_email ? { email: values.attribute_mapping_email } : {}),
          ...(values.attribute_mapping_username ? { username: values.attribute_mapping_username } : {}),
          ...(values.attribute_mapping_display_name ? { display_name: values.attribute_mapping_display_name } : {}),
        },
        is_enabled: values.is_enabled ?? true,
        is_default: values.is_default ?? false,
      };

      if (editingId) {
        await samlService.updateIdpConfig(editingId, payload);
        message.success('更新成功');
      } else {
        await samlService.createIdpConfig(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchConfigs();
    } catch {
      /* form validation error */
    }
  };

  const handleToggle = async (record: SamlIdpConfig, enabled: boolean) => {
    try {
      await samlService.updateIdpConfig(record.id, { is_enabled: enabled });
      message.success(enabled ? '已启用' : '已禁用');
      fetchConfigs();
    } catch {
      message.error('操作失败');
    }
  };

  const showSpMetadata = () => {
    if (!spMetadata) {
      message.warning('SP 未配置，请设置 SAML_SP_ENTITY_ID 和 SAML_SP_ACS_URL 环境变量');
      return;
    }
    modal.info({
      title: 'SP 元数据',
      width: 720,
      content: (
        <div>
          <Paragraph><Text strong>Entity ID:</Text> {spMetadata.entity_id}</Paragraph>
          <Paragraph><Text strong>ACS URL:</Text> {spMetadata.acs_url}</Paragraph>
          <Paragraph><Text strong>SLS URL:</Text> {spMetadata.sls_url || '未配置'}</Paragraph>
          <Paragraph>
            <Text strong>元数据 XML:</Text>
            <Button
              size="small"
              icon={<CopyOutlined />}
              style={{ marginLeft: 8 }}
              onClick={() => {
                navigator.clipboard.writeText(spMetadata.metadata_xml);
                message.success('已复制');
              }}
            >
              复制
            </Button>
          </Paragraph>
          <TextArea value={spMetadata.metadata_xml} rows={10} readOnly />
        </div>
      ),
    });
  };

  const columns: ColumnsType<SamlIdpConfig> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
    },
    {
      title: 'Entity ID',
      dataIndex: 'entity_id',
      key: 'entity_id',
      ellipsis: true,
    },
    {
      title: 'SSO URL',
      dataIndex: 'sso_url',
      key: 'sso_url',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      width: 100,
      render: (enabled: boolean, record) => (
        <Switch
          checked={enabled}
          onChange={(val) => handleToggle(record, val)}
          checkedChildren="启用"
          unCheckedChildren="禁用"
        />
      ),
    },
    {
      title: '默认',
      dataIndex: 'is_default',
      key: 'is_default',
      width: 80,
      render: (val: boolean) =>
        val ? <Tag color="blue">默认</Tag> : <Tag>否</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确认删除此 IdP 配置？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer title="SAML SSO 管理" description="配置 SAML 2.0 单点登录身份提供商">
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          添加 IdP
        </Button>
        <Button icon={<SafetyCertificateOutlined />} onClick={showSpMetadata}>
          查看 SP 元数据
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={configs}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="middle"
      />

      <Modal
        title={editingId ? '编辑 IdP 配置' : '添加 IdP 配置'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="IdP 名称" rules={[{ required: true, message: '请输入 IdP 名称' }]}>
            <Input placeholder="如：企业 Azure AD" />
          </Form.Item>
          <Form.Item name="entity_id" label="Entity ID" rules={[{ required: true, message: '请输入 Entity ID' }]}>
            <Input placeholder="IdP 的 Entity ID (Issuer)" />
          </Form.Item>
          <Form.Item name="sso_url" label="SSO URL" rules={[{ required: true, message: '请输入 SSO URL' }]}>
            <Input placeholder="IdP 单点登录 URL" />
          </Form.Item>
          <Form.Item name="slo_url" label="SLO URL">
            <Input placeholder="IdP 单点登出 URL（可选）" />
          </Form.Item>
          <Form.Item
            name="x509_cert"
            label="X.509 证书"
            rules={[{ required: true, message: '请输入 X.509 证书' }]}
          >
            <TextArea rows={4} placeholder="IdP 签名证书（PEM 格式，不含 BEGIN/END 头尾）" />
          </Form.Item>
          <Form.Item name="metadata_xml" label="元数据 XML">
            <TextArea rows={4} placeholder="完整的 IdP 元数据 XML（可选，方便备份）" />
          </Form.Item>
          <Form.Item name="attribute_mapping_email" label="Email 属性名">
            <Input placeholder="映射 SAML Attribute → email" />
          </Form.Item>
          <Form.Item name="attribute_mapping_username" label="Username 属性名">
            <Input placeholder="映射 SAML Attribute → username" />
          </Form.Item>
          <Form.Item name="attribute_mapping_display_name" label="Display Name 属性名">
            <Input placeholder="映射 SAML Attribute → display_name" />
          </Form.Item>
          <Space>
            <Form.Item name="is_enabled" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" defaultChecked />
            </Form.Item>
            <Form.Item name="is_default" valuePropName="checked">
              <Switch checkedChildren="默认" unCheckedChildren="非默认" />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default SamlPage;
