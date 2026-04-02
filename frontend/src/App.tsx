import { Routes, Route, Navigate } from 'react-router-dom';
import BasicLayout from './layouts/BasicLayout';
import LoginPage from './pages/Login';
import ChatPage from './pages/chat/ChatPage';
import AgentListPage from './pages/agents/AgentListPage';
import AgentEditPage from './pages/agents/AgentEditPage';
import RunListPage from './pages/runs/RunListPage';
import SupervisionPage from './pages/supervision/SupervisionPage';
import ProviderListPage from './pages/providers/ProviderListPage';
import ProviderEditPage from './pages/providers/ProviderEditPage';
import useAuthStore from './stores/authStore';

const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = useAuthStore((s) => s.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
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
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="agents" element={<AgentListPage />} />
        <Route path="agents/new" element={<AgentEditPage />} />
        <Route path="agents/:name/edit" element={<AgentEditPage />} />
        <Route path="runs" element={<RunListPage />} />
        <Route path="supervision" element={<SupervisionPage />} />
        <Route path="providers" element={<ProviderListPage />} />
        <Route path="providers/new" element={<ProviderEditPage />} />
        <Route path="providers/:id/edit" element={<ProviderEditPage />} />
      </Route>
    </Routes>
  );
};

export default App;
