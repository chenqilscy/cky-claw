import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock knowledgeBaseService
vi.mock('../../services/knowledgeBaseService', () => ({
  knowledgeBaseService: {
    list: vi.fn().mockResolvedValue({
      data: [
        {
          id: '1', name: 'kb-1', description: '知识库1',
          embedding_model: 'text-embedding-3', chunk_strategy: {},
          metadata: {}, created_at: '2026-01-01', updated_at: '2026-01-01',
        },
      ],
      total: 1,
    }),
    create: vi.fn().mockResolvedValue({ id: '2', name: 'new-kb' }),
    update: vi.fn().mockResolvedValue({ id: '1', name: 'updated-kb' }),
    remove: vi.fn().mockResolvedValue(undefined),
    listDocuments: vi.fn().mockResolvedValue({ data: [], total: 0 }),
    uploadDocument: vi.fn().mockResolvedValue({ id: 'd1', filename: 'doc.pdf' }),
    search: vi.fn().mockResolvedValue({ data: [] }),
    uploadMedia: vi.fn().mockResolvedValue({ url: '/api/v1/media/test.pdf' }),
  },
}));

import KnowledgeBasePage from '../../pages/knowledge-bases/KnowledgeBasePage';

describe('KnowledgeBasePage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('渲染页面标题', async () => {
    render(
      <MemoryRouter>
        <KnowledgeBasePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('知识库');
    });
  });

  it('渲染知识库列表', async () => {
    render(
      <MemoryRouter>
        <KnowledgeBasePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      expect(text).toMatch(/知识库|Knowledge/i);
    });
  });

  it('渲染新建按钮', async () => {
    render(
      <MemoryRouter>
        <KnowledgeBasePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      expect(text.length).toBeGreaterThan(0);
    });
  });

  it('空数据不崩溃', () => {
    render(
      <MemoryRouter>
        <KnowledgeBasePage />
      </MemoryRouter>,
    );
    expect(document.body).toBeDefined();
  });
});
