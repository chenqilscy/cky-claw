import { api } from './api';

export interface MarketplaceTemplate {
  id: string;
  name: string;
  display_name: string;
  description: string;
  category: string;
  icon: string;
  published: boolean;
  downloads: number;
  rating: number;
  rating_count: number;
  author_org_id: string | null;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface MarketplaceListResponse {
  data: MarketplaceTemplate[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarketplaceReview {
  id: string;
  template_id: string;
  user_id: string;
  score: number;
  comment: string;
  created_at: string;
}

export interface ReviewListResponse {
  data: MarketplaceReview[];
  total: number;
}

export const marketplaceService = {
  async browse(params?: Record<string, string | number | undefined>): Promise<MarketplaceListResponse> {
    return api.get('/api/v1/marketplace', params);
  },

  async getTemplate(id: string): Promise<MarketplaceTemplate> {
    return api.get(`/api/v1/marketplace/${id}`);
  },

  async publish(templateId: string): Promise<MarketplaceTemplate> {
    return api.post('/api/v1/marketplace/publish', { template_id: templateId });
  },

  async unpublish(templateId: string): Promise<MarketplaceTemplate> {
    return api.post('/api/v1/marketplace/unpublish', { template_id: templateId });
  },

  async install(templateId: string, agentName: string): Promise<{ config: Record<string, unknown> }> {
    return api.post(`/api/v1/marketplace/${templateId}/install`, { agent_name: agentName });
  },

  async submitReview(templateId: string, score: number, comment: string): Promise<MarketplaceReview> {
    return api.post(`/api/v1/marketplace/${templateId}/reviews`, { score, comment });
  },

  async listReviews(templateId: string): Promise<ReviewListResponse> {
    return api.get(`/api/v1/marketplace/${templateId}/reviews`);
  },
};
