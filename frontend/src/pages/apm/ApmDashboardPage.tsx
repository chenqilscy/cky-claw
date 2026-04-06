import { useEffect, useState } from 'react';
import {
  Card,
  Col,
  Row,
  Statistic,
  Table,
  Spin,
  message,
  Select,
  Typography,
  Button,
  Tag,
  Space,
} from 'antd';
import {
  DashboardOutlined,
  CloudOutlined,
  DollarOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import type {
  ApmDashboardResponse,
  AgentRankItem,
  ModelUsageItem,
  ToolUsageItem,
} from '../../services/apmService';
import { apmService } from '../../services/apmService';
import { alertService, SLOW_QUERY_PRESETS, type AlertRule } from '../../services/alertService';

const { Title } = Typography;

export default function ApmDashboardPage() {
  const [data, setData] = useState<ApmDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [days, setDays] = useState(30);
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [alertLoading, setAlertLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    apmService
      .dashboard(days)
      .then(setData)
      .catch(() => {
        message.error('加载 APM 数据失败');
        setError(true);
      })
      .finally(() => setLoading(false));
  }, [days]);

  /** 加载告警规则 */
  const loadAlertRules = async () => {
    try {
      const res = await alertService.listRules({ limit: 100 });
      setAlertRules(res.data);
    } catch {
      // 非关键，静默
    }
  };

  useEffect(() => {
    loadAlertRules();
  }, []);

  /** 一键创建预设告警规则 */
  const createPresetAlert = async (presetIdx: number) => {
    setAlertLoading(true);
    try {
      const preset = SLOW_QUERY_PRESETS[presetIdx];
      if (!preset) return;
      await alertService.createRule(preset);
      message.success(`告警规则「${preset.name}」创建成功`);
      await loadAlertRules();
    } catch {
      message.error('创建告警规则失败');
    } finally {
      setAlertLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Typography.Text type="danger">加载 APM 数据失败，请稍后重试</Typography.Text>
      </div>
    );
  }

  const { overview, agent_ranking, model_usage, daily_trend, tool_usage } = data;

  // 每日趋势图 — 双 Y 轴（Traces + Tokens）
  const trendOption = {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['Trace 数量', 'Token 消耗', '成本'] },
    xAxis: { type: 'category' as const, data: daily_trend.map((d) => d.date) },
    yAxis: [
      { type: 'value' as const, name: 'Trace / Token' },
      { type: 'value' as const, name: '成本 ($)', splitLine: { show: false } },
    ],
    series: [
      {
        name: 'Trace 数量',
        type: 'bar',
        data: daily_trend.map((d) => d.traces),
        itemStyle: { color: '#1890ff' },
      },
      {
        name: 'Token 消耗',
        type: 'line',
        data: daily_trend.map((d) => d.tokens),
        smooth: true,
        itemStyle: { color: '#52c41a' },
      },
      {
        name: '成本',
        type: 'line',
        yAxisIndex: 1,
        data: daily_trend.map((d) => d.cost),
        smooth: true,
        itemStyle: { color: '#faad14' },
      },
    ],
  };

  // 模型使用分布饼图
  const modelPieOption = {
    tooltip: { trigger: 'item' as const },
    legend: { orient: 'vertical' as const, left: 'left' },
    series: [
      {
        name: 'Token 分布',
        type: 'pie',
        radius: ['40%', '70%'],
        data: model_usage.map((m) => ({ value: m.total_tokens, name: m.model })),
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } },
      },
    ],
  };

  const agentColumns = [
    { title: 'Agent', dataIndex: 'agent_name', key: 'agent_name' },
    { title: '调用次数', dataIndex: 'call_count', key: 'call_count', sorter: (a: AgentRankItem, b: AgentRankItem) => a.call_count - b.call_count },
    { title: 'Token', dataIndex: 'total_tokens', key: 'total_tokens', render: (v: number) => v.toLocaleString() },
    { title: '成本 ($)', dataIndex: 'total_cost', key: 'total_cost', render: (v: number) => `$${v.toFixed(4)}` },
    { title: '平均耗时 (ms)', dataIndex: 'avg_duration_ms', key: 'avg_duration_ms', render: (v: number) => v.toFixed(1) },
    { title: '错误数', dataIndex: 'error_count', key: 'error_count', render: (v: number) => v > 0 ? <span style={{ color: '#f5222d' }}>{v}</span> : 0 },
  ];

  const modelColumns = [
    { title: '模型', dataIndex: 'model', key: 'model' },
    { title: '调用次数', dataIndex: 'call_count', key: 'call_count' },
    { title: 'Prompt Tokens', dataIndex: 'prompt_tokens', key: 'prompt_tokens', render: (v: number) => v.toLocaleString() },
    { title: 'Completion Tokens', dataIndex: 'completion_tokens', key: 'completion_tokens', render: (v: number) => v.toLocaleString() },
    { title: '总 Token', dataIndex: 'total_tokens', key: 'total_tokens', render: (v: number) => v.toLocaleString() },
    { title: '成本 ($)', dataIndex: 'total_cost', key: 'total_cost', render: (v: number) => `$${v.toFixed(4)}` },
  ];

  const toolColumns = [
    { title: '工具', dataIndex: 'tool_name', key: 'tool_name' },
    { title: '调用次数', dataIndex: 'call_count', key: 'call_count', sorter: (a: ToolUsageItem, b: ToolUsageItem) => a.call_count - b.call_count },
    { title: '平均耗时 (ms)', dataIndex: 'avg_duration_ms', key: 'avg_duration_ms', render: (v: number) => v.toFixed(1) },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <DashboardOutlined /> APM 仪表盘
          </Title>
        </Col>
        <Col>
          <Select
            value={days}
            onChange={setDays}
            style={{ width: 150 }}
            options={[
              { value: 7, label: '最近 7 天' },
              { value: 14, label: '最近 14 天' },
              { value: 30, label: '最近 30 天' },
              { value: 90, label: '最近 90 天' },
            ]}
          />
        </Col>
      </Row>

      {/* 总览卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic title="Trace 总数" value={overview.total_traces} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic title="Span 总数" value={overview.total_spans} prefix={<CloudOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic title="Token 总量" value={overview.total_tokens} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic title="总成本" value={overview.total_cost} prefix={<DollarOutlined />} precision={4} suffix="$" />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic title="平均耗时" value={overview.avg_duration_ms} prefix={<ClockCircleOutlined />} precision={1} suffix="ms" />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <Card>
            <Statistic
              title="错误率"
              value={overview.error_rate}
              prefix={<WarningOutlined />}
              precision={2}
              suffix="%"
              valueStyle={overview.error_rate > 5 ? { color: '#f5222d' } : undefined}
            />
          </Card>
        </Col>
      </Row>

      {/* 趋势图 + 模型分布饼图 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="每日趋势">
            <ReactECharts option={trendOption} style={{ height: 350 }} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="模型 Token 分布">
            <ReactECharts option={modelPieOption} style={{ height: 350 }} />
          </Card>
        </Col>
      </Row>

      {/* Agent 排名 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={24}>
          <Card title="Agent 调用排名 (Top 10)">
            <Table<AgentRankItem>
              dataSource={agent_ranking}
              columns={agentColumns}
              rowKey="agent_name"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* 模型使用 + 工具使用 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="模型使用详情">
            <Table<ModelUsageItem>
              dataSource={model_usage}
              columns={modelColumns}
              rowKey="model"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="工具调用排名 (Top 10)">
            <Table<ToolUsageItem>
              dataSource={tool_usage}
              columns={toolColumns}
              rowKey="tool_name"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* 慢查询告警阈值配置 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card
            title={<Space><WarningOutlined /> 告警规则预设</Space>}
            extra={
              <Space>
                {SLOW_QUERY_PRESETS.map((preset, idx) => (
                  <Button
                    key={idx}
                    size="small"
                    icon={<PlusOutlined />}
                    loading={alertLoading}
                    onClick={() => createPresetAlert(idx)}
                  >
                    {preset.name}
                  </Button>
                ))}
              </Space>
            }
          >
            {alertRules.length > 0 ? (
              <Table<AlertRule>
                dataSource={alertRules}
                rowKey="id"
                pagination={false}
                size="small"
                columns={[
                  { title: '规则名称', dataIndex: 'name', width: 200 },
                  { title: '指标', dataIndex: 'metric', width: 150 },
                  {
                    title: '条件',
                    width: 120,
                    render: (_, r) => `${r.operator} ${r.threshold}`,
                  },
                  { title: '窗口', dataIndex: 'window_minutes', width: 80, render: (v: number) => `${v}min` },
                  {
                    title: '严重级别',
                    dataIndex: 'severity',
                    width: 100,
                    render: (v: string) => (
                      <Tag color={v === 'critical' ? 'red' : v === 'warning' ? 'orange' : 'blue'}>{v}</Tag>
                    ),
                  },
                  {
                    title: '状态',
                    dataIndex: 'is_enabled',
                    width: 80,
                    render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
                  },
                  {
                    title: '最近触发',
                    dataIndex: 'last_triggered_at',
                    width: 180,
                    render: (v: string | null) => v ? new Date(v).toLocaleString('zh-CN') : '-',
                  },
                ]}
              />
            ) : (
              <Typography.Text type="secondary">暂无告警规则，点击上方按钮创建预设规则</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
