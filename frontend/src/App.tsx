import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, Spin, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import BasicLayout from './layouts/BasicLayout';
import RouteErrorBoundary from './components/RouteErrorBoundary';
import useAuthStore from './stores/authStore';
import useThemeStore from './stores/themeStore';

const LoginPage = lazy(() => import('./pages/Login'));
const DashboardPage = lazy(() => import('./pages/dashboard/DashboardPage'));
const ChatPage = lazy(() => import('./pages/chat/ChatPage'));
const AgentListPage = lazy(() => import('./pages/agents/AgentListPage'));
const AgentEditPage = lazy(() => import('./pages/agents/AgentEditPage'));
const AgentVersionPage = lazy(() => import('./pages/agents/AgentVersionPage'));
const HandoffEditorPage = lazy(() => import('./pages/agents/HandoffEditorPage'));
const VisualBuilderPage = lazy(() => import('./pages/agents/VisualBuilderPage'));
const A2APage = lazy(() => import('./pages/a2a/A2APage'));
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
const KnowledgeBasePage = lazy(() => import('./pages/knowledge-bases/KnowledgeBasePage'));
const WorkflowPage = lazy(() => import('./pages/workflows/WorkflowPage'));
const WorkflowEditorPage = lazy(() => import('./pages/workflows/WorkflowEditorPage'));
const TeamPage = lazy(() => import('./pages/teams/TeamPage'));
const TeamFlowPage = lazy(() => import('./pages/teams/TeamFlowPage'));
const AuditLogPage = lazy(() => import('./pages/audit-logs/AuditLogPage'));
const RolePage = lazy(() => import('./pages/roles/RolePage'));
const IMChannelPage = lazy(() => import('./pages/im-channels/IMChannelPage'));
const EvaluationPage = lazy(() => import('./pages/evaluations/EvaluationPage'));
const EvolutionPage = lazy(() => import('./pages/evolution/EvolutionPage'));
const OrganizationPage = lazy(() => import('./pages/organizations/OrganizationPage'));
const ScheduledTasksPage = lazy(() => import('./pages/scheduled-tasks/ScheduledTasksPage'));
const ApmDashboardPage = lazy(() => import('./pages/apm/ApmDashboardPage'));
const CostRouterPage = lazy(() => import('./pages/cost-router/CostRouterPage'));
const CheckpointPage = lazy(() => import('./pages/checkpoints/CheckpointPage'));
const IntentDetectionPage = lazy(() => import('./pages/intent/IntentDetectionPage'));
const ABTestPage = lazy(() => import('./pages/ab-test/ABTestPage'));
const DebugPage = lazy(() => import('./pages/debug/DebugPage'));
const EnvironmentListPage = lazy(() => import('./pages/environments/EnvironmentListPage'));
const EnvironmentDetailPage = lazy(() => import('./pages/environments/EnvironmentDetailPage'));
const I18nSettingsPage = lazy(() => import('./pages/agents/I18nSettingsPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const OAuthCallbackPage = lazy(() => import('./pages/oauth/OAuthCallbackPage'));

const PageLoading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
    <Spin size="large" />
  </div>
);

/** 为路由页面包裹错误边界 */
const guarded = (element: React.ReactNode) => (
  <RouteErrorBoundary>{element}</RouteErrorBoundary>
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
        <Route path="/oauth/callback/:provider" element={<OAuthCallbackPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <BasicLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={guarded(<DashboardPage />)} />
          <Route path="chat" element={guarded(<ChatPage />)} />
          <Route path="agents" element={guarded(<AgentListPage />)} />
          <Route path="agents/new" element={guarded(<AgentEditPage />)} />
          <Route path="agents/:name/edit" element={guarded(<AgentEditPage />)} />
          <Route path="agents/:agentId/versions" element={guarded(<AgentVersionPage />)} />
          <Route path="agents/handoff-editor" element={guarded(<HandoffEditorPage />)} />
          <Route path="agents/visual-builder" element={guarded(<VisualBuilderPage />)} />
          <Route path="runs" element={guarded(<RunListPage />)} />
          <Route path="supervision" element={guarded(<SupervisionPage />)} />
          <Route path="providers" element={guarded(<ProviderListPage />)} />
          <Route path="providers/new" element={guarded(<ProviderEditPage />)} />
          <Route path="providers/:id/edit" element={guarded(<ProviderEditPage />)} />
          <Route path="traces" element={guarded(<TracesPage />)} />
          <Route path="guardrails" element={guarded(<GuardrailRulesPage />)} />
          <Route path="approvals" element={guarded(<ApprovalQueuePage />)} />
          <Route path="mcp-servers" element={guarded(<MCPServerPage />)} />
          <Route path="tool-groups" element={guarded(<ToolGroupPage />)} />
          <Route path="memories" element={guarded(<MemoryPage />)} />
          <Route path="skills" element={guarded(<SkillPage />)} />
          <Route path="templates" element={guarded(<TemplatePage />)} />
          <Route path="knowledge-bases" element={guarded(<KnowledgeBasePage />)} />
          <Route path="workflows" element={guarded(<WorkflowPage />)} />
          <Route path="workflow-editor" element={guarded(<WorkflowEditorPage />)} />
          <Route path="teams" element={guarded(<TeamPage />)} />
          <Route path="teams/flow" element={guarded(<TeamFlowPage />)} />
          <Route path="audit-logs" element={guarded(<AuditLogPage />)} />
          <Route path="roles" element={guarded(<RolePage />)} />
          <Route path="im-channels" element={guarded(<IMChannelPage />)} />
          <Route path="evaluations" element={guarded(<EvaluationPage />)} />
          <Route path="evolution" element={guarded(<EvolutionPage />)} />
          <Route path="organizations" element={guarded(<OrganizationPage />)} />
          <Route path="scheduled-tasks" element={guarded(<ScheduledTasksPage />)} />
          <Route path="apm" element={guarded(<ApmDashboardPage />)} />
          <Route path="cost-router" element={guarded(<CostRouterPage />)} />
          <Route path="checkpoints" element={guarded(<CheckpointPage />)} />
          <Route path="intent" element={guarded(<IntentDetectionPage />)} />
          <Route path="ab-test" element={guarded(<ABTestPage />)} />
          <Route path="debug" element={guarded(<DebugPage />)} />
          <Route path="environments" element={guarded(<EnvironmentListPage />)} />
          <Route path="environments/:envName" element={guarded(<EnvironmentDetailPage />)} />
          <Route path="a2a" element={guarded(<A2APage />)} />
          <Route path="i18n" element={guarded(<I18nSettingsPage />)} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
    </ConfigProvider>
  );
};

export default App;
