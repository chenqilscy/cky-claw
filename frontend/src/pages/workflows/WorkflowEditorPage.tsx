/**
 * WorkflowEditorPage — ReactFlow 拖拽式 DAG 编排画布。
 *
 * 支持：拖拽添加步骤节点、连线、节点属性编辑、保存/验证、加载已有 Workflow。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
  Position,
  MarkerType,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button, Card, Drawer, Form, Input, InputNumber, App, Select, Space, Tag, Typography } from 'antd';
import { SaveOutlined, CheckCircleOutlined, ArrowLeftOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { useWorkflow, useCreateWorkflow, useUpdateWorkflow, useValidateWorkflow } from '../../hooks/useWorkflowQueries';
import type { StepSchema, EdgeSchema, WorkflowCreateParams } from '../../services/workflowService';

const { Text } = Typography;

const STEP_TYPES = [
  { label: 'Agent 步骤', value: 'agent', color: '#1890ff' },
  { label: '并行步骤', value: 'parallel', color: '#52c41a' },
  { label: '条件分支', value: 'conditional', color: '#fa8c16' },
  { label: '循环步骤', value: 'loop', color: '#722ed1' },
] as const;

const NODE_COLORS: Record<string, string> = {
  agent: '#1890ff',
  parallel: '#52c41a',
  conditional: '#fa8c16',
  loop: '#722ed1',
};

let nodeIdCounter = 1;
function nextNodeId(): string {
  return `step_${nodeIdCounter++}`;
}

function stepToNode(step: StepSchema, index: number): Node {
  const COLS = 3;
  const X_GAP = 280;
  const Y_GAP = 140;
  return {
    id: step.id,
    position: { x: (index % COLS) * X_GAP + 60, y: Math.floor(index / COLS) * Y_GAP + 60 },
    data: {
      label: step.name,
      stepType: step.type,
      agentName: step.agent_name ?? '',
      promptTemplate: step.prompt_template ?? '',
      maxTurns: step.max_turns,
      timeout: step.timeout,
    },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    style: {
      border: `2px solid ${NODE_COLORS[step.type] ?? '#d9d9d9'}`,
      borderRadius: 8,
      padding: '8px 16px',
      background: '#fff',
      minWidth: 160,
    },
  };
}

function edgeToFlow(e: EdgeSchema, index: number): Edge {
  return {
    id: e.id || `edge-${index}`,
    source: e.source_step_id,
    target: e.target_step_id,
    label: e.condition ?? undefined,
    animated: !!e.condition,
    markerEnd: { type: MarkerType.ArrowClosed },
  };
}

function nodesToSteps(nodes: Node[]): StepSchema[] {
  return nodes.map((n) => ({
    id: n.id,
    name: String(n.data.label ?? n.id),
    type: (n.data.stepType as StepSchema['type']) ?? 'agent',
    agent_name: n.data.agentName ? String(n.data.agentName) : undefined,
    prompt_template: n.data.promptTemplate ? String(n.data.promptTemplate) : undefined,
    max_turns: n.data.maxTurns as number | undefined,
    timeout: n.data.timeout as number | undefined,
  }));
}

function flowToEdges(edges: Edge[]): EdgeSchema[] {
  return edges.map((e) => ({
    id: e.id,
    source_step_id: e.source,
    target_step_id: e.target,
    condition: typeof e.label === 'string' ? e.label : undefined,
  }));
}

const WorkflowEditorPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editId = searchParams.get('id');

  const { data: existingWorkflow } = useWorkflow(editId ?? undefined);
  const createMutation = useCreateWorkflow();
  const updateMutation = useUpdateWorkflow();
  const validateMutation = useValidateWorkflow();

  // 初始化节点和边
  const initialNodes = useMemo(() => {
    if (existingWorkflow) {
      nodeIdCounter = existingWorkflow.steps.length + 1;
      return existingWorkflow.steps.map(stepToNode);
    }
    return [];
  }, [existingWorkflow]);

  const initialEdges = useMemo(() => {
    if (existingWorkflow) {
      return existingWorkflow.edges.map(edgeToFlow);
    }
    return [];
  }, [existingWorkflow]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // 异步加载完成后同步 nodes/edges
  useEffect(() => {
    if (existingWorkflow) {
      nodeIdCounter = existingWorkflow.steps.length + 1;
      setNodes(existingWorkflow.steps.map(stepToNode));
      setEdges(existingWorkflow.edges.map(edgeToFlow));
      setWfName(existingWorkflow.name);
      setWfDescription(existingWorkflow.description ?? '');
    }
  }, [existingWorkflow, setNodes, setEdges]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [wfName, setWfName] = useState(existingWorkflow?.name ?? '');
  const [wfDescription, setWfDescription] = useState(existingWorkflow?.description ?? '');
  const [form] = Form.useForm();

  // 连线回调
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge({ ...connection, markerEnd: { type: MarkerType.ArrowClosed } }, eds),
      );
    },
    [setEdges],
  );

  // 节点点击 → 打开属性面板
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode(node);
      form.setFieldsValue({
        name: node.data.label,
        stepType: node.data.stepType ?? 'agent',
        agentName: node.data.agentName ?? '',
        promptTemplate: node.data.promptTemplate ?? '',
        maxTurns: node.data.maxTurns,
        timeout: node.data.timeout,
      });
      setDrawerOpen(true);
    },
    [form],
  );

  // 添加新节点
  const addNode = useCallback(
    (type: string) => {
      const id = nextNodeId();
      const color = NODE_COLORS[type] ?? '#d9d9d9';
      const newNode: Node = {
        id,
        position: { x: 100 + Math.random() * 300, y: 100 + Math.random() * 200 },
        data: {
          label: id,
          stepType: type,
          agentName: '',
          promptTemplate: '',
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          border: `2px solid ${color}`,
          borderRadius: 8,
          padding: '8px 16px',
          background: '#fff',
          minWidth: 160,
        },
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes],
  );

  // 更新节点属性
  const updateNodeData = useCallback(() => {
    if (!selectedNode) return;
    const values = form.getFieldsValue();
    const color = NODE_COLORS[values.stepType] ?? '#d9d9d9';
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? {
              ...n,
              data: {
                ...n.data,
                label: values.name,
                stepType: values.stepType,
                agentName: values.agentName,
                promptTemplate: values.promptTemplate,
                maxTurns: values.maxTurns,
                timeout: values.timeout,
              },
              style: { ...n.style, border: `2px solid ${color}` },
            }
          : n,
      ),
    );
    setDrawerOpen(false);
    message.success('节点已更新');
  }, [selectedNode, form, setNodes, message]);

  // 删除选中节点
  const deleteSelectedNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
    setDrawerOpen(false);
    setSelectedNode(null);
  }, [selectedNode, setNodes, setEdges]);

  // 构建保存数据
  const buildParams = useCallback((): WorkflowCreateParams => ({
    name: wfName || 'untitled',
    description: wfDescription,
    steps: nodesToSteps(nodes),
    edges: flowToEdges(edges),
  }), [wfName, wfDescription, nodes, edges]);

  // 验证
  const handleValidate = useCallback(async () => {
    try {
      const res = await validateMutation.mutateAsync(buildParams());
      if (res.valid) {
        message.success('验证通过');
      } else {
        message.warning(`验证失败: ${res.errors.join('; ')}`);
      }
    } catch {
      message.error('验证请求失败');
    }
  }, [buildParams, validateMutation, message]);

  // 保存
  const handleSave = useCallback(async () => {
    if (!wfName) {
      message.warning('请输入工作流名称');
      return;
    }
    try {
      const params = buildParams();
      if (editId) {
        await updateMutation.mutateAsync({ id: editId, data: params });
        message.success('更新成功');
      } else {
        await createMutation.mutateAsync(params);
        message.success('创建成功');
      }
      navigate('/workflows');
    } catch {
      message.error('保存失败');
    }
  }, [wfName, editId, buildParams, createMutation, updateMutation, navigate, message]);

  return (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部工具栏 */}
      <Card size="small" style={{ borderRadius: 0 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/workflows')}>返回</Button>
          <Input
            placeholder="工作流名称"
            value={wfName}
            onChange={(e) => setWfName(e.target.value)}
            style={{ width: 200 }}
          />
          <Input
            placeholder="描述（可选）"
            value={wfDescription}
            onChange={(e) => setWfDescription(e.target.value)}
            style={{ width: 260 }}
          />
          <Button icon={<CheckCircleOutlined />} onClick={() => void handleValidate()}>验证</Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={() => void handleSave()}>
            {editId ? '保存' : '创建'}
          </Button>
        </Space>
      </Card>

      {/* 画布 */}
      <div style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          fitView
          snapToGrid
          snapGrid={[20, 20]}
        >
          <Background gap={20} />
          <Controls />
          <MiniMap />
          <Panel position="top-left">
            <Card size="small" title="添加步骤" style={{ width: 160 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                {STEP_TYPES.map((t) => (
                  <Button
                    key={t.value}
                    size="small"
                    block
                    icon={<PlusOutlined />}
                    onClick={() => addNode(t.value)}
                  >
                    <Tag color={t.color} style={{ margin: 0 }}>{t.label}</Tag>
                  </Button>
                ))}
              </Space>
            </Card>
          </Panel>
          <Panel position="bottom-left">
            <Text type="secondary" style={{ fontSize: 12 }}>
              点击节点编辑属性 • 拖拽连线 • {nodes.length} 步骤 {edges.length} 连线
            </Text>
          </Panel>
        </ReactFlow>
      </div>

      {/* 节点属性 Drawer */}
      <Drawer
        title={`编辑步骤 — ${selectedNode?.id ?? ''}`}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={360}
        extra={
          <Space>
            <Button danger icon={<DeleteOutlined />} onClick={deleteSelectedNode}>删除</Button>
            <Button type="primary" onClick={updateNodeData}>应用</Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="步骤名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="stepType" label="步骤类型" rules={[{ required: true }]}>
            <Select options={STEP_TYPES.map((t) => ({ label: t.label, value: t.value }))} />
          </Form.Item>
          <Form.Item name="agentName" label="Agent 名称">
            <Input placeholder="关联的 Agent 名称" />
          </Form.Item>
          <Form.Item name="promptTemplate" label="提示词模板">
            <Input.TextArea rows={3} placeholder="可选的提示词模板" />
          </Form.Item>
          <Form.Item name="maxTurns" label="最大轮数">
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="timeout" label="超时（秒）">
            <InputNumber min={1} max={3600} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
};

export default WorkflowEditorPage;
