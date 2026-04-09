import {
  Modal,
  Row,
  Col,
  Statistic,
  Card,
  Tree,
  Tabs,
  Space,
  Tag,
  Typography,
  Button,
} from 'antd';
import {
  ApartmentOutlined,
  ClockCircleOutlined,
  DownloadOutlined,
  FireOutlined,
  PlayCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';
import type { TraceItem, SpanItem, FlameTreeResponse, ReplayTimelineResponse } from '../../services/traceService';
import { SPAN_TYPE_TAG_COLORS } from '../../constants/colors';
import SpanWaterfall from './SpanWaterfall';
import FlameChart from './FlameChart';
import TraceReplayTimeline from './TraceReplayTimeline';
import SpanDetailsPanel from './SpanDetailsPanel';

const { Text } = Typography;

/* ---- Span 树构建 ---- */

interface SpanTreeNode extends DataNode {
  span: SpanItem;
}

/** 将 Span 扁平列表构建为嵌套树 */
export function buildSpanTree(spans: SpanItem[]): SpanTreeNode[] {
  const map = new Map<string, SpanTreeNode>();
  const roots: SpanTreeNode[] = [];

  for (const span of spans) {
    const durationText = span.duration_ms !== null && span.duration_ms !== undefined
      ? `${span.duration_ms}ms`
      : '-';

    const isGuardrailTriggered = span.type === 'guardrail' && span.status === 'failed';
    const guardrailType = span.metadata?.guardrail_type as string | undefined;

    map.set(span.id, {
      key: span.id,
      title: (
        <Space size={4}>
          <Tag color={SPAN_TYPE_TAG_COLORS[span.type] || 'default'} style={{ margin: 0 }}>
            {span.type}
          </Tag>
          {guardrailType && (
            <Tag color="volcano" style={{ margin: 0, fontSize: 11 }}>
              {guardrailType}
            </Tag>
          )}
          <Text strong>{span.name}</Text>
          {span.model && <Text type="secondary">({span.model})</Text>}
          <Text type="secondary">
            <ClockCircleOutlined /> {durationText}
          </Text>
          {span.token_usage && (
            <Text type="secondary">
              tokens: {span.token_usage.total_tokens}
            </Text>
          )}
          <Tag color={span.status === 'completed' ? 'success' : 'error'}>{span.status}</Tag>
          {isGuardrailTriggered && (
            <Tag icon={<WarningOutlined />} color="error">
              已拦截
            </Tag>
          )}
        </Space>
      ),
      span,
      children: [],
    });
  }

  for (const span of spans) {
    const node = map.get(span.id);
    if (!node) continue;

    if (span.parent_span_id && map.has(span.parent_span_id)) {
      const parent = map.get(span.parent_span_id) as SpanTreeNode;
      (parent.children as SpanTreeNode[]).push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

/* ---- 组件 Props ---- */

interface TraceDetailModalProps {
  open: boolean;
  onClose: () => void;
  loading: boolean;
  trace: TraceItem | null;
  spans: SpanItem[];
  selectedSpan: SpanItem | null;
  onSpanSelect: (span: SpanItem | null) => void;
  flameData: FlameTreeResponse | null;
  replayData: ReplayTimelineResponse | null;
}

/** Trace 详情模态框 — 包含概览统计、Span 可视化（Waterfall / 火焰 / 回放）、Span 树、Span 详情 */
const TraceDetailModal: React.FC<TraceDetailModalProps> = ({
  open,
  onClose,
  loading,
  trace,
  spans,
  selectedSpan,
  onSpanSelect,
  flameData,
  replayData,
}) => {
  const spanTree = buildSpanTree(spans);
  const allKeys = spans.map((s) => s.id);

  const handleExport = () => {
    if (!trace) return;
    const exportData = { trace, spans };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trace-${trace.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Modal
      title={
        <Space>
          <ApartmentOutlined />
          Trace 详情
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={trace ? <Button icon={<DownloadOutlined />} onClick={handleExport}>导出 JSON</Button> : null}
      width={1100}
      loading={loading}
    >
      {trace && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Statistic title="Span 数" value={trace.span_count} />
            </Col>
            <Col span={6}>
              <Statistic title="状态" value={trace.status} />
            </Col>
            <Col span={6}>
              <Statistic title="Agent" value={trace.agent_name || '-'} />
            </Col>
            <Col span={6}>
              <Statistic
                title="耗时"
                value={trace.duration_ms !== null && trace.duration_ms !== undefined
                  ? trace.duration_ms
                  : '-'}
                suffix={trace.duration_ms !== null ? 'ms' : ''}
              />
            </Col>
          </Row>

          <Card title="Span 可视化" size="small" style={{ marginBottom: 16 }}>
            <Tabs
              defaultActiveKey="waterfall"
              items={[
                {
                  key: 'waterfall',
                  label: <span><ClockCircleOutlined /> Waterfall</span>,
                  children: (
                    <SpanWaterfall
                      spans={spans}
                      onSpanClick={(span) => onSpanSelect(span)}
                      selectedSpanId={selectedSpan?.id}
                    />
                  ),
                },
                {
                  key: 'flame',
                  label: <span><FireOutlined /> 火焰图</span>,
                  children: flameData ? (
                    <FlameChart nodes={flameData.root} totalSpans={flameData.total_spans} />
                  ) : (
                    <Text type="secondary" style={{ display: 'block', padding: 16 }}>加载中...</Text>
                  ),
                },
                {
                  key: 'replay',
                  label: <span><PlayCircleOutlined /> 回放</span>,
                  children: <TraceReplayTimeline data={replayData} />,
                },
              ]}
            />
          </Card>

          <Card title="Span 树" size="small" style={{ marginBottom: 16 }}>
            {spanTree.length > 0 ? (
              <Tree
                showLine
                defaultExpandAll
                expandedKeys={allKeys}
                treeData={spanTree}
                onSelect={(_, info) => {
                  const node = info.node as SpanTreeNode;
                  onSpanSelect(node.span);
                }}
              />
            ) : (
              <Text type="secondary">无 Span 数据</Text>
            )}
          </Card>

          {selectedSpan && <SpanDetailsPanel span={selectedSpan} />}
        </>
      )}
    </Modal>
  );
};

export default TraceDetailModal;
