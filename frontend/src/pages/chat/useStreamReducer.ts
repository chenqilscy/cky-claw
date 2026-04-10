/**
 * useStreamReducer — 流式消息状态管理 Hook。
 *
 * 核心优化：
 * 1. text_delta 累积在 ref 中，通过 requestAnimationFrame 批量刷新到 state，
 *    将 re-render 频率从每 token 一次降至 ~60fps。
 * 2. 支持 tool_call_start/end、handoff、agent_end 等事件，提供完整执行反馈。
 */
import { useCallback, useRef, useState } from 'react';
import type { ChatMessage } from './ChatPage';
import type { SSEEvent } from '../../services/chatService';

/** 工具调用状态 */
export interface ToolCallInfo {
  name: string;
  status: 'running' | 'done';
  result?: string;
}

/** 扩展消息类型：增加 toolCalls 与 statusText */
export interface StreamMessage extends ChatMessage {
  toolCalls?: ToolCallInfo[];
  statusText?: string;
}

interface UseStreamReducerReturn {
  messages: StreamMessage[];
  setMessages: React.Dispatch<React.SetStateAction<StreamMessage[]>>;
  /** 创建用户消息并追加 */
  appendUserMessage: (text: string) => void;
  /** 创建空的 assistant 消息，返回其 id */
  createAssistantMessage: (agentName: string) => string;
  /** 处理 SSE 事件（内部自动 RAF 批处理） */
  handleSSEEvent: (msgId: string, event: SSEEvent) => void;
  /** 标记流式结束 */
  finalizeStream: (msgId: string) => void;
  /** 取消 RAF 定时器（组件卸载时调用） */
  cancelPendingFlush: () => void;
}

export function useStreamReducer(): UseStreamReducerReturn {
  const [messages, setMessages] = useState<StreamMessage[]>([]);

  // --- RAF 批处理 text_delta ---
  const pendingDeltaRef = useRef('');
  const rafIdRef = useRef(0);
  const activeMsgIdRef = useRef('');

  /** 调度一次 RAF 刷新 */
  const scheduleFlush = useCallback(() => {
    if (rafIdRef.current) return; // 已有调度
    rafIdRef.current = requestAnimationFrame(() => {
      rafIdRef.current = 0;
      const delta = pendingDeltaRef.current;
      if (!delta) return;
      pendingDeltaRef.current = '';
      const id = activeMsgIdRef.current;
      setMessages(prev =>
        prev.map(m => (m.id === id ? { ...m, content: m.content + delta } : m)),
      );
    });
  }, []);

  const cancelPendingFlush = useCallback(() => {
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = 0;
    }
    // 刷新残余
    const delta = pendingDeltaRef.current;
    if (delta) {
      pendingDeltaRef.current = '';
      const id = activeMsgIdRef.current;
      setMessages(prev =>
        prev.map(m => (m.id === id ? { ...m, content: m.content + delta } : m)),
      );
    }
  }, []);

  const appendUserMessage = useCallback((text: string) => {
    const msg: StreamMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, msg]);
  }, []);

  const createAssistantMessage = useCallback((agentName: string): string => {
    const id = `assistant-${Date.now()}`;
    const msg: StreamMessage = {
      id,
      role: 'assistant',
      content: '',
      agentName,
      timestamp: Date.now(),
      streaming: true,
      toolCalls: [],
    };
    activeMsgIdRef.current = id;
    pendingDeltaRef.current = '';
    setMessages(prev => [...prev, msg]);
    return id;
  }, []);

  const handleSSEEvent = useCallback(
    (msgId: string, event: SSEEvent) => {
      const data = event.data as Record<string, unknown>;

      switch (event.type) {
        case 'text_delta': {
          const delta = (data.delta as string) || '';
          if (delta) {
            pendingDeltaRef.current += delta;
            scheduleFlush();
          }
          break;
        }

        case 'agent_start': {
          const name = data.agent_name as string | undefined;
          if (name) {
            setMessages(prev =>
              prev.map(m => (m.id === msgId ? { ...m, agentName: name } : m)),
            );
          }
          break;
        }

        case 'tool_call_start': {
          const toolName = (data.tool_name as string) || (data.name as string) || 'tool';
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== msgId) return m;
              const calls = [...(m.toolCalls || [])];
              calls.push({ name: toolName, status: 'running' });
              return { ...m, toolCalls: calls, statusText: `调用工具: ${toolName}...` };
            }),
          );
          break;
        }

        case 'tool_call_end': {
          const toolName = (data.tool_name as string) || (data.name as string) || 'tool';
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== msgId) return m;
              const calls = (m.toolCalls || []).map(tc =>
                tc.name === toolName && tc.status === 'running'
                  ? { ...tc, status: 'done' as const }
                  : tc,
              );
              const running = calls.filter(tc => tc.status === 'running');
              return {
                ...m,
                toolCalls: calls,
                statusText: running.length > 0
                  ? `调用工具: ${running[0].name}...`
                  : undefined,
              };
            }),
          );
          break;
        }

        case 'handoff': {
          const target = (data.agent_name as string) || '';
          if (target) {
            setMessages(prev =>
              prev.map(m =>
                m.id === msgId
                  ? { ...m, agentName: target, statusText: `移交到 ${target}` }
                  : m,
              ),
            );
          }
          break;
        }

        case 'run_end': {
          // 先刷新残余 delta
          cancelPendingFlush();
          setMessages(prev =>
            prev.map(m =>
              m.id === msgId
                ? { ...m, streaming: false, statusText: undefined }
                : m,
            ),
          );
          break;
        }

        case 'error': {
          // error 事件不修改消息，由外层处理
          break;
        }

        default:
          break;
      }
    },
    [scheduleFlush, cancelPendingFlush],
  );

  const finalizeStream = useCallback(
    (msgId: string) => {
      cancelPendingFlush();
      setMessages(prev =>
        prev.map(m =>
          m.id === msgId ? { ...m, streaming: false, statusText: undefined } : m,
        ),
      );
    },
    [cancelPendingFlush],
  );

  return {
    messages,
    setMessages,
    appendUserMessage,
    createAssistantMessage,
    handleSSEEvent,
    finalizeStream,
    cancelPendingFlush,
  };
}
