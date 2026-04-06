import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

/* ---------- mock ReactFlow ---------- */
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) => <div data-testid="reactflow">{children}</div>,
  Background: () => <div data-testid="background" />,
  Controls: () => <div data-testid="controls" />,
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  MarkerType: { ArrowClosed: 'arrowclosed' },
}));

import WorkflowGraphView from '../../pages/workflows/WorkflowGraphView';

describe('WorkflowGraphView', () => {
  const steps = [
    { id: 's1', name: 'step-1', type: 'agent', agent_name: 'bot-1' },
    { id: 's2', name: 'step-2', type: 'parallel', agent_name: '' },
  ];
  const edges = [
    { source: 's1', target: 's2' },
  ];

  it('渲染 ReactFlow 画布', () => {
    const { container } = render(<WorkflowGraphView steps={steps} edges={edges} />);
    const flow = container.querySelector('[data-testid="reactflow"]');
    expect(flow).toBeTruthy();
  });

  it('传入空步骤不崩溃', () => {
    const { container } = render(<WorkflowGraphView steps={[]} edges={[]} />);
    expect(container).toBeTruthy();
  });

  it('渲染 Background 和 Controls', () => {
    const { container } = render(<WorkflowGraphView steps={steps} edges={edges} />);
    expect(container.querySelector('[data-testid="background"]')).toBeTruthy();
    expect(container.querySelector('[data-testid="controls"]')).toBeTruthy();
  });
});
