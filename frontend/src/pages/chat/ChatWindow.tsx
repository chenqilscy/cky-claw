import { useEffect, useRef, useState } from 'react';
import { Button, Input, Space, Spin, Typography, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { chatService } from '../../services/chatService';
import type { ChatMessage } from './ChatPage';

const { Text } = Typography;

interface ChatWindowProps {
  sessionId: string | null;
  agentName: string;
  onSessionCreated: (sessionId: string) => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({
  sessionId,
  agentName,
  onSessionCreated,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // session 切换时清消息
  useEffect(() => {
    setMessages([]);
  }, [sessionId, agentName]);

  // 组件卸载时中止 SSE
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    if (!agentName) {
      message.warning('请先选择一个 Agent');
      return;
    }

    setInput('');
    setSending(true);

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      // 如果没有 session，先创建
      let sid = sessionId;
      if (!sid) {
        const session = await chatService.createSession(agentName);
        sid = session.id;
        onSessionCreated(sid);
      }

      // 添加一条空的 assistant 消息用于流式填充
      const assistantMsgId = `assistant-${Date.now()}`;
      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        agentName,
        timestamp: Date.now(),
        streaming: true,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // SSE 流式请求
      const controller = chatService.runStream(
        sid,
        text,
        (event) => {
          if (event.type === 'text_delta') {
            const delta = (event.data as { delta?: string }).delta || '';
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + delta }
                  : m
              )
            );
          } else if (event.type === 'agent_start') {
            const name = (event.data as { agent_name?: string }).agent_name;
            if (name) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId ? { ...m, agentName: name } : m
                )
              );
            }
          } else if (event.type === 'run_end') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, streaming: false } : m
              )
            );
          } else if (event.type === 'error') {
            const errMsg = (event.data as { message?: string }).message || '执行出错';
            message.error(errMsg);
          }
        },
        () => {
          setSending(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, streaming: false } : m
            )
          );
        },
        () => {
          setSending(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, streaming: false } : m
            )
          );
        },
      );
      abortRef.current = controller;
    } catch {
      message.error('发送失败');
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 顶栏 */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fff',
      }}>
        <Text strong>{agentName || '请选择 Agent'}</Text>
      </div>

      {/* 消息列表 */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '16px',
        background: '#fafafa',
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: 80, color: '#999' }}>
            {agentName ? '发送消息开始对话' : '请从左侧选择 Agent 并创建对话'}
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              marginBottom: 12,
            }}
          >
            <div style={{
              maxWidth: '70%',
              padding: '10px 14px',
              borderRadius: 12,
              background: msg.role === 'user' ? '#1677ff' : '#fff',
              color: msg.role === 'user' ? '#fff' : '#000',
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {msg.agentName && msg.role === 'assistant' && (
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                  {msg.agentName}
                </Text>
              )}
              {msg.content}
              {msg.streaming && <Spin size="small" style={{ marginLeft: 8 }} />}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区 */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid #f0f0f0',
        background: '#fff',
      }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={agentName ? '输入消息...' : '请先选择 Agent'}
            disabled={!agentName || sending}
            autoSize={{ minRows: 1, maxRows: 4 }}
            style={{ resize: 'none' }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={sending}
            disabled={!agentName || !input.trim()}
          />
        </Space.Compact>
      </div>
    </div>
  );
};

export default ChatWindow;
