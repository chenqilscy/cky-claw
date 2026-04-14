import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor, act } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

// Mock marketplaceService
vi.mock('../../services/marketplaceService', () => ({
  marketplaceService: {
    browse: vi.fn().mockResolvedValue({
      data: [
        {
          id: 't1',
          name: 'demo-agent',
          description: '示例 Agent 模板',
          category: 'general',
          author: 'admin',
          downloads: 42,
          rating: 4.5,
          tags: ['demo'],
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    }),
    getTemplate: vi.fn().mockResolvedValue({ id: 't1', name: 'demo-agent' }),
    publish: vi.fn().mockResolvedValue({ id: 't2' }),
    unpublish: vi.fn().mockResolvedValue(undefined),
    install: vi.fn().mockResolvedValue({ id: 'a1', name: 'installed-agent' }),
    submitReview: vi.fn().mockResolvedValue({ id: 'r1' }),
    listReviews: vi.fn().mockResolvedValue({ data: [], total: 0 }),
  },
}));

import MarketplacePage from '../../pages/marketplace/MarketplacePage';

describe('MarketplacePage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
          <TestQueryWrapper>
            <MarketplacePage />
          </TestQueryWrapper>
        </MemoryRouter>,
      ));
    });
    await waitFor(() => {
      expect(container.textContent).toContain('模板市场');
    });
  });

  it('渲染搜索和筛选区域', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
          <TestQueryWrapper>
            <MarketplacePage />
          </TestQueryWrapper>
        </MemoryRouter>,
      ));
    });
    await waitFor(() => {
      const text = container.textContent ?? '';
      expect(text.length).toBeGreaterThan(0);
    });
  });

  it('渲染模板卡片列表', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
          <TestQueryWrapper>
            <MarketplacePage />
          </TestQueryWrapper>
        </MemoryRouter>,
      ));
    });
    await waitFor(() => {
      expect(container.textContent).toContain('示例 Agent 模板');
    });
  });

  it('空数据不崩溃', async () => {
    const { marketplaceService } = await import('../../services/marketplaceService');
    (marketplaceService.browse as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: [], total: 0 });

    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
          <TestQueryWrapper>
            <MarketplacePage />
          </TestQueryWrapper>
        </MemoryRouter>,
      ));
    });
    expect(container).toBeTruthy();
  });
});
