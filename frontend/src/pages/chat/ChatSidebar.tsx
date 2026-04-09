import { useEffect, useState } from 'react';
import { Button, Divider, List, Select, Typography, App, theme } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { agentService } from '../../services/agentService';
import { chatService } from '../../services/chatService';
import type { AgentConfig } from '../../services/agentService';
import type { ChatSession } from '../../services/chatService';

const { Text } = Typography;

interface ChatSidebarProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string, agentName: string) => void;
  onNewSession: (agentName: string) => void;
}

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  currentSessionId,
  onSelectSession,
  onNewSession,
}) => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);

  // 加载 Agent 列表
  useEffect(() => {
    agentService.list({ limit: 100 })
      .then((res) => {
        setAgents(res.data);
        const first = res.data[0];
        if (first && !selectedAgent) {
          setSelectedAgent(first.name);
        }
      })
      .catch(() => message.error('加载 Agent 列表失败'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 加载会话列表
  useEffect(() => {
    if (!selectedAgent) return;
    setLoadingSessions(true);
    chatService.listSessions({ agent_name: selectedAgent, limit: 50 })
      .then((res) => setSessions(res.data))
      .catch(() => message.error('加载会话列表失败'))
      .finally(() => setLoadingSessions(false));
  }, [selectedAgent, message]);

  const handleNewSession = () => {
    if (!selectedAgent) {
      message.warning('请先选择一个 Agent');
      return;
    }
    onNewSession(selectedAgent);
  };

  return (
    <div style={{ padding: '12px 8px' }}>
      <Text strong style={{ display: 'block', marginBottom: 8 }}>选择 Agent</Text>
      <Select
        value={selectedAgent || undefined}
        onChange={(v) => setSelectedAgent(v)}
        placeholder="选择 Agent"
        style={{ width: '100%', marginBottom: 12 }}
        options={agents.map((a) => ({ label: a.name, value: a.name }))}
      />

      <Button
        type="dashed"
        icon={<PlusOutlined />}
        block
        onClick={handleNewSession}
        style={{ marginBottom: 12 }}
      >
        新建对话
      </Button>

      <Divider style={{ margin: '8px 0' }} />
      <Text type="secondary" style={{ fontSize: 12 }}>历史对话</Text>

      <List
        size="small"
        loading={loadingSessions}
        dataSource={sessions}
        locale={{ emptyText: '暂无对话' }}
        renderItem={(item) => (
          <List.Item
            onClick={() => onSelectSession(item.id, item.agent_name)}
            style={{
              cursor: 'pointer',
              padding: '8px 12px',
              borderRadius: 6,
              background: item.id === currentSessionId ? token.colorPrimaryBg : undefined,
            }}
          >
            <div style={{ width: '100%', overflow: 'hidden' }}>
              <Text ellipsis style={{ display: 'block', fontSize: 13 }}>
                {item.title || item.agent_name}
              </Text>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {new Date(item.created_at).toLocaleString('zh-CN')}
              </Text>
            </div>
          </List.Item>
        )}
      />
    </div>
  );
};

export default ChatSidebar;
