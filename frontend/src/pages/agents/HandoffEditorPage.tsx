import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Card, App, Space, Tag, Tooltip, Spin, theme } from 'antd';
import { SaveOutlined, ReloadOutlined, ApartmentOutlined, WarningOutlined } from '@ant-design/icons';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from '@dagrejs/dagre';
import { agentService, type AgentConfig } from '../../services/agentService';

// ─── 常量 ───────────────────────────────────────────────────────
const NODE_WIDTH = 200;
const NODE_HEIGHT = 80;

// ─── 自定义节点 ─────────────────────────────────────────────────
type AgentNodeData = {
  label: string;
  model: string;
  isActive: boolean;
  handoffCount: number;
};

const AgentNode = ({ data }: NodeProps<Node<AgentNodeData>>) => {
  const { token } = theme.useToken();
  return (
    <div
      style={{
        padding: '10px 14px',
        border: `2px solid ${data.isActive ? token.colorPrimary : token.colorBorder}`,
        borderRadius: 8,
        background: data.isActive ? token.colorPrimaryBg : token.colorBgLayout,
        width: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: token.colorPrimary }} />
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{data.label}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Tag color={data.model ? 'blue' : 'default'} style={{ fontSize: 11 }}>
          {data.model || '未配置模型'}
        </Tag>
        {data.handoffCount > 0 && (
          <Tag color="purple" style={{ fontSize: 11 }}>
            {data.handoffCount} handoff
          </Tag>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: token.colorPrimary }} />
    </div>
  );
};

const nodeTypes = { agent: AgentNode };

// ─── dagre 自动布局 ────────────────────────────────────────────
function applyDagreLayout(
  nodes: Node<AgentNodeData>[],
  edges: Edge[],
): { nodes: Node<AgentNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80 });

  nodes.forEach((n) => {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });
  edges.forEach((e) => {
    g.setEdge(e.source, e.target);
  });

  dagre.layout(g);

  const layoutNodes = nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });

  return { nodes: layoutNodes, edges };
}

// ─── 循环检测 ──────────────────────────────────────────────────
function detectCycles(edges: Edge[]): string[][] {
  const adj: Record<string, string[]> = {};
  for (const e of edges) {
    (adj[e.source] ??= []).push(e.target);
  }

  const cycles: string[][] = [];
  const visited = new Set<string>();
  const stack = new Set<string>();
  const path: string[] = [];

  function dfs(node: string) {
    if (stack.has(node)) {
      const idx = path.indexOf(node);
      if (idx >= 0) cycles.push([...path.slice(idx), node]);
      return;
    }
    if (visited.has(node)) return;
    visited.add(node);
    stack.add(node);
    path.push(node);
    for (const next of adj[node] || []) {
      dfs(next);
    }
    path.pop();
    stack.delete(node);
  }

  const allNodes = new Set([...edges.map((e) => e.source), ...edges.map((e) => e.target)]);
  for (const n of allNodes) {
    if (!visited.has(n)) dfs(n);
  }

  return cycles;
}

// ─── 主组件 ────────────────────────────────────────────────────
const HandoffEditorPage: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<AgentNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [dirty, setDirty] = useState(false);

  // 保存初始快照用于 diff
  const snapshotRef = useRef<Record<string, string[]>>({});

  // ── 加载 Agent 列表 ──
  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await agentService.list({ limit: 500 });
      const list = res.data;
      setAgents(list);

      // 构建初始快照
      const snap: Record<string, string[]> = {};
      list.forEach((a) => {
        snap[a.name] = [...(a.handoffs || [])];
      });
      snapshotRef.current = snap;

      // 转成节点
      const rawNodes: Node<AgentNodeData>[] = list.map((a, i) => ({
        id: a.name,
        type: 'agent',
        position: { x: (i % 4) * 260, y: Math.floor(i / 4) * 140 },
        data: {
          label: a.name,
          model: a.model || '',
          isActive: a.is_active,
          handoffCount: (a.handoffs || []).length,
        },
      }));

      // 转成边
      const rawEdges: Edge[] = [];
      const agentNames = new Set(list.map((a) => a.name));
      list.forEach((a) => {
        (a.handoffs || []).forEach((target) => {
          if (agentNames.has(target)) {
            rawEdges.push({
              id: `${a.name}->${target}`,
              source: a.name,
              target,
              label: `→ ${target}`,
              labelStyle: { fontSize: 11, fill: token.colorTextSecondary },
              labelBgStyle: { fill: token.colorBgContainer, fillOpacity: 0.85 },
              labelBgPadding: [4, 6] as [number, number],
              labelBgBorderRadius: 4,
              markerEnd: { type: MarkerType.ArrowClosed, color: token.colorPrimary },
              style: { stroke: token.colorPrimary, strokeWidth: 2 },
              animated: true,
            });
          }
        });
      });

      const layout = applyDagreLayout(rawNodes, rawEdges);
      setNodes(layout.nodes);
      setEdges(layout.edges);
      setDirty(false);
    } catch {
      message.error('加载 Agent 列表失败');
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges, message, token]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  // ── 连线 ──
  const onConnect = useCallback(
    (params: Connection) => {
      if (params.source === params.target) return; // 禁止自连
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            id: `${params.source}->${params.target}`,
            label: `→ ${params.target}`,
            labelStyle: { fontSize: 11, fill: token.colorTextSecondary },
            labelBgStyle: { fill: token.colorBgContainer, fillOpacity: 0.85 },
            labelBgPadding: [4, 6] as [number, number],
            labelBgBorderRadius: 4,
            markerEnd: { type: MarkerType.ArrowClosed, color: token.colorPrimary },
            style: { stroke: token.colorPrimary, strokeWidth: 2 },
            animated: true,
          },
          eds,
        ),
      );
      setDirty(true);
    },
    [setEdges, token],
  );

  // ── 删边 ──
  const onEdgesDelete = useCallback(() => {
    setDirty(true);
  }, []);

  // ── 循环检测 ──
  const cycles = useMemo(() => detectCycles(edges), [edges]);

  // ── 保存 ──
  const handleSave = useCallback(async () => {
    // 从当前 edges 构建 handoffs map
    const handoffMap: Record<string, string[]> = {};
    agents.forEach((a) => {
      handoffMap[a.name] = [];
    });
    edges.forEach((e) => {
      if (handoffMap[e.source]) {
        handoffMap[e.source]?.push(e.target);
      }
    });

    // diff：只更新变更的 Agent
    const updates: { name: string; handoffs: string[] }[] = [];
    for (const [name, handoffs] of Object.entries(handoffMap)) {
      const original = snapshotRef.current[name] || [];
      const sortedNew = [...handoffs].sort();
      const sortedOld = [...original].sort();
      if (JSON.stringify(sortedNew) !== JSON.stringify(sortedOld)) {
        updates.push({ name, handoffs });
      }
    }

    if (updates.length === 0) {
      message.info('没有变更需要保存');
      setDirty(false);
      return;
    }

    setSaving(true);
    try {
      await Promise.all(
        updates.map((u) => agentService.update(u.name, { handoffs: u.handoffs })),
      );
      message.success(`已更新 ${updates.length} 个 Agent 的 Handoff 配置`);
      // 刷新快照
      for (const u of updates) {
        snapshotRef.current[u.name] = [...u.handoffs];
      }
      setDirty(false);
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }, [agents, edges, message]);

  // ── 自动布局 ──
  const handleAutoLayout = useCallback(() => {
    const layout = applyDagreLayout(nodes, edges);
    setNodes(layout.nodes);
    setEdges(layout.edges);
  }, [nodes, edges, setNodes, setEdges]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Card
      title={
        <Space>
          <ApartmentOutlined />
          Agent Handoff 可视化编排
          {dirty && <Tag color="orange">未保存</Tag>}
        </Space>
      }
      extra={
        <Space>
          {cycles.length > 0 && (
            <Tooltip title={`检测到 ${cycles.length} 个循环引用（Framework 有深度保护，不会死循环）`}>
              <Tag color="warning" icon={<WarningOutlined />}>
                {cycles.length} 循环
              </Tag>
            </Tooltip>
          )}
          <Button icon={<ReloadOutlined />} onClick={loadAgents}>
            刷新
          </Button>
          <Button icon={<ApartmentOutlined />} onClick={handleAutoLayout}>
            自动布局
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
            disabled={!dirty}
          >
            保存
          </Button>
        </Space>
      }
      styles={{ body: { padding: 0 } }}
    >
      <div style={{ height: 'calc(100vh - 200px)', minHeight: 500 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={(changes) => {
            onEdgesChange(changes);
            // 检测是否有删除操作
            if (changes.some((c) => c.type === 'remove')) {
              onEdgesDelete();
            }
          }}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          deleteKeyCode="Delete"
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} />
          <Controls />
          <MiniMap
            nodeColor={(n) => {
              const d = n.data as AgentNodeData;
              return d.isActive ? token.colorPrimary : token.colorBorder;
            }}
            zoomable
            pannable
          />
        </ReactFlow>
      </div>
    </Card>
  );
};

export default HandoffEditorPage;
