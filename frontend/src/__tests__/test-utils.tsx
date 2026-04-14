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
 * 包装组件，提供 QueryClientProvider + MemoryRouter。
 * 用法：render(<TestQueryWrapper><MyPage /></TestQueryWrapper>)
 * 若测试自行提供 MemoryRouter（如需 initialEntries），传 withRouter={false}。
 */
export function TestQueryWrapper({
  children,
  withRouter = true,
}: {
  children: React.ReactNode;
  withRouter?: boolean;
}) {
  const queryClient = React.useMemo(() => createTestQueryClient(), []);
  const content = (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
  return withRouter ? <MemoryRouter>{content}</MemoryRouter> : content;
}
