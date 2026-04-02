import { Routes, Route, Navigate } from 'react-router-dom';
import BasicLayout from './layouts/BasicLayout';
import LoginPage from './pages/Login';
import ChatPage from './pages/chat/ChatPage';
import AgentListPage from './pages/agents/AgentListPage';
import AgentEditPage from './pages/agents/AgentEditPage';
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
        <Route path="runs" element={<div>执行记录页（待实现）</div>} />
      </Route>
    </Routes>
  );
};

export default App;
