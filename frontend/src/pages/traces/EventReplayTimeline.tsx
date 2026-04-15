import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Card, Empty, Slider, Space, Tag, Tooltip, Typography, theme } from 'antd';
import {
  CaretRightOutlined,
  PauseOutlined,
  StepForwardOutlined,
  StepBackwardOutlined,
} from '@ant-design/icons';
import type { EventItem } from '../../services/eventService';

const { Text } = Typography;

/** 事件类型到 Tag 颜色映射。 */
const EVENT_TYPE_COLORS: Record<string, string> = {
  run_start: 'blue',
  run_end: 'blue',
  agent_start: 'cyan',
  agent_end: 'cyan',
  llm_call_start: 'green',
  llm_call_end: 'green',
  tool_call_start: 'orange',
  tool_call_end: 'orange',
  handoff: 'purple',
  guardrail_check_start: 'red',
  guardrail_check_end: 'red',
  guardrail_tripwire: 'volcano',
  approval_request: 'gold',
  approval_response: 'gold',
  checkpoint_saved: 'geekblue',
  error: 'magenta',
};

interface EventReplayTimelineProps {
  events: EventItem[];
}

/**
 * 事件回放时间轴 — 按事件粒度逐步重放 Agent 运行过程。
 * 支持播放/暂停/单步/进度条拖拽。
 */
const EventReplayTimeline: React.FC<EventReplayTimelineProps> = ({ events }) => {
  const { token } = theme.useToken();
  const [currentStep, setCurrentStep] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sorted = useMemo(
    () => [...events].sort((a, b) => a.sequence - b.sequence),
    [events],
  );

  const baseTime = useMemo(
    () => (sorted.length > 0 ? new Date(sorted[0]?.timestamp ?? 0).getTime() : 0),
    [sorted],
  );

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const playNext = useCallback(() => {
    setCurrentStep((prev) => {
      const next = prev + 1;
      if (next >= sorted.length) {
        setIsPlaying(false);
        return prev;
      }
      const currMs = new Date(sorted[next]?.timestamp ?? 0).getTime() - baseTime;
      const nextMs = next + 1 < sorted.length
        ? new Date(sorted[next + 1]?.timestamp ?? 0).getTime() - baseTime
        : currMs;
      const delay = Math.max(80, (nextMs - currMs) / 10);
      timerRef.current = setTimeout(playNext, delay);
      return next;
    });
  }, [sorted, baseTime]);

  useEffect(() => {
    if (isPlaying) {
      playNext();
    } else if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [isPlaying, playNext]);

  useEffect(() => {
    setCurrentStep(-1);
    setIsPlaying(false);
  }, [events]);

  if (sorted.length === 0) {
    return <Card size="small"><Empty description="暂无事件数据" /></Card>;
  }

  return (
    <div>
      {/* 控制条 */}
      <Space style={{ marginBottom: 12 }}>
        <Button
          size="small"
          icon={<StepBackwardOutlined />}
          disabled={currentStep <= 0}
          onClick={() => { setIsPlaying(false); setCurrentStep((p) => Math.max(0, p - 1)); }}
        />
        <Button
          size="small"
          type="primary"
          icon={isPlaying ? <PauseOutlined /> : <CaretRightOutlined />}
          onClick={() => {
            if (currentStep >= sorted.length - 1) setCurrentStep(-1);
            setIsPlaying(!isPlaying);
          }}
        >
          {isPlaying ? '暂停' : '播放'}
        </Button>
        <Button
          size="small"
          icon={<StepForwardOutlined />}
          disabled={currentStep >= sorted.length - 1}
          onClick={() => { setIsPlaying(false); setCurrentStep((p) => Math.min(sorted.length - 1, p + 1)); }}
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          {currentStep + 1} / {sorted.length} 步
        </Text>
      </Space>

      {/* 进度条 */}
      <Slider
        min={0}
        max={sorted.length - 1}
        value={Math.max(0, currentStep)}
        onChange={(v) => { setIsPlaying(false); setCurrentStep(v); }}
        tooltip={{
          formatter: (v) => {
            const ev = v != null && v >= 0 ? sorted[v] : null;
            return ev ? `#${ev.sequence} ${ev.event_type}` : '';
          },
        }}
        style={{ marginBottom: 16 }}
      />

      {/* 事件时间轴列表 */}
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {sorted.map((ev, idx) => {
          const isActive = idx === currentStep;
          const isPast = idx < currentStep;
          const offsetMs = new Date(ev.timestamp).getTime() - baseTime;

          return (
            <div
              key={ev.event_id}
              onClick={() => { setIsPlaying(false); setCurrentStep(idx); }}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '6px 8px',
                marginBottom: 2,
                borderRadius: 4,
                cursor: 'pointer',
                background: isActive
                  ? token.colorPrimaryBg
                  : isPast
                    ? token.colorSuccessBg
                    : 'transparent',
                opacity: isPast ? 0.7 : 1,
                borderLeft: `3px solid ${token.colorPrimary}`,
                transition: 'background 0.2s',
              }}
            >
              <div style={{ minWidth: 60, fontSize: 11, color: token.colorTextQuaternary, fontFamily: 'monospace' }}>
                +{offsetMs}ms
              </div>
              <Tag color={EVENT_TYPE_COLORS[ev.event_type] || 'default'} style={{ margin: 0 }}>
                {ev.event_type}
              </Tag>
              <div style={{ flex: 1, minWidth: 0 }}>
                <Text strong={isActive} style={{ fontSize: 13 }}>
                  #{ev.sequence}
                  {ev.agent_name && ` · ${ev.agent_name}`}
                </Text>
                {isActive && ev.payload && Object.keys(ev.payload).length > 0 && (
                  <Tooltip title={JSON.stringify(ev.payload, null, 2)}>
                    <div style={{
                      marginTop: 4,
                      fontSize: 12,
                      color: token.colorTextSecondary,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      maxWidth: 500,
                    }}>
                      {JSON.stringify(ev.payload).slice(0, 120)}
                    </div>
                  </Tooltip>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default EventReplayTimeline;
