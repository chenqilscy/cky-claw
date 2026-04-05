import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, Spin, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import BasicLayout from './layouts/BasicLayout';
import useAuthStore from './stores/authStore';
import useThemeStore from './stores/themeStore';

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
const WorkflowPage = lazy(() => import('./pages/workflows/WorkflowPage'));
const WorkflowEditorPage = lazy(() => import('./pages/workflows/WorkflowEditorPage'));
const TeamPage = lazy(() => import('./pages/teams/TeamPage'));
const TeamFlowPage = lazy(() => import('./pages/teams/TeamFlowPage'));
const AuditLogPage = lazy(() => import('./pages/audit-logs/AuditLogPage'));
const RolePage = lazy(() => import('./pages/roles/RolePage'));
const IMChannelPage = lazy(() => import('./pages/im-channels/IMChannelPage'));
const EvaluationPage = lazy(() => import('./pages/evaluations/EvaluationPage'));
const OrganizationPage = lazy(() => import('./pages/organizations/OrganizationPage'));
const ScheduledTasksPage = lazy(() => import('./pages/scheduled-tasks/ScheduledTasksPage'));
const ApmDashboardPage = lazy(() => import('./pages/apm/ApmDashboardPage'));
const I18nSettingsPage = lazy(() => import('./pages/agents/I18nSettingsPage'));
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
  const themeMode = useThemeStore((s) => s.mode);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{ algorithm: themeMode === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm }}
    >
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
          <Route path="workflows" element={<WorkflowPage />} />
          <Route path="workflow-editor" element={<WorkflowEditorPage />} />
          <Route path="teams" element={<TeamPage />} />
          <Route path="teams/flow" element={<TeamFlowPage />} />
          <Route path="audit-logs" element={<AuditLogPage />} />
          <Route path="roles" element={<RolePage />} />
          <Route path="im-channels" element={<IMChannelPage />} />
          <Route path="evaluations" element={<EvaluationPage />} />
          <Route path="organizations" element={<OrganizationPage />} />
          <Route path="scheduled-tasks" element={<ScheduledTasksPage />} />
          <Route path="apm" element={<ApmDashboardPage />} />
          <Route path="i18n" element={<I18nSettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
    </ConfigProvider>
  );
};

export default App;
