import { useMemo } from 'react';
import { Button, Card, Divider, Space, Typography } from 'antd';
import { SaveOutlined, PlusOutlined } from '@ant-design/icons';
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

const { Text } = Typography;

const initialNodes: Node[] = [
  { id: 'agent', position: { x: 360, y: 160 }, data: { label: 'Agent Core' }, type: 'default' },
];

const initialEdges: Edge[] = [];

const VisualBuilderPage: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = (params: Connection) => {
    setEdges((eds) => addEdge({ ...params, animated: true }, eds));
  };

  const addNode = (kind: 'tool' | 'guardrail' | 'handoff' | 'mcp') => {
    const id = `${kind}-${Date.now()}`;
    const count = nodes.filter((n) => n.id.startsWith(kind)).length;
    const next: Node = {
      id,
      data: { label: `${kind.toUpperCase()}-${count + 1}` },
      position: { x: 120 + (count % 3) * 220, y: 40 + Math.floor(count / 3) * 120 },
      type: 'default',
    };
    setNodes((prev) => [...prev, next]);
  };

  const configJson = useMemo(() => {
    const tools = nodes.filter((n) => n.id.startsWith('tool-')).map((n) => String(n.data?.label ?? n.id));
    const guardrails = nodes.filter((n) => n.id.startsWith('guardrail-')).map((n) => String(n.data?.label ?? n.id));
    const handoffs = nodes.filter((n) => n.id.startsWith('handoff-')).map((n) => String(n.data?.label ?? n.id));
    const mcpServers = nodes.filter((n) => n.id.startsWith('mcp-')).map((n) => String(n.data?.label ?? n.id));

    return {
      instructions: '由 Visual Builder 生成',
      tools,
      guardrails,
      handoffs,
      mcp_servers: mcpServers,
      links: edges.map((e) => ({ from: e.source, to: e.target })),
    };
  }, [edges, nodes]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space wrap>
          <Button icon={<PlusOutlined />} onClick={() => addNode('tool')}>添加 Tool</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('guardrail')}>添加 Guardrail</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('handoff')}>添加 Handoff</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('mcp')}>添加 MCP</Button>
          <Divider type="vertical" />
          <Button type="primary" icon={<SaveOutlined />}>
            保存（生成 JSON）
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

      <Card title="Agent JSON（单向: Canvas -> JSON）">
        <Text code style={{ whiteSpace: 'pre-wrap', display: 'block' }}>
          {JSON.stringify(configJson, null, 2)}
        </Text>
      </Card>
    </Space>
  );
};

export default VisualBuilderPage;
