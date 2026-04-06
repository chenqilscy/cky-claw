import { api } from './api';

export interface ClassifyRequest {
  text: string;
}

export interface ClassifyResponse {
  tier: string;
  text_length: number;
}

export interface RecommendResponse {
  tier: string;
  provider_name: string | null;
  provider_tier: string | null;
}

export const costRouterService = {
  classify: (data: ClassifyRequest) =>
    api.post<ClassifyResponse>('/cost-router/classify', data),

  recommend: (data: ClassifyRequest, capability?: string[]) => {
    let path = '/cost-router/recommend';
    if (capability && capability.length > 0) {
      const params = capability.map((c) => `capability=${encodeURIComponent(c)}`).join('&');
      path += `?${params}`;
    }
    return api.post<RecommendResponse>(path, data);
  },
};
