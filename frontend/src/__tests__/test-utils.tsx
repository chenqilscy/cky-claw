/**
 * 测试工具：为需要 TanStack Query 的组件提供 QueryClientProvider 包装。
 */
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

/**
 * 创建一个不重试、不 GC 的测试用 QueryClient。
 */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

/**
 * 包装组件，提供 QueryClientProvider。
 * 用法：render(<TestQueryWrapper><MyPage /></TestQueryWrapper>)
 */
export function TestQueryWrapper({ children }: { children: React.ReactNode }) {
  const queryClient = React.useMemo(() => createTestQueryClient(), []);
  return (
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </MemoryRouter>
  );
}
