import { useEffect, useRef, useCallback } from 'react';

export interface ApprovalEvent {
  type: 'approval_created' | 'approval_resolved';
  data: Record<string, unknown>;
}

interface UseApprovalWsOptions {
  onEvent: (event: ApprovalEvent) => void;
  enabled?: boolean;
}

/**
 * WebSocket 审批通道 Hook — 实时接收审批事件。
 *
 * 自动处理：
 * - JWT 认证（query param）
 * - 心跳保活（30s ping/pong）
 * - 断线自动重连（指数退避，最大 30s）
 */
export function useApprovalWs({ onEvent, enabled = true }: UseApprovalWsOptions): void {
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retriesRef = useRef(0);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const cleanup = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    const token = localStorage.getItem('kasaya_token');
    if (!token) return;

    cleanup();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/approvals?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      retriesRef.current = 0;
      // 心跳 30s
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30_000);
    };

    ws.onmessage = (event) => {
      if (event.data === 'pong') return;
      try {
        const parsed = JSON.parse(event.data) as ApprovalEvent;
        onEventRef.current(parsed);
      } catch {
        // 忽略非 JSON 消息
      }
    };

    ws.onclose = (event) => {
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      // 非正常关闭时自动重连
      if (event.code !== 1000 && event.code !== 4001) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30_000);
        retriesRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      // onerror 后一定触发 onclose，由 onclose 处理重连
    };
  }, [cleanup]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return cleanup;
  }, [enabled, connect, cleanup]);
}
