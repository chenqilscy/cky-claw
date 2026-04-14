import { useCallback, useState } from 'react';
import { Button, Drawer, Grid, Layout, theme } from 'antd';
import { MenuOutlined } from '@ant-design/icons';
import ChatSidebar from './ChatSidebar';
import ChatWindow from './ChatWindow';

const { Sider, Content } = Layout;
const { useBreakpoint } = Grid;

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agentName?: string;
  timestamp: number;
  streaming?: boolean;
}

const ChatPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [agentName, setAgentName] = useState<string>('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const screens = useBreakpoint();
  const { token } = theme.useToken();
  const isMobile = !screens.md;

  const handleSessionCreated = useCallback((sid: string) => {
    setSessionId(sid);
    setRefreshKey((k) => k + 1);
  }, []);

  const sidebarContent = (
    <ChatSidebar
      currentSessionId={sessionId}
      refreshKey={refreshKey}
      onSelectSession={(sid, agent) => {
        setSessionId(sid);
        setAgentName(agent);
        if (isMobile) setDrawerOpen(false);
      }}
      onNewSession={(agent) => {
        setSessionId(null);
        setAgentName(agent);
        if (isMobile) setDrawerOpen(false);
      }}
    />
  );

  return (
    <Layout style={{ height: '100%', minHeight: 'calc(100vh - 56px)' }}>
      {isMobile ? (
        <>
          <Button
            icon={<MenuOutlined />}
            type="text"
            onClick={() => setDrawerOpen(true)}
            style={{ position: 'absolute', left: 8, top: 8, zIndex: 10 }}
          />
          <Drawer
            placement="left"
            width={280}
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            styles={{ body: { padding: 0 } }}
            forceRender
          >
            {sidebarContent}
          </Drawer>
        </>
      ) : (
        <Sider
          width={280}
          theme="light"
          style={{ borderRight: `1px solid ${token.colorBorderSecondary}`, overflow: 'auto' }}
        >
          {sidebarContent}
        </Sider>
      )}
      <Content style={{ display: 'flex', flexDirection: 'column' }}>
        <ChatWindow
          sessionId={sessionId}
          agentName={agentName}
          onSessionCreated={handleSessionCreated}
        />
      </Content>
    </Layout>
  );
};

export default ChatPage;
