import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
  Position,
  type NodeProps,
  Handle,
} from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import { App, Card, Empty, Spin, Tag, Typography, Descriptions } from 'antd';
import '@xyflow/react/dist/style.css';
import { knowledgeBaseService, type GraphDataResponse } from '../services/knowledgeBaseService';

const { Text } = Typography;

// 实体类型颜色映射
const TYPE_COLORS: Record<string, string> = {
  Tool: '#1677ff',
  Language: '#52c41a',
  Concept: '#722ed1',
  API: '#fa8c16',
  Person: '#eb2f96',
  Organization: '#13c2c2',
  Event: '#f5222d',
};

function getTypeColor(type: string): string {
  return TYPE_COLORS[type] || '#8c8c8c';
}

// 自定义节点组件
function EntityNode({ data }: NodeProps) {
  const color = getTypeColor(data.entityType as string || '');
  return (
    <div
      style={{
        padding: '6px 12px',
        borderRadius: 6,
        border: `2px solid ${color}`,
        background: '#fff',
        fontSize: 12,
        minWidth: 60,
        textAlign: 'center',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color }} />
      <div style={{ fontWeight: 600, color }}>{data.label as string}</div>
      <div style={{ fontSize: 10, color: '#999' }}>{data.entityType as string}</div>
      <Handle type="source" position={Position.Right} style={{ background: color }} />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  entity: EntityNode,
};

// dagre 自动布局
function layoutGraph(
  nodes: Node[],
  edges: Edge[],
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 60 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: 120, height: 50 });
  });
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - 60, y: pos.y - 25 },
    };
  });

  return { nodes: layoutNodes, edges };
}

interface KnowledgeGraphViewProps {
  kbId: string;
}

const KnowledgeGraphView: React.FC<KnowledgeGraphViewProps> = ({ kbId }) => {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [graphData, setGraphData] = useState<GraphDataResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<{ id: string; label: string; type: string; confidence?: number } | null>(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const data = await knowledgeBaseService.getGraphData(kbId, 200);
      setGraphData(data);
    } catch {
      message.error('加载图谱数据失败');
    } finally {
      setLoading(false);
    }
  }, [kbId, message]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const { nodes: flowNodes, edges: flowEdges } = useMemo(() => {
    if (!graphData) return { nodes: [], edges: [] };

    const nodes: Node[] = graphData.nodes.map((n) => ({
      id: n.id,
      type: 'entity',
      position: { x: 0, y: 0 },
      data: { label: n.label, entityType: n.type, confidence: n.confidence },
    }));

    const edges: Edge[] = graphData.edges.map((e, i) => ({
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      label: e.type,
      style: { stroke: '#bbb', strokeWidth: Math.max(1, e.weight * 2) },
      animated: false,
    }));

    return layoutGraph(nodes, edges);
  }, [graphData]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <Spin tip="加载图谱..." />
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return <Empty description="暂无图谱数据，请先构建图谱" />;
  }

  return (
    <div style={{ display: 'flex', gap: 12, height: 500 }}>
      <div style={{ flex: 1, border: '1px solid #e8e8e8', borderRadius: 8, overflow: 'hidden' }}>
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          fitView
          onNodeClick={(_, node) => {
            setSelectedNode({
              id: node.id,
              label: node.data.label as string,
              type: node.data.entityType as string,
              confidence: node.data.confidence as number | undefined,
            });
          }}
          minZoom={0.1}
          maxZoom={2}
        >
          <Background />
          <Controls />
          <MiniMap
            nodeColor={(node) => getTypeColor(node.data?.entityType as string || '')}
            maskColor="rgba(0,0,0,0.1)"
          />
        </ReactFlow>
      </div>

      {selectedNode && (
        <Card
          size="small"
          title={selectedNode.label}
          extra={<Tag color={getTypeColor(selectedNode.type)}>{selectedNode.type}</Tag>}
          style={{ width: 260 }}
        >
          <Descriptions column={1} size="small">
            <Descriptions.Item label="ID">
              <Text copyable style={{ fontSize: 11 }}>{selectedNode.id}</Text>
            </Descriptions.Item>
            {selectedNode.confidence !== undefined && (
              <Descriptions.Item label="置信度">
                <Text>{(selectedNode.confidence * 100).toFixed(0)}%</Text>
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      )}
    </div>
  );
};

export default KnowledgeGraphView;
