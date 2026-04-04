import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  message,
  Modal,
  Space,
  Switch,
  Tag,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { scheduledTaskService } from '../../services/scheduledTaskService';
import type {
  ScheduledTaskItem,
  ScheduledTaskCreateParams,
  ScheduledTaskUpdateParams,
} from '../../services/scheduledTaskService';

const { TextArea } = Input;

const ScheduledTasksPage: React.FC = () => {
  const [data, setData] = useState<ScheduledTaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const [modalVisible, setModalVisible] = useState(false);
  const [editingTask, setEditingTask] = useState<ScheduledTaskItem | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await scheduledTaskService.list({
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      });
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取定时任务列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openCreate = () => {
    setEditingTask(null);
    form.resetFields();
    setModalVisible(true);
  };

  const openEdit = (record: ScheduledTaskItem) => {
    setEditingTask(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      agent_id: record.agent_id,
      cron_expr: record.cron_expr,
      input_text: record.input_text,
    });
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      if (editingTask) {
        const updateData: ScheduledTaskUpdateParams = {
          name: values.name,
          description: values.description,
          cron_expr: values.cron_expr,
          input_text: values.input_text,
        };
        await scheduledTaskService.update(editingTask.id, updateData);
        message.success('更新成功');
      } else {
        const createData: ScheduledTaskCreateParams = {
          name: values.name,
          description: values.description,
          agent_id: values.agent_id,
          cron_expr: values.cron_expr,
          input_text: values.input_text,
        };
        await scheduledTaskService.create(createData);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchList();
    } catch {
      message.error('操作失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await scheduledTaskService.delete(id);
      message.success('删除成功');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggleEnabled = async (record: ScheduledTaskItem, enabled: boolean) => {
    try {
      await scheduledTaskService.update(record.id, { is_enabled: enabled });
      message.success(enabled ? '已启用' : '已禁用');
      fetchList();
    } catch {
      message.error('操作失败');
    }
  };

  const columns: ProColumns<ScheduledTaskItem>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 160,
      render: (_, record) => <strong>{record.name}</strong>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      width: 180,
      ellipsis: true,
    },
    {
      title: 'Cron 表达式',
      dataIndex: 'cron_expr',
      width: 140,
      render: (_, record) => <Tag>{record.cron_expr}</Tag>,
    },
    {
      title: '上次运行',
      dataIndex: 'last_run_at',
      width: 170,
      render: (_, record) =>
        record.last_run_at ? new Date(record.last_run_at).toLocaleString('zh-CN') : '-',
    },
    {
      title: '下次运行',
      dataIndex: 'next_run_at',
      width: 170,
      render: (_, record) =>
        record.next_run_at ? new Date(record.next_run_at).toLocaleString('zh-CN') : '-',
    },
    {
      title: '启用',
      dataIndex: 'is_enabled',
      width: 80,
      render: (_, record) => (
        <Switch
          checked={record.is_enabled}
          onChange={(checked) => handleToggleEnabled(record, checked)}
          size="small"
        />
      ),
    },
    {
      title: '操作',
      width: 140,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确认删除此定时任务？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title={
          <Space>
            <ClockCircleOutlined />
            定时任务管理
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建任务
          </Button>
        }
      >
        <ProTable<ScheduledTaskItem>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          search={false}
          toolBarRender={false}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>

      <Modal
        title={editingTask ? '编辑定时任务' : '新建定时任务'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="任务名称"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="如：每日数据分析" />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input placeholder="任务用途描述" />
          </Form.Item>

          {!editingTask && (
            <Form.Item
              name="agent_id"
              label="关联 Agent ID"
              rules={[{ required: true, message: '请输入 Agent ID' }]}
            >
              <Input placeholder="Agent UUID" />
            </Form.Item>
          )}

          <Form.Item
            name="cron_expr"
            label="Cron 表达式"
            rules={[{ required: true, message: '请输入 Cron 表达式' }]}
            extra="示例：0 9 * * *（每天 9 点）、*/5 * * * *（每 5 分钟）"
          >
            <Input placeholder="0 9 * * *" />
          </Form.Item>

          <Form.Item name="input_text" label="Agent 输入文本">
            <TextArea rows={3} placeholder="发送给 Agent 的文本消息" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default ScheduledTasksPage;
