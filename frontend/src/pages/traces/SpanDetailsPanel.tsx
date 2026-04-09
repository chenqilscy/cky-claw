import { Card, Tag, Alert, Descriptions, Typography } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import type { SpanItem } from '../../services/traceService';
import { SPAN_TYPE_TAG_COLORS } from '../../constants/colors';

interface SpanDetailsPanelProps {
  span: SpanItem;
}

/** 选中 Span 的详细信息展示面板 */
const SpanDetailsPanel: React.FC<SpanDetailsPanelProps> = ({ span }) => {
  return (
    <Card title={`Span 详情: ${span.name}`} size="small">
      {span.type === 'guardrail' && span.status === 'failed' && (
        <Alert
          message="Guardrail 已拦截"
          description={span.metadata?.message as string || '此 Guardrail 触发了拦截'}
          type="error"
          showIcon
          icon={<WarningOutlined />}
          style={{ marginBottom: 12 }}
        />
      )}
      <Descriptions column={2} size="small" bordered>
        <Descriptions.Item label="ID">{span.id}</Descriptions.Item>
        <Descriptions.Item label="类型">
          <Tag color={SPAN_TYPE_TAG_COLORS[span.type] || 'default'}>
            {span.type}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tag color={span.status === 'completed' ? 'success' : 'error'}>
            {span.status}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="模型">{span.model || '-'}</Descriptions.Item>
        <Descriptions.Item label="耗时">
          {span.duration_ms !== null && span.duration_ms !== undefined
            ? `${span.duration_ms}ms`
            : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="开始时间">
          {new Date(span.start_time).toLocaleString('zh-CN')}
        </Descriptions.Item>
        {span.token_usage && (
          <>
            <Descriptions.Item label="输入 Token">
              {span.token_usage.prompt_tokens}
            </Descriptions.Item>
            <Descriptions.Item label="输出 Token">
              {span.token_usage.completion_tokens}
            </Descriptions.Item>
          </>
        )}
        {span.type === 'guardrail' && (
          <>
            <Descriptions.Item label="Guardrail 类型">
              <Tag color="volcano">
                {(span.metadata?.guardrail_type as string) || '-'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="触发">
              {span.metadata?.triggered
                ? <Tag color="error">是</Tag>
                : <Tag color="success">否</Tag>}
            </Descriptions.Item>
            {span.metadata?.message && (
              <Descriptions.Item label="消息" span={2}>
                {span.metadata.message as string}
              </Descriptions.Item>
            )}
            {span.metadata?.tool_name && (
              <Descriptions.Item label="关联工具">
                <Tag color="orange">{span.metadata.tool_name as string}</Tag>
              </Descriptions.Item>
            )}
          </>
        )}
        {span.input && (
          <Descriptions.Item label="输入" span={2}>
            <Typography.Text>
              <pre style={{ margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
                {JSON.stringify(span.input, null, 2)}
              </pre>
            </Typography.Text>
          </Descriptions.Item>
        )}
        {span.output && (
          <Descriptions.Item label="输出" span={2}>
            <Typography.Text>
              <pre style={{ margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
                {JSON.stringify(span.output, null, 2)}
              </pre>
            </Typography.Text>
          </Descriptions.Item>
        )}
      </Descriptions>
    </Card>
  );
};

export default SpanDetailsPanel;
