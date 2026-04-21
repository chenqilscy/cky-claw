import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// 必须在 import hook 之前完成，避免 antd mock 冲突
const { useStreamReducer } = await import('../../pages/chat/useStreamReducer');
type SSEEvent = import('../../services/chatService').SSEEvent;

describe('useStreamReducer', () => {
  let rafCallback: FrameRequestCallback | null = null;
  let rafId = 1;

  beforeEach(() => {
    rafCallback = null;
    rafId = 1;
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      rafCallback = cb;
      return rafId++;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {
      rafCallback = null;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  /** 手动触发 RAF 回调 */
  const flushRAF = () => {
    if (rafCallback) {
      const cb = rafCallback;
      rafCallback = null;
      cb(performance.now());
    }
  };

  it('appendUserMessage 添加用户消息', () => {
    const { result } = renderHook(() => useStreamReducer());

    act(() => {
      result.current.appendUserMessage('hello');
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]!.role).toBe('user');
    expect(result.current.messages[0]!.content).toBe('hello');
  });

  it('createAssistantMessage 创建空的流式助手消息', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('test-agent');
    });

    expect(msgId).toMatch(/^assistant-/);
    expect(result.current.messages).toHaveLength(1);
    const msg = result.current.messages[0]!;
    expect(msg.role).toBe('assistant');
    expect(msg.content).toBe('');
    expect(msg.streaming).toBe(true);
    expect(msg.agentName).toBe('test-agent');
  });

  it('text_delta 通过 RAF 批处理，减少 re-render', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    // 发送多个 text_delta，不触发 RAF
    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'text_delta',
        data: { delta: 'Hello' },
      });
      result.current.handleSSEEvent(msgId, {
        type: 'text_delta',
        data: { delta: ' World' },
      });
      result.current.handleSSEEvent(msgId, {
        type: 'text_delta',
        data: { delta: '!' },
      });
    });

    // RAF 还没触发，内容还是空
    expect(result.current.messages[0]!.content).toBe('');

    // 触发 RAF — 三个 delta 批处理为一次更新
    act(() => {
      flushRAF();
    });

    expect(result.current.messages[0]!.content).toBe('Hello World!');
    // requestAnimationFrame 只被调用一次（批处理）
    expect(window.requestAnimationFrame).toHaveBeenCalledTimes(1);
  });

  it('agent_start 更新 agentName', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('initial-agent');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'agent_start',
        data: { agent_name: 'new-agent' },
      });
    });

    expect(result.current.messages[0]!.agentName).toBe('new-agent');
  });

  it('tool_call_start 添加运行中的工具调用', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'tool_call_start',
        data: { tool_name: 'web_search' },
      });
    });

    const msg = result.current.messages[0]!;
    expect(msg.toolCalls).toHaveLength(1);
    expect(msg.toolCalls![0]).toEqual({ name: 'web_search', status: 'running' });
    expect(msg.statusText).toBe('调用工具: web_search...');
  });

  it('tool_call_end 标记工具完成并清除状态文本', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'tool_call_start',
        data: { tool_name: 'web_search' },
      });
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'tool_call_end',
        data: { tool_name: 'web_search' },
      });
    });

    const msg = result.current.messages[0]!;
    expect(msg.toolCalls![0]!.status).toBe('done');
    expect(msg.statusText).toBeUndefined();
  });

  it('handoff 事件更新 agentName 和 statusText', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent-a');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'handoff',
        data: { agent_name: 'agent-b' },
      });
    });

    const msg = result.current.messages[0]!;
    expect(msg.agentName).toBe('agent-b');
    expect(msg.statusText).toBe('移交到 agent-b');
  });

  it('run_end 刷新残余 delta 并结束流', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    // 发送 delta 但不触发 RAF
    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'text_delta',
        data: { delta: 'final text' },
      });
    });

    // run_end 应该刷新残余 delta
    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'run_end',
        data: { status: 'completed' },
      });
    });

    const msg = result.current.messages[0]!;
    expect(msg.content).toBe('final text');
    expect(msg.streaming).toBe(false);
    expect(msg.statusText).toBeUndefined();
  });

  it('finalizeStream 刷新残余并标记完成', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'text_delta',
        data: { delta: 'pending' },
      });
    });

    act(() => {
      result.current.finalizeStream(msgId);
    });

    expect(result.current.messages[0]!.content).toBe('pending');
    expect(result.current.messages[0]!.streaming).toBe(false);
  });

  it('cancelPendingFlush 取消 RAF 并刷新残余', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'text_delta',
        data: { delta: 'buffered' },
      });
    });

    act(() => {
      result.current.cancelPendingFlush();
    });

    expect(window.cancelAnimationFrame).toHaveBeenCalled();
    expect(result.current.messages[0]!.content).toBe('buffered');
  });

  it('session 切换后消息列表重置', () => {
    const { result } = renderHook(() => useStreamReducer());

    act(() => {
      result.current.appendUserMessage('msg1');
    });
    expect(result.current.messages).toHaveLength(1);

    act(() => {
      result.current.setMessages([]);
    });
    expect(result.current.messages).toHaveLength(0);
  });

  it('多个工具并行调用', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'tool_call_start',
        data: { tool_name: 'search' },
      });
      result.current.handleSSEEvent(msgId, {
        type: 'tool_call_start',
        data: { tool_name: 'calculator' },
      });
    });

    expect(result.current.messages[0]!.toolCalls).toHaveLength(2);
    expect(result.current.messages[0]!.statusText).toBe('调用工具: calculator...');

    // 完成第一个工具
    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'tool_call_end',
        data: { tool_name: 'search' },
      });
    });

    expect(result.current.messages[0]!.toolCalls![0]!.status).toBe('done');
    expect(result.current.messages[0]!.toolCalls![1]!.status).toBe('running');
    expect(result.current.messages[0]!.statusText).toBe('调用工具: calculator...');
  });

  it('error 事件不修改消息', () => {
    const { result } = renderHook(() => useStreamReducer());

    let msgId = '';
    act(() => {
      msgId = result.current.createAssistantMessage('agent');
    });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'text_delta',
        data: { delta: 'content' },
      });
    });
    act(() => { flushRAF(); });

    act(() => {
      result.current.handleSSEEvent(msgId, {
        type: 'error',
        data: { code: 'RUN_FAILED', message: 'oops' },
      } as SSEEvent);
    });

    // 消息不受 error 事件影响
    expect(result.current.messages[0]!.content).toBe('content');
    expect(result.current.messages[0]!.streaming).toBe(true);
  });
});
