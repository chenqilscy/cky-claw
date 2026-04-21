import { useState, useCallback } from 'react';
import {
  App,
  Button,
  Card,
  Tag,
  Space,
  Input,
  Typography,
  Select,
  DatePicker,
  InputNumber,
  Switch,
  Tooltip,
} from 'antd';
import {
  ApartmentOutlined,
  DownloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { traceService } from '../../services/traceService';
import type { TraceItem, SpanItem, TraceListParams, FlameTreeResponse, ReplayTimelineResponse } from '../../services/traceService';
import { useTraceList, useTraceStats } from '../../hooks/useTraceQueries';
import type { Dayjs } from 'dayjs';
import TraceStatsPanel from './TraceStatsPanel';
import TraceDetailModal from './TraceDetailModal';

const { Text } = Typography;
const { RangePicker } = DatePicker;

const TracesPage: React.FC = () => {
  const { message } = App.useApp();
  const [agentFilter, setAgentFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [timeRange, setTimeRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [minDuration, setMinDuration] = useState<number | null>(null);
  const [maxDuration, setMaxDuration] = useState<number | null>(null);
  const [guardrailTriggered, setGuardrailTriggered] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [exporting, setExporting] = useState(false);

  const handleExportCSV = useCallback(async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (agentFilter) params.set('agent_name', agentFilter);
      if (timeRange) {
        params.set('start_time', timeRange[0].toISOString());
        params.set('end_time', timeRange[1].toISOString());
      }
      const token = localStorage.getItem('kasaya_token');
      const resp = await fetch(`/api/v1/export/runs?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error(`导出失败: ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `runs_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      void message.error(err instanceof Error ? err.message : '导出失败');
    } finally {
      setExporting(false);
    }
  }, [agentFilter, timeRange, message]);

  // TanStack Query — list & stats
  const listParams: TraceListParams = {
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  };
  if (agentFilter) listParams.agent_name = agentFilter;
  if (statusFilter) listParams.status = statusFilter;
  if (timeRange) {
    listParams.start_time = timeRange[0].toISOString();
    listParams.end_time = timeRange[1].toISOString();
  }
  if (minDuration !== null) listParams.min_duration_ms = minDuration;
  if (maxDuration !== null) listParams.max_duration_ms = maxDuration;
  if (guardrailTriggered) listParams.has_guardrail_triggered = true;

  const { data: listData, isLoading: loading } = useTraceList(listParams);
  const data = listData?.data ?? [];
  const total = listData?.total ?? 0;

  const statsParams = agentFilter ? { agent_name: agentFilter } : undefined;
  const { data: stats } = useTraceStats(statsParams);

  // Detail modal
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailTrace, setDetailTrace] = useState<TraceItem | null>(null);
  const [detailSpans, setDetailSpans] = useState<SpanItem[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedSpan, setSelectedSpan] = useState<SpanItem | null>(null);
  const [flameData, setFlameData] = useState<FlameTreeResponse | null>(null);
  const [replayData, setReplayData] = useState<ReplayTimelineResponse | null>(null);

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

  return (
    <PageContainer
      title="Trace 追踪"
      icon={<ApartmentOutlined />}
      description="查询与分析 Agent 执行链路追踪"
    >
      {stats && <TraceStatsPanel stats={stats} />}

      <Card
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
          toolBarRender={() => [
            <Button
              key="export"
              icon={<DownloadOutlined />}
              loading={exporting}
              onClick={() => { void handleExportCSV(); }}
            >
              导出 CSV
            </Button>,
          ]}
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

      <TraceDetailModal
        open={detailVisible}
        onClose={() => setDetailVisible(false)}
        loading={detailLoading}
        trace={detailTrace}
        spans={detailSpans}
        selectedSpan={selectedSpan}
        onSpanSelect={setSelectedSpan}
        flameData={flameData}
        replayData={replayData}
      />
    </PageContainer>
  );
};

export default TracesPage;
