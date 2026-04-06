import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { api } from '../services/api';
import { evolutionService } from '../services/evolutionService';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('evolutionService', () => {
  beforeEach(() => vi.clearAllMocks());

  describe('list', () => {
    it('calls GET /evolution/proposals', async () => {
      mockApi.get.mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 });
      const res = await evolutionService.list();
      expect(mockApi.get).toHaveBeenCalledWith('/evolution/proposals', {});
      expect(res.total).toBe(0);
    });

    it('passes filter params', async () => {
      mockApi.get.mockResolvedValue({ data: [], total: 0, limit: 10, offset: 0 });
      await evolutionService.list({
        agent_name: 'bot',
        proposal_type: 'tools',
        status: 'pending',
        limit: 10,
        offset: 5,
      });
      expect(mockApi.get).toHaveBeenCalledWith('/evolution/proposals', {
        agent_name: 'bot',
        proposal_type: 'tools',
        status: 'pending',
        limit: 10,
        offset: 5,
      });
    });

    it('ignores empty params', async () => {
      mockApi.get.mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 });
      await evolutionService.list({ agent_name: '', proposal_type: '' });
      expect(mockApi.get).toHaveBeenCalledWith('/evolution/proposals', {});
    });
  });

  describe('get', () => {
    it('calls GET /evolution/proposals/:id', async () => {
      mockApi.get.mockResolvedValue({ id: 'abc', agent_name: 'bot' });
      const res = await evolutionService.get('abc');
      expect(mockApi.get).toHaveBeenCalledWith('/evolution/proposals/abc');
      expect(res.agent_name).toBe('bot');
    });
  });

  describe('create', () => {
    it('calls POST /evolution/proposals', async () => {
      const payload = { agent_name: 'bot', proposal_type: 'instructions' };
      mockApi.post.mockResolvedValue({ id: 'new', ...payload });
      const res = await evolutionService.create(payload);
      expect(mockApi.post).toHaveBeenCalledWith('/evolution/proposals', payload);
      expect(res.id).toBe('new');
    });
  });

  describe('update', () => {
    it('calls PUT /evolution/proposals/:id', async () => {
      const payload = { status: 'approved' };
      mockApi.put.mockResolvedValue({ id: 'x', status: 'approved' });
      const res = await evolutionService.update('x', payload);
      expect(mockApi.put).toHaveBeenCalledWith('/evolution/proposals/x', payload);
      expect(res.status).toBe('approved');
    });
  });

  describe('delete', () => {
    it('calls DELETE /evolution/proposals/:id', async () => {
      mockApi.delete.mockResolvedValue(undefined);
      await evolutionService.delete('x');
      expect(mockApi.delete).toHaveBeenCalledWith('/evolution/proposals/x');
    });
  });
});
