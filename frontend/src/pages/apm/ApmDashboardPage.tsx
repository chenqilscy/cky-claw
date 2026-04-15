import { useState } from 'react';
import {
  Card,
  Col,
  Row,
  Statistic,
  Table,
  Spin,
  App,
  Select,
  Typography,
  Button,
  Tag,
  Space,
  theme,
} from 'antd';
import {
  DashboardOutlined,
  CloudOutlined,
  DollarOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  PlusOutlined,
  LinkOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import ReactECharts from 'echarts-for-react';
import type {
  AgentRankItem,
  ModelUsageItem,
  ToolUsageItem,
} from '../../services/apmService';
import { SLOW_QUERY_PRESETS, type AlertRule } from '../../services/alertService';
import { useApmDashboard } from '../../hooks/useApmQueries';
import { useAlertRuleList, useCreateAlertRule } from '../../hooks/useAlertQueries';
import { useSystemInfo } from '../../hooks/useSystemQueries';

export default function ApmDashboardPage() {
  const { message } = App.useApp();
  const { token: themeToken } = theme.useToken();
  const [days, setDays] = useState(30);

  const { data, isLoading: loading, isError: error } = useApmDashboard(days);
  const { data: alertListData } = useAlertRuleList({ limit: 100 });
  const alertRules = alertListData?.data ?? [];
  const createAlertMutation = useCreateAlertRule();
  const { data: sysInfo } = useSystemInfo();

  /** 一键创建预设告警规则 */
  const createPresetAlert = async (presetIdx: number) => {
    try {
      const preset = SLOW_QUERY_PRESETS[presetIdx];
      if (!preset) return;
      await createAlertMutation.mutateAsync(preset);
      message.success(`告警规则「${preset.name}」创建成功`);
    } catch {
      message.error('创建告警规则失败');
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
        itemStyle: { color: themeToken.colorPrimary },
      },
      {
        name: 'Token 消耗',
        type: 'line',
        data: daily_trend.map((d) => d.tokens),
        smooth: true,
        itemStyle: { color: themeToken.colorSuccess },
      },
      {
        name: '成本',
        type: 'line',
        yAxisIndex: 1,
        data: daily_trend.map((d) => d.cost),
        smooth: true,
        itemStyle: { color: themeToken.colorWarning },
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
    { title: '错误数', dataIndex: 'error_count', key: 'error_count', render: (v: number) => v > 0 ? <span style={{ color: themeToken.colorError }}>{v}</span> : 0 },
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
    <PageContainer
      title="APM 仪表盘"
      icon={<DashboardOutlined />}
      description="应用性能监控：延迟、错误率、Token 趋势"
      extra={
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
      }
    >

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
              valueStyle={overview.error_rate > 5 ? { color: themeToken.colorError } : undefined}
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
                    loading={createAlertMutation.isPending}
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

      {/* 可观测性集成 — Jaeger / Prometheus 外链 */}
      {sysInfo && (
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col span={24}>
            <Card
              title={<Space><LinkOutlined /> 可观测性集成</Space>}
            >
              <Row gutter={[16, 16]}>
                <Col xs={24} sm={12} md={8}>
                  <Card size="small">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Space>
                        <Typography.Text strong>OpenTelemetry</Typography.Text>
                        {sysInfo.otel_enabled ? (
                          <Tag icon={<CheckCircleOutlined />} color="success">已启用</Tag>
                        ) : (
                          <Tag icon={<CloseCircleOutlined />} color="default">未启用</Tag>
                        )}
                      </Space>
                      <Typography.Text type="secondary">
                        服务名: {sysInfo.otel_service_name}
                      </Typography.Text>
                      {sysInfo.otel_enabled && (
                        <Typography.Text type="secondary">
                          Exporter: {sysInfo.otel_exporter_endpoint}
                        </Typography.Text>
                      )}
                    </Space>
                  </Card>
                </Col>
                {sysInfo.jaeger_ui_url && (
                  <Col xs={24} sm={12} md={8}>
                    <Card size="small">
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Typography.Text strong>Jaeger 链路追踪</Typography.Text>
                        <Button
                          type="primary"
                          ghost
                          icon={<LinkOutlined />}
                          href={sysInfo.jaeger_ui_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          打开 Jaeger UI
                        </Button>
                        <Typography.Text type="secondary">
                          查看分布式链路追踪详情、服务拓扑
                        </Typography.Text>
                      </Space>
                    </Card>
                  </Col>
                )}
                {sysInfo.prometheus_ui_url && (
                  <Col xs={24} sm={12} md={8}>
                    <Card size="small">
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Typography.Text strong>Prometheus 指标</Typography.Text>
                        <Button
                          type="primary"
                          ghost
                          icon={<LinkOutlined />}
                          href={sysInfo.prometheus_ui_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          打开 Prometheus UI
                        </Button>
                        <Typography.Text type="secondary">
                          查看系统指标、告警规则、PromQL 查询
                        </Typography.Text>
                      </Space>
                    </Card>
                  </Col>
                )}
              </Row>
            </Card>
          </Col>
        </Row>
      )}
    </PageContainer>
  );
}
