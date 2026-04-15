import { useMemo, useCallback, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button, Card, Divider, Space, Typography, App, Modal, Form, Input, Select, Dropdown, Collapse,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  SaveOutlined, PlusOutlined, CopyOutlined, RocketOutlined,
  ToolOutlined, SafetyCertificateOutlined, SwapOutlined, CloudServerOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { agentService } from '../../services/agentService';
import type { AgentConfig } from '../../services/agentService';
import { toolGroupService } from '../../services/toolGroupService';
import { guardrailService } from '../../services/guardrailService';
import { mcpServerService } from '../../services/mcpServerService';
import { providerService } from '../../services/providerService';
import type { ProviderResponse } from '../../services/providerService';

const { Text } = Typography;

/** 节点类型配色与图标映射。 */
const NODE_STYLES: Record<string, { color: string; bg: string; icon: string }> = {
  agent:     { color: '#1677ff', bg: '#e6f4ff', icon: '🤖' },
  tool:      { color: '#52c41a', bg: '#f6ffed', icon: '🔧' },
  guardrail: { color: '#faad14', bg: '#fffbe6', icon: '🛡️' },
  handoff:   { color: '#722ed1', bg: '#f9f0ff', icon: '🔀' },
  mcp:       { color: '#13c2c2', bg: '#e6fffb', icon: '☁️' },
};

/** 从节点 id 中提取类型前缀。 */
function nodeKind(id: string): string {
  const idx = id.indexOf('-');
  return idx > 0 ? id.slice(0, idx) : id;
}

const initialNodes: Node[] = [
  { id: 'agent', position: { x: 360, y: 160 }, data: { label: '🤖 Agent Core' }, type: 'default', style: { background: '#e6f4ff', border: '2px solid #1677ff', borderRadius: 8, fontWeight: 600 } },
];
const initialEdges: Edge[] = [];

const VisualBuilderPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveForm] = Form.useForm();

  /* ---- 后端数据加载 ---- */
  const [toolGroupItems, setToolGroupItems] = useState<{ name: string; description: string }[]>([]);
  const [guardrailItems, setGuardrailItems] = useState<{ name: string; mode: string; type: string }[]>([]);
  const [mcpItems, setMcpItems] = useState<{ name: string; transport_type: string }[]>([]);
  const [agentItems, setAgentItems] = useState<{ name: string; description: string }[]>([]);
  const [providerOptions, setProviderOptions] = useState<{ label: string; value: string }[]>([]);
  const [loadingAgent, setLoadingAgent] = useState(false);

  useEffect(() => {
    toolGroupService.list().then((r) => setToolGroupItems(r.data.filter((g) => g.is_enabled))).catch(() => {});
    guardrailService.list({ enabled_only: true, limit: 200 }).then((r) => setGuardrailItems(r.data)).catch(() => {});
    mcpServerService.list({ limit: 200 }).then((r) => setMcpItems(r.data)).catch(() => {});
    agentService.list({ limit: 100 }).then((r) => setAgentItems(r.data.map((a: AgentConfig) => ({ name: a.name, description: a.description })))).catch(() => {});
    providerService.list({ is_enabled: true, limit: 100 })
      .then((r) => setProviderOptions(r.data.map((p: ProviderResponse) => ({ label: `${p.name} (${p.provider_type})`, value: p.name }))))
      .catch(() => {});
  }, []);

  const onConnect = (params: Connection) => {
    setEdges((eds) => addEdge({ ...params, animated: true }, eds));
  };

  /** 添加带样式的节点。 */
  const addStyledNode = useCallback((kind: string, label: string) => {
    const id = `${kind}-${Date.now()}`;
    const count = nodes.filter((n) => nodeKind(n.id) === kind).length;
    const s = NODE_STYLES[kind] ?? NODE_STYLES.tool;
    const next: Node = {
      id,
      data: { label: `${s.icon} ${label}` },
      position: { x: 120 + (count % 4) * 220, y: 40 + Math.floor(count / 4) * 120 },
      type: 'default',
      style: { background: s.bg, border: `2px solid ${s.color}`, borderRadius: 8, fontWeight: 500 },
    };
    setNodes((prev) => [...prev, next]);
  }, [nodes, setNodes]);

  /**
   * 从已有 Agent 加载画布（JSON → Canvas）。
   * 将 Agent 的 tool_groups / mcp_servers / handoffs / guardrails 转化为节点并自动连线。
   */
  const handleLoadAgent = useCallback(async (agentName: string) => {
    setLoadingAgent(true);
    try {
      const agent: AgentConfig = await agentService.get(agentName);
      const s = NODE_STYLES.agent;
      const agentNode: Node = {
        id: 'agent',
        position: { x: 360, y: 200 },
        data: { label: `🤖 ${agent.name}` },
        type: 'default',
        style: { background: s.bg, border: `2px solid ${s.color}`, borderRadius: 8, fontWeight: 600 },
      };
      const newNodes: Node[] = [agentNode];
      const newEdges: Edge[] = [];

      const addGroup = (items: string[], kind: string, offsetX: number) => {
        const st = NODE_STYLES[kind] ?? NODE_STYLES.tool;
        items.forEach((name, i) => {
          const id = `${kind}-loaded-${i}`;
          newNodes.push({
            id,
            data: { label: `${st.icon} ${name}` },
            position: { x: offsetX, y: 40 + i * 100 },
            type: 'default',
            style: { background: st.bg, border: `2px solid ${st.color}`, borderRadius: 8, fontWeight: 500 },
          });
          newEdges.push({ id: `e-${id}`, source: id, target: 'agent', animated: true });
        });
      };

      addGroup(agent.tool_groups ?? [], 'tool', 80);
      addGroup(agent.mcp_servers ?? [], 'mcp', 320);
      addGroup(agent.handoffs ?? [], 'handoff', 580);
      const inputGuardrails = agent.guardrails?.input ?? [];
      addGroup(inputGuardrails, 'guardrail', 800);

      setNodes(newNodes);
      setEdges(newEdges);

      // 预填保存表单
      saveForm.setFieldsValue({
        name: '',
        description: agent.description || '',
        instructions: agent.instructions || '',
        provider_name: agent.provider_name || undefined,
        model: agent.model || '',
      });
      message.success(`已加载 Agent「${agentName}」到画布`);
    } catch {
      message.error('加载 Agent 失败');
    } finally {
      setLoadingAgent(false);
    }
  }, [setNodes, setEdges, saveForm, message]);

  /* ---- 下拉菜单构建 ---- */
  const toolMenu: MenuProps['items'] = [
    { key: 'custom', label: '自定义 Tool 节点', onClick: () => addStyledNode('tool', `TOOL-${nodes.filter((n) => nodeKind(n.id) === 'tool').length + 1}`) },
    ...(toolGroupItems.length > 0 ? [{ type: 'divider' as const }] : []),
    ...toolGroupItems.map((g) => ({ key: `tg-${g.name}`, label: g.name, onClick: () => addStyledNode('tool', g.name) })),
  ];

  const guardrailMenu: MenuProps['items'] = [
    { key: 'custom', label: '自定义 Guardrail 节点', onClick: () => addStyledNode('guardrail', `GUARD-${nodes.filter((n) => nodeKind(n.id) === 'guardrail').length + 1}`) },
    ...(guardrailItems.length > 0 ? [{ type: 'divider' as const }] : []),
    ...guardrailItems.map((g) => ({ key: `gr-${g.name}`, label: `${g.name} (${g.type}/${g.mode})`, onClick: () => addStyledNode('guardrail', g.name) })),
  ];

  const handoffMenu: MenuProps['items'] = [
    { key: 'custom', label: '自定义 Handoff 节点', onClick: () => addStyledNode('handoff', `HANDOFF-${nodes.filter((n) => nodeKind(n.id) === 'handoff').length + 1}`) },
    ...(agentItems.length > 0 ? [{ type: 'divider' as const }] : []),
    ...agentItems.map((a) => ({ key: `ho-${a.name}`, label: a.name, onClick: () => addStyledNode('handoff', a.name) })),
  ];

  const mcpMenu: MenuProps['items'] = [
    { key: 'custom', label: '自定义 MCP 节点', onClick: () => addStyledNode('mcp', `MCP-${nodes.filter((n) => nodeKind(n.id) === 'mcp').length + 1}`) },
    ...(mcpItems.length > 0 ? [{ type: 'divider' as const }] : []),
    ...mcpItems.map((m) => ({ key: `mcp-${m.name}`, label: `${m.name} (${m.transport_type})`, onClick: () => addStyledNode('mcp', m.name) })),
  ];

  /* ---- JSON 配置生成 ---- */
  const configJson = useMemo(() => {
    /** 提取节点标签（去掉 emoji 前缀）。 */
    const cleanLabel = (n: Node) => String(n.data?.label ?? n.id).replace(/^[^\w]*\s*/, '');
    const tools = nodes.filter((n) => nodeKind(n.id) === 'tool').map(cleanLabel);
    const guardrails = nodes.filter((n) => nodeKind(n.id) === 'guardrail').map(cleanLabel);
    const handoffs = nodes.filter((n) => nodeKind(n.id) === 'handoff').map(cleanLabel);
    const mcpServers = nodes.filter((n) => nodeKind(n.id) === 'mcp').map(cleanLabel);
    const instructions = (saveForm.getFieldValue('instructions') as string) || '由 Visual Builder 生成';
    const model = (saveForm.getFieldValue('model') as string) || 'openai/glm-4-flash';
    const providerName = (saveForm.getFieldValue('provider_name') as string) || null;

    return {
      instructions,
      model,
      provider_name: providerName,
      tool_groups: tools,
      guardrails: { input: guardrails, output: [], tool: [] },
      handoffs,
      mcp_servers: mcpServers,
      links: edges.map((e) => ({ from: e.source, to: e.target })),
    };
  }, [edges, nodes, saveForm]);

  /* ---- 复制 JSON ---- */
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(configJson, null, 2));
      message.success('Agent JSON 已复制到剪贴板');
    } catch {
      message.info('请手动复制下方 JSON 配置');
    }
  }, [configJson, message]);

  /* ---- 保存为 Agent ---- */
  const handleSaveAsAgent = useCallback(async () => {
    try {
      const values = await saveForm.validateFields();
      setSaving(true);
      await agentService.create({
        name: values.name,
        description: values.description || '',
        instructions: configJson.instructions,
        tool_groups: configJson.tool_groups,
        handoffs: configJson.handoffs,
        mcp_servers: configJson.mcp_servers,
        guardrails: configJson.guardrails,
      });
      message.success(`Agent "${values.name}" 已创建`);
      setSaveModalOpen(false);
      saveForm.resetFields();
      navigate(`/agents/${values.name}/edit`);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) return; // form validation
      message.error('创建 Agent 失败');
    } finally {
      setSaving(false);
    }
  }, [configJson, saveForm, message, navigate]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {/* ---- 加载已有 Agent（JSON → Canvas） ---- */}
      <Card size="small">
        <Space wrap>
          <Select
            showSearch
            placeholder="选择已有 Agent 加载到画布..."
            style={{ minWidth: 260 }}
            options={agentItems.map((a) => ({ label: a.name, value: a.name }))}
            loading={loadingAgent}
            allowClear
            onSelect={(val: string) => handleLoadAgent(val)}
            filterOption={(input, option) => String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
          />
          <Button icon={<DownloadOutlined />} loading={loadingAgent} disabled>
            从 Agent 加载
          </Button>
        </Space>
      </Card>
      <Card>
        <Space wrap>
          <Dropdown menu={{ items: toolMenu }} trigger={['click']}>
            <Button icon={<ToolOutlined />} style={{ color: NODE_STYLES.tool.color }}>添加 Tool</Button>
          </Dropdown>
          <Dropdown menu={{ items: guardrailMenu }} trigger={['click']}>
            <Button icon={<SafetyCertificateOutlined />} style={{ color: NODE_STYLES.guardrail.color }}>添加 Guardrail</Button>
          </Dropdown>
          <Dropdown menu={{ items: handoffMenu }} trigger={['click']}>
            <Button icon={<SwapOutlined />} style={{ color: NODE_STYLES.handoff.color }}>添加 Handoff</Button>
          </Dropdown>
          <Dropdown menu={{ items: mcpMenu }} trigger={['click']}>
            <Button icon={<CloudServerOutlined />} style={{ color: NODE_STYLES.mcp.color }}>添加 MCP</Button>
          </Dropdown>
          <Divider type="vertical" />
          <Button icon={<CopyOutlined />} onClick={handleCopy}>复制 JSON</Button>
          <Button type="primary" icon={<RocketOutlined />} onClick={() => setSaveModalOpen(true)}>
            保存为 Agent
          </Button>
        </Space>
      </Card>

      <Card style={{ height: 520, padding: 0 }} bodyStyle={{ height: 520, padding: 0 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <MiniMap />
          <Controls />
          <Background />
        </ReactFlow>
      </Card>

      <Collapse
        items={[{
          key: 'json',
          label: 'Agent JSON（单向: Canvas → JSON）',
          children: (
            <Text code style={{ whiteSpace: 'pre-wrap', display: 'block' }}>
              {JSON.stringify(configJson, null, 2)}
            </Text>
          ),
        }]}
        defaultActiveKey={[]}
      />

      {/* ---- Save as Agent Modal ---- */}
      <Modal
        title="保存为 Agent"
        open={saveModalOpen}
        onCancel={() => setSaveModalOpen(false)}
        onOk={handleSaveAsAgent}
        confirmLoading={saving}
        okText="创建"
        destroyOnClose
        width={600}
      >
        <Form form={saveForm} layout="vertical">
          <Form.Item
            name="name"
            label="Agent 名称"
            rules={[
              { required: true, message: '请输入名称' },
              { pattern: /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/, message: '小写字母/数字/连字符，3-64 字符' },
            ]}
          >
            <Input placeholder="例如: my-visual-agent" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="Agent 功能描述（可选）" />
          </Form.Item>
          <Form.Item name="instructions" label="系统指令">
            <Input.TextArea rows={3} placeholder="Agent 的角色和行为指令" />
          </Form.Item>
          <Form.Item name="provider_name" label="模型厂商">
            <Select options={providerOptions} allowClear placeholder="选择厂商（可选）" />
          </Form.Item>
          <Form.Item name="model" label="模型标识">
            <Input placeholder="如 openai/glm-4-flash，留空使用默认" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};

export default VisualBuilderPage;
