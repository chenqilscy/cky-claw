import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button, Card, message, Space, Tag, Tooltip, Spin, Empty, Select } from 'antd';
import {
  SaveOutlined, ReloadOutlined, ApartmentOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from '@dagrejs/dagre';
import { type TeamConfig, getTeam, updateTeam } from '../../services/teamService';
import { agentService, type AgentConfig } from '../../services/agentService';

// ─── 常量 ──────────────────────────────────────────────────
const NODE_WIDTH = 220;
const NODE_HEIGHT = 90;

const protocolLabel: Record<string, string> = {
  SEQUENTIAL: '顺序执行',
  PARALLEL: '并行执行',
  COORDINATOR: '协调者模式',
};

const protocolColor: Record<string, string> = {
  SEQUENTIAL: '#1890ff',
  PARALLEL: '#52c41a',
  COORDINATOR: '#722ed1',
};

// ─── 自定义节点 ───────────────────────────────────────────────
type MemberNodeData = {
  label: string;
  description: string;
  model: string;
  isCoordinator: boolean;
};

const MemberNode = ({ data }: NodeProps<Node<MemberNodeData>>) => {
  const borderColor = data.isCoordinator ? '#722ed1' : '#1677ff';
  const bgColor = data.isCoordinator ? '#f9f0ff' : '#f0f5ff';
  return (
    <div
      style={{
        padding: '10px 14px',
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        background: bgColor,
        width: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: borderColor }} />
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{data.label}</div>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {data.description || '无描述'}
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        <Tag color={data.model ? 'blue' : 'default'} style={{ fontSize: 11 }}>
          {data.model || '未配置'}
        </Tag>
        {data.isCoordinator && <Tag color="purple" style={{ fontSize: 11 }}>协调者</Tag>}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: borderColor }} />
    </div>
  );
};

const nodeTypes = { member: MemberNode };

// ─── dagre 自动布局 ──────────────────────────────────────────
function applyDagreLayout(
  nodes: Node<MemberNodeData>[],
  edges: Edge[],
): { nodes: Node<MemberNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 80, ranksep: 100 });
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  const layoutNodes = nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 } };
  });
  return { nodes: layoutNodes, edges };
}

// ─── 根据协议构建边 ────────────────────────────────────────
function buildEdges(team: TeamConfig): Edge[] {
  const edges: Edge[] = [];
  const ids = team.member_agent_ids;

  if (team.protocol === 'SEQUENTIAL') {
    for (let i = 0; i < ids.length - 1; i++) {
      const src = ids[i]!;
      const tgt = ids[i + 1]!;
      edges.push({
        id: `e-${src}-${tgt}`,
        source: src,
        target: tgt,
        animated: true,
        label: `第 ${i + 1} 步`,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#1890ff', strokeWidth: 2 },
      });
    }
  } else if (team.protocol === 'PARALLEL') {
    // 并行：创建虚拟 start → 所有节点
    for (const id of ids) {
      edges.push({
        id: `e-start-${id}`,
        source: '__start__',
        target: id,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#52c41a', strokeWidth: 2 },
      });
    }
  } else if (team.protocol === 'COORDINATOR' && team.coordinator_agent_id) {
    // 协调者 → 每个成员
    for (const id of ids) {
      if (id !== team.coordinator_agent_id) {
        edges.push({
          id: `e-coord-${id}`,
          source: team.coordinator_agent_id,
          target: id,
          animated: true,
          label: '调度',
        markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: '#722ed1', strokeWidth: 2 },
        });
      }
    }
  }
  return edges;
}

function buildNodes(team: TeamConfig, agentMap: Map<string, AgentConfig>): Node<MemberNodeData>[] {
  const nodes: Node<MemberNodeData>[] = [];

  // PARALLEL 模式增加 start 虚节点
  if (team.protocol === 'PARALLEL') {
    nodes.push({
      id: '__start__',
      type: 'member',
      position: { x: 0, y: 0 },
      data: { label: '并行开始', description: '所有成员同时执行', model: '', isCoordinator: false },
    });
  }

  // COORDINATOR 模式：确保 coordinator 在节点列表中（即使不在 member_agent_ids 里）
  const memberSet = new Set(team.member_agent_ids);
  if (team.protocol === 'COORDINATOR' && team.coordinator_agent_id && !memberSet.has(team.coordinator_agent_id)) {
    const ca = agentMap.get(team.coordinator_agent_id);
    nodes.push({
      id: team.coordinator_agent_id,
      type: 'member',
      position: { x: 0, y: 0 },
      data: {
        label: ca?.name ?? team.coordinator_agent_id,
        description: ca?.description ?? '',
        model: ca?.model ?? '',
        isCoordinator: true,
      },
    });
  }

  for (const agentId of team.member_agent_ids) {
    const agent = agentMap.get(agentId);
    nodes.push({
      id: agentId,
      type: 'member',
      position: { x: 0, y: 0 },
      data: {
        label: agent?.name ?? agentId,
        description: agent?.description ?? '',
        model: agent?.model ?? '',
        isCoordinator: agentId === team.coordinator_agent_id,
      },
    });
  }
  return nodes;
}

// ─── 主组件 ──────────────────────────────────────────────────
const TeamFlowPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const teamId = searchParams.get('id');

  const [team, setTeam] = useState<TeamConfig | null>(null);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<MemberNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const agentMap = useMemo(() => {
    const map = new Map<string, AgentConfig>();
    agents.forEach((a) => map.set(a.id, a));
    return map;
  }, [agents]);

  const fetchData = useCallback(async () => {
    if (!teamId) return;
    setLoading(true);
    try {
      const [teamData, agentResp] = await Promise.all([
        getTeam(teamId),
        agentService.list({ limit: 200 }),
      ]);
      setTeam(teamData);
      setAgents(agentResp.data);

      const agMap = new Map<string, AgentConfig>();
      agentResp.data.forEach((a) => agMap.set(a.id, a));

      const rawNodes = buildNodes(teamData, agMap);
      const rawEdges = buildEdges(teamData);
      const layout = applyDagreLayout(rawNodes, rawEdges);
      setNodes(layout.nodes);
      setEdges(layout.edges);
      setDirty(false);
    } catch {
      message.error('加载团队数据失败');
    } finally {
      setLoading(false);
    }
  }, [teamId, setNodes, setEdges]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAutoLayout = useCallback(() => {
    const layout = applyDagreLayout(nodes, edges);
    setNodes(layout.nodes);
    setEdges(layout.edges);
  }, [nodes, edges, setNodes, setEdges]);

  const handleAddMember = useCallback(async (agentId: string) => {
    if (!team) return;
    if (team.member_agent_ids.includes(agentId)) {
      message.warning('该 Agent 已是团队成员');
      return;
    }
    const newIds = [...team.member_agent_ids, agentId];
    const updated: TeamConfig = { ...team, member_agent_ids: newIds };
    setTeam(updated);

    const rawNodes = buildNodes(updated, agentMap);
    const rawEdges = buildEdges(updated);
    const layout = applyDagreLayout(rawNodes, rawEdges);
    setNodes(layout.nodes);
    setEdges(layout.edges);
    setDirty(true);
  }, [team, agentMap, setNodes, setEdges]);

  const handleSave = useCallback(async () => {
    if (!team) return;
    setSaving(true);
    try {
      await updateTeam(team.id, {
        member_agent_ids: team.member_agent_ids,
        coordinator_agent_id: team.coordinator_agent_id,
      });
      message.success('团队拓扑已保存');
      setDirty(false);
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }, [team]);

  const availableAgents = useMemo(() => {
    if (!team) return [];
    return agents.filter((a) => !team.member_agent_ids.includes(a.id));
  }, [agents, team]);

  if (!teamId) {
    return (
      <Card>
        <Empty description="缺少团队 ID，请从团队列表进入" />
      </Card>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 100 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!team) {
    return <Card><Empty description="团队不存在" /></Card>;
  }

  return (
    <Card
      title={
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/teams')} type="text" />
          <span>团队拓扑：{team.name}</span>
          <Tag color={protocolColor[team.protocol]}>{protocolLabel[team.protocol] ?? team.protocol}</Tag>
          <Tag>{team.member_agent_ids.length} 成员</Tag>
        </Space>
      }
      extra={
        <Space>
          <Tooltip title="自动布局">
            <Button icon={<ApartmentOutlined />} onClick={handleAutoLayout} />
          </Tooltip>
          <Tooltip title="刷新">
            <Button icon={<ReloadOutlined />} onClick={fetchData} />
          </Tooltip>
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
      styles={{ body: { height: 'calc(100vh - 220px)', padding: 0 } }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={2}
      >
        <Background gap={16} />
        <Controls />
        <MiniMap
          nodeColor={(n: Node) => {
            const d = n.data as MemberNodeData;
            return d?.isCoordinator ? '#722ed1' : '#1677ff';
          }}
        />
        <Panel position="top-left">
          <Space size="small" style={{ background: 'rgba(255,255,255,0.9)', padding: '8px 12px', borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>添加成员：</span>
            <Select
              showSearch
              placeholder="选择 Agent"
              style={{ width: 200 }}
              optionFilterProp="label"
              onChange={handleAddMember}
              value={undefined}
              options={availableAgents.map((a) => ({ label: a.name, value: a.id }))}
            />
          </Space>
        </Panel>
      </ReactFlow>
    </Card>
  );
};

export default TeamFlowPage;
