import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Button, Input, Space, Spin, Tag, Typography, App, theme, Upload } from 'antd';
import { SendOutlined, ToolOutlined, SwapOutlined, PaperClipOutlined } from '@ant-design/icons';
import { chatService } from '../../services/chatService';
import { knowledgeBaseService } from '../../services/knowledgeBaseService';
import { useStreamReducer } from './useStreamReducer';
import { useResponsive } from '../../hooks/useResponsive';
import type { StreamMessage } from './useStreamReducer';

const MarkdownRenderer = lazy(() => import('../../components/MarkdownRenderer'));

const { Text } = Typography;

interface AttachedFile {
  filename: string;
  mediaType: string;
  url: string;
}

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
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const { isMobile } = useResponsive();
  const {
    messages,
    setMessages,
    appendUserMessage,
    createAssistantMessage,
    handleSSEEvent,
    finalizeStream,
    cancelPendingFlush,
  } = useStreamReducer();
  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // session 切换时加载历史消息
  useEffect(() => {
    setMessages([]);
    if (!sessionId) return;
    let cancelled = false;
    chatService.getMessages(sessionId).then((res) => {
      if (cancelled) return;
      const history = res.messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({
          id: `hist-${m.id}`,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          agentName: m.agent_name ?? undefined,
          timestamp: new Date(m.created_at).getTime(),
        }));
      setMessages(history);
    }).catch(() => {
      // 加载失败时静默，用户仍可正常发送消息
    });
    return () => { cancelled = true; };
  }, [sessionId, setMessages]);

  // 组件卸载时中止 SSE + 取消 RAF
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      cancelPendingFlush();
    };
  }, [cancelPendingFlush]);

  const handleSend = async () => {
    const text = input.trim();
    if ((!text && attachments.length === 0) || sending) return;
    if (!agentName) {
      message.warning('请先选择一个 Agent');
      return;
    }

    setInput('');
    setSending(true);

    const attachmentText = attachments
      .map((f) => (f.mediaType.startsWith('image/') ? `![${f.filename}](${f.url})` : `[文件: ${f.filename}](${f.url})`))
      .join('\n');
    const finalText = [text, attachmentText].filter(Boolean).join('\n\n');
    setAttachments([]);

    // 添加用户消息
    appendUserMessage(finalText);

    try {
      // 如果没有 session，先创建
      let sid = sessionId;
      if (!sid) {
        const session = await chatService.createSession(agentName);
        sid = session.id;
        onSessionCreated(sid);
      }

      // 添加一条空的 assistant 消息用于流式填充
      const assistantMsgId = createAssistantMessage(agentName);

      // SSE 流式请求（text_delta 通过 RAF 批处理优化）
      const controller = chatService.runStream(
        sid,
        finalText,
        (event) => {
          if (event.type === 'error') {
            const data = event.data as { code?: string; message?: string };
            const code = data.code || '';
            const errMsg = data.message || '执行出错';
            if (code === 'INPUT_GUARDRAIL_TRIGGERED' || code === 'OUTPUT_GUARDRAIL_TRIGGERED') {
              message.warning(errMsg);
            } else {
              message.error(errMsg);
            }
          } else {
            handleSSEEvent(assistantMsgId, event);
          }
        },
        () => {
          setSending(false);
          finalizeStream(assistantMsgId);
        },
        () => {
          setSending(false);
          finalizeStream(assistantMsgId);
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

  const handleUpload = async (file: File): Promise<boolean> => {
    try {
      setUploading(true);
      const uploaded = await knowledgeBaseService.uploadMedia(file);
      setAttachments((prev) => [
        ...prev,
        { filename: uploaded.filename, mediaType: uploaded.media_type, url: uploaded.url },
      ]);
      message.success(`${uploaded.filename} 上传成功`);
    } catch {
      message.error('附件上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 顶栏 */}
      <div style={{
        padding: '12px 16px',
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        background: token.colorBgContainer,
      }}>
        <Text strong>{agentName || '请选择 Agent'}</Text>
      </div>

      {/* 消息列表 */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '16px',
        background: token.colorBgLayout,
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: 80, color: token.colorTextDisabled }}>
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
              maxWidth: isMobile ? '85%' : '70%',
              padding: '10px 14px',
              borderRadius: 12,
              background: msg.role === 'user' ? token.colorPrimary : token.colorBgContainer,
              color: msg.role === 'user' ? token.colorTextLightSolid : token.colorText,
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
              whiteSpace: msg.role === 'user' ? 'pre-wrap' : undefined,
              wordBreak: 'break-word',
            }}>
              {msg.agentName && msg.role === 'assistant' && (
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                  {msg.agentName}
                </Text>
              )}
              {/* 工具调用状态标签 */}
              {(msg as StreamMessage).toolCalls && (msg as StreamMessage).toolCalls!.length > 0 && (
                <div style={{ marginBottom: 4 }}>
                  {(msg as StreamMessage).toolCalls!.map((tc, i) => (
                    <Tag
                      key={`${tc.name}-${i}`}
                      icon={tc.status === 'running' ? <ToolOutlined spin /> : <ToolOutlined />}
                      color={tc.status === 'running' ? 'processing' : 'success'}
                      style={{ marginBottom: 2 }}
                    >
                      {tc.name}
                    </Tag>
                  ))}
                </div>
              )}
              {/* Handoff 状态提示 */}
              {(msg as StreamMessage).statusText && (
                <div style={{ marginBottom: 4 }}>
                  <Tag icon={<SwapOutlined />} color="blue">
                    {(msg as StreamMessage).statusText}
                  </Tag>
                </div>
              )}
              {msg.role === 'assistant' ? (
                <Suspense fallback={<Spin size="small" />}>
                  <MarkdownRenderer content={msg.content} />
                </Suspense>
              ) : (
                msg.content
              )}
              {msg.streaming && <Spin size="small" style={{ marginLeft: 8 }} />}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区 */}
      <div style={{
        padding: '12px 16px',
        borderTop: `1px solid ${token.colorBorderSecondary}`,
        background: token.colorBgContainer,
      }}>
        {attachments.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            {attachments.map((f) => (
              <Tag
                key={`${f.url}-${f.filename}`}
                closable
                onClose={() => setAttachments((prev) => prev.filter((item) => item.url !== f.url))}
              >
                {f.filename}
              </Tag>
            ))}
          </div>
        )}
        <Space.Compact style={{ width: '100%' }}>
          <Upload beforeUpload={handleUpload} showUploadList={false} disabled={uploading || sending}>
            <Button icon={<PaperClipOutlined />} loading={uploading} disabled={!agentName || sending} />
          </Upload>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={agentName ? '输入消息，可上传图片/文件...' : '请先选择 Agent'}
            disabled={!agentName || sending}
            autoSize={{ minRows: 1, maxRows: 4 }}
            style={{ resize: 'none' }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={sending}
            disabled={!agentName || (!input.trim() && attachments.length === 0)}
          />
        </Space.Compact>
      </div>
    </div>
  );
};

export default ChatWindow;
