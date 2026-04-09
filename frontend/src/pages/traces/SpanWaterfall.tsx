import { useMemo, useState } from 'react';
import { Tag, Tooltip, Typography, theme } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';
import type { SpanItem } from '../../services/traceService';

const { Text } = Typography;

import { SPAN_TYPE_COLORS } from '../../constants/colors';

interface WaterfallRow {
  span: SpanItem;
  depth: number;
  startOffset: number; // ms from trace start
  duration: number;    // ms
}

function buildWaterfallRows(spans: SpanItem[]): WaterfallRow[] {
  if (spans.length === 0) return [];

  // Find global min start_time
  const startTimes = spans.map((s) => new Date(s.start_time).getTime());
  const globalStart = Math.min(...startTimes);

  // Build parent map for depth calculation
  const depthMap = new Map<string, number>();
  const spanMap = new Map<string, SpanItem>();
  for (const s of spans) {
    spanMap.set(s.id, s);
  }

  function getDepth(span: SpanItem): number {
    if (depthMap.has(span.id)) return depthMap.get(span.id) as number;
    if (!span.parent_span_id || !spanMap.has(span.parent_span_id)) {
      depthMap.set(span.id, 0);
      return 0;
    }
    const parentDepth = getDepth(spanMap.get(span.parent_span_id) as SpanItem);
    const d = parentDepth + 1;
    depthMap.set(span.id, d);
    return d;
  }

  const rows: WaterfallRow[] = spans.map((span) => {
    const t0 = new Date(span.start_time).getTime();
    const startOffset = t0 - globalStart;
    let duration = span.duration_ms ?? 0;
    if (duration === 0 && span.end_time) {
      duration = new Date(span.end_time).getTime() - t0;
    }
    if (duration < 1) duration = 1; // min 1ms for visibility

    return {
      span,
      depth: getDepth(span),
      startOffset,
      duration,
    };
  });

  // Sort by start time, then depth
  rows.sort((a, b) => a.startOffset - b.startOffset || a.depth - b.depth);
  return rows;
}

interface SpanWaterfallProps {
  spans: SpanItem[];
  onSpanClick?: (span: SpanItem) => void;
  selectedSpanId?: string;
}

const ROW_HEIGHT = 28;
const LABEL_WIDTH = 220;
const BAR_AREA_MIN_WIDTH = 500;

const SpanWaterfall: React.FC<SpanWaterfallProps> = ({ spans, onSpanClick, selectedSpanId }) => {
  const { token } = theme.useToken();
  const rows = useMemo(() => buildWaterfallRows(spans), [spans]);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  if (rows.length === 0) {
    return <Text type="secondary">无 Span 数据</Text>;
  }

  // Total timeline width in ms
  const totalDuration = Math.max(
    ...rows.map((r) => r.startOffset + r.duration),
    1,
  );

  return (
    <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 400 }}>
      <div style={{ display: 'flex', minWidth: LABEL_WIDTH + BAR_AREA_MIN_WIDTH }}>
        {/* Label column */}
        <div style={{ width: LABEL_WIDTH, flexShrink: 0, borderRight: `1px solid ${token.colorBorderSecondary}` }}>
          {rows.map((row) => (
            <div
              key={row.span.id}
              style={{
                height: ROW_HEIGHT,
                display: 'flex',
                alignItems: 'center',
                paddingLeft: 4 + row.depth * 16,
                cursor: 'pointer',
                backgroundColor:
                  row.span.id === selectedSpanId
                    ? token.colorPrimaryBg
                    : row.span.id === hoveredId
                      ? token.colorBgLayout
                      : undefined,
                borderBottom: `1px solid ${token.colorFillQuaternary}`,
              }}
              onClick={() => onSpanClick?.(row.span)}
              onMouseEnter={() => setHoveredId(row.span.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              <Tag
                color={SPAN_TYPE_COLORS[row.span.type] || 'default'}
                style={{ margin: 0, fontSize: 11, lineHeight: '18px', padding: '0 4px' }}
              >
                {row.span.type}
              </Tag>
              <Text
                ellipsis
                style={{ marginLeft: 4, fontSize: 12, maxWidth: LABEL_WIDTH - 80 - row.depth * 16 }}
              >
                {row.span.name}
              </Text>
            </div>
          ))}
        </div>

        {/* Bar area */}
        <div style={{ flex: 1, position: 'relative', minWidth: BAR_AREA_MIN_WIDTH }}>
          {rows.map((row) => {
            const leftPct = (row.startOffset / totalDuration) * 100;
            const widthPct = Math.max((row.duration / totalDuration) * 100, 0.3);
            const color = SPAN_TYPE_COLORS[row.span.type] || token.colorTextQuaternary;
            const isFailed = row.span.status === 'failed';

            return (
              <Tooltip
                key={row.span.id}
                title={
                  <div>
                    <div><strong>{row.span.type}</strong>: {row.span.name}</div>
                    <div><ClockCircleOutlined /> {row.duration}ms</div>
                    {row.span.model && <div>模型: {row.span.model}</div>}
                    {row.span.token_usage && (
                      <div>Token: {row.span.token_usage.total_tokens}</div>
                    )}
                    <div>状态: {row.span.status}</div>
                  </div>
                }
                placement="top"
              >
                <div
                  style={{
                    height: ROW_HEIGHT,
                    position: 'relative',
                    cursor: 'pointer',
                    backgroundColor:
                      row.span.id === selectedSpanId
                        ? token.colorPrimaryBg
                        : row.span.id === hoveredId
                          ? token.colorBgLayout
                          : undefined,
                    borderBottom: `1px solid ${token.colorFillQuaternary}`,
                  }}
                  onClick={() => onSpanClick?.(row.span)}
                  onMouseEnter={() => setHoveredId(row.span.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <div
                    style={{
                      position: 'absolute',
                      left: `${leftPct}%`,
                      width: `${widthPct}%`,
                      top: 5,
                      height: ROW_HEIGHT - 10,
                      backgroundColor: isFailed ? token.colorError : color,
                      opacity: 0.85,
                      borderRadius: 2,
                      minWidth: 3,
                    }}
                  />
                  {/* Duration label on bar */}
                  {widthPct > 5 && (
                    <span
                      style={{
                        position: 'absolute',
                        left: `${leftPct}%`,
                        top: 6,
                        paddingLeft: 4,
                        fontSize: 10,
                        color: token.colorBgContainer,
                        whiteSpace: 'nowrap',
                        pointerEvents: 'none',
                      }}
                    >
                      {row.duration}ms
                    </span>
                  )}
                </div>
              </Tooltip>
            );
          })}

          {/* Time axis ticks */}
          <div
            style={{
              height: 20,
              position: 'relative',
              borderTop: `1px solid ${token.colorBorder}`,
            }}
          >
            {[0, 25, 50, 75, 100].map((pct) => (
              <span
                key={pct}
                style={{
                  position: 'absolute',
                  left: `${pct}%`,
                  top: 2,
                  fontSize: 10,
                  color: token.colorTextQuaternary,
                  transform: pct > 0 ? 'translateX(-50%)' : undefined,
                }}
              >
                {Math.round((pct / 100) * totalDuration)}ms
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SpanWaterfall;
