import { api } from './api';

export interface KnowledgeBaseItem {
  id: string;
  name: string;
  description: string;
  embedding_model: string;
  chunk_strategy: Record<string, unknown>;
  metadata: Record<string, unknown>;
  mode?: string;
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

// --- Graph types ---

export interface GraphBuildStatus {
  task_id: string;
  status: string;
  progress: number;
  entity_count: number;
  relation_count: number;
  community_count: number;
  error: string | null;
}

export interface GraphEntityItem {
  id: string;
  knowledge_base_id: string;
  document_id: string;
  name: string;
  entity_type: string;
  description: string;
  attributes: Record<string, unknown>;
  confidence: number;
  confidence_label: string;
  content_hash: string;
  created_at: string;
}

export interface GraphRelationItem {
  id: string;
  knowledge_base_id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation_type: string;
  description: string;
  weight: number;
  confidence: number;
  confidence_label: string;
}

export interface GraphCommunityItem {
  id: string;
  knowledge_base_id: string;
  name: string;
  summary: string;
  entity_count: number;
  level: number;
  parent_community_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface GraphDataResponse {
  nodes: { id: string; label: string; type: string; confidence?: number }[];
  edges: { source: string; target: string; type: string; weight: number }[];
}

export interface GraphSearchResultItem {
  entity?: { id: string; name: string; entity_type: string; description: string; confidence?: number; confidence_label?: string };
  relation?: { id: string; source_entity_id: string; target_entity_id: string; relation_type: string; description: string; weight: number };
  community?: { id: string; name: string; summary: string; level: number };
  score: number;
  source: string;
}

export interface GraphSearchResponse {
  knowledge_base_id: string;
  query: string;
  results: GraphSearchResultItem[];
}

export const knowledgeBaseService = {
  list: (params?: { limit?: number; offset?: number }) =>
    api.get<KnowledgeBaseListResponse>('/knowledge-bases', params),

  create: (payload: { name: string; description?: string; embedding_model?: string; chunk_strategy?: Record<string, unknown>; mode?: string }) =>
    api.post<KnowledgeBaseItem>('/knowledge-bases', payload),

  update: (id: string, payload: Partial<{ name: string; description: string; embedding_model: string; chunk_strategy: Record<string, unknown>; mode: string }>) =>
    api.put<KnowledgeBaseItem>(`/knowledge-bases/${id}`, payload),

  remove: async (id: string): Promise<void> => {
    await api.delete(`/knowledge-bases/${id}`);
  },

  listDocuments: (id: string) =>
    api.get<KnowledgeDocumentItem[]>(`/knowledge-bases/${id}/documents`),

  uploadDocument: async (id: string, file: File): Promise<KnowledgeDocumentItem> => {
    const form = new FormData();
    form.append('file', file);
    const token = localStorage.getItem('kasaya_token');
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
    const token = localStorage.getItem('kasaya_token');
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

  // --- Graph APIs ---

  buildGraph: (id: string, payload: { extract_model?: string; entity_types?: string[]; chunk_size?: number; overlap?: number; resolution?: number }) =>
    api.post<{ task_id: string; status: string }>(`/knowledge-bases/${id}/build-graph`, payload),

  getGraphStatus: (id: string, taskId: string) =>
    api.get<GraphBuildStatus>(`/knowledge-bases/${id}/graph-status`, { task_id: taskId }),

  getGraphData: (id: string, maxNodes?: number) =>
    api.get<GraphDataResponse>(`/knowledge-bases/${id}/graph`, { max_nodes: maxNodes ?? 200 }),

  listEntities: (id: string, params?: { name_contains?: string; entity_type?: string; limit?: number; offset?: number }) =>
    api.get<{ data: GraphEntityItem[]; total: number; limit: number; offset: number }>(`/knowledge-bases/${id}/entities`, params),

  listRelations: (id: string, params?: { relation_type?: string; limit?: number; offset?: number }) =>
    api.get<{ data: GraphRelationItem[]; total: number; limit: number; offset: number }>(`/knowledge-bases/${id}/relations`, params),

  listCommunities: (id: string, params?: { level?: number; limit?: number; offset?: number }) =>
    api.get<{ data: GraphCommunityItem[]; total: number; limit: number; offset: number }>(`/knowledge-bases/${id}/communities`, params),

  graphSearch: (id: string, payload: { query: string; top_k?: number; max_depth?: number; search_mode?: string }) =>
    api.post<GraphSearchResponse>(`/knowledge-bases/${id}/graph-search`, payload),

  deleteGraph: (id: string) =>
    api.delete<{ deleted_count: number }>(`/knowledge-bases/${id}/graph`),
};
