import { useState } from 'react';
import { Card, Modal, Form, Input, Tag, App, Badge, Tooltip, Table, Typography, Tabs } from 'antd';
import { EyeOutlined, CheckCircleOutlined, BranchesOutlined, NodeIndexOutlined, PartitionOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { WorkflowItem, StepSchema, EdgeSchema, WorkflowCreateParams, WorkflowUpdateParams } from '../../services/workflowService';
import { useWorkflowList, useCreateWorkflow, useUpdateWorkflow, useDeleteWorkflow, useValidateWorkflow } from '../../hooks/useWorkflowQueries';
import { CrudTable, PageContainer, buildActionColumn } from '../../components';
import type { CrudTableActions } from '../../components';
import WorkflowGraphView from './WorkflowGraphView';

const { TextArea } = Input;
const { Text } = Typography;

const stepTypeLabel: Record<string, string> = {
  agent: 'Agent 步骤',
  parallel: '并行步骤',
  conditional: '条件分支',
  loop: '循环步骤',
};

import { STEP_TYPE_TAG_COLORS as stepTypeColor } from '../../constants/colors';

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<WorkflowItem>,
  navigate: ReturnType<typeof useNavigate>,
  handlePreview: (r: WorkflowItem) => void,
): ProColumns<WorkflowItem>[] => [
  {
    title: '名称',
    dataIndex: 'name',
    render: (_, record) => <strong>{record.name}</strong>,
  },
  {
    title: '描述',
    dataIndex: 'description',
    ellipsis: true,
  },
  {
    title: '步骤数',
    width: 100,
    render: (_, record) => (
      <Badge count={record.steps.length} showZero color="blue" />
    ),
  },
  {
    title: '边数',
    width: 100,
    render: (_, record) => (
      <Badge count={record.edges.length} showZero color="green" />
    ),
  },
  {
    title: '步骤类型',
    width: 200,
    render: (_, record) => {
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
    width: 100,
    render: (_, record) => record.timeout ?? '-',
  },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    width: 180,
    render: (_, record) => new Date(record.updated_at).toLocaleString(),
  },
  buildActionColumn<WorkflowItem>(actions, {
    deleteConfirmTitle: '确认删除工作流',
    extraItems: (record) => [
      {
        key: 'preview',
        label: '预览',
        icon: <EyeOutlined />,
        onClick: () => handlePreview(record),
      },
      {
        key: 'visual',
        label: '可视化编辑',
        icon: <PartitionOutlined />,
        onClick: () => navigate(`/workflow-editor?id=${record.id}`),
      },
    ],
  }),
];

/* ---- 步骤预览表格列 ---- */

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

/* ---- 页面组件 ---- */

const WorkflowPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewRecord, setPreviewRecord] = useState<WorkflowItem | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const queryResult = useWorkflowList({
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const createMutation = useCreateWorkflow();
  const updateMutation = useUpdateWorkflow();
  const deleteMutation = useDeleteWorkflow();
  const validateMutation = useValidateWorkflow();

  const handlePreview = (record: WorkflowItem) => {
    setPreviewRecord(record);
    setPreviewOpen(true);
  };

  /** 表单内验证按钮调用 */
  const handleValidateFromForm = async (form: FormInstance) => {
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

  const renderForm = (form: FormInstance, editing: WorkflowItem | null) => (
    <>
      <Form.Item name="name" label="名称" rules={[{ required: true, pattern: /^[a-z0-9][a-z0-9-]*$/, message: '小写字母/数字/连字符' }]}>
        <Input placeholder="my-workflow" disabled={!!editing} />
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
      <Button icon={<CheckCircleOutlined />} onClick={() => void handleValidateFromForm(form)} style={{ marginBottom: 8 }}>
        验证
      </Button>
    </>
  );

  return (
    <PageContainer
      title="工作流管理"
      icon={<BranchesOutlined />}
      description="管理工作流编排，支持可视化预览"
    >
      <CrudTable<
        WorkflowItem,
        WorkflowCreateParams,
        { id: string; data: WorkflowUpdateParams }
      >
        hideTitle
        title="工作流管理"
        queryResult={queryResult}
        createMutation={createMutation}
        updateMutation={updateMutation}
        deleteMutation={deleteMutation}
        createButtonText="新建工作流"
        modalTitle={(editing) => (editing ? '编辑工作流' : '新建工作流')}
        modalWidth={720}
        columns={(actions) => buildColumns(actions, navigate, handlePreview)}
        renderForm={renderForm}
        toFormValues={(record) => ({
          name: record.name,
          description: record.description,
          steps_json: JSON.stringify(record.steps, null, 2),
          edges_json: JSON.stringify(record.edges, null, 2),
          output_keys: record.output_keys?.join(', ') ?? '',
          timeout: record.timeout,
        })}
        toCreatePayload={(values) => {
          const steps: StepSchema[] = JSON.parse(values.steps_json as string);
          const edges: EdgeSchema[] = JSON.parse(values.edges_json as string);
          return {
            name: values.name as string,
            steps,
            edges,
            description: values.description as string,
            output_keys: values.output_keys ? (values.output_keys as string).split(',').map((s: string) => s.trim()).filter(Boolean) : undefined,
            timeout: values.timeout ? Number(values.timeout) : undefined,
          };
        }}
        toUpdatePayload={(values, record) => {
          const steps: StepSchema[] = JSON.parse(values.steps_json as string);
          const edges: EdgeSchema[] = JSON.parse(values.edges_json as string);
          return {
            id: record.id,
            data: {
              name: values.name as string,
              steps,
              edges,
              description: values.description as string,
              output_keys: values.output_keys ? (values.output_keys as string).split(',').map((s: string) => s.trim()).filter(Boolean) : undefined,
              timeout: values.timeout ? Number(values.timeout) : undefined,
            },
          };
        }}
        extraToolbar={
          <Button icon={<PartitionOutlined />} onClick={() => navigate('/workflow-editor')}>可视化编排</Button>
        }
        pagination={pagination}
        onPaginationChange={(current, pageSize) => setPagination({ current, pageSize })}
        showRefresh
      />

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
    </PageContainer>
  );
};

export default WorkflowPage;
