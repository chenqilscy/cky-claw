/**
 * TanStack Query hooks — MCP Server 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { mcpServerService } from '../services/mcpServerService';
import type {
  MCPServerCreateRequest,
  MCPServerUpdateRequest,
  MCPServerListParams,
} from '../services/mcpServerService';

const KEY = ['mcp-servers'] as const;

export function useMCPServerList(params?: MCPServerListParams) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => mcpServerService.list(params),
  });
}

export function useMCPServer(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => mcpServerService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateMCPServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MCPServerCreateRequest) => mcpServerService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateMCPServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MCPServerUpdateRequest }) =>
      mcpServerService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteMCPServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => mcpServerService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useTestMCPConnection() {
  return useMutation({
    mutationFn: (id: string) => mcpServerService.testConnection(id),
  });
}
