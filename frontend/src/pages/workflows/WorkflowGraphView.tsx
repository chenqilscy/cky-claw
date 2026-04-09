/**
 * WorkflowGraphView — ReactFlow 工作流 DAG 可视化组件
 */
import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { StepSchema, EdgeSchema } from '../../services/workflowService';

import { NODE_COLORS } from '../../constants/colors';

const NODE_LABELS: Record<string, string> = {
  agent: 'Agent',
  parallel: '并行',
  conditional: '条件',
  loop: '循环',
};

interface WorkflowGraphViewProps {
  steps: StepSchema[];
  edges: EdgeSchema[];
}

const WorkflowGraphView: React.FC<WorkflowGraphViewProps> = ({ steps, edges }) => {
  const { nodes, flowEdges } = useMemo(() => {
    const COLS = 3;
    const X_GAP = 250;
    const Y_GAP = 120;

    const flowNodes: Node[] = steps.map((step, i) => ({
      id: step.id,
      position: { x: (i % COLS) * X_GAP + 50, y: Math.floor(i / COLS) * Y_GAP + 50 },
      data: {
        label: (
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 10,
              color: NODE_COLORS[step.type] ?? '#999',
              fontWeight: 600,
              marginBottom: 2,
            }}>
              {NODE_LABELS[step.type] ?? step.type}
            </div>
            <div style={{ fontWeight: 500 }}>{step.name}</div>
            {step.agent_name && (
              <div style={{ fontSize: 11, color: '#888' }}>{step.agent_name}</div>
            )}
          </div>
        ),
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      style: {
        border: `2px solid ${NODE_COLORS[step.type] ?? '#d9d9d9'}`,
        borderRadius: 8,
        padding: '8px 12px',
        background: '#fff',
        minWidth: 140,
      },
    }));

    const fe: Edge[] = edges.map((e, i) => ({
      id: e.id || `edge-${i}`,
      source: e.source_step_id,
      target: e.target_step_id,
      label: e.condition ?? undefined,
      animated: !!e.condition,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: '#aaa' },
    }));

    return { nodes: flowNodes, flowEdges: fe };
  }, [steps, edges]);

  if (steps.length === 0) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>无步骤定义</div>;
  }

  return (
    <div style={{ width: '100%', height: 400 }}>
      <ReactFlow
        nodes={nodes}
        edges={flowEdges}
        fitView
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
};

export default WorkflowGraphView;
