import { useState, useEffect } from 'react';
import { Button, App, Tag, Popconfirm, Space, Modal, Form, Input, ColorPicker, InputNumber, Switch } from 'antd';
import { PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined, DeploymentUnitOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { useNavigate } from 'react-router-dom';
import { environmentService } from '../../services/environmentService';
import type { Environment, EnvironmentCreateInput, EnvironmentUpdateInput } from '../../services/environmentService';

const EnvironmentListPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Environment[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Environment | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await environmentService.list();
      setData(res.data);
    } catch {
      message.error('获取环境列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async (envName: string) => {
    try {
      await environmentService.delete(envName);
      message.success('删除成功');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const openCreate = () => {
    setEditTarget(null);
    form.resetFields();
    form.setFieldsValue({ color: '#1890ff', sort_order: 0, is_protected: false });
    setModalOpen(true);
  };

  const openEdit = (record: Environment) => {
    setEditTarget(record);
    form.setFieldsValue({
      name: record.name,
      display_name: record.display_name,
      description: record.description,
      color: record.color,
      sort_order: record.sort_order,
      is_protected: record.is_protected,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const color = typeof values.color === 'string' ? values.color : values.color?.toHexString?.() ?? '#1890ff';
      if (editTarget) {
        const payload: EnvironmentUpdateInput = {
          display_name: values.display_name,
          description: values.description,
          color,
          sort_order: values.sort_order,
          is_protected: values.is_protected,
        };
        await environmentService.update(editTarget.name, payload);
        message.success('更新成功');
      } else {
        const payload: EnvironmentCreateInput = {
          name: values.name,
          display_name: values.display_name,
          description: values.description,
          color,
          sort_order: values.sort_order,
          is_protected: values.is_protected,
        };
        await environmentService.create(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch {
      message.error('提交失败');
    }
  };

  const columns: ProColumns<Environment>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 120,
      render: (_, record) => (
        <a onClick={() => navigate(`/environments/${record.name}`)}>{record.name}</a>
      ),
    },
    {
      title: '显示名称',
      dataIndex: 'display_name',
      width: 120,
      render: (_, record) => (
        <Tag color={record.color}>{record.display_name}</Tag>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
    },
    {
      title: '排序',
      dataIndex: 'sort_order',
      width: 80,
    },
    {
      title: '受保护',
      dataIndex: 'is_protected',
      width: 80,
      render: (_, record) => record.is_protected ? <Tag color="red">是</Tag> : <Tag>否</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (_, record) => new Date(record.created_at).toLocaleString(),
    },
    {
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title={record.is_protected ? '该环境受保护，确认删除？' : '确认删除该环境？'}
            onConfirm={() => handleDelete(record.name)}
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
    <PageContainer
      title="环境管理"
      icon={<DeploymentUnitOutlined />}
      description="Dev/Staging/Prod 多环境隔离管理"
    >
      <ProTable<Environment>
        headerTitle="环境管理"
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        search={false}
        pagination={false}
        options={false}
        toolBarRender={() => [
          <Button key="reload" icon={<ReloadOutlined />} onClick={fetchData}>
            刷新
          </Button>,
          <Button key="create" type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建环境
          </Button>,
        ]}
      />

      <Modal
        title={editTarget ? '编辑环境' : '新建环境'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          {!editTarget && (
            <Form.Item name="name" label="环境标识" rules={[{ required: true, message: '请输入环境标识' }]}>
              <Input placeholder="例如: dev, staging, prod" />
            </Form.Item>
          )}
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true, message: '请输入显示名称' }]}>
            <Input placeholder="例如: 开发, 预发, 生产" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="color" label="颜色">
            <ColorPicker />
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="is_protected" label="受保护" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default EnvironmentListPage;
