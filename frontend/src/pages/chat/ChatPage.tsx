import { useState } from 'react';
import { Layout } from 'antd';
import ChatSidebar from './ChatSidebar';
import ChatWindow from './ChatWindow';

const { Sider, Content } = Layout;

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

  return (
    <Layout style={{ height: '100%', minHeight: 'calc(100vh - 56px)' }}>
      <Sider
        width={280}
        theme="light"
        style={{ borderRight: '1px solid #f0f0f0', overflow: 'auto' }}
      >
        <ChatSidebar
          currentSessionId={sessionId}
          onSelectSession={(sid, agent) => {
            setSessionId(sid);
            setAgentName(agent);
          }}
          onNewSession={(agent) => {
            setSessionId(null);
            setAgentName(agent);
          }}
        />
      </Sider>
      <Content style={{ display: 'flex', flexDirection: 'column' }}>
        <ChatWindow
          sessionId={sessionId}
          agentName={agentName}
          onSessionCreated={(sid) => setSessionId(sid)}
        />
      </Content>
    </Layout>
  );
};

export default ChatPage;
