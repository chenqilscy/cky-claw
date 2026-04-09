import { Row, Col, Card, Statistic, theme } from 'antd';
import { ThunderboltOutlined, SafetyOutlined } from '@ant-design/icons';
import type { TraceStatsResponse } from '../../services/traceService';

interface TraceStatsPanelProps {
  stats: TraceStatsResponse;
}

/** 6 张统计卡片 — Trace 概览面板 */
const TraceStatsPanel: React.FC<TraceStatsPanelProps> = ({ stats }) => {
  const { token } = theme.useToken();

  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col xs={12} sm={8} md={4}>
        <Card size="small">
          <Statistic title="总 Trace 数" value={stats.total_traces} />
        </Card>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Card size="small">
          <Statistic title="总 Span 数" value={stats.total_spans} />
        </Card>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Card size="small">
          <Statistic
            title="平均耗时"
            value={stats.avg_duration_ms !== null ? stats.avg_duration_ms.toFixed(0) : '-'}
            suffix="ms"
            prefix={<ThunderboltOutlined />}
          />
        </Card>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Card size="small">
          <Statistic
            title="总 Token"
            value={stats.total_tokens.total_tokens}
          />
        </Card>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Card size="small">
          <Statistic
            title="Guardrail 拦截"
            value={stats.guardrail_stats.triggered}
            suffix={`/ ${stats.guardrail_stats.total}`}
            prefix={<SafetyOutlined />}
            valueStyle={stats.guardrail_stats.triggered > 0 ? { color: token.colorError } : undefined}
          />
        </Card>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Card size="small">
          <Statistic
            title="错误率"
            value={(stats.error_rate * 100).toFixed(1)}
            suffix="%"
            valueStyle={stats.error_rate > 0.1 ? { color: token.colorError } : undefined}
          />
        </Card>
      </Col>
    </Row>
  );
};

export default TraceStatsPanel;
