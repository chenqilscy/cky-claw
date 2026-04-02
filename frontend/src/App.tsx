import { Routes, Route, Navigate } from 'react-router-dom';
import BasicLayout from './layouts/BasicLayout';
import LoginPage from './pages/Login';

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<BasicLayout />}>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<div>对话页（待实现）</div>} />
        <Route path="agents" element={<div>Agent 管理页（待实现）</div>} />
        <Route path="runs" element={<div>执行记录页（待实现）</div>} />
      </Route>
    </Routes>
  );
};

export default App;
