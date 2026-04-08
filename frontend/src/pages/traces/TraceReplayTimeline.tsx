import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Card, Slider, Space, Tag, Tooltip, Typography } from 'antd';
import {
  CaretRightOutlined,
  PauseOutlined,
  StepForwardOutlined,
  StepBackwardOutlined,
} from '@ant-design/icons';
import type { ReplayTimelineResponse } from '../../services/traceService';

const { Text } = Typography;

const TYPE_COLORS: Record<string, string> = {
  agent: '#1677ff',
  llm: '#52c41a',
  tool: '#fa8c16',
  handoff: '#722ed1',
  guardrail: '#eb2f96',
};

interface TraceReplayTimelineProps {
  data: ReplayTimelineResponse | null;
}

/**
 * Trace 回放器 — 按时间轴逐步重放 Agent 执行过程。
 * 支持播放/暂停/单步/进度条拖拽。
 */
const TraceReplayTimeline: React.FC<TraceReplayTimelineProps> = ({ data }) => {
  const [currentStep, setCurrentStep] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const timeline = useMemo(() => data?.timeline ?? [], [data?.timeline]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  // 播放逻辑
  const playNext = useCallback(() => {
    setCurrentStep((prev) => {
      const next = prev + 1;
      if (next >= timeline.length) {
        setIsPlaying(false);
        return prev;
      }
      // 下一步的延迟基于 offset 差值（加速 10x，最小 100ms）
      const delay =
        next + 1 < timeline.length
          ? Math.max(100, ((timeline[next + 1]?.offset_ms ?? 0) - (timeline[next]?.offset_ms ?? 0)) / 10)
          : 500;
      timerRef.current = setTimeout(playNext, delay);
      return next;
    });
  }, [timeline]);

  useEffect(() => {
    if (isPlaying) {
      playNext();
    } else if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isPlaying, playNext]);

  // 重置
  useEffect(() => {
    setCurrentStep(-1);
    setIsPlaying(false);
  }, [data]);

  if (!data || timeline.length === 0) {
    return <Card size="small"><Text type="secondary">暂无回放数据</Text></Card>;
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
            if (currentStep >= timeline.length - 1) {
              setCurrentStep(-1);
            }
            setIsPlaying(!isPlaying);
          }}
        >
          {isPlaying ? '暂停' : '播放'}
        </Button>
        <Button
          size="small"
          icon={<StepForwardOutlined />}
          disabled={currentStep >= timeline.length - 1}
          onClick={() => { setIsPlaying(false); setCurrentStep((p) => Math.min(timeline.length - 1, p + 1)); }}
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          {currentStep + 1} / {timeline.length} 步
          {data.total_duration_ms > 0 && ` · 总耗时 ${data.total_duration_ms}ms`}
        </Text>
      </Space>

      {/* 进度条 */}
      <Slider
        min={0}
        max={timeline.length - 1}
        value={Math.max(0, currentStep)}
        onChange={(v) => { setIsPlaying(false); setCurrentStep(v); }}
        tooltip={{
          formatter: (v) => {
            const ev = v != null && v >= 0 ? timeline[v] : null;
            return ev ? `${ev.name} (${ev.type})` : '';
          },
        }}
        style={{ marginBottom: 16 }}
      />

      {/* 时间轴条目 */}
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {timeline.map((ev, idx) => {
          const isActive = idx === currentStep;
          const isPast = idx < currentStep;
          return (
            <div
              key={ev.span_id}
              onClick={() => { setIsPlaying(false); setCurrentStep(idx); }}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '6px 8px',
                marginBottom: 2,
                borderRadius: 4,
                cursor: 'pointer',
                background: isActive ? '#e6f4ff' : isPast ? '#f6ffed' : 'transparent',
                opacity: isPast ? 0.7 : 1,
                borderLeft: `3px solid ${TYPE_COLORS[ev.type] || '#999'}`,
                transition: 'background 0.2s',
              }}
            >
              <div style={{ minWidth: 60, fontSize: 11, color: '#999', fontFamily: 'monospace' }}>
                +{ev.offset_ms}ms
              </div>
              <Tag color={TYPE_COLORS[ev.type] || 'default'} style={{ margin: 0 }}>
                {ev.type}
              </Tag>
              <div style={{ flex: 1, minWidth: 0 }}>
                <Text strong={isActive} style={{ fontSize: 13 }}>{ev.name}</Text>
                {ev.duration_ms != null && (
                  <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                    {ev.duration_ms}ms
                  </Text>
                )}
                {ev.status === 'failed' && <Tag color="red" style={{ marginLeft: 4 }}>失败</Tag>}
                {isActive && (
                  <div style={{ marginTop: 4, fontSize: 12 }}>
                    {ev.model && <div><Text type="secondary">模型:</Text> {ev.model}</div>}
                    {ev.input_summary && (
                      <Tooltip title={ev.input_summary}>
                        <div style={{ color: '#666', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 500 }}>
                          <Text type="secondary">输入:</Text> {ev.input_summary}
                        </div>
                      </Tooltip>
                    )}
                    {ev.output_summary && (
                      <Tooltip title={ev.output_summary}>
                        <div style={{ color: '#666', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 500 }}>
                          <Text type="secondary">输出:</Text> {ev.output_summary}
                        </div>
                      </Tooltip>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TraceReplayTimeline;
