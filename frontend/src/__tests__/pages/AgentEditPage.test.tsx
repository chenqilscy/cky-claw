import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

/* ---------- mock services ---------- */
const mockAgentGet = vi.fn();
const mockAgentList = vi.fn();
const mockAgentCreate = vi.fn();
const mockAgentUpdate = vi.fn();
const mockGuardrailList = vi.fn();
const mockToolGroupList = vi.fn();
const mockProviderList = vi.fn();

vi.mock('../../services/agentService', () => ({
  agentService: {
    get: (...args: unknown[]) => mockAgentGet(...args),
    list: (...args: unknown[]) => mockAgentList(...args),
    create: (...args: unknown[]) => mockAgentCreate(...args),
    update: (...args: unknown[]) => mockAgentUpdate(...args),
  },
}));

vi.mock('../../services/guardrailService', () => ({
  guardrailService: {
    list: (...args: unknown[]) => mockGuardrailList(...args),
  },
}));

vi.mock('../../services/toolGroupService', () => ({
  toolGroupService: {
    list: (...args: unknown[]) => mockToolGroupList(...args),
  },
}));

vi.mock('../../services/providerService', () => ({
  providerService: {
    list: (...args: unknown[]) => mockProviderList(...args),
  },
}));

import AgentEditPage from '../../pages/agents/AgentEditPage';

function renderWithRouter(path: string, routePath: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={<AgentEditPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('AgentEditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGuardrailList.mockResolvedValue({ data: [] });
    mockToolGroupList.mockResolvedValue({ data: [] });
    mockAgentList.mockResolvedValue({ data: [] });
    mockProviderList.mockResolvedValue({ data: [] });
    mockAgentGet.mockResolvedValue({
      name: 'bot-1', description: 'desc', instructions: 'test',
      model: 'gpt-4', approval_mode: 'suggest',
      guardrails: { input: [], output: [], tool: [] },
      tool_groups: [], handoffs: [], agent_tools: [],
    });
    mockAgentCreate.mockResolvedValue({});
    mockAgentUpdate.mockResolvedValue({});
  });

  it('创建模式渲染标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderWithRouter('/agents/new', '/agents/new'));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('创建新 Agent');
  });

  it('编辑模式渲染标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderWithRouter('/agents/bot-1/edit', '/agents/:name/edit'));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('编辑 Agent');
  });

  it('渲染表单字段', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderWithRouter('/agents/new', '/agents/new'));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('名称');
    expect(text).toContain('系统指令');
    expect(text).toContain('审批模式');
  });

  it('编辑模式加载 Agent 详情', async () => {
    await act(async () => {
      renderWithRouter('/agents/bot-1/edit', '/agents/:name/edit');
    });
    expect(mockAgentGet).toHaveBeenCalledWith('bot-1');
  });

  it('加载下拉选项', async () => {
    await act(async () => {
      renderWithRouter('/agents/new', '/agents/new');
    });
    expect(mockGuardrailList).toHaveBeenCalled();
    expect(mockToolGroupList).toHaveBeenCalled();
    expect(mockProviderList).toHaveBeenCalled();
  });
});
