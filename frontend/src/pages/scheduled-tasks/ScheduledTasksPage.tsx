import { useState } from 'react';
import { Form, Input, Switch, Tag, Button, Space, Popconfirm, App } from 'antd';
import { ClockCircleOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import {
  useScheduledTaskList,
  useCreateScheduledTask,
  useUpdateScheduledTask,
  useDeleteScheduledTask,
} from '../../hooks/useScheduledTaskQueries';
import type {
  ScheduledTaskItem,
  ScheduledTaskCreateParams,
  ScheduledTaskUpdateParams,
} from '../../services/scheduledTaskService';
import { CrudTable } from '../../components';
import type { CrudTableActions } from '../../components';

const { TextArea } = Input;

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<ScheduledTaskItem>,
  handleToggleEnabled: (record: ScheduledTaskItem, enabled: boolean) => void,
): ProColumns<ScheduledTaskItem>[] => [
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
        <Button type="link" size="small" icon={<EditOutlined />} onClick={() => actions.openEdit(record)}>
          编辑
        </Button>
        <Popconfirm title="确认删除此定时任务？" onConfirm={() => actions.handleDelete(record.id)}>
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      </Space>
    ),
  },
];

/* ---- 表单渲染 ---- */

const renderForm = (_form: FormInstance, editing: ScheduledTaskItem | null) => (
  <>
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

    {!editing && (
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
    >
      <Input placeholder="如：0 0 * * *（每日 0 点）" />
    </Form.Item>

    <Form.Item name="input_text" label="输入文本">
      <TextArea rows={3} placeholder="可选。传给 Agent 的输入内容" />
    </Form.Item>
  </>
);

/* ---- 页面组件 ---- */

const ScheduledTasksPage: React.FC = () => {
  const { message } = App.useApp();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const queryResult = useScheduledTaskList({
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const createMutation = useCreateScheduledTask();
  const updateMutation = useUpdateScheduledTask();
  const deleteMutation = useDeleteScheduledTask();

  const handleToggleEnabled = async (record: ScheduledTaskItem, enabled: boolean) => {
    try {
      await updateMutation.mutateAsync({ id: record.id, data: { is_enabled: enabled } });
      message.success(enabled ? '已启用' : '已禁用');
    } catch {
      message.error('操作失败');
    }
  };

  return (
    <CrudTable<
      ScheduledTaskItem,
      ScheduledTaskCreateParams,
      { id: string; data: ScheduledTaskUpdateParams }
    >
      title="定时任务管理"
      icon={<ClockCircleOutlined />}
      queryResult={queryResult}
      createMutation={createMutation}
      updateMutation={updateMutation}
      deleteMutation={deleteMutation}
      createButtonText="新建任务"
      modalWidth={600}
      modalTitle={(editing) => (editing ? '编辑定时任务' : '新建定时任务')}
      pagination={pagination}
      onPaginationChange={(page, pageSize) => setPagination({ current: page, pageSize })}
      columns={(actions) => buildColumns(actions, handleToggleEnabled)}
      renderForm={renderForm}
      toFormValues={(record) => ({
        name: record.name,
        description: record.description,
        agent_id: record.agent_id,
        cron_expr: record.cron_expr,
        input_text: record.input_text,
      })}
      toCreatePayload={(values) => ({
        name: values.name as string,
        description: values.description as string,
        agent_id: values.agent_id as string,
        cron_expr: values.cron_expr as string,
        input_text: values.input_text as string,
      })}
      toUpdatePayload={(values, record) => ({
        id: record.id,
        data: {
          name: values.name as string,
          description: values.description as string,
          cron_expr: values.cron_expr as string,
          input_text: values.input_text as string,
        },
      })}
    />
  );
};

export default ScheduledTasksPage;
