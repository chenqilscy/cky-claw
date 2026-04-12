import { api } from './api';

export interface KnowledgeBaseItem {
  id: string;
  name: string;
  description: string;
  embedding_model: string;
  chunk_strategy: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentItem {
  id: string;
  knowledge_base_id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  status: string;
  chunk_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseListResponse {
  data: KnowledgeBaseItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface KnowledgeSearchResultItem {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface KnowledgeSearchResponse {
  knowledge_base_id: string;
  query: string;
  results: KnowledgeSearchResultItem[];
}

export interface MediaUploadResponse {
  url: string;
  filename: string;
  media_type: string;
  size_bytes: number;
}

export const knowledgeBaseService = {
  list: (params?: { limit?: number; offset?: number }) =>
    api.get<KnowledgeBaseListResponse>('/knowledge-bases', params),

  create: (payload: { name: string; description?: string; embedding_model?: string; chunk_strategy?: Record<string, unknown> }) =>
    api.post<KnowledgeBaseItem>('/knowledge-bases', payload),

  update: (id: string, payload: Partial<{ name: string; description: string; embedding_model: string; chunk_strategy: Record<string, unknown> }>) =>
    api.put<KnowledgeBaseItem>(`/knowledge-bases/${id}`, payload),

  remove: (id: string) =>
    api.delete<void>(`/knowledge-bases/${id}`),

  listDocuments: (id: string) =>
    api.get<KnowledgeDocumentItem[]>(`/knowledge-bases/${id}/documents`),

  uploadDocument: async (id: string, file: File): Promise<KnowledgeDocumentItem> => {
    const form = new FormData();
    form.append('file', file);
    const token = localStorage.getItem('ckyclaw_token');
    const response = await fetch(`/api/v1/knowledge-bases/${id}/documents`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
    if (!response.ok) {
      throw new Error(`上传失败: ${response.status}`);
    }
    return response.json();
  },

  search: (id: string, payload: { query: string; top_k?: number; min_score?: number }) =>
    api.post<KnowledgeSearchResponse>(`/knowledge-bases/${id}/search`, payload),

  uploadMedia: async (file: File): Promise<MediaUploadResponse> => {
    const form = new FormData();
    form.append('file', file);
    const token = localStorage.getItem('ckyclaw_token');
    const response = await fetch('/api/v1/media/upload', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
    if (!response.ok) {
      throw new Error(`上传失败: ${response.status}`);
    }
    return response.json();
  },
};
