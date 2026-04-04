import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import BasicLayout from './layouts/BasicLayout';
import useAuthStore from './stores/authStore';

const LoginPage = lazy(() => import('./pages/Login'));
const DashboardPage = lazy(() => import('./pages/dashboard/DashboardPage'));
const ChatPage = lazy(() => import('./pages/chat/ChatPage'));
const AgentListPage = lazy(() => import('./pages/agents/AgentListPage'));
const AgentEditPage = lazy(() => import('./pages/agents/AgentEditPage'));
const AgentVersionPage = lazy(() => import('./pages/agents/AgentVersionPage'));
const HandoffEditorPage = lazy(() => import('./pages/agents/HandoffEditorPage'));
const RunListPage = lazy(() => import('./pages/runs/RunListPage'));
const SupervisionPage = lazy(() => import('./pages/supervision/SupervisionPage'));
const ProviderListPage = lazy(() => import('./pages/providers/ProviderListPage'));
const ProviderEditPage = lazy(() => import('./pages/providers/ProviderEditPage'));
const TracesPage = lazy(() => import('./pages/traces/TracesPage'));
const GuardrailRulesPage = lazy(() => import('./pages/guardrails/GuardrailRulesPage'));
const ApprovalQueuePage = lazy(() => import('./pages/approvals/ApprovalQueuePage'));
const MCPServerPage = lazy(() => import('./pages/mcp/MCPServerPage'));
const ToolGroupPage = lazy(() => import('./pages/tool-groups/ToolGroupPage'));
const MemoryPage = lazy(() => import('./pages/memories/MemoryPage'));
const SkillPage = lazy(() => import('./pages/skills/SkillPage'));
const TemplatePage = lazy(() => import('./pages/templates/TemplatePage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

const PageLoading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
    <Spin size="large" tip="加载中..." />
  </div>
);

const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = useAuthStore((s) => s.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <Suspense fallback={<PageLoading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <BasicLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="agents" element={<AgentListPage />} />
          <Route path="agents/new" element={<AgentEditPage />} />
          <Route path="agents/:name/edit" element={<AgentEditPage />} />
          <Route path="agents/:agentId/versions" element={<AgentVersionPage />} />
          <Route path="agents/handoff-editor" element={<HandoffEditorPage />} />
          <Route path="runs" element={<RunListPage />} />
          <Route path="supervision" element={<SupervisionPage />} />
          <Route path="providers" element={<ProviderListPage />} />
          <Route path="providers/new" element={<ProviderEditPage />} />
          <Route path="providers/:id/edit" element={<ProviderEditPage />} />
          <Route path="traces" element={<TracesPage />} />
          <Route path="guardrails" element={<GuardrailRulesPage />} />
          <Route path="approvals" element={<ApprovalQueuePage />} />
          <Route path="mcp-servers" element={<MCPServerPage />} />
          <Route path="tool-groups" element={<ToolGroupPage />} />
          <Route path="memories" element={<MemoryPage />} />
          <Route path="skills" element={<SkillPage />} />
          <Route path="templates" element={<TemplatePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
};

export default App;
