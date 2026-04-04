import { useState } from 'react';
import {
  Card, Button, Space, Modal, Form, Input, Table, Tag, message, Popconfirm,
  Typography, Descriptions,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined,
  BankOutlined, EyeOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { organizationService } from '../../services/organizationService';
import type { OrganizationItem, OrganizationCreateParams } from '../../services/organizationService';

const { Text } = Typography;
const { TextArea } = Input;

const OrganizationPage: React.FC = () => {
  const [createOpen, setCreateOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<OrganizationItem | null>(null);
  const [detailRecord, setDetailRecord] = useState<OrganizationItem | null>(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => organizationService.list({ limit: 200 }),
  });
  const orgs = data?.data ?? [];

  const createMutation = useMutation({
    mutationFn: (params: OrganizationCreateParams) => organizationService.create(params),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['organizations'] }); },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data: d }: { id: string; data: Parameters<typeof organizationService.update>[1] }) =>
      organizationService.update(id, d),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['organizations'] }); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => organizationService.delete(id),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['organizations'] }); },
  });

  const handleCreate = () => {
    setEditRecord(null);
    form.resetFields();
    setCreateOpen(true);
  };

  const handleEdit = (record: OrganizationItem) => {
    setEditRecord(record);
    form.setFieldsValue({
      name: record.name,
      slug: record.slug,
      description: record.description,
      settings: JSON.stringify(record.settings, null, 2),
      quota: JSON.stringify(record.quota, null, 2),
    });
    setCreateOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      message.success('已删除');
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        name: values.name,
        slug: values.slug,
        description: values.description || '',
        settings: values.settings ? JSON.parse(values.settings as string) : {},
        quota: values.quota ? JSON.parse(values.quota as string) : {},
      };
      if (editRecord) {
        await updateMutation.mutateAsync({
          id: editRecord.id,
          data: { name: payload.name, description: payload.description, settings: payload.settings, quota: payload.quota },
        });
        message.success('更新成功');
      } else {
        await createMutation.mutateAsync(payload);
        message.success('创建成功');
      }
      setCreateOpen(false);
    } catch {
      message.error('操作失败');
    }
  };

  const columns: ColumnsType<OrganizationItem> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: 'Slug',
      dataIndex: 'slug',
      key: 'slug',
      render: (slug: string) => <Tag color="blue">{slug}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '启用' : '停用'}</Tag>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: OrganizationItem) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => setDetailRecord(record)}>
            详情
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title={<><BankOutlined /> 组织管理</>}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建组织</Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          columns={columns}
          dataSource={orgs}
          loading={isLoading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
        />
      </Card>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editRecord ? '编辑组织' : '新建组织'}
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleSubmit}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入组织名称' }]}>
            <Input placeholder="CkyClaw Tech" />
          </Form.Item>
          <Form.Item name="slug" label="Slug" rules={[{ required: !editRecord, message: '请输入唯一标识' }]}>
            <Input placeholder="ckyclaw-tech" disabled={!!editRecord} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="组织描述" />
          </Form.Item>
          <Form.Item name="settings" label="设置 (JSON)">
            <TextArea rows={3} placeholder="{}" />
          </Form.Item>
          <Form.Item name="quota" label="配额 (JSON)">
            <TextArea rows={3} placeholder='{"max_agents": 50, "max_tokens_per_day": 1000000}' />
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情弹窗 */}
      <Modal
        title="组织详情"
        open={!!detailRecord}
        onCancel={() => setDetailRecord(null)}
        footer={null}
        width={600}
      >
        {detailRecord && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="ID">{detailRecord.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{detailRecord.name}</Descriptions.Item>
            <Descriptions.Item label="Slug">{detailRecord.slug}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={detailRecord.is_active ? 'green' : 'default'}>
                {detailRecord.is_active ? '启用' : '停用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述">{detailRecord.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="设置">
              <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(detailRecord.settings, null, 2)}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="配额">
              <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(detailRecord.quota, null, 2)}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{new Date(detailRecord.created_at).toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{new Date(detailRecord.updated_at).toLocaleString()}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </>
  );
};

export default OrganizationPage;
