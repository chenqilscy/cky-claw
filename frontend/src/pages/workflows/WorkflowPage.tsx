import { useState } from 'react';
import { Card, Button, Space, Modal, Form, Input, Tag, message, Popconfirm, Empty, Typography, Table, Badge, Tooltip, Tabs } from 'antd';
import { PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined, EyeOutlined, CheckCircleOutlined, BranchesOutlined, NodeIndexOutlined, PartitionOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { ColumnsType } from 'antd/es/table';
import type { WorkflowItem, StepSchema, EdgeSchema, WorkflowCreateParams } from '../../services/workflowService';
import { useWorkflowList, useCreateWorkflow, useUpdateWorkflow, useDeleteWorkflow, useValidateWorkflow } from '../../hooks/useWorkflowQueries';
import WorkflowGraphView from './WorkflowGraphView';

const { TextArea } = Input;
const { Text } = Typography;

const stepTypeLabel: Record<string, string> = {
  agent: 'Agent 步骤',
  parallel: '并行步骤',
  conditional: '条件分支',
  loop: '循环步骤',
};

const stepTypeColor: Record<string, string> = {
  agent: 'blue',
  parallel: 'green',
  conditional: 'orange',
  loop: 'purple',
};

const WorkflowPage: React.FC = () => {
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<WorkflowItem | null>(null);
  const [previewRecord, setPreviewRecord] = useState<WorkflowItem | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [form] = Form.useForm();

  const { data: listData, isLoading: loading, refetch: fetchData } = useWorkflowList({
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });
  const workflows = listData?.data ?? [];
  const total = listData?.total ?? 0;

  const createMutation = useCreateWorkflow();
  const updateMutation = useUpdateWorkflow();
  const deleteMutation = useDeleteWorkflow();
  const validateMutation = useValidateWorkflow();

  const handleCreate = () => {
    setEditRecord(null);
    form.resetFields();
    form.setFieldsValue({ steps_json: '[]', edges_json: '[]' });
    setCreateOpen(true);
  };

  const handleEdit = (record: WorkflowItem) => {
    setEditRecord(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      steps_json: JSON.stringify(record.steps, null, 2),
      edges_json: JSON.stringify(record.edges, null, 2),
      output_keys: record.output_keys?.join(', ') ?? '',
      timeout: record.timeout,
    });
    setCreateOpen(true);
  };

  const handlePreview = (record: WorkflowItem) => {
    setPreviewRecord(record);
    setPreviewOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      message.success('已删除');
    } catch {
      message.error('删除失败');
    }
  };

  const handleValidate = async () => {
    try {
      const values = await form.validateFields();
      const steps: StepSchema[] = JSON.parse(values.steps_json);
      const edges: EdgeSchema[] = JSON.parse(values.edges_json);
      const params: WorkflowCreateParams = {
        name: values.name,
        steps,
        edges,
        description: values.description,
        output_keys: values.output_keys ? values.output_keys.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined,
        timeout: values.timeout ? Number(values.timeout) : undefined,
      };
      const res = await validateMutation.mutateAsync(params);
      if (res.valid) {
        message.success('验证通过');
      } else {
        Modal.warning({
          title: '验证不通过',
          content: (
            <ul>
              {res.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}
            </ul>
          ),
        });
      }
    } catch {
      message.error('请检查 JSON 格式');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const steps: StepSchema[] = JSON.parse(values.steps_json);
      const edges: EdgeSchema[] = JSON.parse(values.edges_json);
      const params: WorkflowCreateParams = {
        name: values.name,
        steps,
        edges,
        description: values.description,
        output_keys: values.output_keys ? values.output_keys.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined,
        timeout: values.timeout ? Number(values.timeout) : undefined,
      };
      if (editRecord) {
        await updateMutation.mutateAsync({ id: editRecord.id, data: params });
        message.success('更新成功');
      } else {
        await createMutation.mutateAsync(params);
        message.success('创建成功');
      }
      setCreateOpen(false);
    } catch {
      message.error('操作失败，请检查输入');
    }
  };

  const columns: ColumnsType<WorkflowItem> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '步骤数',
      key: 'steps',
      width: 100,
      render: (_: unknown, record: WorkflowItem) => (
        <Badge count={record.steps.length} showZero color="blue" />
      ),
    },
    {
      title: '边数',
      key: 'edges',
      width: 100,
      render: (_: unknown, record: WorkflowItem) => (
        <Badge count={record.edges.length} showZero color="green" />
      ),
    },
    {
      title: '步骤类型',
      key: 'types',
      width: 200,
      render: (_: unknown, record: WorkflowItem) => {
        const types = [...new Set(record.steps.map(s => s.type))];
        return (
          <Space size={4} wrap>
            {types.map(t => (
              <Tag key={t} color={stepTypeColor[t]}>{stepTypeLabel[t] ?? t}</Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: '超时(s)',
      dataIndex: 'timeout',
      key: 'timeout',
      width: 100,
      render: (v: number | null) => v ?? '-',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: WorkflowItem) => (
        <Space>
          <Tooltip title="预览">
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handlePreview(record)} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Tooltip title="可视化编辑">
            <Button type="link" size="small" icon={<PartitionOutlined />} onClick={() => navigate(`/workflow-editor?id=${record.id}`)} />
          </Tooltip>
          <Popconfirm title="确认删除此工作流？" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Tooltip title="删除">
              <Button type="link" danger size="small" icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const stepColumns: ColumnsType<StepSchema> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 120,
      render: (t: string) => <Tag color={stepTypeColor[t]}>{stepTypeLabel[t] ?? t}</Tag>,
    },
    { title: 'Agent', dataIndex: 'agent_name', key: 'agent_name', render: (v: string) => v ?? '-' },
    { title: '超时', dataIndex: 'timeout', key: 'timeout', width: 80, render: (v: number | undefined) => v ?? '-' },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={<Space><BranchesOutlined />工作流管理</Space>}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchData()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建工作流</Button>
            <Button icon={<PartitionOutlined />} onClick={() => navigate('/workflow-editor')}>可视化编排</Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          columns={columns}
          dataSource={workflows}
          loading={loading}
          locale={{ emptyText: <Empty description="暂无工作流" /> }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, s) => { setPage(p); setPageSize(s); },
          }}
        />
      </Card>

      {/* 创建/编辑 Modal */}
      <Modal
        title={editRecord ? '编辑工作流' : '新建工作流'}
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        width={720}
        footer={
          <Space>
            <Button onClick={() => setCreateOpen(false)}>取消</Button>
            <Button icon={<CheckCircleOutlined />} onClick={handleValidate}>验证</Button>
            <Button type="primary" onClick={handleSubmit}>
              {editRecord ? '保存' : '创建'}
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, pattern: /^[a-z0-9][a-z0-9-]*$/, message: '小写字母/数字/连字符' }]}>
            <Input placeholder="my-workflow" disabled={!!editRecord} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="工作流描述" />
          </Form.Item>
          <Form.Item name="steps_json" label="步骤 (JSON)" rules={[{ required: true }]}>
            <TextArea rows={8} placeholder='[{"id":"step1","name":"分析","type":"agent","agent_name":"researcher"}]' style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="edges_json" label="边 (JSON)" rules={[{ required: true }]}>
            <TextArea rows={4} placeholder='[{"source_step_id":"step1","target_step_id":"step2"}]' style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="output_keys" label="输出键 (逗号分隔)">
            <Input placeholder="result, summary" />
          </Form.Item>
          <Form.Item name="timeout" label="超时 (秒)">
            <Input type="number" placeholder="300" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 预览 Modal */}
      <Modal
        title={`工作流详情 — ${previewRecord?.name ?? ''}`}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        width={800}
        footer={<Button onClick={() => setPreviewOpen(false)}>关闭</Button>}
      >
        {previewRecord && (
          <Tabs defaultActiveKey="graph" items={[
            {
              key: 'graph',
              label: <span><NodeIndexOutlined /> 流程图</span>,
              children: (
                <WorkflowGraphView steps={previewRecord.steps} edges={previewRecord.edges} />
              ),
            },
            {
              key: 'info',
              label: '基本信息',
              children: (
                <Card size="small">
                  <p><Text strong>名称：</Text>{previewRecord.name}</p>
                  <p><Text strong>描述：</Text>{previewRecord.description ?? '无'}</p>
                  <p><Text strong>超时：</Text>{previewRecord.timeout ?? '无'} 秒</p>
                  {previewRecord.output_keys && previewRecord.output_keys.length > 0 && (
                    <p><Text strong>输出键：</Text>{previewRecord.output_keys.map(k => <Tag key={k}>{k}</Tag>)}</p>
                  )}
                  {previewRecord.guardrail_names && previewRecord.guardrail_names.length > 0 && (
                    <p><Text strong>护栏：</Text>{previewRecord.guardrail_names.map(g => <Tag key={g} color="red">{g}</Tag>)}</p>
                  )}
                </Card>
              ),
            },
            {
              key: 'steps',
              label: `步骤 (${previewRecord.steps.length})`,
              children: (
                <Table
                  rowKey="id"
                  columns={stepColumns}
                  dataSource={previewRecord.steps}
                  pagination={false}
                  size="small"
                />
              ),
            },
            {
              key: 'edges',
              label: `边 (${previewRecord.edges.length})`,
              children: previewRecord.edges.length > 0 ? (
                <Space wrap>
                  {previewRecord.edges.map((e, i) => (
                    <Tag key={i} color="cyan">{e.source_step_id} → {e.target_step_id}{e.condition ? ` [${e.condition}]` : ''}</Tag>
                  ))}
                </Space>
              ) : (
                <Text type="secondary">无边定义</Text>
              ),
            },
          ]} />
        )}
      </Modal>
    </div>
  );
};

export default WorkflowPage;
