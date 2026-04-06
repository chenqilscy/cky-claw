import { useCallback, useEffect, useState } from 'react';
import {
  Card,
  Col,
  Row,
  Statistic,
  Table,
  Tag,
  Space,
  Typography,
  Spin,
  message,
} from 'antd';
import ReactECharts from 'echarts-for-react';
import {
  RobotOutlined,
  MessageOutlined,
  ApartmentOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
  DashboardOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { agentService } from '../../services/agentService';
import type { AgentRealtimeStatusItem } from '../../services/agentService';
import { chatService } from '../../services/chatService';
import { traceService } from '../../services/traceService';
import type { TraceStatsResponse } from '../../services/traceService';
import { tokenUsageService } from '../../services/tokenUsageService';
import type { TokenUsageByModelItem, TokenUsageTrendItem } from '../../services/tokenUsageService';

const { Title, Text } = Typography;

const SPAN_TYPE_COLOR_VALUES: Record<string, string> = {
  agent: '#1677ff',
  llm: '#52c41a',
  tool: '#fa8c16',
  handoff: '#722ed1',
  guardrail: '#f5222d',
};

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [agentCount, setAgentCount] = useState(0);
  const [sessionCount, setSessionCount] = useState(0);
  const [traceStats, setTraceStats] = useState<TraceStatsResponse | null>(null);
  const [tokenByModel, setTokenByModel] = useState<TokenUsageByModelItem[]>([]);
  const [tokenTrend, setTokenTrend] = useState<TokenUsageTrendItem[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentRealtimeStatusItem[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      agentService.list({ limit: 1, offset: 0 }),
      chatService.listSessions({ limit: 1, offset: 0 }),
      traceService.stats(),
      tokenUsageService.summary({ group_by: 'model' }),
      tokenUsageService.trend({ days: 7 }),
      agentService.realtimeStatus({ minutes: 5 }),
    ]);

    if (results[0].status === 'fulfilled') {
      setAgentCount(results[0].value.total);
    }
    if (results[1].status === 'fulfilled') {
      setSessionCount(results[1].value.total);
    }
    if (results[2].status === 'fulfilled') {
      setTraceStats(results[2].value);
    }
    if (results[3].status === 'fulfilled') {
      setTokenByModel(results[3].value.data as TokenUsageByModelItem[]);
    }
    if (results[4].status === 'fulfilled') {
      setTokenTrend(results[4].value.data);
    }
    if (results[5].status === 'fulfilled') {
      setAgentStatus(results[5].value.data);
    }

    const failedCount = results.filter((r) => r.status === 'rejected').length;
    if (failedCount > 0) {
      message.warning(`${failedCount} 个统计接口加载失败`);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalTokens = traceStats?.total_tokens.total_tokens ?? 0;

  const spanTypeCounts = traceStats?.span_type_counts;
  const totalSpansByType = spanTypeCounts
    ? Object.values(spanTypeCounts).reduce((a, b) => a + b, 0)
    : 0;

  const tokenModelColumns = [
    {
      title: '模型',
      dataIndex: 'model',
      key: 'model',
      render: (v: string) => <Tag color="processing">{v}</Tag>,
    },
    {
      title: 'Prompt Tokens',
      dataIndex: 'total_prompt_tokens',
      key: 'total_prompt_tokens',
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: 'Completion Tokens',
      dataIndex: 'total_completion_tokens',
      key: 'total_completion_tokens',
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '总 Tokens',
      dataIndex: 'total_tokens',
      key: 'total_tokens',
      render: (v: number) => <Text strong>{v.toLocaleString()}</Text>,
    },
    {
      title: '调用次数',
      dataIndex: 'call_count',
      key: 'call_count',
    },
  ];

  return (
    <Spin spinning={loading}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {/* Header */}
        <Title level={4} style={{ margin: 0 }}>
          <DashboardOutlined /> 平台概览
        </Title>

        {/* Row 1: Key Metrics */}
        <Row gutter={16}>
          <Col span={4}>
            <Card
              size="small"
              hoverable
              onClick={() => navigate('/agents')}
              style={{ cursor: 'pointer' }}
            >
              <Statistic
                title="Agent 总数"
                value={agentCount}
                prefix={<RobotOutlined />}
                valueStyle={{ color: '#1677ff' }}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card
              size="small"
              hoverable
              onClick={() => navigate('/chat')}
              style={{ cursor: 'pointer' }}
            >
              <Statistic
                title="Session 总数"
                value={sessionCount}
                prefix={<MessageOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card
              size="small"
              hoverable
              onClick={() => navigate('/traces')}
              style={{ cursor: 'pointer' }}
            >
              <Statistic
                title="Trace 总数"
                value={traceStats?.total_traces ?? 0}
                prefix={<ApartmentOutlined />}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic
                title="Span 总数"
                value={traceStats?.total_spans ?? 0}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic
                title="平均耗时"
                value={traceStats?.avg_duration_ms !== null && traceStats?.avg_duration_ms !== undefined
                  ? traceStats.avg_duration_ms.toFixed(0)
                  : '-'}
                suffix="ms"
                prefix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic
                title="错误率"
                value={traceStats ? (traceStats.error_rate * 100).toFixed(1) : '-'}
                suffix="%"
                valueStyle={traceStats && traceStats.error_rate > 0.1 ? { color: '#cf1322' } : undefined}
                prefix={<WarningOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* Row 2: Token + Guardrail + Span Types */}
        <Row gutter={16}>
          <Col span={14}>
            <Card title="Token 消耗（按模型）" size="small">
              <Row gutter={16} style={{ marginBottom: 12 }}>
                <Col span={8}>
                  <Statistic title="总 Token" value={totalTokens.toLocaleString()} />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="Prompt"
                    value={(traceStats?.total_tokens.prompt_tokens ?? 0).toLocaleString()}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="Completion"
                    value={(traceStats?.total_tokens.completion_tokens ?? 0).toLocaleString()}
                  />
                </Col>
              </Row>
              <Table
                dataSource={tokenByModel}
                columns={tokenModelColumns}
                rowKey="model"
                size="small"
                pagination={false}
                locale={{ emptyText: '暂无数据' }}
              />
            </Card>
          </Col>
          <Col span={10}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              {/* Guardrail Stats */}
              <Card
                title={
                  <Space>
                    <SafetyCertificateOutlined />
                    Guardrail 护栏
                  </Space>
                }
                size="small"
                hoverable
                onClick={() => navigate('/guardrails')}
                style={{ cursor: 'pointer' }}
              >
                {traceStats ? (
                  <>
                    <Row gutter={16} style={{ marginBottom: 12 }}>
                      <Col span={8}>
                        <Statistic title="总检查" value={traceStats.guardrail_stats.total} />
                      </Col>
                      <Col span={8}>
                        <Statistic
                          title="已拦截"
                          value={traceStats.guardrail_stats.triggered}
                          valueStyle={traceStats.guardrail_stats.triggered > 0 ? { color: '#cf1322' } : undefined}
                        />
                      </Col>
                      <Col span={8}>
                        <Statistic
                          title="拦截率"
                          value={(traceStats.guardrail_stats.trigger_rate * 100).toFixed(1)}
                          suffix="%"
                        />
                      </Col>
                    </Row>
                    <ReactECharts
                      style={{ height: 100 }}
                      option={{
                        series: [{
                          type: 'gauge',
                          startAngle: 200,
                          endAngle: -20,
                          min: 0,
                          max: 100,
                          radius: '90%',
                          progress: { show: true, width: 10 },
                          axisLine: { lineStyle: { width: 10 } },
                          axisTick: { show: false },
                          splitLine: { show: false },
                          axisLabel: { show: false },
                          pointer: { show: false },
                          detail: {
                            valueAnimation: true,
                            fontSize: 16,
                            formatter: '{value}%',
                            offsetCenter: [0, '10%'],
                            color: traceStats.guardrail_stats.trigger_rate > 0.2 ? '#cf1322' : '#52c41a',
                          },
                          data: [{ value: Number((traceStats.guardrail_stats.trigger_rate * 100).toFixed(1)) }],
                          itemStyle: {
                            color: traceStats.guardrail_stats.trigger_rate > 0.2 ? '#cf1322' : '#52c41a',
                          },
                        }],
                      }}
                    />
                  </>
                ) : (
                  <Text type="secondary">暂无数据</Text>
                )}
              </Card>

              {/* Span Type Distribution */}
              <Card title="Span 类型分布" size="small">
                {spanTypeCounts && totalSpansByType > 0 ? (
                  <ReactECharts
                    style={{ height: 180 }}
                    option={{
                      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
                      legend: { orient: 'vertical', right: 0, top: 'center', textStyle: { fontSize: 12 } },
                      series: [{
                        type: 'pie',
                        radius: ['40%', '70%'],
                        center: ['35%', '50%'],
                        avoidLabelOverlap: false,
                        label: { show: false },
                        emphasis: { label: { show: true, fontSize: 12 } },
                        data: Object.entries(spanTypeCounts).map(([type, count]) => ({
                          name: type,
                          value: count,
                          itemStyle: { color: SPAN_TYPE_COLOR_VALUES[type] ?? '#8c8c8c' },
                        })),
                      }],
                    }}
                  />
                ) : (
                  <Text type="secondary">暂无数据</Text>
                )}
              </Card>
            </Space>
          </Col>
        </Row>

        {/* Row 3: Agent Realtime Status */}
        <Row gutter={16}>
          <Col span={24}>
            <Card title="Agent 实时状态（近 5 分钟）" size="small">
              {agentStatus.length > 0 ? (
                <Table
                  dataSource={agentStatus}
                  rowKey="agent_name"
                  size="small"
                  pagination={false}
                  locale={{ emptyText: '暂无活跃 Agent' }}
                  columns={[
                    {
                      title: 'Agent',
                      dataIndex: 'agent_name',
                      key: 'agent_name',
                      render: (v: string) => <Tag color="blue">{v}</Tag>,
                    },
                    {
                      title: '运行次数',
                      dataIndex: 'run_count',
                      key: 'run_count',
                      sorter: (a: AgentRealtimeStatusItem, b: AgentRealtimeStatusItem) => a.run_count - b.run_count,
                    },
                    {
                      title: '错误次数',
                      dataIndex: 'error_count',
                      key: 'error_count',
                      render: (v: number) => v > 0 ? <Text type="danger">{v}</Text> : v,
                    },
                    {
                      title: '最近活跃',
                      dataIndex: 'last_active_at',
                      key: 'last_active_at',
                      render: (v: string | null) => v ? new Date(v).toLocaleString() : '-',
                    },
                    {
                      title: '状态',
                      dataIndex: 'status',
                      key: 'status',
                      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '正常' : '异常'}</Tag>,
                    },
                  ]}
                />
              ) : (
                <Text type="secondary">暂无活跃 Agent</Text>
              )}
            </Card>
          </Col>
        </Row>

        {/* Row 4: Token Trend Chart */}
        <Row gutter={16}>
          <Col span={24}>
            <Card title="Token 消耗趋势（近 7 天）" size="small">
              {tokenTrend.length > 0 ? (
                <ReactECharts
                  style={{ height: 280 }}
                  option={{
                    tooltip: {
                      trigger: 'axis',
                      formatter: (params: Array<{ name: string; value: number; seriesName: string }>) =>
                        params.map((p) => `${p.seriesName}: ${p.value.toLocaleString()}`).join('<br/>'),
                    },
                    legend: { data: ['Token 消耗', '调用次数'], top: 0 },
                    grid: { left: 60, right: 60, bottom: 30, top: 40 },
                    xAxis: {
                      type: 'category',
                      data: tokenTrend.map((d) => d.date),
                      axisLabel: { fontSize: 11 },
                    },
                    yAxis: [
                      { type: 'value', name: 'Tokens', axisLabel: { formatter: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v) } },
                      { type: 'value', name: '调用次数', splitLine: { show: false } },
                    ],
                    series: [
                      {
                        name: 'Token 消耗',
                        type: 'line',
                        data: tokenTrend.map((d) => d.total_tokens),
                        smooth: true,
                        areaStyle: { opacity: 0.15 },
                        itemStyle: { color: '#1677ff' },
                      },
                      {
                        name: '调用次数',
                        type: 'bar',
                        yAxisIndex: 1,
                        data: tokenTrend.map((d) => d.call_count),
                        itemStyle: { color: '#52c41a', opacity: 0.6 },
                        barMaxWidth: 30,
                      },
                    ],
                  }}
                />
              ) : (
                <Text type="secondary">暂无趋势数据</Text>
              )}
            </Card>
          </Col>
        </Row>
      </Space>
    </Spin>
  );
};

export default DashboardPage;
