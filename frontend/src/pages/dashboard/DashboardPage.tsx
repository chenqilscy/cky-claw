import { useCallback, useEffect, useState } from 'react';
import {
  Card,
  Col,
  Row,
  Statistic,
  Progress,
  Table,
  Tag,
  Space,
  Typography,
  Spin,
  message,
} from 'antd';
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
import { chatService } from '../../services/chatService';
import { traceService } from '../../services/traceService';
import type { TraceStatsResponse } from '../../services/traceService';
import { tokenUsageService } from '../../services/tokenUsageService';
import type { TokenUsageByModelItem } from '../../services/tokenUsageService';

const { Title, Text } = Typography;

const SPAN_TYPE_COLORS: Record<string, string> = {
  agent: 'blue',
  llm: 'green',
  tool: 'orange',
  handoff: 'purple',
  guardrail: 'red',
};

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [agentCount, setAgentCount] = useState(0);
  const [sessionCount, setSessionCount] = useState(0);
  const [traceStats, setTraceStats] = useState<TraceStatsResponse | null>(null);
  const [tokenByModel, setTokenByModel] = useState<TokenUsageByModelItem[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      agentService.list({ limit: 1, offset: 0 }),
      chatService.listSessions({ limit: 1, offset: 0 }),
      traceService.stats(),
      tokenUsageService.summary({ group_by: 'model' }),
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
                    <Progress
                      percent={Number((traceStats.guardrail_stats.trigger_rate * 100).toFixed(1))}
                      status={traceStats.guardrail_stats.trigger_rate > 0.2 ? 'exception' : 'normal'}
                      format={(p) => `${p}% 拦截`}
                    />
                  </>
                ) : (
                  <Text type="secondary">暂无数据</Text>
                )}
              </Card>

              {/* Span Type Distribution */}
              <Card title="Span 类型分布" size="small">
                {spanTypeCounts && totalSpansByType > 0 ? (
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    {Object.entries(spanTypeCounts).map(([type, count]) => (
                      <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Tag color={SPAN_TYPE_COLORS[type] || 'default'} style={{ width: 70, textAlign: 'center' }}>
                          {type}
                        </Tag>
                        <Progress
                          percent={Number(((count / totalSpansByType) * 100).toFixed(1))}
                          size="small"
                          style={{ flex: 1, marginBottom: 0 }}
                          format={() => `${count}`}
                        />
                      </div>
                    ))}
                  </Space>
                ) : (
                  <Text type="secondary">暂无数据</Text>
                )}
              </Card>
            </Space>
          </Col>
        </Row>
      </Space>
    </Spin>
  );
};

export default DashboardPage;
