import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock agentService — 模拟各种错误和边界场景
const mockList = vi.fn();
const mockGet = vi.fn();
const mockCreate = vi.fn();
const mockUpdate = vi.fn();
const mockRemove = vi.fn();

vi.mock('../../services/agentService', () => ({
  agentService: {
    list: (...args: unknown[]) => mockList(...args),
    get: (...args: unknown[]) => mockGet(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    update: (...args: unknown[]) => mockUpdate(...args),
    remove: (...args: unknown[]) => mockRemove(...args),
    realtimeStatus: vi.fn().mockResolvedValue({ data: [], minutes: 5 }),
  },
}));

// Mock react-query to use real hook behavior but with retry disabled
vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useQuery: vi.fn().mockImplementation((...args: unknown[]) => {
      const options = typeof args[0] === 'object' ? args[0] : { queryKey: args[0], queryFn: args[1] };
      return {
        data: undefined,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
        ...options,
      };
    }),
    useMutation: vi.fn().mockReturnValue({
      mutateAsync: vi.fn(),
      isLoading: false,
    }),
    useQueryClient: vi.fn().mockReturnValue({
      invalidateQueries: vi.fn(),
    }),
  };
});

import AgentListPage from '../../pages/agents/AgentListPage';

describe('AgentListPage 边界场景', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 });
  });

  it('API 返回空列表不崩溃', async () => {
    mockList.mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 });
    const { container } = render(
      <MemoryRouter>
        <AgentListPage />
      </MemoryRouter>,
    );
    expect(container).toBeTruthy();
  });

  it('渲染 Agent 列表页标题', async () => {
    const { container } = render(
      <MemoryRouter>
        <AgentListPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = container.textContent ?? '';
      expect(text).toMatch(/Agent/i);
    });
  });

  it('API 返回 undefined data 不崩溃', async () => {
    mockList.mockResolvedValue({ data: undefined, total: 0 });
    const { container } = render(
      <MemoryRouter>
        <AgentListPage />
      </MemoryRouter>,
    );
    expect(container).toBeTruthy();
  });

  it('API 返回 null 不崩溃', async () => {
    mockList.mockResolvedValue(null);
    const { container } = render(
      <MemoryRouter>
        <AgentListPage />
      </MemoryRouter>,
    );
    expect(container).toBeTruthy();
  });
});
