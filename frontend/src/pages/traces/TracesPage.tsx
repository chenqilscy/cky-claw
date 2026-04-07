import { useCallback, useEffect, useState } from 'react';
import {
  message,
  Card,
  Tag,
  Space,
  Input,
  Modal,
  Tree,
  Descriptions,
  Typography,
  Row,
  Col,
  Statistic,
  Select,
  Alert,
  DatePicker,
  InputNumber,
  Switch,
  Button,
  Tooltip,
  Tabs,
} from 'antd';
import {
  ApartmentOutlined,
  ClockCircleOutlined,
  SearchOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  WarningOutlined,
  DownloadOutlined,
  FireOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { traceService } from '../../services/traceService';
import type { TraceItem, SpanItem, TraceStatsResponse, TraceListParams, FlameTreeResponse, ReplayTimelineResponse } from '../../services/traceService';
import type { DataNode } from 'antd/es/tree';
import type { Dayjs } from 'dayjs';
import SpanWaterfall from './SpanWaterfall';
import FlameChart from './FlameChart';
import TraceReplayTimeline from './TraceReplayTimeline';

const { Text } = Typography;
const { RangePicker } = DatePicker;

const SPAN_TYPE_COLORS: Record<string, string> = {
  agent: 'blue',
  llm: 'green',
  tool: 'orange',
  handoff: 'purple',
  guardrail: 'red',
};

interface SpanTreeNode extends DataNode {
  span: SpanItem;
}

function buildSpanTree(spans: SpanItem[]): SpanTreeNode[] {
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
          <Tag color={SPAN_TYPE_COLORS[span.type] || 'default'} style={{ margin: 0 }}>
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

const TracesPage: React.FC = () => {
  const [data, setData] = useState<TraceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [agentFilter, setAgentFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [timeRange, setTimeRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [minDuration, setMinDuration] = useState<number | null>(null);
  const [maxDuration, setMaxDuration] = useState<number | null>(null);
  const [guardrailTriggered, setGuardrailTriggered] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [stats, setStats] = useState<TraceStatsResponse | null>(null);

  // Detail modal
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailTrace, setDetailTrace] = useState<TraceItem | null>(null);
  const [detailSpans, setDetailSpans] = useState<SpanItem[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedSpan, setSelectedSpan] = useState<SpanItem | null>(null);
  const [flameData, setFlameData] = useState<FlameTreeResponse | null>(null);
  const [replayData, setReplayData] = useState<ReplayTimelineResponse | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await traceService.stats(
        agentFilter ? { agent_name: agentFilter } : undefined,
      );
      setStats(res);
    } catch {
      // 非关键数据，静默
    }
  }, [agentFilter]);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params: TraceListParams = {
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      };
      if (agentFilter) params.agent_name = agentFilter;
      if (statusFilter) params.status = statusFilter;
      if (timeRange) {
        params.start_time = timeRange[0].toISOString();
        params.end_time = timeRange[1].toISOString();
      }
      if (minDuration !== null) params.min_duration_ms = minDuration;
      if (maxDuration !== null) params.max_duration_ms = maxDuration;
      if (guardrailTriggered) params.has_guardrail_triggered = true;
      const res = await traceService.list(params);
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取 Trace 列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination, agentFilter, statusFilter, timeRange, minDuration, maxDuration, guardrailTriggered]);

  useEffect(() => {
    fetchList();
    fetchStats();
  }, [fetchList, fetchStats]);

  const openDetail = async (traceId: string) => {
    setDetailVisible(true);
    setDetailLoading(true);
    setSelectedSpan(null);
    setFlameData(null);
    setReplayData(null);
    try {
      const [detailRes, flameRes, replayRes] = await Promise.allSettled([
        traceService.detail(traceId),
        traceService.flame(traceId),
        traceService.replay(traceId),
      ]);
      if (detailRes.status === 'fulfilled') {
        setDetailTrace(detailRes.value.trace);
        setDetailSpans(detailRes.value.spans);
      }
      if (flameRes.status === 'fulfilled') {
        setFlameData(flameRes.value);
      }
      if (replayRes.status === 'fulfilled') {
        setReplayData(replayRes.value);
      }
    } catch {
      message.error('获取 Trace 详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const columns: ProColumns<TraceItem>[] = [
    {
      title: 'Trace ID',
      dataIndex: 'id',
      width: 200,
      ellipsis: true,
      copyable: true,
      render: (_, record) => (
        <a onClick={() => openDetail(record.id)}>{record.id.slice(0, 12)}...</a>
      ),
    },
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 160,
      render: (_, record) =>
        record.agent_name ? <Tag color="blue">{record.agent_name}</Tag> : '-',
    },
    {
      title: 'Session',
      dataIndex: 'session_id',
      width: 120,
      ellipsis: true,
      render: (_, record) =>
        record.session_id ? (
          <Tooltip title={record.session_id}>
            <Text copyable={{ text: record.session_id }} style={{ fontSize: 12 }}>
              {record.session_id.slice(0, 8)}...
            </Text>
          </Tooltip>
        ) : '-',
    },
    {
      title: 'Workflow',
      dataIndex: 'workflow_name',
      width: 140,
    },
    {
      title: 'Span 数',
      dataIndex: 'span_count',
      width: 90,
      sorter: (a, b) => a.span_count - b.span_count,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (_, record) => (
        <Tag color={record.status === 'completed' ? 'success' : 'error'}>{record.status}</Tag>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      width: 180,
      render: (_, record) => new Date(record.start_time).toLocaleString('zh-CN'),
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      width: 100,
      sorter: (a, b) => (a.duration_ms ?? 0) - (b.duration_ms ?? 0),
      render: (_, record) =>
        record.duration_ms !== null && record.duration_ms !== undefined
          ? `${record.duration_ms}ms`
          : '-',
    },
  ];

  const spanTree = buildSpanTree(detailSpans);
  const allKeys = detailSpans.map((s) => s.id);

  return (
    <>
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Card size="small">
              <Statistic title="总 Trace 数" value={stats.total_traces} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="总 Span 数" value={stats.total_spans} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic
                title="平均耗时"
                value={stats.avg_duration_ms !== null ? stats.avg_duration_ms.toFixed(0) : '-'}
                suffix="ms"
                prefix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic
                title="总 Token"
                value={stats.total_tokens.total_tokens}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic
                title="Guardrail 拦截"
                value={stats.guardrail_stats.triggered}
                suffix={`/ ${stats.guardrail_stats.total}`}
                prefix={<SafetyOutlined />}
                valueStyle={stats.guardrail_stats.triggered > 0 ? { color: '#cf1322' } : undefined}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic
                title="错误率"
                value={(stats.error_rate * 100).toFixed(1)}
                suffix="%"
                valueStyle={stats.error_rate > 0.1 ? { color: '#cf1322' } : undefined}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Card
        title={
          <Space>
            <ApartmentOutlined />
            Trace 追踪
          </Space>
        }
        extra={
          <Space wrap>
            <RangePicker
              showTime
              placeholder={['开始时间', '结束时间']}
              onChange={(dates) => {
                setTimeRange(dates as [Dayjs, Dayjs] | null);
                setPagination((p) => ({ ...p, current: 1 }));
              }}
              style={{ width: 340 }}
            />
            <InputNumber
              placeholder="最小耗时(ms)"
              min={0}
              value={minDuration}
              onChange={(v) => {
                setMinDuration(v);
                setPagination((p) => ({ ...p, current: 1 }));
              }}
              style={{ width: 130 }}
            />
            <InputNumber
              placeholder="最大耗时(ms)"
              min={0}
              value={maxDuration}
              onChange={(v) => {
                setMaxDuration(v);
                setPagination((p) => ({ ...p, current: 1 }));
              }}
              style={{ width: 130 }}
            />
            <Space size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>Guardrail 拦截</Text>
              <Switch
                size="small"
                checked={guardrailTriggered}
                onChange={(v) => {
                  setGuardrailTriggered(v);
                  setPagination((p) => ({ ...p, current: 1 }));
                }}
              />
            </Space>
            <Select
              placeholder="状态筛选"
              value={statusFilter}
              onChange={(v) => {
                setStatusFilter(v);
                setPagination((p) => ({ ...p, current: 1 }));
              }}
              allowClear
              style={{ width: 120 }}
              options={[
                { label: '已完成', value: 'completed' },
                { label: '失败', value: 'failed' },
              ]}
            />
            <Input
              placeholder="按 Agent 筛选"
              prefix={<SearchOutlined />}
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              onPressEnter={() => setPagination((p) => ({ ...p, current: 1 }))}
              allowClear
              style={{ width: 200 }}
            />
          </Space>
        }
      >
        <ProTable<TraceItem>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          search={false}
          toolBarRender={false}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>

      <Modal
        title={
          <Space>
            <ApartmentOutlined />
            Trace 详情
          </Space>
        }
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={
          detailTrace ? (
            <Button
              icon={<DownloadOutlined />}
              onClick={() => {
                const exportData = {
                  trace: detailTrace,
                  spans: detailSpans,
                };
                const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `trace-${detailTrace.id.slice(0, 8)}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              导出 JSON
            </Button>
          ) : null
        }
        width={1100}
        loading={detailLoading}
      >
        {detailTrace && (
          <>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Statistic title="Span 数" value={detailTrace.span_count} />
              </Col>
              <Col span={6}>
                <Statistic title="状态" value={detailTrace.status} />
              </Col>
              <Col span={6}>
                <Statistic title="Agent" value={detailTrace.agent_name || '-'} />
              </Col>
              <Col span={6}>
                <Statistic
                  title="耗时"
                  value={detailTrace.duration_ms !== null && detailTrace.duration_ms !== undefined
                    ? detailTrace.duration_ms
                    : '-'}
                  suffix={detailTrace.duration_ms !== null ? 'ms' : ''}
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
                        spans={detailSpans}
                        onSpanClick={(span) => setSelectedSpan(span)}
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
                      <div style={{ color: '#999', padding: 16 }}>加载中...</div>
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
                    setSelectedSpan(node.span);
                  }}
                />
              ) : (
                <Text type="secondary">无 Span 数据</Text>
              )}
            </Card>

            {selectedSpan && (
              <Card title={`Span 详情: ${selectedSpan.name}`} size="small">
                {selectedSpan.type === 'guardrail' && selectedSpan.status === 'failed' && (
                  <Alert
                    message="Guardrail 已拦截"
                    description={selectedSpan.metadata?.message as string || '此 Guardrail 触发了拦截'}
                    type="error"
                    showIcon
                    icon={<WarningOutlined />}
                    style={{ marginBottom: 12 }}
                  />
                )}
                <Descriptions column={2} size="small" bordered>
                  <Descriptions.Item label="ID">{selectedSpan.id}</Descriptions.Item>
                  <Descriptions.Item label="类型">
                    <Tag color={SPAN_TYPE_COLORS[selectedSpan.type] || 'default'}>
                      {selectedSpan.type}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={selectedSpan.status === 'completed' ? 'success' : 'error'}>
                      {selectedSpan.status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="模型">{selectedSpan.model || '-'}</Descriptions.Item>
                  <Descriptions.Item label="耗时">
                    {selectedSpan.duration_ms !== null && selectedSpan.duration_ms !== undefined
                      ? `${selectedSpan.duration_ms}ms`
                      : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="开始时间">
                    {new Date(selectedSpan.start_time).toLocaleString('zh-CN')}
                  </Descriptions.Item>
                  {selectedSpan.token_usage && (
                    <>
                      <Descriptions.Item label="输入 Token">
                        {selectedSpan.token_usage.prompt_tokens}
                      </Descriptions.Item>
                      <Descriptions.Item label="输出 Token">
                        {selectedSpan.token_usage.completion_tokens}
                      </Descriptions.Item>
                    </>
                  )}
                  {selectedSpan.type === 'guardrail' && (
                    <>
                      <Descriptions.Item label="Guardrail 类型">
                        <Tag color="volcano">
                          {(selectedSpan.metadata?.guardrail_type as string) || '-'}
                        </Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="触发">
                        {selectedSpan.metadata?.triggered
                          ? <Tag color="error">是</Tag>
                          : <Tag color="success">否</Tag>}
                      </Descriptions.Item>
                      {selectedSpan.metadata?.message && (
                        <Descriptions.Item label="消息" span={2}>
                          {selectedSpan.metadata.message as string}
                        </Descriptions.Item>
                      )}
                      {selectedSpan.metadata?.tool_name && (
                        <Descriptions.Item label="关联工具">
                          <Tag color="orange">{selectedSpan.metadata.tool_name as string}</Tag>
                        </Descriptions.Item>
                      )}
                    </>
                  )}
                  {selectedSpan.input && (
                    <Descriptions.Item label="输入" span={2}>
                      <pre style={{ margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
                        {JSON.stringify(selectedSpan.input, null, 2)}
                      </pre>
                    </Descriptions.Item>
                  )}
                  {selectedSpan.output && (
                    <Descriptions.Item label="输出" span={2}>
                      <pre style={{ margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
                        {JSON.stringify(selectedSpan.output, null, 2)}
                      </pre>
                    </Descriptions.Item>
                  )}
                </Descriptions>
              </Card>
            )}
          </>
        )}
      </Modal>
    </>
  );
};

export default TracesPage;
